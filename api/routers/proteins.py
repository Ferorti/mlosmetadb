import json
import logging

import aiosqlite
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, Response

import policy
from config import DEFAULT_PAGE, DEFAULT_PER_PAGE, DEFAULT_PPI_PER_PAGE, MAX_PER_PAGE
from models.schemas import (
    CitationCheckRequest,
    CitationCheckResponse,
    DomainRegion,
    IdrRegion,
    LcdRegion,
    MloAnnotation,
    MorfRegion,
    OrthoFeatureRegion,
    OrthoFeatures,
    OrthologDetail,
    OrthologsResponse,
    PlddtRegion,
    PpiAllResponse,
    PpiEdge,
    PpiPartner,
    ProteinDetail,
    ProteinsResponse,
    ProteinSummary,
    PpiInteractionItem,
    PpiInteractions,
    PpiSummary,
    SearchFacets,
    SequenceFeatures,
)
from queries.protein_queries import (
    get_ortholog_features,
    get_orthologs,
    get_protein_features,
    get_protein_meta,
    get_protein_mlo_annotations,
    get_proteins_export,
    get_proteins_facets,
    get_proteins_page,
    get_ppi_all,
    get_ppi_inter_edges,
    get_ppi_page,
    get_ppi_summary,
    get_source_dbs_for_uniprot_ids,
)

router = APIRouter()
logger = logging.getLogger(__name__)


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


_EXPORT_BASIC_FIELDS = [
    "uniprot_id", "gene_name", "protein_name", "organism", "sequence_length", "reviewed",
    "mlos", "role", "source_dbs",
]
_EXPORT_FULL_FIELDS = _EXPORT_BASIC_FIELDS + [
    "has_driver", "has_client", "mlo_count", "idr_regions", "lcr_regions", "domains",
]


def _export_role(row: dict) -> str:
    if row.get("has_driver"):
        return "driver"
    if row.get("has_client"):
        return "client"
    return ""


def _build_export_record(row: dict, fields: str) -> dict:
    record = {
        "uniprot_id": row["uniprot_id"],
        "gene_name": row.get("gene_name"),
        "protein_name": row.get("protein_name"),
        "organism": row.get("organism"),
        "sequence_length": row.get("sequence_length"),
        "reviewed": row.get("reviewed"),
        "mlos": _parse_mlos(row.get("mlos")),
        "role": _export_role(row),
        "source_dbs": _parse_source_dbs(row.get("source_dbs")),
    }
    if fields == "full":
        record["has_driver"] = bool(row.get("has_driver", 0))
        record["has_client"] = bool(row.get("has_client", 0))
        record["mlo_count"] = row.get("mlo_count", 0)
        # Kept as the raw JSON text from protein_summary for the TSV path (see
        # _records_to_tsv -- a raw string just passes through unchanged), and
        # re-parsed into real nested structures for the JSON path (see the
        # format == "json" branch in export_proteins).
        record["idr_regions"] = row.get("idr_regions")
        record["lcr_regions"] = row.get("lcr_regions")
        record["domains"] = row.get("domains")
    return record


def _records_to_tsv(records: list[dict], columns: list[str]) -> str:
    lines = ["\t".join(columns)]
    for record in records:
        values = []
        for col in columns:
            v = record.get(col)
            if isinstance(v, list):
                values.append(";".join(v))
            elif v is None:
                values.append("")
            else:
                values.append(str(v))
        # Build the row, preserving trailing tabs for empty values
        row = "\t".join(values)
        lines.append(row)
    # Add a trailing newline to the whole TSV, but preserve internal structure
    return "\n".join(lines) + "\n"


def _plddt_category(score: float) -> str:
    if score < 50:
        return "very_low"
    if score < 70:
        return "low"
    if score < 90:
        return "confident"
    return "very_high"


