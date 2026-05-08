import aiosqlite
from fastapi import APIRouter, HTTPException, Query

from database import fetchall
from models.schemas import OrganismResult, OrganismsSearchResponse

router = APIRouter()


@router.get("/organisms/search", response_model=OrganismsSearchResponse)
async def search_organisms(
    q: str = Query(min_length=3),
    limit: int = Query(default=10, ge=1, le=50),
):
    if len(q) < 3:
        raise HTTPException(422, {"error": "invalid_parameter", "message": "Query 'q' must be at least 3 characters"})

    pattern = f"%{q.lower()}%"
    try:
        rows = await fetchall(
            """
            SELECT organism, COUNT(*) AS protein_count
            FROM proteins
            WHERE LOWER(organism) LIKE ?
            GROUP BY organism
            ORDER BY protein_count DESC
            LIMIT ?
            """,
            (pattern, limit),
        )
    except aiosqlite.Error:
        raise HTTPException(500, {"error": "database_error", "message": "Internal database error"})

    return OrganismsSearchResponse(
        query=q,
        results=[OrganismResult(organism=r["organism"], protein_count=r["protein_count"]) for r in rows],
    )
