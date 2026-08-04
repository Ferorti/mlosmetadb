from fastapi import APIRouter, Request
from models.schemas import StatsResponse

router = APIRouter()


@router.get("/stats", response_model=StatsResponse)
async def get_stats(request: Request):
    return request.app.state.stats
