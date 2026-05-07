from database import fetchone, fetchall, fetchval


async def get_mlo_meta(unified_mlo: str) -> dict | None:
    return await fetchone(
        "SELECT unified_mlo, category FROM mlo_vocabulary WHERE unified_mlo = ?",
        (unified_mlo,),
    )


async def get_mlo_definitions(unified_mlo: str) -> list[dict]:
    return await fetchall(
        "SELECT source_db, source_name, definition FROM mlo_definitions WHERE unified_mlo = ? ORDER BY source_db",
        (unified_mlo,),
    )


async def get_mlo_stats(unified_mlo: str) -> dict:
    total = await fetchval(
        "SELECT COUNT(DISTINCT uniprot_id) FROM mlo_annotations WHERE unified_mlo = ?",
        (unified_mlo,),
    ) or 0

    source_rows = await fetchall(
        "SELECT source_db, COUNT(DISTINCT uniprot_id) AS cnt FROM mlo_annotations WHERE unified_mlo = ? GROUP BY source_db",
        (unified_mlo,),
    )
    by_source = {r["source_db"]: r["cnt"] for r in source_rows}

    role_rows = await fetchall(
        """
        SELECT COALESCE(LOWER(unified_role), 'unknown') AS role, COUNT(DISTINCT uniprot_id) AS cnt
        FROM mlo_annotations
        WHERE unified_mlo = ?
        GROUP BY role
        """,
        (unified_mlo,),
    )
    by_role = {r["role"]: r["cnt"] for r in role_rows}

    org_rows = await fetchall(
        """
        SELECT DISTINCT p.organism
        FROM mlo_annotations ma
        JOIN proteins p ON ma.uniprot_id = p.uniprot_id
        WHERE ma.unified_mlo = ?
        ORDER BY p.organism
        """,
        (unified_mlo,),
    )
    organisms = [r["organism"] for r in org_rows if r["organism"]]

    return {
        "total_proteins": total,
        "by_source": by_source,
        "by_role": by_role,
        "organisms": organisms,
    }


async def get_mlo_proteins_page(
    unified_mlo: str,
    organism: str | None,
    role: str | None,
    source_db: str | None,
    page: int,
    per_page: int,
) -> tuple[int, list[dict]]:
    conditions = ["ma.unified_mlo = ?"]
    params: list = [unified_mlo]

    if organism:
        conditions.append("LOWER(p.organism) = LOWER(?)")
        params.append(organism)
    if role:
        conditions.append("LOWER(ma.unified_role) = LOWER(?)")
        params.append(role)
    if source_db:
        conditions.append("ma.source_db = ?")
        params.append(source_db)

    where = "WHERE " + " AND ".join(conditions)

    total = await fetchval(
        f"SELECT COUNT(DISTINCT ma.uniprot_id) FROM mlo_annotations ma JOIN proteins p ON ma.uniprot_id = p.uniprot_id {where}",
        tuple(params),
    ) or 0

    offset = (page - 1) * per_page
    rows = await fetchall(
        f"""
        WITH filtered AS (
            SELECT DISTINCT ma.uniprot_id
            FROM mlo_annotations ma
            JOIN proteins p ON ma.uniprot_id = p.uniprot_id
            {where}
            ORDER BY ma.uniprot_id
            LIMIT ? OFFSET ?
        )
        SELECT p.uniprot_id, p.gene_name, p.organism,
               p.disorder_mobidb_lite_dc, p.disorder_alphafold_dc,
               ps.idr_regions, ps.lcr_regions, ps.domains,
               MAX(ma.unified_role) AS unified_role,
               GROUP_CONCAT(DISTINCT ma.source_db) AS sources_concat
        FROM filtered f
        JOIN proteins p          ON p.uniprot_id  = f.uniprot_id
        JOIN protein_summary ps  ON ps.uniprot_id = f.uniprot_id
        JOIN mlo_annotations ma  ON ma.uniprot_id = f.uniprot_id AND ma.unified_mlo = ?
        GROUP BY f.uniprot_id
        ORDER BY f.uniprot_id
        """,
        tuple(params) + (per_page, offset, unified_mlo),
    )
    return total, rows


async def get_all_mlos(category: str | None) -> list[dict]:
    if category:
        return await fetchall(
            """
            SELECT mv.unified_mlo, mv.category, COUNT(DISTINCT ma.uniprot_id) AS protein_count
            FROM mlo_vocabulary mv
            LEFT JOIN mlo_annotations ma ON mv.unified_mlo = ma.unified_mlo
            WHERE mv.category = ?
            GROUP BY mv.unified_mlo
            ORDER BY mv.unified_mlo
            """,
            (category,),
        )
    return await fetchall(
        """
        SELECT mv.unified_mlo, mv.category, COUNT(DISTINCT ma.uniprot_id) AS protein_count
        FROM mlo_vocabulary mv
        LEFT JOIN mlo_annotations ma ON mv.unified_mlo = ma.unified_mlo
        GROUP BY mv.unified_mlo
        ORDER BY mv.unified_mlo
        """,
    )