def _build_features(rows: list[dict]) -> SequenceFeatures:
    idrs, domains, lcds, morfs, plddt_regions = [], [], [], [], []
    for r in rows:
        ft = r["feature_type"]
        if ft in ("idr", "idr_curated"):
            idrs.append(IdrRegion(start=r["start"], end=r["end"], score=r["score"], source=r["source"]))
        elif ft in ("domain", "family"):
            domains.append(DomainRegion(
                start=r["start"], end=r["end"],
                label=r.get("label"), accession=r.get("accession"),
                database=r.get("source"),
            ))
        elif ft == "lcd":
            lcds.append(LcdRegion(start=r["start"], end=r["end"], label=r.get("label"), source=r["source"]))
        elif ft == "morf":
            morfs.append(MorfRegion(start=r["start"], end=r["end"], score=r["score"], source=r["source"]))
        elif ft == "plddt_region":
            score = r["score"]
            plddt_regions.append(PlddtRegion(
                start=r["start"], end=r["end"],
                mean_score=score,
                category=_plddt_category(score) if score is not None else None,
            ))
    return SequenceFeatures(idrs=idrs, domains=domains, lcds=lcds, morfs=morfs, plddt_regions=plddt_regions)


def _build_mlo_annotation(row: dict) -> MloAnnotation:
    raw = row.get("evidence") or ""
    pmids = [p.strip() for p in raw.split(";") if p.strip() and p.strip().upper() != "NULL"]
    return MloAnnotation(
        unified_mlo=row["unified_mlo"],
        category=row.get("category"),
        source_db=row["source_db"],
        source_mlo=row.get("source_mlo"),
        unified_role=row.get("unified_role"),
        evidence_pmids=pmids,
    )


def _build_ppi_item(row: dict) -> PpiInteractionItem:
    exp = row.get("experimental_system")
    return PpiInteractionItem(
        partner_uniprot_id=row["partner_uniprot_id"],
        partner_gene=row.get("partner_gene"),
        in_mlosmetadb=bool(row.get("in_db")),
        evidence_types=[exp] if exp else [],
        pubmed_id=row.get("pubmed_id"),
        source=row.get("source") or "",
    )


@router.get("/protein/{uniprot_id}", response_model=ProteinDetail)
async def get_protein(
    uniprot_id: str,
    ppi_page: int | None = Query(default=None, ge=1),
    ppi_per_page: int = Query(default=DEFAULT_PPI_PER_PAGE, ge=1, le=MAX_PER_PAGE),
):
    try:
        meta = await get_protein_meta(uniprot_id)
    except aiosqlite.Error:
        raise HTTPException(500, {"error": "database_error", "message": "Internal database error"})

    if meta is None:
        raise HTTPException(404, {"error": "protein_not_found", "message": f"No protein with UniProt ID '{uniprot_id}'"})

    try:
        ann_rows = await get_protein_mlo_annotations(uniprot_id)
        feat_rows = await get_protein_features(uniprot_id)
        ppi_summary = await get_ppi_summary(uniprot_id)

        interactions = None
        if ppi_page is not None:
            ppi_per_page = min(ppi_per_page, MAX_PER_PAGE)
            total_ppi, ppi_rows = await get_ppi_page(uniprot_id, ppi_page, ppi_per_page)
            interactions = PpiInteractions(
                page=ppi_page,
                per_page=ppi_per_page,
                total=total_ppi,
                items=[_build_ppi_item(r) for r in ppi_rows],
            )
    except aiosqlite.Error:
        raise HTTPException(500, {"error": "database_error", "message": "Internal database error"})

    return ProteinDetail(
        uniprot_id=meta["uniprot_id"],
        gene_name=meta.get("gene_name"),
        protein_name=meta.get("protein_name"),
        organism=meta.get("organism"),
        taxon_id=meta.get("taxon_id"),
        sequence_length=meta.get("length"),
        sequence=meta.get("sequence"),
        disorder_mobidb_lite_dc=meta.get("disorder_mobidb_lite_dc"),
        disorder_alphafold_dc=meta.get("disorder_alphafold_dc"),
        mlo_annotations=[_build_mlo_annotation(r) for r in ann_rows],
        sequence_features=_build_features(feat_rows),
        ppi=PpiSummary(
            total_partners=ppi_summary["total_partners"],
            partners_in_mlosmetadb=ppi_summary["partners_in_mlosmetadb"],
            interactions=interactions,
        ),
    )


