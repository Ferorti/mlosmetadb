import json
import logging

import aiosqlite
from fastapi import APIRouter, HTTPException, Query

from config import DEFAULT_PAGE, DEFAULT_PER_PAGE, MAX_PER_PAGE
from models.schemas import (
    ProteinsResponse,
    ProteinSummary,
    SearchFacets,
    SearchMloHit,
    SearchResponse,
)
from queries.search_queries import (
    advanced_search,
    get_advanced_search_facets,
    search_mlos_like,
    search_proteins_exact_identifier,
    search_proteins_like,
)


def _parse_json(val: str | None) -> dict | None:
    if not val:
        return None
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return None


def _parse_mlos(val: str | None) -> list[str]:
    if not val:
        return []
    try:
        result = json.loads(val)
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _parse_source_dbs(val: str | None) -> list[str]:
    if not val:
        return []
    return [s for s in val.split(",") if s]


router = APIRouter()
logger = logging.getLogger(__name__)

_VALID_SORT_BY = {"gene_name", "mlo_count", "source_db_count", "disorder_mobidb_lite_dc", "role"}


@router.get("/search", response_model=SearchResponse)
async def search(
    # One character is a legitimate broad search, not a malformed request: the
    # LIKE path below caps itself at 50 rows, so the old two-character floor
    # only produced an error where results were expected. Empty is still
    # rejected — '%%' would match the whole corpus.
    q: str = Query(min_length=1),
    mode: str = Query(default="fuzzy", pattern="^(exact|fuzzy)$"),
):
    # min_length counts characters, so "   " passes it. A blank search is not a
    # broad search: it used to reach LIKE '%   %' and return whatever happened
    # to contain that run of spaces.
    q = q.strip()
    if not q:
        raise HTTPException(422, {"error": "invalid_parameter", "message": "q: search term cannot be blank"})

    try:
        if mode == "exact":
            proteins = await search_proteins_exact_identifier(q)
            mlos = []
        else:
            proteins = await search_proteins_like(q)
            mlos = await search_mlos_like(q)
    except aiosqlite.Error:
        raise HTTPException(500, {"error": "database_error", "message": "Internal database error"})

    protein_hits = [ProteinSummary(
        uniprot_id=r["uniprot_id"],
        gene_name=r.get("gene_name"),
        protein_name=r.get("protein_name"),
        organism=r.get("organism"),
        sequence_length=r.get("sequence_length"),
        disorder_mobidb_lite_dc=r.get("disorder_mobidb_lite_dc"),
        disorder_alphafold_dc=r.get("disorder_alphafold_dc"),
        reviewed=r.get("reviewed"),
        idr_regions=_parse_json(r.get("idr_regions")),
        lcr_regions=_parse_json(r.get("lcr_regions")),
        domains=_parse_json(r.get("domains")),
        has_driver=bool(r.get("has_driver", 0)),
        has_client=bool(r.get("has_client", 0)),
        has_regulator=bool(r.get("has_regulator", 0)),
        source_db_count=r.get("source_db_count", 0),
        source_dbs=_parse_source_dbs(r.get("source_dbs")),
        mlo_count=r.get("mlo_count", 0),
        mlos=_parse_mlos(r.get("mlos")),
        match_field=r.get("match_field"),
    ) for r in proteins]

    mlo_hits = [SearchMloHit(
        unified_mlo=r["unified_mlo"],
        spatial_location=r.get("spatial_location"),
        taxonomic_scope=r.get("taxonomic_scope"),
        physiological_state=r.get("physiological_state"),
        cell_type_context=r.get("cell_type_context"),
        match_field=r.get("match_field", "unified_mlo"),
    ) for r in mlos]

    return SearchResponse(
        query=q,
        mode=mode,
        total_hits=len(protein_hits) + len(mlo_hits),
        proteins=protein_hits,
        mlos=mlo_hits,
    )


