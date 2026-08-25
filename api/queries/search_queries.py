import policy
from database import fetchall, like_contains
from queries.protein_queries import _SORT_NEEDS_PS, _build_sort, _has_regulator_select, _scoped_role_counts


async def search_proteins_exact_identifier(q: str) -> list[dict]:
    return await fetchall(
        f"""
        SELECT p.uniprot_id, p.gene_name, p.protein_name, p.organism,
               p.length AS sequence_length,
               p.disorder_mobidb_lite_dc, p.disorder_alphafold_dc,
               p.reviewed,
               ps.idr_regions, ps.lcr_regions, ps.domains,
               ps.has_driver, ps.has_client, ps.source_db_count, ps.mlo_count, ps.mlos,
               ps.source_dbs,
               {_has_regulator_select("p")},
               CASE
                   WHEN LOWER(p.uniprot_id) = LOWER(?) THEN 'uniprot_id'
                   ELSE 'gene_name'
               END AS match_field
        FROM proteins p
        LEFT JOIN protein_summary ps ON ps.uniprot_id = p.uniprot_id
        WHERE LOWER(p.uniprot_id) = LOWER(?) OR LOWER(p.gene_name) = LOWER(?)
        LIMIT 50
        """,
        (q, q, q),
    )


async def search_proteins_like(q: str) -> list[dict]:
    sub = like_contains(q)
    return await fetchall(
        f"""
        SELECT p.uniprot_id, p.gene_name, p.protein_name, p.organism,
               p.length AS sequence_length,
               p.disorder_mobidb_lite_dc, p.disorder_alphafold_dc,
               p.reviewed,
               ps.idr_regions, ps.lcr_regions, ps.domains,
               ps.has_driver, ps.has_client, ps.source_db_count, ps.mlo_count, ps.mlos,
               ps.source_dbs,
               {_has_regulator_select("p")},
               CASE
                   WHEN LOWER(p.uniprot_id) LIKE LOWER(?) ESCAPE '\\' THEN 'uniprot_id'
                   ELSE 'gene_name'
               END AS match_field
        FROM proteins p
        LEFT JOIN protein_summary ps ON ps.uniprot_id = p.uniprot_id
        WHERE LOWER(p.uniprot_id) LIKE LOWER(?) ESCAPE '\\'
           OR LOWER(p.gene_name) LIKE LOWER(?) ESCAPE '\\'
        ORDER BY p.uniprot_id
        LIMIT 50
        """,
        (sub, sub, sub),
    )


