from database import fetchone, fetchall, fetchval

# ── protein list ─────────────────────────────────────────────────────────────

# sort_by values that require a protein_summary join inside the CTE
_SORT_NEEDS_PS = {"mlo_count", "source_db_count", "role"}


def _build_sort(sort_by: str | None, sort_order: str) -> tuple[str, str, str]:
    """Return (cte_extra_select, cte_order_by, outer_order_by).

    sort_by and sort_order must already be validated by the caller.
    NULL values are always sorted last regardless of direction.
    For role: asc=drivers first, desc=clients first (encoded in rank, always ORDER BY ASC).
    """
    if sort_by is None:
        return "", "p.uniprot_id", "f.uniprot_id"

    asc = sort_order == "asc"
    dir_sql = "ASC" if asc else "DESC"

    if sort_by == "gene_name":
        return (
            ", p.gene_name AS _sk",
            f"(p.gene_name IS NULL), p.gene_name {dir_sql}, p.uniprot_id",
            f"(f._sk IS NULL), f._sk {dir_sql}, f.uniprot_id",
        )
    if sort_by == "disorder_mobidb_lite_dc":
        return (
            ", p.disorder_mobidb_lite_dc AS _sk",
            f"(p.disorder_mobidb_lite_dc IS NULL), p.disorder_mobidb_lite_dc {dir_sql}, p.uniprot_id",
            f"(f._sk IS NULL), f._sk {dir_sql}, f.uniprot_id",
        )
    if sort_by == "mlo_count":
        return (
            ", ps_s.mlo_count AS _sk",
            f"(ps_s.mlo_count IS NULL), ps_s.mlo_count {dir_sql}, p.uniprot_id",
            f"(f._sk IS NULL), f._sk {dir_sql}, f.uniprot_id",
        )
    if sort_by == "source_db_count":
        return (
            ", ps_s.source_db_count AS _sk",
            f"(ps_s.source_db_count IS NULL), ps_s.source_db_count {dir_sql}, p.uniprot_id",
            f"(f._sk IS NULL), f._sk {dir_sql}, f.uniprot_id",
        )
    if sort_by == "role":
        # Direction is encoded in the rank; always ORDER BY ASC so no NULLs-last needed.
        if asc:
            rank = "CASE WHEN ps_s.has_driver = 1 THEN 0 WHEN ps_s.has_client = 1 THEN 1 ELSE 2 END"
        else:
            rank = "CASE WHEN ps_s.has_client = 1 THEN 0 WHEN ps_s.has_driver = 1 THEN 1 ELSE 2 END"
        return (
            f", {rank} AS _sk",
            "_sk, p.uniprot_id",
            "f._sk, f.uniprot_id",
        )
    return "", "p.uniprot_id", "f.uniprot_id"


async def get_proteins_page(
    organism: str | None,
    taxon_id: int | None,
    mlo: str | None,
    role: str | None,
    source_db: str | None,
    uniprot_id: str | None,
    sort_by: str | None,
    sort_order: str,
    page: int,
    per_page: int,
) -> tuple[int, list[dict]]:
    conditions: list[str] = []
    params: list = []
    needs_mlo = any(x is not None for x in [mlo, role, source_db])
    needs_ps_sort = sort_by in _SORT_NEEDS_PS

    from_clause = "FROM proteins p"
    if needs_mlo:
        from_clause += " JOIN mlo_annotations ma ON p.uniprot_id = ma.uniprot_id"
    if needs_ps_sort:
        from_clause += " LEFT JOIN protein_summary ps_s ON p.uniprot_id = ps_s.uniprot_id"

    if uniprot_id is not None:
        conditions.append("p.uniprot_id = ?")
        params.append(uniprot_id)
    if organism:
        conditions.append("LOWER(p.organism) = LOWER(?)")
        params.append(organism)
    if taxon_id is not None:
        conditions.append("p.taxon_id = ?")
        params.append(taxon_id)
    if mlo:
        conditions.append("ma.unified_mlo = ?")
        params.append(mlo)
    if role:
        conditions.append("LOWER(ma.unified_role) = LOWER(?)")
        params.append(role)
    if source_db:
        conditions.append("ma.source_db = ?")
        params.append(source_db)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    cte_extra, cte_order, outer_order = _build_sort(sort_by, sort_order)

    total = await fetchval(
        f"SELECT COUNT(DISTINCT p.uniprot_id) {from_clause} {where}",
        tuple(params),
    ) or 0

    offset = (page - 1) * per_page
    rows = await fetchall(
        f"""
        WITH filtered AS (
            SELECT DISTINCT p.uniprot_id{cte_extra}
            {from_clause} {where}
            ORDER BY {cte_order}
            LIMIT ? OFFSET ?
        )
        SELECT p.uniprot_id, p.gene_name, p.protein_name, p.organism,
               p.length AS sequence_length,
               p.disorder_mobidb_lite_dc, p.disorder_alphafold_dc,
               p.reviewed,
               ps.idr_regions, ps.lcr_regions, ps.domains,
               ps.has_driver, ps.has_client, ps.source_db_count, ps.mlo_count, ps.mlos,
               ps.source_dbs
        FROM filtered f
        JOIN proteins p          ON p.uniprot_id  = f.uniprot_id
        JOIN protein_summary ps  ON ps.uniprot_id = f.uniprot_id
        ORDER BY {outer_order}
        """,
        tuple(params) + (per_page, offset),
    )
    return total, rows