@router.get("/search/advanced", response_model=ProteinsResponse)
async def search_advanced(
    # Free text over accession + gene name + protein name, the same corpus
    # /search uses. `gene_name` stays for callers that really do want a
    # single-column match; the UI sends `q`.
    q: str | None = None,
    gene_name: str | None = None,
    uniprot_id: str | None = None,
    organism: str | None = None,
    taxon_id: int | None = None,
    mlo: str | None = None,
    role: str | None = None,
    source_db: str | None = None,
    feature_type: str | None = None,
    feature_label: str | None = None,
    feature_accession: str | None = None,
    sort_by: str | None = None,
    sort_order: str = Query(default="desc"),
    page: int = Query(default=DEFAULT_PAGE, ge=1),
    per_page: int = Query(default=DEFAULT_PER_PAGE, ge=1, le=MAX_PER_PAGE),
):
    if sort_by is not None and sort_by not in _VALID_SORT_BY:
        raise HTTPException(422, {"error": "invalid_parameter", "message": f"sort_by must be one of: {', '.join(sorted(_VALID_SORT_BY))}"})
    if sort_order.lower() not in {"asc", "desc"}:
        raise HTTPException(422, {"error": "invalid_parameter", "message": "sort_order must be 'asc' or 'desc'"})
    sort_order = sort_order.lower()

    filters = {k: v for k, v in {
        "q": q,
        "gene_name": gene_name,
        "uniprot_id": uniprot_id,
        "organism": organism,
        "taxon_id": taxon_id,
        "mlo": mlo,
        "role": role,
        "source_db": source_db,
        "feature_type": feature_type,
        "feature_label": feature_label,
        "feature_accession": feature_accession,
    }.items() if v is not None}

    if not filters:
        raise HTTPException(422, {"error": "no_filters_provided", "message": "At least one filter parameter is required"})

    per_page = min(per_page, MAX_PER_PAGE)
    try:
        total, rows = await advanced_search(
            q=q,
            gene_name=gene_name,
            uniprot_id=uniprot_id,
            organism=organism,
            taxon_id=taxon_id,
            mlo=mlo,
            role=role,
            source_db=source_db,
            feature_type=feature_type,
            feature_label=feature_label,
            feature_accession=feature_accession,
            page=page,
            per_page=per_page,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        facets_data = await get_advanced_search_facets(
            q=q,
            gene_name=gene_name,
            uniprot_id=uniprot_id,
            organism=organism,
            taxon_id=taxon_id,
            mlo=mlo,
            role=role,
            source_db=source_db,
            feature_type=feature_type,
            feature_label=feature_label,
            feature_accession=feature_accession,
        )
    except aiosqlite.Error:
        raise HTTPException(500, {"error": "database_error", "message": "Internal database error"})

    proteins = []
    for r in rows:
        proteins.append(ProteinSummary(
            uniprot_id=r["uniprot_id"],
            gene_name=r.get("gene_name"),
            protein_name=r.get("protein_name"),
            organism=r.get("organism"),
            sequence_length=r.get("sequence_length"),
            disorder_mobidb_lite_dc=r.get("disorder_mobidb_lite_dc"),
            disorder_alphafold_dc=r.get("disorder_alphafold_dc"),
            reviewed=r.get("reviewed"),
            idr_regions=_parse_json(r.get("idr_regions")),
            lcr_regions=_parse_json(r.get("lcr_regions")),
            domains=_parse_json(r.get("domains")),
            has_driver=bool(r.get("has_driver", 0)),
            has_client=bool(r.get("has_client", 0)),
            has_regulator=bool(r.get("has_regulator", 0)),
            source_db_count=r.get("source_db_count", 0),
            source_dbs=_parse_source_dbs(r.get("source_dbs")),
            mlo_count=r.get("mlo_count", 0),
            mlos=_parse_mlos(r.get("mlos")),
        ))

    return ProteinsResponse(
        total=total, page=page, per_page=per_page,
        filters_applied=filters,
        facets=SearchFacets(**facets_data),
        proteins=proteins,
    )
