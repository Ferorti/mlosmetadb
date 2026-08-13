import asyncio
import logging
import os
import sqlite3
from typing import Any

import aiosqlite

from config import DB_PATH

logger = logging.getLogger(__name__)

_db: aiosqlite.Connection | None = None
_mem_hold: sqlite3.Connection | None = None  # keeps named in-memory DB alive

_MEM_URI = "file:mlosmetadb_api?mode=memory&cache=shared"

LIKE_ESCAPE = "\\"


def escape_like(value: str) -> str:
    """Disarm the LIKE metacharacters in a user string.

    Without this, '%' and '_' arriving from a search box are SQL wildcards
    rather than characters: a query of a single '%' matched every protein in
    the database, and searching the real gene name 'A_B' also returned 'AXB'.

    Every call site must pair the pattern with `ESCAPE '\\'` in the SQL.
    """
    return (
        value.replace(LIKE_ESCAPE, LIKE_ESCAPE * 2)
        .replace("%", LIKE_ESCAPE + "%")
        .replace("_", LIKE_ESCAPE + "_")
    )


def like_contains(value: str) -> str:
    """A LIKE "contains anywhere" pattern over an escaped user string."""
    return f"%{escape_like(value)}%"


async def get_db() -> aiosqlite.Connection:
    return _db


async def open_db() -> None:
    global _db, _mem_hold

    # sqlite3.connect() CREATES an empty file when the path does not exist, so a
    # wrong DB_PATH does not fail here — it fails much later, and unhelpfully,
    # as "no such table: main.proteins" while FTS5 is being built. Check first
    # and say what is actually wrong.
    # os.path, not Path methods: DB_PATH is a Path from config but the tests
    # monkeypatch it with a plain string, and a guard is worthless if it is
    # itself fragile.
    if not os.path.exists(DB_PATH):
        raise RuntimeError(
            f"Database not found at {DB_PATH}. Set MLOSMETADB_PATH, or place the "
            f"file there — sqlite would otherwise create an empty one and the "
            f"first query would fail with a confusing 'no such table' error."
        )
    if os.path.getsize(DB_PATH) == 0:
        raise RuntimeError(f"Database at {DB_PATH} is empty (0 bytes).")

    logger.info("Loading database into memory from %s ...", DB_PATH)

    def _backup() -> sqlite3.Connection:
        src = sqlite3.connect(str(DB_PATH))
        dst = sqlite3.connect(_MEM_URI, uri=True, check_same_thread=False)
        src.backup(dst)
        src.close()
        return dst

    _mem_hold = await asyncio.to_thread(_backup)
    _db = await aiosqlite.connect(_MEM_URI, uri=True)
    _db.row_factory = aiosqlite.Row
    logger.info("Database loaded into memory.")


async def close_db() -> None:
    global _mem_hold
    if _db:
        await _db.close()
    if _mem_hold:
        _mem_hold.close()
        _mem_hold = None


async def fetchall(sql: str, params: tuple = ()) -> list[dict]:
    try:
        async with _db.execute(sql, params) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]
    except aiosqlite.Error as e:
        logger.error("DB error — query: %s | params: %s | exc: %s", sql, params, e)
        raise


async def fetchone(sql: str, params: tuple = ()) -> dict | None:
    try:
        async with _db.execute(sql, params) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None
    except aiosqlite.Error as e:
        logger.error("DB error — query: %s | params: %s | exc: %s", sql, params, e)
        raise


async def fetchval(sql: str, params: tuple = ()) -> Any:
    row = await fetchone(sql, params)
    if row is None:
        return None
    return next(iter(row.values()))

