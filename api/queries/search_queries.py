from database import fetchall, fts5_available


async def search_proteins_fts(q: str) -> list[dict]:
    return await fetchall(
        """
        SELECT p.uniprot_id, p.gene_name, p.protein_name, p.organism,
               CASE
                   WHEN LOWER(p.uniprot_id) = LOWER(?) THEN 'uniprot_id'
                   WHEN LOWER(p.gene_name) = LOWER(?) THEN 'gene_name'
                   ELSE 'protein_name'
               END AS match_field
        FROM fts_proteins ft
        JOIN proteins p ON p.rowid = ft.rowid
        WHERE fts_proteins MATCH ?
        ORDER BY rank
        LIMIT 50
        """,
        (q, q, q),
    )


async def search_proteins_like(q: str) -> list[dict]:
    sub = f"%{q}%"        # substring match for codes (uniprot_id, gene_name)
    word = f"% {q} %"    # whole-word match for prose (protein_name)
    return await fetchall(
        """
        SELECT uniprot_id, gene_name, protein_name, organism,
               CASE
                   WHEN LOWER(uniprot_id) LIKE LOWER(?) THEN 'uniprot_id'
                   WHEN LOWER(gene_name) LIKE LOWER(?) THEN 'gene_name'
                   ELSE 'protein_name'
               END AS match_field
        FROM proteins
        WHERE LOWER(uniprot_id) LIKE LOWER(?)
           OR LOWER(gene_name) LIKE LOWER(?)
           OR LOWER(' ' || protein_name || ' ') LIKE LOWER(?)
        ORDER BY uniprot_id
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
            ps.idr_regions, ps.lcr_regions, ps.domains,
            ps.mlo_count, ps.mlos
        FROM filtered f
        JOIN proteins p ON p.uniprot_id = f.uniprot_id
        LEFT JOIN protein_summary ps ON ps.uniprot_id = f.uniprot_id
        ORDER BY f.uniprot_id
        """,
        tuple(params) + (per_page, offset),
    )
    return total, rows
