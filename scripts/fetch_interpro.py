#!/usr/bin/env python3
"""
fetch_interpro.py — fetch InterPro entries y features → interpro_cache.db
"""

import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "database" / "mlosmetadb.db"
CACHE_DB = ROOT / "database" / "cache" / "interpro_cache.db"

BASE = "https://www.ebi.ac.uk/interpro/api"
DELAY = 0.2
MAX_RETRIES = 3


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch_with_retry(session: requests.Session, url: str, params: dict | None = None) -> requests.Response:
    for attempt in range(MAX_RETRIES):
        try:
            resp = session.get(url, params=params, timeout=60)
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
    return session.get(url, params=params, timeout=60)


def fetch_entries(session: requests.Session, uid: str) -> list[dict]:
    # Correct endpoint: /entry/all/protein/uniprot/{uid}/ (not /protein/{uid}/entry/all/)
    url = f"{BASE}/entry/all/protein/uniprot/{uid}/"
    params = {"format": "json", "page_size": 200}
    all_entries = []

    while url:
        resp = fetch_with_retry(session, url, params if "?" not in url else None)
        if resp.status_code in (404, 204):
            return []
        resp.raise_for_status()
        if not resp.content:
            return []
        data = resp.json()
        all_entries.extend(data.get("results", []))
        next_url = data.get("next")
        url = next_url if next_url else None
        params = None
        if url:
            time.sleep(0.05)

    return all_entries


def fetch_protein_features(session: requests.Session, uid: str) -> dict:
    url = f"{BASE}/protein/uniprot/{uid}/"
    params = {"format": "json", "extra_fields": "sequence"}
    resp = fetch_with_retry(session, url, params)
    if resp.status_code in (404, 204) or not resp.content:
        return {}
    resp.raise_for_status()
    return resp.json()


def main() -> None:
    con_main = sqlite3.connect(DB)
    con_cache = sqlite3.connect(CACHE_DB)
    con_cache.execute("PRAGMA journal_mode=WAL")

    all_ids = [r[0] for r in con_main.execute("SELECT uniprot_id FROM proteins")]

    # Load all cached responses in one pass to classify them
    cached_with_entries: set[str] = set()
    cached_no_entries: set[str] = set()
    for uid, resp in con_cache.execute("SELECT uniprot_id, response FROM responses"):
        try:
            data = json.loads(resp)
            if data.get("entries"):
                cached_with_entries.add(uid)
            else:
                cached_no_entries.add(uid)
        except (json.JSONDecodeError, TypeError):
            cached_no_entries.add(uid)

    pending_new = [uid for uid in all_ids if uid not in cached_with_entries and uid not in cached_no_entries]
    pending_refetch = [uid for uid in all_ids if uid in cached_no_entries]

    print(f"Total proteinas:          {len(all_ids)}")
    print(f"Cache OK (con entries):   {len(cached_with_entries)}")
    print(f"Cache vacío (sin entries):{len(cached_no_entries)}")
    print(f"Sin cache:                {len(pending_new)}")
    print(f"Por fetchear (nuevo):     {len(pending_new)}")
    print(f"Por refetchear (entries): {len(pending_refetch)}")

    pending = pending_new + pending_refetch
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
        if i % 500 == 0 or i == 1:
            print(f"[{i}/{len(pending)}] procesando {uid} ...")

        is_refetch = uid in cached_no_entries

        try:
            entries = fetch_entries(session, uid)

            if is_refetch:
                # Keep existing protein metadata, only update entries
                existing = json.loads(
                    con_cache.execute(
                        "SELECT response FROM responses WHERE uniprot_id=?", (uid,)
                    ).fetchone()[0]
                )
                protein = existing.get("protein", {})
            else:
                protein = fetch_protein_features(session, uid)
                time.sleep(DELAY)

            combined = {"entries": entries, "protein": protein}

            con_cache.execute(
                "INSERT OR REPLACE INTO responses (uniprot_id, response, fetched_at, status_code) VALUES (?,?,?,?)",
                (uid, json.dumps(combined), fetched_at, 200),
            )
            con_cache.commit()

            if not entries and not protein:
                total_404 += 1
            else:
                total_ok += 1

        except requests.exceptions.HTTPError as exc:
            code = exc.response.status_code if exc.response else 0
            if code == 404:
                con_cache.execute(
                    "INSERT OR IGNORE INTO responses (uniprot_id, response, fetched_at, status_code) VALUES (?,?,?,?)",
                    (uid, json.dumps({}), fetched_at, 404),
                )
                con_cache.commit()
                total_404 += 1
            else:
                con_cache.execute(
                    "INSERT OR IGNORE INTO fetch_errors (uniprot_id, error_type, error_detail, attempted_at) VALUES (?,?,?,?)",
                    (uid, "http_error", str(exc), now()),
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
    print(f"Fetcheadas con datos: {total_ok}")
    print(f"Sin entradas (404/vacio): {total_404}")
    print(f"Errores: {total_err}")
    print(f"Total en cache: {n_cached}")

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
