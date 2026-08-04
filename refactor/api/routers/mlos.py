import json
import logging

import aiosqlite
from fastapi import APIRouter, HTTPException, Query

from config import DEFAULT_PAGE, DEFAULT_PER_PAGE, MAX_PER_PAGE
from models.schemas import (
    MloDefinition,
    MloDetail,
    MloListItem,
    MloProteinItem,
    MloProteins,
    MlosResponse,
    MloStats,
)
from queries.mlo_queries import (
    get_all_mlos,
    get_definitions_for_mlos,
    get_mlo_definitions,
    get_mlo_meta,
    get_mlo_proteins_page,
    get_mlo_stats,
)

router = APIRouter()
logger = logging.getLogger(__name__)

_COMPONENT_ROLES = {"client", "unknown", "unmapped"}


def _normalize_role(role: str | None) -> str | None:
    if role and role.lower() in _COMPONENT_ROLES:
        return "component"
    return role


@router.get("/mlo/{unified_mlo}", response_model=MloDetail)
async def get_mlo(
    unified_mlo: str,
    organism: str | None = None,
    role: str | None = None,
    source_db: str | None = None,
    page: int = Query(default=DEFAULT_PAGE, ge=1),
    per_page: int = Query(default=DEFAULT_PER_PAGE, ge=1, le=MAX_PER_PAGE),
):
    try:
        meta = await get_mlo_meta(unified_mlo)
    except aiosqlite.Error:
        raise HTTPException(500, {"error": "database_error", "message": "Internal database error"})

    if meta is None:
        raise HTTPException(404, {"error": "mlo_not_found", "message": f"MLO '{unified_mlo}' not in vocabulary"})

    try:
        per_page = min(per_page, MAX_PER_PAGE)
        defs = await get_mlo_definitions(unified_mlo)
        stats = await get_mlo_stats(unified_mlo)
        total, rows = await get_mlo_proteins_page(unified_mlo, organism, role, source_db, page, per_page)
    except aiosqlite.Error:
        raise HTTPException(500, {"error": "database_error", "message": "Internal database error"})

    items = []
    for r in rows:
        sources_raw = r.get("sources_concat") or ""
        idr_raw = r.get("idr_regions")
        lcr_raw = r.get("lcr_regions")
        dom_raw = r.get("domains")
        items.append(MloProteinItem(
            uniprot_id=r["uniprot_id"],
            gene_name=r.get("gene_name"),
            organism=r.get("organism"),
            unified_role=_normalize_role(r.get("unified_role")),
            sources=[s for s in sources_raw.split(",") if s],
            disorder_mobidb_lite_dc=r.get("disorder_mobidb_lite_dc"),
            disorder_alphafold_dc=r.get("disorder_alphafold_dc"),
            idr_regions=json.loads(idr_raw) if idr_raw else None,
            lcr_regions=json.loads(lcr_raw) if lcr_raw else None,
            domains=json.loads(dom_raw) if dom_raw else None,
        ))

    return MloDetail(
        unified_mlo=meta["unified_mlo"],
        category=meta.get("category"),
        definitions=[MloDefinition(
            source_db=d["source_db"],
            source_name=d.get("source_name"),
            definition=d.get("definition"),
        ) for d in defs],
        stats=MloStats(
            total_proteins=stats["total_proteins"],
            by_source=stats["by_source"],
            by_role=stats["by_role"],
            organisms=stats["organisms"],
        ),
        proteins=MloProteins(page=page, per_page=per_page, total=total, items=items),
    )


@router.get("/mlos", response_model=MlosResponse)
async def list_mlos(
    category: str | None = None,
    source_db: str | None = None,
    organism: str | None = None,
    q: str | None = None,
):
    try:
        rows = await get_all_mlos(category, source_db, organism, q)
        defs_by_mlo = await get_definitions_for_mlos([r["unified_mlo"] for r in rows])
    except aiosqlite.Error:
        raise HTTPException(500, {"error": "database_error", "message": "Internal database error"})

    items = []
    for r in rows:
        sources_raw = r.get("sources_concat") or ""
        mlo_defs = defs_by_mlo.get(r["unified_mlo"], [])
        items.append(MloListItem(
            unified_mlo=r["unified_mlo"],
            category=r.get("category"),
            protein_count=r.get("protein_count", 0),
            driver_count=r.get("driver_count", 0),
            sources=[s for s in sources_raw.split(",") if s],
            definitions=[MloDefinition(
                source_db=d["source_db"],
                source_name=d.get("source_name"),
                definition=d.get("definition"),
            ) for d in mlo_defs],
        ))

    return MlosResponse(total=len(items), mlos=items)
