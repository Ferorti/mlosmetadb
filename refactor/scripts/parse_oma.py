#!/usr/bin/env python3
"""
parse_oma.py — populate orthologs table from oma_cache.db
"""

import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "database" / "mlosmetadb.db"
CACHE_DB = ROOT / "database" / "cache" / "oma_cache.db"

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

# UniProt accession regex (both old and new format)
UNIPROT_RE = re.compile(
    r"^([OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2})$"
)

TEST_PROTEINS = ["P35637", "Q92520", "P09651", "P38919", "Q9NQC3"]


def is_uniprot_accession(s: str) -> bool:
    return bool(UNIPROT_RE.match(s))


def init_db(con: sqlite3.Connection) -> None:
    con.executescript("""
        CREATE TABLE IF NOT EXISTS orthologs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            uniprot_id      TEXT NOT NULL REFERENCES proteins(uniprot_id),
            ortholog_id     TEXT NOT NULL,
            organism        TEXT NOT NULL,
            taxon_id        INTEGER NOT NULL,
            og_id           TEXT,
            in_db           INTEGER NOT NULL DEFAULT 0,
            source          TEXT DEFAULT 'OMA',
            source_version  TEXT DEFAULT 'OMA-2024'
        );
        CREATE INDEX IF NOT EXISTS idx_orth_uniprot ON orthologs(uniprot_id);
        CREATE INDEX IF NOT EXISTS idx_orth_indb    ON orthologs(in_db);
        CREATE INDEX IF NOT EXISTS idx_orth_taxon   ON orthologs(taxon_id);
    """)
    con.commit()


def parse_orthologs(uniprot_id: str, ortholog_list: list, db_proteins: set) -> list[tuple]:
    rows = []
    seen = set()

    for entry in ortholog_list:
        sp = entry.get("species", {})
        taxon_id = sp.get("taxon_id")
        if taxon_id not in TARGET_TAXONS:
            continue

        organism = TARGET_TAXONS[taxon_id]
        canonical = entry.get("canonicalid", "").strip()

        # Skip empty, self-references, and non-UniProt IDs (mnemonics, Ensembl)
        if not canonical or canonical == uniprot_id:
            continue
        if not is_uniprot_accession(canonical):
            continue

        og_id = str(entry.get("oma_group")) if entry.get("oma_group") else None
        in_db = 1 if canonical in db_proteins else 0

        key = (uniprot_id, canonical, taxon_id)
        if key in seen:
            continue
        seen.add(key)

        rows.append((uniprot_id, canonical, organism, taxon_id, og_id, in_db, "OMA", "OMA-2024"))

    return rows


def run_test(con_main: sqlite3.Connection, con_cache: sqlite3.Connection) -> bool:
    db_proteins = {r[0] for r in con_main.execute("SELECT uniprot_id FROM proteins")}
    print("=== TEST con TEST_PROTEINS ===")
    all_ok = True

    for uid in TEST_PROTEINS:
        row = con_cache.execute(
            "SELECT response, status_code FROM responses WHERE uniprot_id=?", (uid,)
        ).fetchone()
        if not row:
            print(f"{uid}: NO EN CACHE — correr fetch_oma.py primero")
            all_ok = False
            continue

        data = json.loads(row[0])
        rows = parse_orthologs(uid, data, db_proteins)

        by_org: dict[str, list] = {}
        for r in rows:
            org = r[2]
            entry = {"ortholog_id": r[1], "in_db": r[5]}
            by_org.setdefault(org, []).append(entry)

        print(f"\n{uid} ({len(rows)} ortólogos en organismos de interés):")
        if not by_org:
            print("  Sin ortólogos con accession UniProt en organismos de interés")
            all_ok = False
        else:
            for org, entries in sorted(by_org.items()):
                ids = ", ".join(f"{e['ortholog_id']}(in_db={e['in_db']})" for e in entries[:5])
                print(f"  {org}: {ids}")

    return all_ok


def main(test_only: bool = False) -> None:
    con_main = sqlite3.connect(DB)
    con_cache = sqlite3.connect(CACHE_DB)

    init_db(con_main)

    # Run test
    ok = run_test(con_main, con_cache)
    if not ok:
        print("\nTEST FALLIDO — verificar fetch_oma.py antes de continuar.")
        con_main.close()
        con_cache.close()
        return

    print("\nTEST PASADO — procediendo con dataset completo.\n")

    if test_only:
        con_main.close()
        con_cache.close()
        return

    # Full parse
    db_proteins = {r[0] for r in con_main.execute("SELECT uniprot_id FROM proteins")}

    # Clear existing OMA orthologs to allow re-runs
    con_main.execute("DELETE FROM orthologs WHERE source='OMA'")
    con_main.commit()

    all_uids = [r[0] for r in con_main.execute("SELECT uniprot_id FROM proteins")]
    total_proteins = len(all_uids)
    with_gene_id = 0   # proteins found in OMA cache with data
    with_ortholog = 0  # proteins that got at least one row
    no_ortholog = 0

    stats_indb = 0
    stats_per_org: dict[str, int] = {name: 0 for name in TARGET_TAXONS.values()}

    batch = []
    BATCH_SIZE = 500

    def flush(batch):
        con_main.executemany(
            "INSERT INTO orthologs "
            "(uniprot_id, ortholog_id, organism, taxon_id, og_id, in_db, source, source_version) "
            "VALUES (?,?,?,?,?,?,?,?)",
            batch,
        )
        con_main.commit()

    total_inserted = 0

    for i, uid in enumerate(all_uids, 1):
        row = con_cache.execute(
            "SELECT response, status_code FROM responses WHERE uniprot_id=?", (uid,)
        ).fetchone()
        if not row:
            continue

        status = row[1]
        data = json.loads(row[0])

        if status == 404 or not data:
            continue

        with_gene_id += 1
        rows = parse_orthologs(uid, data, db_proteins)

        if not rows:
            no_ortholog += 1
        else:
            with_ortholog += 1
            for r in rows:
                stats_indb += r[5]
                stats_per_org[r[2]] = stats_per_org.get(r[2], 0) + 1
            batch.extend(rows)
            total_inserted += len(rows)

        if len(batch) >= BATCH_SIZE:
            flush(batch)
            batch.clear()

        if i % 2000 == 0:
            print(f"[{i}/{total_proteins}] insertadas hasta ahora: {total_inserted}")

    if batch:
        flush(batch)

    print()
    print("=== Reporte final parse_oma.py ===")
    print(f"Proteínas en dataset:          {total_proteins}")
    print(f"Fetcheadas de OMA (con datos): {with_gene_id}")
    print(f"404 (no en OMA):               {total_proteins - with_gene_id}")
    print(f"Con ortólogos insertados:      {with_ortholog}")
    print(f"Sin ortólogos en taxons target:{no_ortholog}")
    print(f"Filas insertadas en orthologs: {total_inserted}")
    print(f"  - con in_db = 1:             {stats_indb}")
    print("Por organismo:")
    for org, count in sorted(stats_per_org.items(), key=lambda x: -x[1]):
        print(f"  {org}: {count}")

    con_main.close()
    con_cache.close()


if __name__ == "__main__":
    main()
