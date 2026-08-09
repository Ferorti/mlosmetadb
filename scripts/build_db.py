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

# Curation revision of database/mappings/mlo_mapping.csv, stamped onto every
# mlo_vocabulary row. Bump it in the same commit that changes the mapping file,
# and record what changed in database/mappings/_archive/mlo_mapping_decisions.md.
# Until 2026-08-08 nothing stamped this at all, so all 170 rows carried the
# column DEFAULT ('v3') while the shipped mapping was already v4 — the v4 splits
# (spindle_pole_body, chromatoid_body, sex_body, simr_foci, mardo,
# axonal_tiar2_granule, wnt_destruction_complex) were present in the data under
# a version label that predated them.
MAPPING_VERSION = "v5"


def nullable(value: str | None) -> str | None:
    """Read a TSV field, honouring 'NULL' as the absent-value sentinel.

    integrate.py writes the literal string 'NULL' for a field it has no value
    for (see _merge_evidence / _first_real), and every other column read here
    already treats it that way. `evidence` did not, so 13,847 CD-CODE rows
    reached the DB with the text 'NULL' instead of SQL NULL, and any query
    filtering `evidence IS NOT NULL` counted a quarter of the dataset as
    PMID-backed when none of it is.
    """
    value = (value or "").strip()
    return value if value and value != "NULL" else None

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
    dataset_active   INTEGER NOT NULL DEFAULT 1,
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
    """Load mlo_mapping.csv into mlo_vocabulary, one curated row per canonical.

    Several source names collapse into one canonical, so the same canonical
    appears in many rows of the mapping file. Until 2026-08-08 this function
    kept whichever row it read first and inserted with OR IGNORE, which meant
    that when those rows disagreed on `Categoria` the stored category was
    decided by file order rather than by a curator — arbitrary for 24 of the
    170 terms, including cases with real biological content
    (`polarity_condensate`: Citoesqueleto / Neuronal / Procariota). A conflict
    is now a hard failure: the mapping file has to say one thing.
    """
    path = MAP_DIR / "mlo_mapping.csv"
    categories: dict[str, dict[str, int]] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for line_no, row in enumerate(csv.DictReader(f), start=2):
            unified = row["Nombre Sugerido"].strip()
            if unified in SKIP_MLO:
                continue
            category = row["Categoria"].strip()
            categories.setdefault(unified, {}).setdefault(category, line_no)

    conflicts = {u: c for u, c in categories.items() if len(c) > 1}
    if conflicts:
        detail = "\n".join(
            f"    {unified}: " + ", ".join(f"{cat!r} (línea {ln})" for cat, ln in sorted(cats.items(), key=lambda kv: kv[1]))
            for unified, cats in sorted(conflicts.items())
        )
        raise SystemExit(
            f"[FATAL] {len(conflicts)} canónicos con Categoria en conflicto en {path.name}.\n"
            f"  Cada canónico necesita una sola categoría curada — resolvelas en el archivo:\n{detail}"
        )

    rows = [(unified, next(iter(cats)), MAPPING_VERSION) for unified, cats in categories.items()]

    # Terms the current mapping no longer produces have to leave the table, or
    # the vocabulary keeps accumulating entries from older revisions. Safe here
    # because reset_owned_tables() has already cleared mlo_annotations and
    # mlo_definitions, the only tables holding a FK into it.
    con.execute("DELETE FROM mlo_vocabulary")
    # INSERT OR REPLACE, not OR IGNORE: a recurated category has to land on a
    # term that already exists instead of being silently dropped.
    con.executemany(
        "INSERT OR REPLACE INTO mlo_vocabulary (unified_mlo, category, mapping_version) VALUES (?, ?, ?)",
        rows,
    )
    con.commit()

    stale = con.execute(
        "SELECT COUNT(*) FROM mlo_vocabulary WHERE mapping_version IS NOT ?",
        (MAPPING_VERSION,),
    ).fetchone()[0]
    if stale:
        raise SystemExit(f"[FATAL] {stale} filas de mlo_vocabulary quedaron fuera de {MAPPING_VERSION}")
    return len(rows)


