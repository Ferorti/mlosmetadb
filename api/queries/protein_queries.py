import policy
from database import fetchone, fetchall, fetchval

# ── protein list ─────────────────────────────────────────────────────────────

# sort_by values that require a protein_summary join inside the CTE
_SORT_NEEDS_PS = {"mlo_count", "source_db_count", "role"}


def _has_regulator_select(alias: str = "p") -> str:
    """Correlated EXISTS, computed at query time rather than stored: true iff
    {alias}'s protein has at least one curator-assigned regulator annotation
    anywhere in the dataset. Not mutually exclusive with has_driver -- a
    protein can be a regulator for one MLO via one source and a driver for a
    different MLO via a different source, and this reports both facts rather
    than picking one (see policy.regulator_only_role_clause()'s docstring for
    the deliberately-separate "regulator, never a driver" bucket that clause
    encodes for the /results role=regulator filter and the home page's
    regulator card -- this column is not that; it's "has any regulator claim
    at all," matching how has_driver/has_client already work)."""
    active = policy.active_annotation_clause("mar")
    regulator = policy.regulator_annotation_clause("mar")
    return (
        f"EXISTS (SELECT 1 FROM mlo_annotations mar "
        f"WHERE mar.uniprot_id = {alias}.uniprot_id AND {active} AND {regulator}) AS has_regulator"
    )


def _build_sort(sort_by: str | None, sort_order: str) -> tuple[str, str, str]:
    """Return (cte_extra_select, cte_order_by, outer_order_by).

    sort_by and sort_order must already be validated by the caller.
    NULL values are always sorted last regardless of direction.
    For role: asc=drivers first, desc=components first (encoded in rank, always ORDER BY ASC).

    KEEP IN SYNC: refactor/frontend/src/utils/sortProteins.js is a client-side
    mirror of these exact semantics (NULL-last, uniprot_id tie-break, role-rank),
    used to re-sort the plain-text /search fallback path, which has no sort_by of
    its own. If the sort semantics here change, that file must change with them --
    there is no test suite that would catch the drift.
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
        active = policy.active_annotation_clause("ma")
        from_clause += f" JOIN mlo_annotations ma ON p.uniprot_id = ma.uniprot_id AND {active}"
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
        if role.lower() == "component":
            conditions.append(policy.component_role_clause("ma"))
            conditions.append(policy.component_only_role_clause("ma"))
        elif role.lower() == "regulator":
            conditions.append(policy.regulator_annotation_clause("ma"))
            conditions.append(policy.regulator_only_role_clause("ma"))
        else:
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
               ps.source_dbs,
               {_has_regulator_select("p")}
        FROM filtered f
        JOIN proteins p          ON p.uniprot_id  = f.uniprot_id
        JOIN protein_summary ps  ON ps.uniprot_id = f.uniprot_id
        ORDER BY {outer_order}
        """,
        tuple(params) + (per_page, offset),
    )
    return total, rows


async def _scoped_role_counts(
    base_cte: str, base_params: tuple, mlo: str | None, source_db: str | None,
) -> tuple[int, int]:
    """Driver/component counts for the proteins in base_cte, scoped to the SAME mlo/
    source_db filter already narrowing base_cte -- deliberately NOT protein_summary.
    has_driver, which is a per-protein flag true if the protein drives ANY MLO/source
    anywhere in the dataset. A protein that drives one MLO while being a mere component
    (or unannotated) in the MLO base_cte is actually filtered to would otherwise be
    miscounted as a driver for the wrong MLO (confirmed against p_granule: has_driver
    over-counts 46 vs. the real MLO-scoped 26)."""
    active = policy.active_annotation_clause("ma_role")
    conds = [active, "LOWER(ma_role.unified_role) = 'driver'"]
    extra_params: list = []
    if mlo:
        conds.append("ma_role.unified_mlo = ?")
        extra_params.append(mlo)
    if source_db:
        conds.append("ma_role.source_db = ?")
        extra_params.append(source_db)
    driver_where = " AND ".join(conds)
    row = await fetchone(
        f"""
        SELECT
            SUM(CASE WHEN dr.uniprot_id IS NOT NULL THEN 1 ELSE 0 END) AS driver,
            SUM(CASE WHEN dr.uniprot_id IS NULL THEN 1 ELSE 0 END) AS component
        FROM ({base_cte}) f
        LEFT JOIN (
            SELECT DISTINCT ma_role.uniprot_id FROM mlo_annotations ma_role WHERE {driver_where}
        ) dr ON dr.uniprot_id = f.uniprot_id
        """,
        tuple(base_params) + tuple(extra_params),
    )
    return (row["driver"] or 0, row["component"] or 0)


