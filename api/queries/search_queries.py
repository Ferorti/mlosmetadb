from database import fetchall, fts5_available


async def search_proteins_fts(q: str) -> list[dict]:
    return await fetchall(
        """
        SELECT p.uniprot_id, p.gene_name, p.protein_name, p.organism,
               p.length AS sequence_length,
               p.disorder_mobidb_lite_dc, p.disorder_alphafold_dc,
               p.reviewed,
               ps.idr_regions, ps.lcr_regions, ps.domains,
               ps.has_driver, ps.has_client, ps.source_db_count, ps.mlo_count, ps.mlos,
               ps.source_dbs,
               CASE
                   WHEN LOWER(p.uniprot_id) = LOWER(?) THEN 'uniprot_id'
                   WHEN LOWER(p.gene_name) = LOWER(?) THEN 'gene_name'
                   ELSE 'protein_name'
               END AS match_field
        FROM fts_proteins ft
        JOIN proteins p ON p.rowid = ft.rowid
        LEFT JOIN protein_summary ps ON ps.uniprot_id = p.uniprot_id
        WHERE fts_proteins MATCH ?
        ORDER BY rank
        LIMIT 50
        """,
        (q, q, q),
    )


async def search_proteins_like(q: str) -> list[dict]:
    sub = f"%{q}%"
    word = f"% {q} %"
    return await fetchall(
        """
        SELECT p.uniprot_id, p.gene_name, p.protein_name, p.organism,
               p.length AS sequence_length,
               p.disorder_mobidb_lite_dc, p.disorder_alphafold_dc,
               p.reviewed,
               ps.idr_regions, ps.lcr_regions, ps.domains,
               ps.has_driver, ps.has_client, ps.source_db_count, ps.mlo_count, ps.mlos,
               ps.source_dbs,
               CASE
                   WHEN LOWER(p.uniprot_id) LIKE LOWER(?) THEN 'uniprot_id'
                   WHEN LOWER(p.gene_name) LIKE LOWER(?) THEN 'gene_name'
                   ELSE 'protein_name'
               END AS match_field
        FROM proteins p
        LEFT JOIN protein_summary ps ON ps.uniprot_id = p.uniprot_id
        WHERE LOWER(p.uniprot_id) LIKE LOWER(?)
           OR LOWER(p.gene_name) LIKE LOWER(?)
           OR LOWER(' ' || p.protein_name || ' ') LIKE LOWER(?)
        ORDER BY p.uniprot_id
        LIMIT 50
        """,
        (sub, sub, sub, sub, word),
    )


async def search_mlos_fts(q: str) -> list[dict]:
    return await fetchall(
        """
        SELECT mv.unified_mlo, mv.category, 'unified_mlo' AS match_field
        FROM fts_mlos ft
        JOIN mlo_vocabulary mv ON mv.rowid = ft.rowid
        WHERE fts_mlos MATCH ?
        ORDER BY rank
        LIMIT 20
        """,
        (q,),
    )


async def search_mlos_like(q: str) -> list[dict]:
    pattern = f"%{q}%"
    return await fetchall(
        """
        SELECT unified_mlo, category, 'unified_mlo' AS match_field
        FROM mlo_vocabulary
        WHERE LOWER(unified_mlo) LIKE LOWER(?)
        ORDER BY unified_mlo
        LIMIT 20
        """,
        (pattern,),
    )


def _build_advanced_clauses(
    gene_name: str | None,
    uniprot_id: str | None,
    organism: str | None,
    taxon_id: int | None,
    mlo: str | None,
    role: str | None,
    source_db: str | None,
    feature_type: str | None,
    feature_label: str | None,
    feature_accession: str | None,
) -> tuple[list[str], list[str], list]:
    joins = ["FROM proteins p"]
    conditions: list[str] = []
    params: list = []

    need_mlo = any(x is not None for x in [mlo, role, source_db])
    need_feat = any(x is not None for x in [feature_type, feature_label, feature_accession])

    if need_mlo:
        joins.append("JOIN mlo_annotations ma ON p.uniprot_id = ma.uniprot_id")
    if need_feat:
        joins.append("JOIN sequence_features sf ON p.uniprot_id = sf.uniprot_id")

    if gene_name:
        conditions.append("LOWER(p.gene_name) LIKE LOWER(?)")
        params.append(f"%{gene_name}%")
    if uniprot_id:
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
    if feature_type:
        conditions.append("LOWER(sf.feature_type) = LOWER(?)")
        params.append(feature_type)
    if feature_label:
        conditions.append("LOWER(sf.label) LIKE LOWER(?)")
        params.append(f"%{feature_label}%")
    if feature_accession:
        conditions.append("sf.accession = ?")
        params.append(feature_accession)

    return joins, conditions, params