def reset_owned_tables(con: sqlite3.Connection) -> None:
    """Clear the three tables build_db.py owns, in foreign-key-safe order.

    This script is documented as re-runnable over an existing mlosmetadb.db,
    and without this a second run appends a full duplicate copy of every
    definition and annotation. Only the tables build_db.py owns are cleared —
    proteins, sequence_features, ppi and orthologs carry fetched data this
    script never writes and must survive untouched.

    Order matters: mlo_annotations and mlo_definitions both hold a FK into
    mlo_vocabulary, so they go first, which is also what lets
    load_mlo_vocabulary() drop terms the mapping no longer produces.
    """
    con.execute("DELETE FROM mlo_annotations")
    con.execute("DELETE FROM mlo_definitions")
    con.commit()


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
                nullable(row.get("source_role")),
                nullable(row.get("unified_role")),
                int(row.get("dataset_active", "1").strip() or 1),
                nullable(row.get("evidence")),
            ))

    con.executemany(
        "INSERT OR IGNORE INTO proteins (uniprot_id) VALUES (?)",
        [(uid,) for uid in protein_stubs],
    )
    con.executemany(
        """INSERT INTO mlo_annotations
           (uniprot_id, source_db, source_mlo, unified_mlo, source_role, unified_role, dataset_active, evidence)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        annotation_rows,
    )
    con.commit()
    return len(protein_stubs), len(annotation_rows)


def prune_unsupported_vocabulary(con: sqlite3.Connection) -> list[str]:
    """Drop vocabulary terms that no annotation reaches.

    The project's own rule is that a canonical term is not created unless some
    source annotates proteins at that resolution, but nothing enforced it: three
    terms (adhesin_nanodomain, npr1_condensate, rosenthal_fiber) were curated
    from source names that no interim file ever emits, so they shipped as
    vocabulary entries with zero proteins behind them. Their mapping rows stay
    in mlo_mapping.csv — the curation record is not the thing that was wrong —
    but they do not become served terms.

    Runs after load_annotations() so "supported" is measured against the
    annotations actually loaded, and re-checks on every rebuild instead of
    encoding a fixed list that would go stale.
    """
    orphans = [
        r[0] for r in con.execute(
            """SELECT unified_mlo FROM mlo_vocabulary v
               WHERE NOT EXISTS (SELECT 1 FROM mlo_annotations a WHERE a.unified_mlo = v.unified_mlo)
               ORDER BY unified_mlo"""
        )
    ]
    if orphans:
        marks = ",".join("?" * len(orphans))
        con.execute(f"DELETE FROM mlo_definitions WHERE unified_mlo IN ({marks})", orphans)
        con.execute(f"DELETE FROM mlo_vocabulary WHERE unified_mlo IN ({marks})", orphans)
        con.commit()
    return orphans


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
    reset_owned_tables(con)

    print("Cargando mlo_vocabulary ...")
    n_vocab = load_mlo_vocabulary(con)
    print(f"  {n_vocab} entradas insertadas")

    print("Cargando mlo_definitions ...")
    n_defs = load_mlo_definitions(con)
    print(f"  {n_defs} entradas insertadas")

    print("Cargando mlosmetadb.tsv ...")
    n_proteins, n_annotations = load_annotations(con)
    print(f"  {n_proteins} proteinas stub, {n_annotations} anotaciones")

    orphans = prune_unsupported_vocabulary(con)
    if orphans:
        print(f"Vocabulario sin soporte ({len(orphans)} términos, 0 anotaciones) — removidos:")
        for term in orphans:
            print(f"  - {term}")

    print("Inicializando caches ...")
    for name in ("uniprot_cache.db", "interpro_cache.db", "mobidb_cache.db"):
        init_cache(name)

    print()
    print("=== Conteos finales ===")
    report(con, n_proteins, n_annotations)

    con.close()


if __name__ == "__main__":
    main()