def _build_proteins_conditions(
    organism: str | None,
    taxon_id: int | None,
    mlo: str | None,
    role: str | None,
    source_db: str | None,
    uniprot_id: str | None,
) -> tuple[str, list[str], list]:
    conditions: list[str] = []
    params: list = []
    needs_mlo = any(x is not None for x in [mlo, role, source_db])

    from_clause = "FROM proteins p"
    if needs_mlo:
        active = policy.active_annotation_clause("ma")
        from_clause += f" JOIN mlo_annotations ma ON p.uniprot_id = ma.uniprot_id AND {active}"

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
        if role.lower() == "component":
            conditions.append(policy.component_role_clause("ma"))
            conditions.append(policy.component_only_role_clause("ma"))
        elif role.lower() == "regulator":
            conditions.append(policy.regulator_annotation_clause("ma"))
            conditions.append(policy.regulator_only_role_clause("ma"))
        else:
            conditions.append("LOWER(ma.unified_role) = LOWER(?)")
            params.append(role)
    if source_db:
        conditions.append("ma.source_db = ?")
        params.append(source_db)

    return from_clause, conditions, params


async def get_proteins_facets(
    organism: str | None,
    taxon_id: int | None,
    mlo: str | None,
    role: str | None,
    source_db: str | None,
    uniprot_id: str | None,
) -> dict:
    from_clause, conditions, params = _build_proteins_conditions(
        organism, taxon_id, mlo, role, source_db, uniprot_id
    )
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

    # Role facet pivots on role, so it's computed from a role-free scope (same mlo/
    # source_db/organism/uniprot_id filters, without whatever role may already be applied).
    _, conditions_no_role, params_no_role = _build_proteins_conditions(
        organism, taxon_id, mlo, None, source_db, uniprot_id
    )
    where_no_role = ("WHERE " + " AND ".join(conditions_no_role)) if conditions_no_role else ""
    base_cte_no_role = f"SELECT DISTINCT p.uniprot_id {from_clause} {where_no_role}"
    driver_cnt, component_cnt = await _scoped_role_counts(
        base_cte_no_role, tuple(params_no_role), mlo, source_db
    )

    mlo_rows = await fetchall(
        f"""
        SELECT ma2.unified_mlo, COUNT(DISTINCT ma2.uniprot_id) AS cnt
        FROM ({base_cte}) f
        JOIN mlo_annotations ma2 ON ma2.uniprot_id = f.uniprot_id AND {policy.active_annotation_clause("ma2")}
        GROUP BY ma2.unified_mlo
        ORDER BY cnt DESC
        """,
        p,
    )

    by_organism = {r["organism"]: r["cnt"] for r in org_rows if r["organism"]}
    by_mlo = {r["unified_mlo"]: r["cnt"] for r in mlo_rows if r["unified_mlo"]}
    by_role: dict[str, int] = {}
    for k, v in (("driver", driver_cnt), ("component", component_cnt)):
        if v:
            by_role[k] = int(v)

    return {"by_organism": by_organism, "by_role": by_role, "by_mlo": by_mlo}