async def get_advanced_search_facets(
    gene_name: str | None,
    uniprot_id: str | None,
    organism: str | None,
    taxon_id: int | None,
    mlo: str | None,
    role: str | None,
    source_db: str | None,
    feature_type: str | None,
    feature_label: str | None,
    feature_accession: str | None,
) -> dict:
    joins, conditions, params = _build_advanced_clauses(
        gene_name, uniprot_id, organism, taxon_id, mlo, role, source_db,
        feature_type, feature_label, feature_accession,
    )
    from_clause = " ".join(joins)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    p = tuple(params)
    base_cte = f"SELECT DISTINCT p.uniprot_id {from_clause} {where}"

    org_rows = await fetchall(
        f"""
        SELECT p.organism, COUNT(DISTINCT p.uniprot_id) AS cnt
        {from_clause} {where}
        GROUP BY p.organism
        ORDER BY cnt DESC
        """,
        p,
    )

    role_rows = await fetchall(
        f"""
        SELECT
            SUM(ps.has_driver) AS driver,
            SUM(ps.has_client) AS client,
            SUM(CASE WHEN ps.has_driver = 0 AND ps.has_client = 0 THEN 1 ELSE 0 END) AS unknown
        FROM ({base_cte}) f
        LEFT JOIN protein_summary ps ON ps.uniprot_id = f.uniprot_id
        """,
        p,
    )

    mlo_rows = await fetchall(
        f"""
        SELECT ma2.unified_mlo, COUNT(DISTINCT ma2.uniprot_id) AS cnt
        FROM ({base_cte}) f
        JOIN mlo_annotations ma2 ON ma2.uniprot_id = f.uniprot_id
        GROUP BY ma2.unified_mlo
        ORDER BY cnt DESC
        """,
        p,
    )

    by_organism = {r["organism"]: r["cnt"] for r in org_rows if r["organism"]}
    by_mlo = {r["unified_mlo"]: r["cnt"] for r in mlo_rows if r["unified_mlo"]}
    by_role: dict[str, int] = {}
    if role_rows:
        r = role_rows[0]
        for k in ("driver", "client", "unknown"):
            v = r.get(k)
            if v:
                by_role[k] = int(v)

    return {"by_organism": by_organism, "by_role": by_role, "by_mlo": by_mlo}


async def advanced_search(
    gene_name: str | None,
    uniprot_id: str | None,
    organism: str | None,
    taxon_id: int | None,
    mlo: str | None,
    role: str | None,
    source_db: str | None,
    feature_type: str | None,
    feature_label: str | None,
    feature_accession: str | None,
    page: int,
    per_page: int,
) -> tuple[int, list[dict]]:
    from database import fetchval

    joins, conditions, params = _build_advanced_clauses(
        gene_name, uniprot_id, organism, taxon_id, mlo, role, source_db,
        feature_type, feature_label, feature_accession,
    )
    from_clause = " ".join(joins)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    total = await fetchval(
        f"SELECT COUNT(DISTINCT p.uniprot_id) {from_clause} {where}",
        tuple(params),
    ) or 0

    offset = (page - 1) * per_page
    rows = await fetchall(
        f"""
        WITH filtered AS (
            SELECT DISTINCT p.uniprot_id
            {from_clause} {where}
            ORDER BY p.uniprot_id
            LIMIT ? OFFSET ?
        )
        SELECT
            p.uniprot_id, p.gene_name, p.protein_name, p.organism,
            p.length AS sequence_length,
            p.disorder_mobidb_lite_dc, p.disorder_alphafold_dc,
            p.reviewed,
            ps.idr_regions, ps.lcr_regions, ps.domains,
            ps.has_driver, ps.has_client, ps.source_db_count, ps.mlo_count, ps.mlos,
            ps.source_dbs
        FROM filtered f
        JOIN proteins p ON p.uniprot_id = f.uniprot_id
        LEFT JOIN protein_summary ps ON ps.uniprot_id = f.uniprot_id
        ORDER BY f.uniprot_id
        """,
        tuple(params) + (per_page, offset),
    )
    return total, rows
