#!/usr/bin/env python3
"""
parse_biogrid.py — parsea BIOGRID-ALL-5.0.257.tab3.zip → tabla ppi en mlosmetadb.db

Solo interacciones físicas experimentales de fuentes validadas.
"""

import csv
import sqlite3
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "database" / "mlosmetadb.db"
BIOGRID_ZIP = ROOT / "database" / "crossref" / "BIOGRID-ALL-5.0.257.tab3.zip"

VALID_SYSTEMS = {
    "Co-immunoprecipitation",
    "Affinity Capture-MS",
    "Affinity Capture-Western",
    "Affinity Capture-RNA",
    "FRET",
    "Proximity Label-MS",
    "Biochemical Activity",
    "Reconstituted Complex",
    "Co-crystal Structure",
    "Co-purification",
    "Protein-RNA EMSA",
    "PCA",
}

TEST_PROTEINS = {"P35637", "Q92520", "P09651", "P38919", "Q9NQC3"}


def create_tables(con: sqlite3.Connection) -> None:
    con.executescript("""
        CREATE TABLE IF NOT EXISTS ppi (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            uniprot_id_a        TEXT NOT NULL REFERENCES proteins(uniprot_id),
            uniprot_id_b        TEXT NOT NULL,
            in_db               INTEGER NOT NULL DEFAULT 0,
            experimental_system TEXT NOT NULL,
            throughput          TEXT,
            organism_id_a       INTEGER,
            organism_id_b       INTEGER,
            pubmed_id           TEXT,
            source_version      TEXT DEFAULT 'BIOGRID-5.0.257'
        );
        CREATE INDEX IF NOT EXISTS idx_ppi_a     ON ppi(uniprot_id_a);
        CREATE INDEX IF NOT EXISTS idx_ppi_b     ON ppi(uniprot_id_b);
        CREATE INDEX IF NOT EXISTS idx_ppi_indb  ON ppi(in_db);
    """)
    con.commit()


def resolve_uniprot(swiss: str, trembl: str) -> str | None:
    for acc in swiss.split("|"):
        acc = acc.strip()
        if acc and acc != "-":
            return acc
    for acc in trembl.split("|"):
        acc = acc.strip()
        if acc and acc != "-":
            return acc
    return None


def parse_biogrid(
    db_proteins: set[str],
    filter_to: set[str] | None = None,
) -> tuple[list[tuple], dict]:
    """
    Parsea el ZIP y devuelve (rows, stats).
    Si filter_to no es None, solo procesa filas donde al menos un interactor está en filter_to.
    """
    stats = {
        "total": 0,
        "skip_not_physical": 0,
        "skip_invalid_system": 0,
        "skip_no_uniprot": 0,
        "skip_none_in_dataset": 0,
        "inserted": 0,
        "in_db_1": 0,
        "in_db_0": 0,
    }
    seen: set[tuple] = set()
    rows: list[tuple] = []

    with zipfile.ZipFile(BIOGRID_ZIP) as z:
        fname = z.namelist()[0]
        with z.open(fname) as f:
            reader = csv.DictReader(
                (line.decode("utf-8") for line in f),
                delimiter="\t",
            )
            for row in reader:
                stats["total"] += 1

                if row["Experimental System Type"].strip() != "physical":
                    stats["skip_not_physical"] += 1
                    continue

                system = row["Experimental System"].strip()
                if system not in VALID_SYSTEMS:
                    stats["skip_invalid_system"] += 1
                    continue

                uid_a = resolve_uniprot(
                    row["SWISS-PROT Accessions Interactor A"],
                    row["TREMBL Accessions Interactor A"],
                )
                uid_b = resolve_uniprot(
                    row["SWISS-PROT Accessions Interactor B"],
                    row["TREMBL Accessions Interactor B"],
                )

                if not uid_a or not uid_b:
                    stats["skip_no_uniprot"] += 1
                    continue

                # Si hay filtro de test, aplicarlo antes del dataset check
                if filter_to and uid_a not in filter_to and uid_b not in filter_to:
                    continue

                a_in = uid_a in db_proteins
                b_in = uid_b in db_proteins

                if not a_in and not b_in:
                    stats["skip_none_in_dataset"] += 1
                    continue

                # Normalizar: el del dataset va en uniprot_id_a
                org_a = row["Organism ID Interactor A"].strip()
                org_b = row["Organism ID Interactor B"].strip()

                if not a_in:
                    uid_a, uid_b = uid_b, uid_a
                    org_a, org_b = org_b, org_a

                pubmed_raw = row["Publication Source"].strip()
                pubmed_id = pubmed_raw.replace("PUBMED:", "").strip() if "PUBMED" in pubmed_raw else None

                try:
                    oid_a = int(org_a) if org_a else None
                except ValueError:
                    oid_a = None
                try:
                    oid_b = int(org_b) if org_b else None
                except ValueError:
                    oid_b = None

                throughput = row["Throughput"].strip() or None
                in_db = 1 if uid_b in db_proteins else 0

                key = (uid_a, uid_b, system)
                if key in seen:
                    continue
                seen.add(key)

                rows.append((
                    uid_a, uid_b, in_db, system,
                    throughput, oid_a, oid_b, pubmed_id,
                ))
                stats["inserted"] += 1
                if in_db:
                    stats["in_db_1"] += 1
                else:
                    stats["in_db_0"] += 1

    return rows, stats


