from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from queries import unification_queries as uq

router = APIRouter()


@router.get("/unification/stats")
async def get_unification_stats(request: Request):
    stats = request.app.state.unification_stats
    if stats is None:
        raise HTTPException(503, {
            "error": "unification_stats_unavailable",
            "message": "unification_stats.json has not been generated yet -- run scripts/build_unification_stats.py",
        })
    return stats


def _export_or_503(path, filename: str):
    if not path.exists():
        raise HTTPException(503, {
            "error": "unification_export_unavailable",
            "message": f"{filename} has not been generated yet -- run scripts/build_unification_stats.py",
        })
    return FileResponse(path, media_type="text/csv", filename=filename)


@router.get("/unification/discrepant-pairs/export")
async def export_discrepant_pairs():
    path = uq.discrepant_pairs_csv_path()
    return _export_or_503(path, "discrepant_pairs.csv")


@router.get("/unification/mlo-term-mapping/export")
async def export_mlo_term_mapping():
    path = uq.mlo_term_mapping_csv_path()
    return _export_or_503(path, "mlo_term_mapping.csv")