@router.get("/protein/{uniprot_id}/ppi", response_model=PpiAllResponse)
async def get_protein_ppi(
    uniprot_id: str,
    role: str | None = Query(default=None),
    mlo: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
):
    try:
        meta = await get_protein_meta(uniprot_id)
    except aiosqlite.Error:
        raise HTTPException(500, {"error": "database_error", "message": "Internal database error"})

    if meta is None:
        raise HTTPException(404, {"error": "protein_not_found", "message": f"No protein with UniProt ID '{uniprot_id}'"})

    try:
        total, rows = await get_ppi_all(uniprot_id, role, mlo, limit)
        partner_ids = [r["partner_uniprot_id"] for r in rows]
        inter_edge_rows = await get_ppi_inter_edges(partner_ids)
    except aiosqlite.Error:
        raise HTTPException(500, {"error": "database_error", "message": "Internal database error"})

    items = []
    for r in rows:
        mlos = _parse_mlos(r.get("mlos"))
        exp_systems = list({s for s in (r.get("experimental_systems") or "").split(",") if s})
        pmids = list({p for p in (r.get("pubmed_ids") or "").split(",") if p and p.upper() != "NONE"})
        items.append(PpiPartner(
            partner_uniprot_id=r["partner_uniprot_id"],
            partner_gene=r.get("partner_gene"),
            has_driver=bool(r.get("has_driver")),
            mlos=mlos,
            experimental_systems=exp_systems,
            evidence_count=r.get("evidence_count", 1),
            pubmed_ids=pmids,
        ))

    inter_edges = [PpiEdge(source=e["source"], target=e["target"]) for e in inter_edge_rows]

    return PpiAllResponse(
        uniprot_id=uniprot_id,
        total=total,
        total_returned=len(items),
        items=items,
        inter_edges=inter_edges,
    )


_TAXON_ORDER = {
    9606:  0,   # Homo sapiens
    10090: 1,   # Mus musculus
    7955:  2,   # Danio rerio
    7227:  3,   # Drosophila melanogaster
    6239:  4,   # Caenorhabditis elegans
    4932:  5,   # Saccharomyces cerevisiae
    3702:  6,   # Arabidopsis thaliana
    44689: 7,   # Dictyostelium discoideum
    83333: 8,   # Escherichia coli K-12
}


def _build_ortho_features(feat_rows: list[dict]) -> OrthoFeatures:
    idrs, lcds, morfs, plddt_regions, domains = [], [], [], [], []
    for r in feat_rows:
        ft = r["feature_type"]
        meta = _parse_json(r.get("metadata"))
        region = OrthoFeatureRegion(
            start=r["start"],
            end=r["end"],
            score=r.get("score"),
            label=r.get("label"),
            accession=r.get("accession"),
            source=r.get("source"),
            metadata=meta,
        )
        if ft == "idr":
            idrs.append(region)
        elif ft == "lcd":
            lcds.append(region)
        elif ft == "morf":
            morfs.append(region)
        elif ft == "plddt_region":
            plddt_regions.append(region)
        elif ft == "domain":
            domains.append(region)
    return OrthoFeatures(idrs=idrs, lcds=lcds, morfs=morfs, plddt_regions=plddt_regions, domains=domains)


@router.get("/protein/{uniprot_id}/orthologs", response_model=OrthologsResponse)
async def get_protein_orthologs(uniprot_id: str):
    try:
        meta = await get_protein_meta(uniprot_id)
    except aiosqlite.Error:
        raise HTTPException(500, {"error": "database_error", "message": "Internal database error"})

    if meta is None:
        raise HTTPException(404, {"error": "protein_not_found", "message": f"No protein with UniProt ID '{uniprot_id}'"})

    try:
        orth_rows = await get_orthologs(uniprot_id)
        orth_ids = [r["ortholog_id"] for r in orth_rows]
        features_by_id = await get_ortholog_features(orth_ids)
    except aiosqlite.Error:
        raise HTTPException(500, {"error": "database_error", "message": "Internal database error"})

    organisms = sorted({r["organism"] for r in orth_rows if r["organism"]})

    orthologs = []
    for r in orth_rows:
        oid = r["ortholog_id"]
        feat_rows = features_by_id.get(oid, [])
        orthologs.append(OrthologDetail(
            ortholog_id=oid,
            organism=r["organism"],
            taxon_id=r.get("taxon_id"),
            og_id=r.get("og_ids"),
            sources=r.get("sources"),
            in_db=bool(r.get("in_db")),
            gene_name=r.get("gene_name"),
            protein_name=r.get("protein_name"),
            length=r.get("length"),
            disorder_mobidb_lite_dc=r.get("disorder_mobidb_lite_dc"),
            disorder_alphafold_dc=r.get("disorder_alphafold_dc"),
            sequence=r.get("sequence"),
            features=_build_ortho_features(feat_rows) if feat_rows else None,
        ))

    orthologs.sort(key=lambda o: (
        _TAXON_ORDER.get(o.taxon_id, 999),
        o.organism or "",
        o.ortholog_id,
    ))

    return OrthologsResponse(
        uniprot_id=uniprot_id,
        total=len(orthologs),
        organisms=organisms,
        orthologs=orthologs,
    )