async def get_proteins_export(
    organism: str | None,
    taxon_id: int | None,
    mlo: str | None,
    role: str | None,
    source_dbs: list[str] | None,
) -> list[dict]:
    """Unpaginated protein list for bulk export. Deliberately NOT reusing
    _build_proteins_conditions: source_dbs here is a list matched via
    IN (...), while every caller of that helper takes a single source_db
    matched via '='. Sharing it would require source_dbs to participate in
    its needs_mlo/join decision too, which isn't worth threading through a
    function three other call sites already depend on."""
    conditions: list[str] = []
    params: list = []
    needs_mlo = any([mlo, role, source_dbs])

    from_clause = "FROM proteins p"
    if needs_mlo:
        active = policy.active_annotation_clause("ma")
        from_clause += f" JOIN mlo_annotations ma ON p.uniprot_id = ma.uniprot_id AND {active}"

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
        if role.lower() == "component":
            conditions.append(policy.component_role_clause("ma"))
            conditions.append(policy.component_only_role_clause("ma"))
        elif role.lower() == "regulator":
            conditions.append(policy.regulator_annotation_clause("ma"))
            conditions.append(policy.regulator_only_role_clause("ma"))
        else:
            conditions.append("LOWER(ma.unified_role) = LOWER(?)")
            params.append(role)
    if source_dbs:
        placeholders = ",".join("?" * len(source_dbs))
        conditions.append(f"ma.source_db IN ({placeholders})")
        params.extend(source_dbs)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    return await fetchall(
        f"""
        WITH filtered AS (
            SELECT DISTINCT p.uniprot_id
            {from_clause} {where}
            ORDER BY p.uniprot_id
            LIMIT 50000
        )
        SELECT p.uniprot_id, p.gene_name, p.protein_name, p.organism,
               p.length AS sequence_length, p.reviewed,
               ps.has_driver, ps.has_client, ps.source_db_count, ps.mlo_count, ps.mlos,
               ps.source_dbs, ps.idr_regions, ps.lcr_regions, ps.domains
        FROM filtered f
        JOIN proteins p          ON p.uniprot_id  = f.uniprot_id
        JOIN protein_summary ps  ON ps.uniprot_id = f.uniprot_id
        ORDER BY p.uniprot_id
        """,
        tuple(params),
    )


# ── single protein ───────────────────────────────────────────────────────────

async def get_protein_meta(uniprot_id: str) -> dict | None:
    return await fetchone(
        """
        SELECT uniprot_id, gene_name, protein_name, organism, taxon_id, length,
               disorder_mobidb_lite_dc, disorder_alphafold_dc, sequence
        FROM proteins WHERE uniprot_id = ?
        """,
        (uniprot_id,),
    )


