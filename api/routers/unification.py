from fastapi import APIRouter, HTTPException, Request

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