def print_test_results(rows: list[tuple]) -> None:
    from collections import defaultdict
    by_a: dict[str, list] = defaultdict(list)
    for r in rows:
        by_a[r[0]].append(r)

    print("\n=== TEST RESULTS ===")
    for uid in sorted(TEST_PROTEINS):
        interactions = by_a.get(uid, [])
        print(f"\n  {uid}: {len(interactions)} interacciones")
        for r in interactions[:5]:
            print(f"    → {r[1]:12s}  {r[3]}")
        if len(interactions) > 5:
            print(f"    ... y {len(interactions)-5} más")


def main(test_only: bool = False) -> None:
    con = sqlite3.connect(DB)
    con.execute("PRAGMA journal_mode=WAL")
    create_tables(con)

    db_proteins = {r[0] for r in con.execute("SELECT uniprot_id FROM proteins")}
    print(f"Proteínas en DB: {len(db_proteins)}")

    # Check idempotency: proteínas ya procesadas
    already_done = {
        r[0] for r in con.execute("SELECT DISTINCT uniprot_id_a FROM ppi")
    }
    if already_done:
        print(f"Ya procesadas en ppi: {len(already_done)} proteínas — modo append")

    # ── TEST ──────────────────────────────────────────────────────────────
    print("\n--- Corriendo test con TEST_PROTEINS ---")
    test_rows, test_stats = parse_biogrid(db_proteins, filter_to=TEST_PROTEINS)
    print_test_results(test_rows)

    # Verificación básica: FUS debe tener interacciones con TDP-43/hnRNP A1
    fus_partners = {r[1] for r in test_rows if r[0] == "P35637"}
    ok_fus = "Q13148" in fus_partners or "P09651" in fus_partners
    print(f"\n  FUS partners found: {sorted(fus_partners)[:10]}")
    print(f"  Test FUS↔TDP43/hnRNPA1: {'PASS ✓' if ok_fus else 'FAIL ✗'}")

    if not ok_fus:
        print("\nTest falló — abortando pipeline completo.")
        con.close()
        return

    if test_only:
        con.close()
        return

    # ── PIPELINE COMPLETO ─────────────────────────────────────────────────
    print("\n--- Pipeline completo ---")
    rows, stats = parse_biogrid(db_proteins, filter_to=None)

    if rows:
        # Idempotencia: eliminar filas ya existentes del batch
        existing = {
            (r[0], r[1], r[3])
            for r in con.execute("SELECT uniprot_id_a, uniprot_id_b, experimental_system FROM ppi")
        }
        rows = [r for r in rows if (r[0], r[1], r[3]) not in existing]

        con.executemany(
            "INSERT INTO ppi "
            "(uniprot_id_a, uniprot_id_b, in_db, experimental_system, "
            "throughput, organism_id_a, organism_id_b, pubmed_id) "
            "VALUES (?,?,?,?,?,?,?,?)",
            rows,
        )
        con.commit()

    print()
    print("=== Reporte final parse_biogrid ===")
    print(f"Filas procesadas:          {stats['total']:>10,}")
    print(f"Filtradas (no physical):   {stats['skip_not_physical']:>10,}")
    print(f"Filtradas (sistema inv.):  {stats['skip_invalid_system']:>10,}")
    print(f"Sin UniProt ID:            {stats['skip_no_uniprot']:>10,}")
    print(f"Ninguno en dataset:        {stats['skip_none_in_dataset']:>10,}")
    print(f"Insertadas:                {stats['inserted']:>10,}")
    print(f"  - con in_db = 1:         {stats['in_db_1']:>10,}")
    print(f"  - con in_db = 0:         {stats['in_db_0']:>10,}")

    print("\n--- Distribución por sistema experimental ---")
    for r in con.execute(
        "SELECT experimental_system, COUNT(*) FROM ppi GROUP BY experimental_system ORDER BY 2 DESC"
    ):
        print(f"  {r[0]:35s} {r[1]:>8,}")

    con.close()


if __name__ == "__main__":
    main()