async def get_protein_mlo_annotations(uniprot_id: str) -> list[dict]:
    active = policy.active_annotation_clause("ma")
    return await fetchall(
        f"""
        SELECT
            ma.unified_mlo,
            mv.spatial_location,
            mv.taxonomic_scope,
            mv.physiological_state,
            mv.cell_type_context,
            ma.source_db,
            ma.source_mlo,
            ma.source_role,
            ma.unified_role,
            ma.evidence
        FROM mlo_annotations ma
        LEFT JOIN mlo_vocabulary mv ON ma.unified_mlo = mv.unified_mlo
        WHERE ma.uniprot_id = ? AND {active}
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
    """A protein's own self-interaction (BioGRID records homodimerization,
    e.g. P04637/p53) is not a PARTNER -- excluded here and in get_ppi_all/
    get_ppi_page, or the protein shows up as its own PPI partner: the graph's
    center node duplicated as an ordinary, isolated node elsewhere in it.
    3,367 rows across 2,098 proteins in the live DB; see docs/issues/004.

    Both uniprot_id_a and uniprot_id_b must be checked, not just uniprot_id_a:
    scripts/parse_biogrid.py only swaps the interactor NOT already in
    `proteins` into uniprot_id_a; when both sides of a pair are already
    in-dataset, whichever BioGRID called "Interactor A" keeps that column, so
    a protein's own partner can be recorded with the protein itself in
    uniprot_id_b. Anchoring only on uniprot_id_a = ? silently drops those --
    94% of distinct ordered pairs in the live DB (795,987 of 847,051) have no
    separate reverse row, so this isn't a rare edge case: querying only
    P35637 -> WHERE uniprot_id_a='P35637' misses a real partner recorded as
    (PREV01, P35637). See docs/issues/006.

    A partner found via uniprot_id_b (this protein in uniprot_id_a's slot)
    reports the stored `in_db` flag, which is defined as "is uniprot_id_b in
    `proteins`". A partner found via uniprot_id_a (this protein in
    uniprot_id_b's slot) has no such flag on that row -- but uniprot_id_a is
    *always* in `proteins` by construction (parse_biogrid.py's normalization
    guarantees it), so that partner is always in_db=1 whenever found this
    way, without needing a lookup."""
    partner = "CASE WHEN uniprot_id_a = ? THEN uniprot_id_b ELSE uniprot_id_a END"
    partner_in_db = "CASE WHEN uniprot_id_a = ? THEN in_db ELSE 1 END"
    where = "WHERE (uniprot_id_a = ? OR uniprot_id_b = ?) AND uniprot_id_a != uniprot_id_b"

    total = await fetchval(
        f"SELECT COUNT(DISTINCT {partner}) FROM ppi {where}",
        (uniprot_id, uniprot_id, uniprot_id),
    ) or 0
    in_db = await fetchval(
        f"""
        SELECT COUNT(*) FROM (
            SELECT MAX({partner_in_db}) AS partner_in_db
            FROM ppi {where}
            GROUP BY {partner}
        )
        WHERE partner_in_db = 1
        """,
        (uniprot_id, uniprot_id, uniprot_id, uniprot_id),
    ) or 0
    return {"total_partners": total, "partners_in_mlosmetadb": in_db}


async def get_ppi_all(
    uniprot_id: str,
    role: str | None,
    mlo: str | None,
    limit: int = 500,
) -> tuple[int, list[dict]]:
    """Return in-DB partners only (self-interactions excluded, see the CTE's
    WHERE), with optional role/mlo filters. `role` accepts "driver",
    "component", or "regulator".

    role and mlo interact: `role` alone reads the partner's GLOBAL driver flag
    (protein_summary.has_driver, true if it drives ANY MLO anywhere), but once
    `mlo` narrows to one organelle, `role` must be re-checked against THAT
    MLO specifically -- otherwise "role=driver&mlo=X" ANDs two independent
    facts ("drives something" AND "has any annotation in X") instead of
    testing "drives X", and mislabels a partner that drives a different MLO
    while merely being annotated (any role) in X. Same bug class
    `_scoped_role_counts` above exists to avoid; see docs/issues/003.

    `has_regulator` on the returned rows (unlike the `role="regulator"`
    filter) is the general, non-exclusive "has any regulator claim at all"
    flag -- matches ProteinSummary.has_regulator/_has_regulator_select()'s
    display semantics, so a driver-and-regulator partner still shows
    has_driver=1 (the filter's mutually-exclusive bucket is a separate,
    narrower thing; see docs/issues/004).

    The partners CTE matches uniprot_id in EITHER column, not just
    uniprot_id_a: see get_ppi_summary's docstring for why (parse_biogrid.py
    only swaps the not-yet-in-dataset side into uniprot_id_a, so when both
    interactors of a pair are already in `proteins`, whichever BioGRID called
    "Interactor A" keeps that column -- this protein's own partner can be
    recorded with this protein itself in uniprot_id_b). See docs/issues/006."""
    extra_where: list[str] = ["pt.in_db = 1"]
    extra_params: list = []
    active = policy.active_annotation_clause("ma")

    if mlo and role == "driver":
        extra_where.append(
            f"EXISTS (SELECT 1 FROM mlo_annotations ma "
            f"WHERE ma.uniprot_id = pt.partner_uniprot_id AND ma.unified_mlo = ? "
            f"AND LOWER(ma.unified_role) = 'driver' AND {active})"
        )
        extra_params.append(mlo)
    elif mlo and role == "component":
        extra_where.append(
            f"EXISTS (SELECT 1 FROM mlo_annotations ma "
            f"WHERE ma.uniprot_id = pt.partner_uniprot_id AND ma.unified_mlo = ? "
            f"AND {policy.component_role_clause('ma')} AND {active})"
        )
        extra_params.append(mlo)
    elif mlo and role == "regulator":
        extra_where.append(
            f"EXISTS (SELECT 1 FROM mlo_annotations ma "
            f"WHERE ma.uniprot_id = pt.partner_uniprot_id AND ma.unified_mlo = ? "
            f"AND {policy.regulator_annotation_clause('ma')} AND {active})"
        )
        extra_params.append(mlo)
        extra_where.append(policy.regulator_only_role_clause("ps"))
    elif mlo:
        extra_where.append(
            f"EXISTS (SELECT 1 FROM mlo_annotations ma "
            f"WHERE ma.uniprot_id = pt.partner_uniprot_id AND ma.unified_mlo = ? AND {active})"
        )
        extra_params.append(mlo)
    elif role == "driver":
        extra_where.append("COALESCE(ps.has_driver, 0) = 1")
    elif role == "component":
        extra_where.append("COALESCE(ps.has_driver, 0) = 0")
    elif role == "regulator":
        # Mirrors _build_proteins_conditions' role=="regulator" branch: "has a
        # curator-assigned regulator claim" alone would also match a protein
        # that's a driver elsewhere (977 today) -- pair with
        # regulator_only_role_clause so this is the same mutually-exclusive
        # "regulator, never a driver" bucket /proteins?role=regulator and the
        # home page's regulator card use, via protein_summary.has_driver=0.
        extra_where.append(
            f"EXISTS (SELECT 1 FROM mlo_annotations ma "
            f"WHERE ma.uniprot_id = pt.partner_uniprot_id AND {policy.regulator_annotation_clause('ma')} AND {active})"
        )
        extra_where.append(policy.regulator_only_role_clause("ps"))

    where_clause = "AND " + " AND ".join(extra_where)

    cte = """
    WITH partners AS (
        SELECT
            CASE WHEN p.uniprot_id_a = ? THEN p.uniprot_id_b ELSE p.uniprot_id_a END AS partner_uniprot_id,
            MAX(CASE WHEN p.uniprot_id_a = ? THEN p.in_db ELSE 1 END) AS in_db,
            GROUP_CONCAT(DISTINCT p.experimental_system) AS experimental_systems,
            COUNT(p.id) AS evidence_count,
            GROUP_CONCAT(DISTINCT p.pubmed_id) AS pubmed_ids
        FROM ppi p
        WHERE (p.uniprot_id_a = ? OR p.uniprot_id_b = ?) AND p.uniprot_id_b != p.uniprot_id_a
        GROUP BY partner_uniprot_id
    )
    """
    base_params = (uniprot_id, uniprot_id, uniprot_id, uniprot_id) + tuple(extra_params)

    total = await fetchval(
        cte + f"""
        SELECT COUNT(*)
        FROM partners pt
        LEFT JOIN protein_summary ps ON ps.uniprot_id = pt.partner_uniprot_id
        WHERE 1=1 {where_clause}
        """,
        base_params,
    ) or 0

    rows = await fetchall(
        cte + f"""
        SELECT
            pt.partner_uniprot_id,
            pr.gene_name AS partner_gene,
            COALESCE(ps.has_driver, 0) AS has_driver,
            EXISTS (SELECT 1 FROM mlo_annotations mar WHERE mar.uniprot_id = pt.partner_uniprot_id
                    AND {policy.active_annotation_clause('mar')} AND {policy.regulator_annotation_clause('mar')}) AS has_regulator,
            ps.mlos,
            pt.experimental_systems,
            pt.evidence_count,
            pt.pubmed_ids
        FROM partners pt
        LEFT JOIN proteins pr ON pr.uniprot_id = pt.partner_uniprot_id
        LEFT JOIN protein_summary ps ON ps.uniprot_id = pt.partner_uniprot_id
        WHERE 1=1 {where_clause}
        ORDER BY COALESCE(ps.has_driver, 0) DESC, pr.gene_name ASC
        LIMIT ?
        """,
        base_params + (limit,),
    )
    return total, rows


async def get_orthologs(uniprot_id: str) -> list[dict]:
    return await fetchall(
        """
        SELECT
            o.ortholog_id,
            o.organism,
            o.taxon_id,
            GROUP_CONCAT(DISTINCT o.og_id)  AS og_ids,
            MAX(o.in_db)                    AS in_db,
            GROUP_CONCAT(DISTINCT o.source) AS sources,
            m.gene_name,
            m.protein_name,
            m.length,
            m.disorder_mobidb_lite_dc,
            m.disorder_alphafold_dc,
            m.sequence
        FROM orthologs o
        LEFT JOIN ortholog_meta m ON m.ortholog_id = o.ortholog_id
        WHERE o.uniprot_id = ?
        GROUP BY o.ortholog_id
        ORDER BY o.organism, o.ortholog_id
        """,
        (uniprot_id,),
    )


async def get_ortholog_features(ortholog_ids: list[str]) -> dict[str, list[dict]]:
    if not ortholog_ids:
        return {}
    ph = ",".join("?" * len(ortholog_ids))
    rows = await fetchall(
        f"""
        SELECT ortholog_id, feature_type, source, label, accession, start, end, score, metadata
        FROM ortholog_features
        WHERE ortholog_id IN ({ph})
        ORDER BY ortholog_id, feature_type, start
        """,
        tuple(ortholog_ids),
    )
    result: dict[str, list[dict]] = {}
    for r in rows:
        result.setdefault(r["ortholog_id"], []).append(r)
    return result


async def get_ppi_inter_edges(partner_ids: list[str], max_edges: int = 5000) -> list[dict]:
    """Return deduplicated edges between partners (excludes hub)."""
    if len(partner_ids) < 2:
        return []
    ph = ",".join("?" * len(partner_ids))
    ids = tuple(partner_ids)
    return await fetchall(
        f"""
        SELECT DISTINCT
            MIN(uniprot_id_a, uniprot_id_b) AS source,
            MAX(uniprot_id_a, uniprot_id_b) AS target
        FROM ppi
        WHERE uniprot_id_a IN ({ph})
          AND uniprot_id_b IN ({ph})
          AND uniprot_id_a != uniprot_id_b
        LIMIT ?
        """,
        ids + ids + (max_edges,),
    )


async def get_ppi_page(uniprot_id: str, page: int, per_page: int) -> tuple[int, list[dict]]:
    """One row per partner. `ppi` has no unique constraint on
    (uniprot_id_a, uniprot_id_b) -- most partners carry several independent
    BioGRID evidence rows (different experimental_system/pubmed_id), so every
    non-key column has to be aggregated explicitly. A bare GROUP BY here used
    to leave experimental_system/pubmed_id/source_version unaggregated, which
    SQLite resolves by picking an arbitrary row per group -- silently
    collapsing real, distinct evidence (55k+ partner pairs in the live DB
    carry more than one evidence row). Mirrors get_ppi_all's aggregation for
    the identical relationship; see docs/issues/003. Self-interactions
    (uniprot_id_b = uniprot_id_a, e.g. P04637/p53 homodimerizing) are excluded
    the same way get_ppi_all/get_ppi_summary are -- see docs/issues/004.

    Matches uniprot_id in EITHER column, not just uniprot_id_a -- see
    get_ppi_summary's docstring for why: parse_biogrid.py only swaps the
    not-yet-in-dataset side into uniprot_id_a, so when both interactors of a
    pair are already in `proteins`, whichever BioGRID called "Interactor A"
    keeps that column, and this protein's own partner can be recorded with
    this protein itself in uniprot_id_b. See docs/issues/006."""
    total = await fetchval(
        """
        SELECT COUNT(DISTINCT CASE WHEN uniprot_id_a = ? THEN uniprot_id_b ELSE uniprot_id_a END)
        FROM ppi WHERE (uniprot_id_a = ? OR uniprot_id_b = ?) AND uniprot_id_a != uniprot_id_b
        """,
        (uniprot_id, uniprot_id, uniprot_id),
    ) or 0
    offset = (page - 1) * per_page
    rows = await fetchall(
        """
        WITH partners AS (
            SELECT
                CASE WHEN p.uniprot_id_a = ? THEN p.uniprot_id_b ELSE p.uniprot_id_a END AS partner_uniprot_id,
                MAX(CASE WHEN p.uniprot_id_a = ? THEN p.in_db ELSE 1 END) AS in_db,
                GROUP_CONCAT(DISTINCT p.experimental_system) AS experimental_systems,
                COUNT(p.id) AS evidence_count,
                GROUP_CONCAT(DISTINCT p.pubmed_id) AS pubmed_ids,
                GROUP_CONCAT(DISTINCT p.source_version) AS sources
            FROM ppi p
            WHERE (p.uniprot_id_a = ? OR p.uniprot_id_b = ?) AND p.uniprot_id_b != p.uniprot_id_a
            GROUP BY partner_uniprot_id
        )
        SELECT pt.*, pr.gene_name AS partner_gene
        FROM partners pt
        LEFT JOIN proteins pr ON pr.uniprot_id = pt.partner_uniprot_id
        ORDER BY pt.partner_uniprot_id
        LIMIT ? OFFSET ?
        """,
        (uniprot_id, uniprot_id, uniprot_id, uniprot_id, per_page, offset),
    )
    return total, rows


async def get_source_dbs_for_uniprot_ids(uniprot_ids: list[str]) -> list[dict]:
    if not uniprot_ids:
        return []
    ph = ",".join("?" * len(uniprot_ids))
    active = policy.active_annotation_clause("mlo_annotations")
    return await fetchall(
        f"""
        SELECT DISTINCT uniprot_id, source_db
        FROM mlo_annotations
        WHERE uniprot_id IN ({ph}) AND {active}
        """,
        tuple(uniprot_ids),
    )