_VALID_SORT_BY = {"gene_name", "mlo_count", "source_db_count", "disorder_mobidb_lite_dc", "role"}


@router.get("/proteins", response_model=ProteinsResponse)
async def list_proteins(
    organism: str | None = None,
    taxon_id: int | None = None,
    mlo: str | None = None,
    role: str | None = None,
    source_db: str | None = None,
    uniprot_id: str | None = None,
    sort_by: str | None = None,
    sort_order: str = Query(default="asc"),
    page: int = Query(default=DEFAULT_PAGE, ge=1),
    per_page: int = Query(default=DEFAULT_PER_PAGE, ge=1, le=MAX_PER_PAGE),
):
    per_page = min(per_page, MAX_PER_PAGE)
    if sort_by is not None and sort_by not in _VALID_SORT_BY:
        raise HTTPException(422, {"error": "invalid_parameter", "message": f"sort_by must be one of: {', '.join(sorted(_VALID_SORT_BY))}"})
    if sort_order.lower() not in {"asc", "desc"}:
        raise HTTPException(422, {"error": "invalid_parameter", "message": "sort_order must be 'asc' or 'desc'"})
    sort_order = sort_order.lower()
    try:
        total, rows = await get_proteins_page(organism, taxon_id, mlo, role, source_db, uniprot_id, sort_by, sort_order, page, per_page)
        facets_data = await get_proteins_facets(organism, taxon_id, mlo, role, source_db, uniprot_id)
    except aiosqlite.Error:
        raise HTTPException(500, {"error": "database_error", "message": "Internal database error"})

    filters = {k: v for k, v in {
        "uniprot_id": uniprot_id,
        "organism": organism,
        "taxon_id": taxon_id,
        "mlo": mlo,
        "role": role,
        "source_db": source_db,
    }.items() if v is not None}

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


@router.get("/proteins/export")
async def export_proteins(
    organism: str | None = None,
    taxon_id: int | None = None,
    mlo: str | None = None,
    role: str | None = None,
    source_db: list[str] | None = Query(default=None),
    fields: str = Query(default="full"),
    format: str = Query(default="tsv"),
):
    if fields not in {"basic", "full"}:
        raise HTTPException(422, {"error": "invalid_parameter", "message": "fields must be 'basic' or 'full'"})
    if format not in {"tsv", "json"}:
        raise HTTPException(422, {"error": "invalid_parameter", "message": "format must be 'tsv' or 'json'"})

    try:
        rows = await get_proteins_export(organism, taxon_id, mlo, role, source_db)
    except aiosqlite.Error:
        raise HTTPException(500, {"error": "database_error", "message": "Internal database error"})

    records = [_build_export_record(r, fields) for r in rows]
    columns = _EXPORT_BASIC_FIELDS if fields == "basic" else _EXPORT_FULL_FIELDS

    if format == "json":
        if fields == "full":
            for record in records:
                record["idr_regions"] = _parse_json(record["idr_regions"])
                record["lcr_regions"] = _parse_json(record["lcr_regions"])
                record["domains"] = _parse_json(record["domains"])
        return JSONResponse(content=records)

    tsv_body = _records_to_tsv(records, columns)
    return Response(
        content=tsv_body,
        media_type="text/tab-separated-values",
        headers={"Content-Disposition": 'attachment; filename="mlosmetadb_export.tsv"'},
    )


def _aggregate_citation_sources(rows: list[dict]) -> dict[str, int]:
    by_source: dict[str, set] = {}
    for r in rows:
        display = policy.CANONICAL_SOURCE_NAMES.get(r["source_db"], r["source_db"])
        by_source.setdefault(display, set()).add(r["uniprot_id"])
    return {name: len(ids) for name, ids in by_source.items()}


@router.post("/proteins/citations", response_model=CitationCheckResponse)
async def check_citations(body: CitationCheckRequest):
    try:
        rows = await get_source_dbs_for_uniprot_ids(body.uniprot_ids)
    except aiosqlite.Error:
        raise HTTPException(500, {"error": "database_error", "message": "Internal database error"})

    return CitationCheckResponse(by_source=_aggregate_citation_sources(rows))
