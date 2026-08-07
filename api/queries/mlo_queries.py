import policy
from database import fetchone, fetchall, fetchval, like_contains


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
    active = policy.active_annotation_clause("ma")

    total = await fetchval(
        f"SELECT COUNT(DISTINCT ma.uniprot_id) FROM mlo_annotations ma WHERE ma.unified_mlo = ? AND {active}",
        (unified_mlo,),
    ) or 0

    source_rows = await fetchall(
        f"""
        SELECT ma.source_db, COUNT(DISTINCT ma.uniprot_id) AS cnt
        FROM mlo_annotations ma
        WHERE ma.unified_mlo = ? AND {active}
        GROUP BY ma.source_db
        """,
        (unified_mlo,),
    )
    by_source = {r["source_db"]: r["cnt"] for r in source_rows}

    role_rows = await fetchall(
        f"""
        SELECT
            CASE WHEN LOWER(ma.unified_role) = 'driver' THEN 'driver' ELSE 'component' END AS role,
            COUNT(DISTINCT ma.uniprot_id) AS cnt
        FROM mlo_annotations ma
        WHERE ma.unified_mlo = ? AND {active}
        GROUP BY role
        """,
        (unified_mlo,),
    )
    by_role = {r["role"]: r["cnt"] for r in role_rows}

    org_rows = await fetchall(
        f"""
        SELECT DISTINCT p.organism
        FROM mlo_annotations ma
        JOIN proteins p ON ma.uniprot_id = p.uniprot_id
        WHERE ma.unified_mlo = ? AND {active}
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
    active = policy.active_annotation_clause("ma")
    conditions = ["ma.unified_mlo = ?", active]
    params: list = [unified_mlo]

    if organism:
        conditions.append("LOWER(p.organism) = LOWER(?)")
        params.append(organism)
    if role:
        if role.lower() == "component":
            conditions.append(policy.component_role_clause("ma"))
        else:
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
        JOIN mlo_annotations ma  ON ma.uniprot_id = f.uniprot_id AND ma.unified_mlo = ? AND {active}
        GROUP BY f.uniprot_id
        ORDER BY f.uniprot_id
        """,
        tuple(params) + (per_page, offset, unified_mlo),
    )
    return total, rows


async def get_all_mlos(
    category: str | None,
    source_db: str | None = None,
    organism: str | None = None,
    q: str | None = None,
) -> list[dict]:
    active_ma = policy.active_annotation_clause("ma")
    active_x = policy.active_annotation_clause("x")
    excluded_clause, excluded_params = policy.excluded_mlo_category_clause("mv")

    conditions: list[str] = []
    params: list = []

    if excluded_clause:
        conditions.append(excluded_clause)
        params.extend(excluded_params)
    if category:
        conditions.append("mv.category = ?")
        params.append(category)
    if q:
        conditions.append("LOWER(mv.unified_mlo) LIKE LOWER(?) ESCAPE '\\'")
        params.append(like_contains(q))
    if source_db:
        conditions.append(
            f"EXISTS (SELECT 1 FROM mlo_annotations x WHERE x.unified_mlo = mv.unified_mlo AND x.source_db = ? AND {active_x})"
        )
        params.append(source_db)
    if organism:
        conditions.append(
            "EXISTS ("
            "SELECT 1 FROM mlo_annotations x "
            "JOIN proteins p ON x.uniprot_id = p.uniprot_id "
            f"WHERE x.unified_mlo = mv.unified_mlo AND LOWER(p.organism) = LOWER(?) AND {active_x}"
            ")"
        )
        params.append(organism)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    return await fetchall(
        f"""
        SELECT mv.unified_mlo, mv.category,
               COUNT(DISTINCT ma.uniprot_id) AS protein_count,
               COUNT(DISTINCT CASE WHEN LOWER(ma.unified_role) = 'driver' THEN ma.uniprot_id END) AS driver_count,
               GROUP_CONCAT(DISTINCT ma.source_db) AS sources_concat
        FROM mlo_vocabulary mv
        LEFT JOIN mlo_annotations ma ON mv.unified_mlo = ma.unified_mlo AND {active_ma}
        {where}
        GROUP BY mv.unified_mlo, mv.category
        ORDER BY mv.unified_mlo
        """,
        tuple(params),
    )


async def get_definitions_for_mlos(unified_mlos: list[str]) -> dict[str, list[dict]]:
    if not unified_mlos:
        return {}
    placeholders = ",".join("?" * len(unified_mlos))
    rows = await fetchall(
        f"SELECT unified_mlo, source_db, source_name, definition FROM mlo_definitions "
        f"WHERE unified_mlo IN ({placeholders}) ORDER BY unified_mlo, source_db",
        tuple(unified_mlos),
    )
    result: dict[str, list[dict]] = {}
    for r in rows:
        mlo = r["unified_mlo"]
        result.setdefault(mlo, []).append(r)
    return result


async def get_source_names_for_mlos(unified_mlos: list[str]) -> dict[str, list[str]]:
    """Every name the source databases use for each organelle.

    Two tables carry them and neither is complete on its own: 91 aliases exist
    only in mlo_annotations.source_mlo, 36 only in mlo_definitions.source_name,
    and 36 organelles have no definitions at all. Hence the UNION.

    Names equal to the unified name are dropped (115 of 416 are just the same
    string) and casing variants are collapsed — the nucleolus alone carries
    "Dense Fibrillar Component", "Dense fibrillar component" and "dense
    fibrillar component". MIN() picks one deterministically.

    What is left is not a clean synonym list: some sources label a condensate
    by its driver protein, so 'NONO' maps to paraspeckle and
    transcriptional_condensate collects 22 named instances. That is what those
    databases recorded; the display layer decides how much of it to show.
    """
    if not unified_mlos:
        return {}
    placeholders = ",".join("?" * len(unified_mlos))
    active = policy.active_annotation_clause("ma")
    rows = await fetchall(
        f"""
        WITH alias AS (
            SELECT ma.unified_mlo AS unified_mlo, ma.source_mlo AS name
            FROM mlo_annotations ma
            WHERE ma.unified_mlo IN ({placeholders}) AND ma.source_mlo IS NOT NULL AND {active}
            UNION
            SELECT d.unified_mlo, d.source_name
            FROM mlo_definitions d
            WHERE d.unified_mlo IN ({placeholders}) AND d.source_name IS NOT NULL
        )
        SELECT unified_mlo, MIN(name) AS name
        FROM alias
        WHERE LOWER(name) != LOWER(REPLACE(unified_mlo, '_', ' '))
        GROUP BY unified_mlo, LOWER(name)
        ORDER BY unified_mlo, LOWER(name)
        """,
        tuple(unified_mlos) * 2,
    )
    result: dict[str, list[str]] = {}
    for r in rows:
        result.setdefault(r["unified_mlo"], []).append(r["name"])
    return result