# ── single protein ───────────────────────────────────────────────────────────

async def get_protein_meta(uniprot_id: str) -> dict | None:
    return await fetchone(
        """
        SELECT uniprot_id, gene_name, protein_name, organism, taxon_id, length,
               disorder_mobidb_lite_dc, disorder_alphafold_dc
        FROM proteins WHERE uniprot_id = ?
        """,
        (uniprot_id,),
    )


async def get_protein_mlo_annotations(uniprot_id: str) -> list[dict]:
    return await fetchall(
        """
        SELECT
            ma.unified_mlo,
            mv.category,
            ma.source_db,
            ma.source_mlo,
            ma.unified_role,
            ma.evidence
        FROM mlo_annotations ma
        LEFT JOIN mlo_vocabulary mv ON ma.unified_mlo = mv.unified_mlo
        WHERE ma.uniprot_id = ?
        ORDER BY ma.unified_mlo, ma.source_db
        """,
        (uniprot_id,),
    )


async def get_protein_features(uniprot_id: str) -> list[dict]:
    return await fetchall(
        """
        SELECT feature_type, source, label, accession, start, end, score, metadata
        FROM sequence_features
        WHERE uniprot_id = ?
        ORDER BY feature_type, start
        """,
        (uniprot_id,),
    )


async def get_ppi_summary(uniprot_id: str) -> dict:
    total = await fetchval(
        "SELECT COUNT(DISTINCT uniprot_id_b) FROM ppi WHERE uniprot_id_a = ?",
        (uniprot_id,),
    ) or 0
    in_db = await fetchval(
        "SELECT COUNT(DISTINCT uniprot_id_b) FROM ppi WHERE uniprot_id_a = ? AND in_db = 1",
        (uniprot_id,),
    ) or 0
    return {"total_partners": total, "partners_in_mlosmetadb": in_db}


async def get_ppi_page(uniprot_id: str, page: int, per_page: int) -> tuple[int, list[dict]]:
    total = await fetchval(
        "SELECT COUNT(DISTINCT uniprot_id_b) FROM ppi WHERE uniprot_id_a = ?",
        (uniprot_id,),
    ) or 0
    offset = (page - 1) * per_page
    rows = await fetchall(
        """
        SELECT
            p.uniprot_id_b AS partner_uniprot_id,
            pr.gene_name AS partner_gene,
            p.in_db,
            p.experimental_system,
            p.pubmed_id,
            p.source_version AS source
        FROM ppi p
        LEFT JOIN proteins pr ON p.uniprot_id_b = pr.uniprot_id
        WHERE p.uniprot_id_a = ?
        GROUP BY p.uniprot_id_b
        ORDER BY p.uniprot_id_b
        LIMIT ? OFFSET ?
        """,
        (uniprot_id, per_page, offset),
    )
    return total, rows
