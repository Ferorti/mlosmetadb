#!/usr/bin/env python3
"""
build_db.py — crea esquema y carga archivos de database/final/
"""

import csv
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_DIR   = ROOT / "database"
MAP_DIR  = DB_DIR / "mappings"
FINAL    = DB_DIR / "final"
DB       = DB_DIR / "mlosmetadb.db"
CACHE_DIR = DB_DIR / "cache"

SKIP_MLO = {"DISCARD", "NULL", "synthetic_condensate", ""}

SCHEMA_MAIN = """
CREATE TABLE IF NOT EXISTS mlo_vocabulary (
    unified_mlo      TEXT PRIMARY KEY,
    category         TEXT,
    mapping_version  TEXT DEFAULT 'v3'
);

CREATE TABLE IF NOT EXISTS mlo_definitions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    unified_mlo      TEXT NOT NULL REFERENCES mlo_vocabulary(unified_mlo),
    source_db        TEXT NOT NULL,
    source_name      TEXT NOT NULL,
    definition       TEXT
);

CREATE TABLE IF NOT EXISTS proteins (
    uniprot_id       TEXT PRIMARY KEY,
    gene_name        TEXT,
    protein_name     TEXT,
    organism         TEXT,
    taxon_id         INTEGER,
    sequence         TEXT,
    length           INTEGER,
    lineage          TEXT,
    reviewed         INTEGER,
    fetch_date       TEXT
);

CREATE TABLE IF NOT EXISTS mlo_annotations (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    uniprot_id       TEXT NOT NULL REFERENCES proteins(uniprot_id),
    source_db        TEXT NOT NULL,
    source_mlo       TEXT NOT NULL,
    unified_mlo      TEXT NOT NULL REFERENCES mlo_vocabulary(unified_mlo),
    source_role      TEXT,
    unified_role     TEXT,
    evidence         TEXT,
    dataset_version  TEXT DEFAULT 'v2'
);

CREATE TABLE IF NOT EXISTS sequence_features (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    uniprot_id       TEXT NOT NULL REFERENCES proteins(uniprot_id),
    feature_type     TEXT NOT NULL,
    source           TEXT NOT NULL,
    label            TEXT,
    accession        TEXT,
    start            INTEGER,
    end              INTEGER,
    score            REAL,
    metadata         TEXT,
    fetch_date       TEXT
);

CREATE TABLE IF NOT EXISTS ortholog_meta (
    ortholog_id              TEXT PRIMARY KEY,
    gene_name                TEXT,
    protein_name             TEXT,
    organism                 TEXT,
    taxon_id                 INTEGER,
    length                   INTEGER,
    disorder_mobidb_lite_dc  REAL,
    disorder_alphafold_dc    REAL,
    sequence                 TEXT,
    fetch_date               TEXT
);

CREATE TABLE IF NOT EXISTS ortholog_features (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ortholog_id  TEXT NOT NULL,
    feature_type TEXT NOT NULL,
    source       TEXT NOT NULL,
    label        TEXT,
    accession    TEXT,
    start        INTEGER,
    end          INTEGER,
    score        REAL,
    metadata     TEXT,
    fetch_date   TEXT
);

CREATE TABLE IF NOT EXISTS orthologs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    uniprot_id      TEXT NOT NULL REFERENCES proteins(uniprot_id),
    ortholog_id     TEXT NOT NULL,
    organism        TEXT NOT NULL DEFAULT '',
    taxon_id        INTEGER NOT NULL DEFAULT 0,
    og_id           TEXT,
    in_db           INTEGER NOT NULL DEFAULT 0,
    source          TEXT DEFAULT 'OMA',
    source_version  TEXT DEFAULT 'OMA-2024'
);

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

CREATE INDEX IF NOT EXISTS idx_ortholog_features_id ON ortholog_features(ortholog_id);
CREATE INDEX IF NOT EXISTS idx_orth_uniprot         ON orthologs(uniprot_id);
CREATE INDEX IF NOT EXISTS idx_orth_indb            ON orthologs(in_db);
CREATE INDEX IF NOT EXISTS idx_orth_taxon           ON orthologs(taxon_id);
CREATE INDEX IF NOT EXISTS idx_ppi_a                ON ppi(uniprot_id_a);
CREATE INDEX IF NOT EXISTS idx_ppi_b                ON ppi(uniprot_id_b);
CREATE INDEX IF NOT EXISTS idx_ppi_indb             ON ppi(in_db);
"""