async def search_mlos_like(q: str) -> list[dict]:
    # MLO names are stored slugged ('stress_granule') but people type them the
    # way they read them ('stress granule'). Match against both spellings by
    # unslugging the column rather than by rewriting the query — replacing the
    # user's spaces with '_' would smuggle in a LIKE single-char wildcard.
    pattern = like_contains(q)
    return await fetchall(
        """
        SELECT unified_mlo, spatial_location, taxonomic_scope,
               physiological_state, cell_type_context,
               'unified_mlo' AS match_field
        FROM mlo_vocabulary
        WHERE LOWER(unified_mlo) LIKE LOWER(?) ESCAPE '\\'
           OR LOWER(REPLACE(unified_mlo, '_', ' ')) LIKE LOWER(?) ESCAPE '\\'
        ORDER BY unified_mlo
        LIMIT 20
        """,
        (pattern, pattern),
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
    q: str | None = None,
    mode: str = "fuzzy",
) -> tuple[list[str], list[str], list]:
    joins = ["FROM proteins p"]
    conditions: list[str] = []
    params: list = []

    # Free text over the same two columns search_proteins_like uses. Keeping
    # the two identical is the point: `gene_name` used to be the only text
    # parameter here, so applying any filter silently narrowed the corpus
    # from what /search matched to a single column, and a query that matched
    # by gene_name via /search returned nothing the moment a filter was
    # touched via /search/advanced.
    #
    # mode="exact" swaps LIKE for a full-field equality, mirroring
    # search_proteins_exact_identifier's pattern -- without this, the
    # frontend's "Exact match" checkbox had nothing to bind to here (every
    # free-text search from the results page goes through this function, not
    # /search's own mode=exact, since the /search/advanced consolidation) and
    # q="FUS" matched "FUS3" too. See docs/issues/005.
    if q:
        if mode == "exact":
            conditions.append("(LOWER(p.uniprot_id) = LOWER(?) OR LOWER(p.gene_name) = LOWER(?))")
            params.extend([q, q])
        else:
            conditions.append(
                "(LOWER(p.uniprot_id) LIKE LOWER(?) ESCAPE '\\'"
                " OR LOWER(p.gene_name) LIKE LOWER(?) ESCAPE '\\')"
            )
            sub = like_contains(q)
            params.extend([sub, sub])

    need_mlo = any(x is not None for x in [mlo, role, source_db])
    need_feat = any(x is not None for x in [feature_type, feature_label, feature_accession])

    if need_mlo:
        joins.append(
            f"JOIN mlo_annotations ma ON p.uniprot_id = ma.uniprot_id AND {policy.active_annotation_clause('ma')}"
        )
    if need_feat:
        joins.append("JOIN sequence_features sf ON p.uniprot_id = sf.uniprot_id")

    if gene_name:
        conditions.append("LOWER(p.gene_name) LIKE LOWER(?) ESCAPE '\\'")
        params.append(like_contains(gene_name))
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
    if feature_type:
        conditions.append("LOWER(sf.feature_type) = LOWER(?)")
        params.append(feature_type)
    if feature_label:
        conditions.append("LOWER(sf.label) LIKE LOWER(?) ESCAPE '\\'")
        params.append(like_contains(feature_label))
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
    q: str | None = None,
    mode: str = "fuzzy",
) -> dict:
    joins, conditions, params = _build_advanced_clauses(
        gene_name, uniprot_id, organism, taxon_id, mlo, role, source_db,
        feature_type, feature_label, feature_accession, q, mode,
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

    # Role facet pivots on role, so it's computed from a role-free scope (same mlo/
    # source_db/etc. filters, without whatever role may already be applied) -- and from
    # each protein's role WITHIN that scope, not protein_summary.has_driver (a global flag
    # true if the protein drives ANY MLO/source anywhere, which over-counts here the same
    # way it did in protein_queries.get_proteins_facets -- see that function's docstring).
    _, conditions_no_role, params_no_role = _build_advanced_clauses(
        gene_name, uniprot_id, organism, taxon_id, mlo, None, source_db,
        feature_type, feature_label, feature_accession, q, mode,
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
    sort_by: str | None = None,
    sort_order: str = "desc",
    q: str | None = None,
    mode: str = "fuzzy",
) -> tuple[int, list[dict]]:
    from database import fetchval

    joins, conditions, params = _build_advanced_clauses(
        gene_name, uniprot_id, organism, taxon_id, mlo, role, source_db,
        feature_type, feature_label, feature_accession, q, mode,
    )
    if sort_by in _SORT_NEEDS_PS:
        joins.append("LEFT JOIN protein_summary ps_s ON p.uniprot_id = ps_s.uniprot_id")
    from_clause = " ".join(joins)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    total = await fetchval(
        f"SELECT COUNT(DISTINCT p.uniprot_id) {from_clause} {where}",
        tuple(params),
    ) or 0

    cte_extra, cte_order, outer_order = _build_sort(sort_by, sort_order)

    offset = (page - 1) * per_page
    rows = await fetchall(
        f"""
        WITH filtered AS (
            SELECT DISTINCT p.uniprot_id{cte_extra}
            {from_clause} {where}
            ORDER BY {cte_order}
            LIMIT ? OFFSET ?
        )
        SELECT
            p.uniprot_id, p.gene_name, p.protein_name, p.organism,
            p.length AS sequence_length,
            p.disorder_mobidb_lite_dc, p.disorder_alphafold_dc,
            p.reviewed,
            ps.idr_regions, ps.lcr_regions, ps.domains,
            ps.has_driver, ps.has_client, ps.source_db_count, ps.mlo_count, ps.mlos,
            ps.source_dbs,
            {_has_regulator_select("p")}
        FROM filtered f
        JOIN proteins p ON p.uniprot_id = f.uniprot_id
        LEFT JOIN protein_summary ps ON ps.uniprot_id = f.uniprot_id
        ORDER BY {outer_order}
        """,
        tuple(params) + (per_page, offset),
    )
    return total, rows
