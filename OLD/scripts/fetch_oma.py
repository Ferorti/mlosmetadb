#!/usr/bin/env python3
"""
fetch_oma.py — fetch orthologs from OMA Browser API → oma_cache.db
"""

import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "database" / "mlosmetadb.db"
CACHE_DB = ROOT / "database" / "cache" / "oma_cache.db"

BASE_URL = "https://omabrowser.org/api/protein/{uid}/orthologs/?format=json"
DELAY = 0.3
MAX_RETRIES = 3

TEST_PROTEINS = ["P35637", "Q92520", "P09651", "P38919", "Q9NQC3"]

TARGET_TAXONS = {
    9606:  "Homo sapiens",
    10090: "Mus musculus",
    7955:  "Danio rerio",
    7227:  "Drosophila melanogaster",
    6239:  "Caenorhabditis elegans",
    4932:  "Saccharomyces cerevisiae",
    3702:  "Arabidopsis thaliana",
    44689: "Dictyostelium discoideum",
    83333: "Escherichia coli K-12",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_link_header(link_header: str) -> dict:
    links = {}
    for part in link_header.split(","):
        part = part.strip()
        if not part:
            continue
        segments = [s.strip() for s in part.split(";")]
        if len(segments) < 2:
            continue
        url = segments[0].strip("<>")
        for seg in segments[1:]:
            if seg.startswith("rel="):
                rel = seg[4:].strip('"\'')
                links[rel] = url
    return links


def fetch_with_retry(session: requests.Session, url: str) -> requests.Response:
    for attempt in range(MAX_RETRIES):
        try:
            resp = session.get(url, timeout=30)
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
    return session.get(url, timeout=30)


def fetch_orthologs(session: requests.Session, uniprot_id: str) -> tuple[list | None, int]:
    all_results = []
    url = BASE_URL.format(uid=uniprot_id)

    while url:
        resp = fetch_with_retry(session, url)
        if resp.status_code == 404:
            time.sleep(DELAY)
            return None, 404
        resp.raise_for_status()
        data = resp.json()

        if isinstance(data, list):
            all_results.extend(data)
            url = None
        else:
            all_results.extend(data.get("results", []))
            url = None
            if "Link" in resp.headers:
                links = parse_link_header(resp.headers["Link"])
                url = links.get("next")

        time.sleep(DELAY)

    return all_results, 200


def init_cache(con_cache: sqlite3.Connection) -> None:
    con_cache.executescript("""
        CREATE TABLE IF NOT EXISTS responses (
            uniprot_id   TEXT PRIMARY KEY,
            response     TEXT NOT NULL,
            fetched_at   TEXT NOT NULL,
            status_code  INTEGER
        );
        CREATE TABLE IF NOT EXISTS fetch_errors (
            uniprot_id   TEXT,
            error_type   TEXT,
            error_detail TEXT,
            attempted_at TEXT,
            attempts     INTEGER DEFAULT 1
        );
    """)
    con_cache.commit()


def run_test(session: requests.Session, con_cache: sqlite3.Connection) -> bool:
    print("=== TEST con TEST_PROTEINS ===")
    all_pass = True

    for uid in TEST_PROTEINS:
        print(f"\n{uid}:")
        try:
            orthologs, status = fetch_orthologs(session, uid)
            if status == 404 or orthologs is None:
                print("  404 — no encontrado en OMA")
                all_pass = False
                continue

            fetched_at = now()
            con_cache.execute(
                "INSERT OR REPLACE INTO responses (uniprot_id, response, fetched_at, status_code) VALUES (?,?,?,?)",
                (uid, json.dumps(orthologs), fetched_at, 200),
            )
            con_cache.commit()

            by_organism: dict[str, list[str]] = {}
            for entry in orthologs:
                taxon_id = entry.get("species", {}).get("taxon_id")
                if taxon_id not in TARGET_TAXONS:
                    continue
                org_name = TARGET_TAXONS[taxon_id]
                canonical = entry.get("canonicalid", "").strip()
                if canonical and canonical != uid:
                    by_organism.setdefault(org_name, []).append(canonical)

            if not by_organism:
                print("  Sin ortólogos en organismos de interés")
                all_pass = False
            else:
                for org, ids in sorted(by_organism.items()):
                    print(f"  {org}: {', '.join(ids[:5])}{' ...' if len(ids) > 5 else ''}")

        except Exception as exc:
            print(f"  ERROR: {exc}")
            all_pass = False

    return all_pass


def main(test_only: bool = False) -> None:
    con_cache = sqlite3.connect(CACHE_DB)
    con_cache.execute("PRAGMA journal_mode=WAL")
    init_cache(con_cache)

    session = requests.Session()
    session.headers["Accept"] = "application/json"

    # Step 1: run test
    test_ok = run_test(session, con_cache)
    if not test_ok:
        print("\nTEST FALLIDO — no se procesa el dataset completo.")
        con_cache.close()
        return

    print("\nTEST PASADO — procediendo con dataset completo.\n")

    if test_only:
        con_cache.close()
        return

    # Step 2: full dataset
    con_main = sqlite3.connect(DB)
    all_ids = [r[0] for r in con_main.execute("SELECT uniprot_id FROM proteins")]
    con_main.close()

    cached_ids = {r[0] for r in con_cache.execute("SELECT uniprot_id FROM responses")}
    error_ids = {r[0] for r in con_cache.execute("SELECT uniprot_id FROM fetch_errors")}
    pending = [uid for uid in all_ids if uid not in cached_ids and uid not in error_ids]

    print(f"Total proteínas:    {len(all_ids)}")
    print(f"Ya en cache:        {len(cached_ids)}")
    print(f"Con errores previos:{len(error_ids)}")
    print(f"Por fetchear:       {len(pending)}")

    if not pending:
        print("Nada que fetchear.")
        con_cache.close()
        return

    total_ok = 0
    total_404 = 0
    total_err = 0
    fetched_at = now()

    for i, uid in enumerate(pending, 1):
        if i % 500 == 0 or i == 1:
            print(f"[{i}/{len(pending)}] {uid} ...")

        try:
            orthologs, status = fetch_orthologs(session, uid)

            if status == 404 or orthologs is None:
                con_cache.execute(
                    "INSERT OR IGNORE INTO responses (uniprot_id, response, fetched_at, status_code) VALUES (?,?,?,?)",
                    (uid, json.dumps([]), fetched_at, 404),
                )
                con_cache.commit()
                total_404 += 1
            else:
                con_cache.execute(
                    "INSERT OR REPLACE INTO responses (uniprot_id, response, fetched_at, status_code) VALUES (?,?,?,?)",
                    (uid, json.dumps(orthologs), fetched_at, 200),
                )
                con_cache.commit()
                total_ok += 1

        except requests.exceptions.HTTPError as exc:
            code = exc.response.status_code if exc.response else 0
            con_cache.execute(
                "INSERT OR IGNORE INTO fetch_errors (uniprot_id, error_type, error_detail, attempted_at) VALUES (?,?,?,?)",
                (uid, "http_error", str(exc), now()),
            )
            con_cache.commit()
            total_err += 1
            if code != 404:
                print(f"  HTTP ERROR {uid}: {exc}")

        except Exception as exc:
            print(f"  ERROR {uid}: {exc}")
            con_cache.execute(
                "INSERT OR IGNORE INTO fetch_errors (uniprot_id, error_type, error_detail, attempted_at) VALUES (?,?,?,?)",
                (uid, "request_error", str(exc), now()),
            )
            con_cache.commit()
            total_err += 1

    print()
    print("=== Fetch completado ===")
    print(f"OK:    {total_ok}")
    print(f"404:   {total_404}")
    print(f"Errores: {total_err}")
    print(f"Total en cache: {con_cache.execute('SELECT COUNT(*) FROM responses').fetchone()[0]}")

    con_cache.close()


if __name__ == "__main__":
    main()