SCHEMA_CACHE = """
CREATE TABLE IF NOT EXISTS responses (
    uniprot_id   TEXT PRIMARY KEY,
    response     TEXT NOT NULL,
    fetched_at   TEXT NOT NULL,
    api_version  TEXT,
    status_code  INTEGER
);

CREATE TABLE IF NOT EXISTS fetch_errors (
    uniprot_id   TEXT NOT NULL,
    error_type   TEXT,
    error_detail TEXT,
    attempted_at TEXT NOT NULL,
    attempts     INTEGER DEFAULT 1
);
"""


def create_schema(con: sqlite3.Connection, schema: str) -> None:
    con.executescript(schema)
    con.commit()


def load_mlo_vocabulary(con: sqlite3.Connection) -> int:
    path = MAP_DIR / "mlo_mapping.csv"
    seen: set[str] = set()
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            unified = row["Nombre Sugerido"].strip()
            if unified in SKIP_MLO:
                continue
            if unified in seen:
                continue
            seen.add(unified)
            rows.append((unified, row["Categoria"].strip()))

    con.executemany(
        "INSERT OR IGNORE INTO mlo_vocabulary (unified_mlo, category) VALUES (?, ?)",
        rows,
    )
    con.commit()
    return len(rows)


def load_mlo_definitions(con: sqlite3.Connection) -> int:
    path = FINAL / "mlo_definitions.csv"
    vocab = {r[0] for r in con.execute("SELECT unified_mlo FROM mlo_vocabulary")}
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            unified = row["unified_mlo"].strip()
            definition = row["definition"].strip()
            if not unified or unified not in vocab:
                continue
            if not definition:
                continue
            rows.append((unified, row["source_db"].strip(), row["source_name"].strip(), definition))

    con.executemany(
        "INSERT INTO mlo_definitions (unified_mlo, source_db, source_name, definition) VALUES (?, ?, ?, ?)",
        rows,
    )
    con.commit()
    return len(rows)


def load_annotations(con: sqlite3.Connection) -> tuple[int, int]:
    path = DB_DIR / "mlosmetadb.tsv"
    vocab = {r[0] for r in con.execute("SELECT unified_mlo FROM mlo_vocabulary")}
    protein_stubs: set[str] = set()
    annotation_rows = []

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            uid = row["uniprot_id"].strip()
            unified = row["unified_mlo"].strip()

            if not uid or uid == "NULL":
                continue
            if not unified or unified in ("unmapped", "NULL"):
                continue
            if unified not in vocab:
                continue

            protein_stubs.add(uid)
            annotation_rows.append((
                uid,
                row["source_db"].strip(),
                row["source_mlo"].strip(),
                unified,
                row.get("source_role", "").strip() or None,
                row.get("unified_role", "").strip() or None,
                row.get("evidence", "").strip() or None,
            ))

    con.executemany(
        "INSERT OR IGNORE INTO proteins (uniprot_id) VALUES (?)",
        [(uid,) for uid in protein_stubs],
    )
    con.executemany(
        """INSERT INTO mlo_annotations
           (uniprot_id, source_db, source_mlo, unified_mlo, source_role, unified_role, evidence)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        annotation_rows,
    )
    con.commit()
    return len(protein_stubs), len(annotation_rows)


def init_cache(name: str) -> None:
    path = CACHE_DIR / name
    con = sqlite3.connect(path)
    create_schema(con, SCHEMA_CACHE)
    con.close()


def report(con: sqlite3.Connection, n_proteins: int, n_annotations: int) -> None:
    vocab_n = con.execute("SELECT COUNT(*) FROM mlo_vocabulary").fetchone()[0]
    defs_n = con.execute("SELECT COUNT(*) FROM mlo_definitions").fetchone()[0]
    print(f"mlo_vocabulary:   {vocab_n} entradas")
    print(f"mlo_definitions:  {defs_n} entradas")
    print(f"proteins (stub):  {n_proteins} entradas")
    print(f"mlo_annotations:  {n_annotations} entradas")
    print("cache dbs:        creados vacios")


def main() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Creando {DB} ...")
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys = ON")
    create_schema(con, SCHEMA_MAIN)

    print("Cargando mlo_vocabulary ...")
    n_vocab = load_mlo_vocabulary(con)
    print(f"  {n_vocab} entradas insertadas")

    print("Cargando mlo_definitions ...")
    n_defs = load_mlo_definitions(con)
    print(f"  {n_defs} entradas insertadas")

    print("Cargando mlosmetadb.tsv ...")
    n_proteins, n_annotations = load_annotations(con)
    print(f"  {n_proteins} proteinas stub, {n_annotations} anotaciones")

    print("Inicializando caches ...")
    for name in ("uniprot_cache.db", "interpro_cache.db", "mobidb_cache.db"):
        init_cache(name)

    print()
    print("=== Conteos finales ===")
    report(con, n_proteins, n_annotations)

    con.close()


if __name__ == "__main__":
    main()
