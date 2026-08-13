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
from queries import unification_queries
from routers import mlos, organisms, proteins, search, stats, unification

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
        SELECT {policy.canonical_source_case_sql('source_db')} AS source_db,
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
    # by_organism above is LIMIT-10'd -- this is what's left out of it, so any
    # chart built from by_organism's top 10 + this "other" bucket reconciles
    # exactly to prot_total, instead of silently summing to less than it.
    other_organisms_count = prot_total - sum(r["cnt"] for r in org_rows)

    # Mutually-exclusive protein-level driver/component/regulator split (has_driver=1
    # -> driver, else -> component). Distinct from mlo_annotations.by_role below, which
    # buckets by annotation ROW and lets one protein count in more than one bucket (e.g.
    # a driver with some client-role rows too), so it can't be used as a "the rest of the
    # dataset" figure.
    component_role_rows = await database.fetchall(
        "SELECT CASE WHEN has_driver = 1 THEN 'driver' ELSE 'component' END AS role, "
        "COUNT(*) AS cnt FROM protein_summary GROUP BY role"
    )
    component_role_map = {r["role"]: r["cnt"] for r in component_role_rows}

    # Regulator-only proteins were previously folded silently into "component" here
    # (a curator-assigned regulator call is not driver evidence, so has_driver stays 0
    # for them). Carve them into their own bucket instead: any non-driver protein with
    # at least one curator-assigned regulator annotation, per
    # policy.regulator_annotation_clause() -- the same predicate /mlo/{id}'s by_role
    # uses for its third bucket. driver + component + regulator still sums to
    # proteins.total, since this only re-splits the existing "component" count.
    regulator_count = await database.fetchval(
        f"""
        SELECT COUNT(DISTINCT ma.uniprot_id)
        FROM mlo_annotations ma
        JOIN protein_summary ps ON ps.uniprot_id = ma.uniprot_id
        WHERE ps.has_driver = 0 AND {policy.regulator_annotation_clause('ma')}
        """
    ) or 0

    return {
        "database_version": "2.0",
        "last_updated": "2026-05-04",
        "proteins": {
            "total": prot_total,
            "by_organism": {r["organism"]: r["cnt"] for r in org_rows},
            "by_organism_drivers": {r["organism"]: r["driver_cnt"] or 0 for r in org_rows},
            "top_organisms": 10,
            "total_organisms": total_organisms,
            "other_organisms_count": other_organisms_count,
            "by_component_role": {
                "driver": component_role_map.get("driver", 0),
                "component": component_role_map.get("component", 0) - regulator_count,
                "regulator": regulator_count,
            },
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
    app.state.stats = await _compute_stats()
    app.state.unification_stats = unification_queries.load_unification_stats()
    if app.state.unification_stats is None:
        logger.warning("unification_stats.json unavailable -- /unification/stats will return 503")
    logger.info("Startup complete")
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


_LOC_CONTAINERS = ("query", "body", "path", "header", "cookie")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Never str() the exception into the response. Pydantic renders a
    # ValidationError with the raising source file and line, so `str(exc)` would
    # publish the server's filesystem layout to anyone who can type a bad query.
    # The full error still goes to the log, where it belongs.
    logger.warning("Validation error on %s %s: %s", request.method, request.url.path, exc.errors())

    parts = []
    for err in exc.errors():
        loc = tuple(err.get("loc") or ())
        if loc and loc[0] in _LOC_CONTAINERS:
            loc = loc[1:]
        name = ".".join(str(x) for x in loc)
        msg = err.get("msg", "Invalid value")
        parts.append(f"{name}: {msg}" if name else msg)

    return JSONResponse(
        status_code=422,
        content={
            "error": "invalid_parameter",
            "message": "; ".join(parts) or "Invalid request parameters",
        },
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
app.include_router(unification.router)
