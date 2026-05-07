import asyncio
import logging
import sqlite3
from typing import Any

import aiosqlite

from config import DB_PATH

logger = logging.getLogger(__name__)

_db: aiosqlite.Connection | None = None
_mem_hold: sqlite3.Connection | None = None  # keeps named in-memory DB alive
fts5_available: bool = False

_MEM_URI = "file:mlosmetadb_api?mode=memory&cache=shared"


async def get_db() -> aiosqlite.Connection:
    return _db


async def open_db() -> None:
    global _db, _mem_hold
    logger.info("Loading database into memory from %s ...", DB_PATH)

    def _backup() -> sqlite3.Connection:
        src = sqlite3.connect(str(DB_PATH))
        dst = sqlite3.connect(_MEM_URI, uri=True)
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


async def check_fts5() -> bool:
    try:
        await _db.execute("SELECT fts5(?1)", ("test",))
        return True
    except Exception:
        return False


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


async def setup_fts5() -> None:
    global fts5_available
    fts5_available = await check_fts5()
    if not fts5_available:
        logger.warning("FTS5 not available — fuzzy search will fall back to LIKE")
        return

    await _db.executescript("""
        CREATE VIRTUAL TABLE IF NOT EXISTS fts_proteins USING fts5(
            uniprot_id, gene_name, protein_name,
            content='proteins', content_rowid='rowid'
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS fts_mlos USING fts5(
            unified_mlo,
            content='mlo_vocabulary', content_rowid='rowid'
        );
    """)

    prot_count = await fetchval("SELECT COUNT(*) FROM fts_proteins")
    if not prot_count:
        await _db.execute("INSERT INTO fts_proteins SELECT rowid, uniprot_id, gene_name, protein_name FROM proteins")
    await _db.execute("INSERT INTO fts_proteins(fts_proteins) VALUES('rebuild')")

    mlo_count = await fetchval("SELECT COUNT(*) FROM fts_mlos")
    if not mlo_count:
        await _db.execute("INSERT INTO fts_mlos SELECT rowid, unified_mlo FROM mlo_vocabulary")
    await _db.execute("INSERT INTO fts_mlos(fts_mlos) VALUES('rebuild')")

    await _db.commit()
