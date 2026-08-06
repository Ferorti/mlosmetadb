#!/usr/bin/env python3
"""
fetch_mobidb.py — fetch MobiDB entries → mobidb_cache.db
"""

import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "database" / "mlosmetadb.db"
CACHE_DB = ROOT / "database" / "cache" / "mobidb_cache.db"

BASE_URL = "https://mobidb.org/api/download"
DELAY = 0.2
MAX_RETRIES = 3


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch_with_retry(session: requests.Session, url: str) -> requests.Response:
    for attempt in range(MAX_RETRIES):
        try:
            resp = session.get(url, timeout=60)
            if resp.status_code == 404:
                return resp
            if resp.status_code in (429, 500, 502, 503, 504):
                wait = 2 ** attempt
                print(f"  HTTP {resp.status_code}, reintentando en {wait}s ...")
                time.sleep(wait)
                continue
            return resp
        except requests.exceptions.Timeout:
            wait = 2 ** attempt
            print(f"  Timeout, reintentando en {wait}s ...")
            time.sleep(wait)
    return session.get(url, timeout=60)


def main() -> None:
    con_main = sqlite3.connect(DB)
    con_cache = sqlite3.connect(CACHE_DB)

    all_ids = [r[0] for r in con_main.execute("SELECT uniprot_id FROM proteins")]
    cached = {r[0] for r in con_cache.execute("SELECT uniprot_id FROM responses")}

    pending = [uid for uid in all_ids if uid not in cached]
    print(f"Total proteinas: {len(all_ids)}")
    print(f"Ya en cache:     {len(cached)}")
    print(f"Por fetchear:    {len(pending)}")

    if not pending:
        print("Nada que hacer.")
        con_main.close()
        con_cache.close()
        return

    session = requests.Session()
    session.headers["Accept"] = "application/json"

    total_ok = 0
    total_404 = 0
    total_err = 0
    fetched_at = now()

    for i, uid in enumerate(pending, 1):
        if i % 200 == 0 or i == 1:
            print(f"[{i}/{len(pending)}] procesando {uid} ...")

        url = f"{BASE_URL}?acc={uid}"

        try:
            resp = fetch_with_retry(session, url)

            if resp.status_code == 404:
                con_cache.execute(
                    "INSERT OR IGNORE INTO responses (uniprot_id, response, fetched_at, status_code) VALUES (?,?,?,?)",
                    (uid, "{}", fetched_at, 404),
                )
                con_cache.commit()
                total_404 += 1

            elif resp.status_code == 200:
                try:
                    payload = resp.json()
                except Exception:
                    payload = {}
                con_cache.execute(
                    "INSERT OR REPLACE INTO responses (uniprot_id, response, fetched_at, status_code) VALUES (?,?,?,?)",
                    (uid, json.dumps(payload), fetched_at, 200),
                )
                con_cache.commit()
                total_ok += 1

            else:
                con_cache.execute(
                    "INSERT OR IGNORE INTO fetch_errors (uniprot_id, error_type, error_detail, attempted_at) VALUES (?,?,?,?)",
                    (uid, "http_error", str(resp.status_code), now()),
                )
                con_cache.commit()
                total_err += 1

        except Exception as exc:
            print(f"  ERROR {uid}: {exc}")
            con_cache.execute(
                "INSERT OR IGNORE INTO fetch_errors (uniprot_id, error_type, error_detail, attempted_at) VALUES (?,?,?,?)",
                (uid, "request_error", str(exc), now()),
            )
            con_cache.commit()
            total_err += 1

        time.sleep(DELAY)

    print()
    print("=== Resultados ===")
    n_cached = con_cache.execute("SELECT COUNT(*) FROM responses").fetchone()[0]
    n_ok = con_cache.execute("SELECT COUNT(*) FROM responses WHERE status_code=200").fetchone()[0]
    n_404 = con_cache.execute("SELECT COUNT(*) FROM responses WHERE status_code=404").fetchone()[0]
    print(f"Fetcheadas con datos: {total_ok}")
    print(f"No encontradas (404): {total_404}")
    print(f"Errores: {total_err}")
    print(f"Total en cache — ok: {n_ok}, 404: {n_404}")

    errs = con_cache.execute(
        "SELECT error_type, COUNT(*) FROM fetch_errors GROUP BY error_type"
    ).fetchall()
    if errs:
        print("Errores por tipo:")
        for etype, cnt in errs:
            print(f"  {etype}: {cnt}")

    con_main.close()
    con_cache.close()


if __name__ == "__main__":
    main()
