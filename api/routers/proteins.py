import json
import logging

import aiosqlite
from fastapi import APIRouter, HTTPException, Query

from config import DEFAULT_PAGE, DEFAULT_PER_PAGE, DEFAULT_PPI_PER_PAGE, MAX_PER_PAGE
from models.schemas import (
    DomainRegion,
    IdrRegion,
    LcdRegion,
    MloAnnotation,
    MorfRegion,
    PlddtRegion,
    ProteinDetail,
    ProteinsResponse,
    ProteinSummary,
    PpiInteractionItem,
    PpiInteractions,
    PpiSummary,
    SequenceFeatures,
)
from queries.protein_queries import (
    get_protein_features,
    get_protein_meta,
    get_protein_mlo_annotations,
    get_proteins_page,
    get_ppi_page,
    get_ppi_summary,
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


@router.get("/proteins", response_model=ProteinsResponse)
async def list_proteins(
    organism: str | None = None,
    taxon_id: int | None = None,
    mlo: str | None = None,
    role: str | None = None,
    source_db: str | None = None,
    uniprot_id: str | None = None,
    page: int = Query(default=DEFAULT_PAGE, ge=1),
    per_page: int = Query(default=DEFAULT_PER_PAGE, ge=1, le=MAX_PER_PAGE),
):
    per_page = min(per_page, MAX_PER_PAGE)
    try:
        total, rows = await get_proteins_page(organism, taxon_id, mlo, role, source_db, uniprot_id, page, per_page)
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

    return ProteinsResponse(total=total, page=page, per_page=per_page, filters_applied=filters, proteins=proteins)
