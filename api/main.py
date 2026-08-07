import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import database
from config import CORS_ORIGINS
import policy
from routers import mlos, organisms, proteins, search, stats

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def _compute_stats() -> dict:
    prot_total = await database.fetchval("SELECT COUNT(*) FROM proteins") or 0
    # has_driver here is the protein's GLOBAL driver flag (driver of ANY MLO) -- correct for
    # a per-organism breakdown, unlike the MLO-scoped bug fixed in protein_queries.py's
    # _scoped_role_counts (there, "driver" needed to mean "driver of THIS specific MLO").
    org_rows = await database.fetchall(
        "SELECT p.organism, COUNT(DISTINCT p.uniprot_id) AS cnt, "
        "SUM(CASE WHEN ps.has_driver = 1 THEN 1 ELSE 0 END) AS driver_cnt "
        "FROM proteins p LEFT JOIN protein_summary ps ON ps.uniprot_id = p.uniprot_id "
        "WHERE p.organism IS NOT NULL "
        "GROUP BY p.organism ORDER BY cnt DESC LIMIT 10"
    )

    active = policy.active_annotation_clause("mlo_annotations")

    ann_total = await database.fetchval(f"SELECT COUNT(*) FROM mlo_annotations WHERE {active}") or 0
    unique_mlos = await database.fetchval(
        f"SELECT COUNT(DISTINCT unified_mlo) FROM mlo_annotations WHERE {active}"
    ) or 0
    src_rows = await database.fetchall(
        f"SELECT source_db, COUNT(*) AS cnt FROM mlo_annotations WHERE {active} GROUP BY source_db"
    )
    unique_src_rows = await database.fetchall(
        f"""
        SELECT
            CASE source_db
                WHEN 'PhaseDB' THEN 'PhaSePDB'
                WHEN 'PhasePDB' THEN 'PhaSePDB'
                WHEN 'PhasePro' THEN 'PhaSePro'
                WHEN 'CDCODE' THEN 'CD-CODE'
                ELSE source_db
            END AS source_db,
            COUNT(DISTINCT uniprot_id) AS cnt
        FROM mlo_annotations WHERE {active}
        GROUP BY 1
        """
    )
    role_rows = await database.fetchall(
        f"SELECT COALESCE(LOWER(unified_role), 'unknown') AS role, COUNT(DISTINCT uniprot_id) AS cnt "
        f"FROM mlo_annotations WHERE {active} GROUP BY role"
    )

    feat_total = await database.fetchval("SELECT COUNT(*) FROM sequence_features") or 0
    feat_rows = await database.fetchall(
        "SELECT feature_type, COUNT(*) AS cnt FROM sequence_features GROUP BY feature_type"
    )
    prot_with_feat = await database.fetchval("SELECT COUNT(DISTINCT uniprot_id) FROM sequence_features") or 0

    ppi_total = await database.fetchval("SELECT COUNT(*) FROM ppi") or 0
    prot_with_ppi = await database.fetchval("SELECT COUNT(DISTINCT uniprot_id_a) FROM ppi") or 0

    total_organisms = await database.fetchval("SELECT COUNT(DISTINCT organism) FROM proteins") or 0

    # Mutually-exclusive protein-level driver/component split (has_driver=1 -> driver,
    # else -> component) — distinct from mlo_annotations.by_role below, which buckets by
    # annotation ROW and lets one protein count in more than one bucket (e.g. a driver with
    # some client-role rows too), so it can't be used as a "the rest of the dataset" figure.
    component_role_rows = await database.fetchall(
        "SELECT CASE WHEN has_driver = 1 THEN 'driver' ELSE 'component' END AS role, "
        "COUNT(*) AS cnt FROM protein_summary GROUP BY role"
    )

    return {
        "database_version": "2.0",
        "last_updated": "2026-05-04",
        "proteins": {
            "total": prot_total,
            "by_organism": {r["organism"]: r["cnt"] for r in org_rows},
            "by_organism_drivers": {r["organism"]: r["driver_cnt"] or 0 for r in org_rows},
            "top_organisms": 10,
            "total_organisms": total_organisms,
            "by_component_role": {r["role"]: r["cnt"] for r in component_role_rows},
        },
        "mlo_annotations": {
            "total": ann_total,
            "unique_mlos": unique_mlos,
            "by_source": {r["source_db"]: r["cnt"] for r in src_rows},
            "unique_proteins_by_source": {r["source_db"]: r["cnt"] for r in unique_src_rows},
            "by_role": {r["role"]: r["cnt"] for r in role_rows},
        },
        "sequence_features": {
            "total": feat_total,
            "by_type": {r["feature_type"]: r["cnt"] for r in feat_rows},
            "proteins_with_features": prot_with_feat,
        },
        "ppi": {
            "total_interactions": ppi_total,
            "proteins_with_ppi": prot_with_ppi,
        },
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.open_db()
    await database.setup_fts5()
    app.state.stats = await _compute_stats()
    logger.info("Startup complete — FTS5=%s", database.fts5_available)
    yield
    await database.close_db()
    logger.info("Shutdown complete")


app = FastAPI(title="MLOsMetaDB API", version="2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "error", "message": str(exc.detail)},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": "invalid_parameter", "message": str(exc)},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url)
    return JSONResponse(
        status_code=500,
        content={"error": "database_error", "message": "Internal server error"},
    )


app.include_router(proteins.router)
app.include_router(mlos.router)
app.include_router(search.router)
app.include_router(stats.router)
app.include_router(organisms.router)
