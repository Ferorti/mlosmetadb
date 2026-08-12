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

# Curation revision of the mapping files (mlo_mapping.csv, mlo_organism_scoped.csv
# and mlo_axes.csv), stamped onto every mlo_vocabulary row. Bump it in the same
# commit that changes any of them, and record what changed in
# database/mappings/_archive/mlo_mapping_decisions.md.
# Until 2026-08-08 nothing stamped this at all, so all 170 rows carried the
# column DEFAULT ('v3') while the shipped mapping was already v4 — the v4 splits
# (spindle_pole_body, chromatoid_body, sex_body, simr_foci, mardo,
# axonal_tiar2_granule, wnt_destruction_complex) were present in the data under
# a version label that predated them.
MAPPING_VERSION = "v7"


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
    unified_mlo               TEXT PRIMARY KEY,
    -- Four orthogonal axes, replacing the single `category` column (R1-ACT-06).
    -- Loaded from database/mappings/mlo_axes.csv; see SCHEMA.md for the value
    -- vocabularies and load_mlo_vocabulary() for what the loader refuses to do.
    spatial_location          TEXT,
    spatial_location_evidence TEXT,
    taxonomic_scope           TEXT,
    taxonomic_support_n       INTEGER,
    physiological_state       TEXT,
    cell_type_context         TEXT,
    mapping_version           TEXT DEFAULT 'v3'
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
    -- What kind of claim the row makes, which unified_role cannot express: one of
    -- in_vitro_llps | cellular_localisation | cellular_requirement |
    -- curator_assignment | membership_only. See compute_evidence_type() in
    -- integrate.py for why five values and what each one means.
    evidence_type    TEXT,
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

-- mlo_annotations no tenía ningún índice, así que toda consulta por proteína o
-- por MLO recorría las 35.732 filas enteras. Es la tabla que la API consulta en
-- casi todos sus endpoints (COUNT(DISTINCT uniprot_id) por MLO, anotaciones de
-- una proteína), y el join contra proteins hacía SCAN del lado grande.
CREATE INDEX IF NOT EXISTS idx_ann_uniprot          ON mlo_annotations(uniprot_id);
CREATE INDEX IF NOT EXISTS idx_ann_mlo              ON mlo_annotations(unified_mlo);
CREATE INDEX IF NOT EXISTS idx_ann_mlo_active       ON mlo_annotations(unified_mlo, dataset_active);
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


AXIS_COLUMNS = ["spatial_location", "spatial_location_evidence", "taxonomic_scope",
                "taxonomic_support_n", "physiological_state", "cell_type_context"]


def load_axes() -> dict[str, dict[str, str | int | None]]:
    """Read database/mappings/mlo_axes.csv — one row per canonical, keyed by it.

    This file replaced `Categoria` as the source of the vocabulary's
    classification (R1-ACT-06 / R2-DEC-axes). Being keyed by canonical is the
    point, not a convenience: `Categoria` lived in `mlo_mapping.csv`, which is
    keyed by *source label*, so the same canonical carried as many category
    values as it had source names and a conflict between them was possible at
    all. Here it isn't expressible — a duplicate key is a hard failure.

    `taxonomic_scope` and `cell_type_context` come back as None when the field is
    empty, and those two absences mean different things: rho_body has no
    taxonomic scope because its only protein is deleted in UniProt (a gap), while
    143 terms have no cell-type context because the axis only applies where the
    cell type is part of the organelle's definition (by design). Both are NULL in
    the DB; the difference is documented, not encoded.
    """
    path = MAP_DIR / "mlo_axes.csv"
    axes: dict[str, dict[str, str | int | None]] = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing_cols = [c for c in ["unified_mlo", *AXIS_COLUMNS] if c not in (reader.fieldnames or [])]
        if missing_cols:
            raise SystemExit(f"[FATAL] mlo_axes.csv sin las columnas {missing_cols}")
        for line_no, row in enumerate(reader, start=2):
            unified = row["unified_mlo"].strip()
            if not unified:
                raise SystemExit(f"[FATAL] mlo_axes.csv:{line_no} sin unified_mlo")
            if unified in axes:
                raise SystemExit(
                    f"[FATAL] mlo_axes.csv:{line_no} repite {unified!r}: el archivo es "
                    f"uno-a-uno con el canónico y no admite dos filas para el mismo término"
                )
            support = (row["taxonomic_support_n"] or "").strip()
            axes[unified] = {
                **{c: ((row[c] or "").strip() or None) for c in AXIS_COLUMNS},
                "taxonomic_support_n": int(support) if support else None,
            }
    return axes


def load_mlo_vocabulary(con: sqlite3.Connection) -> int:
    """Load the mapping files into mlo_vocabulary, one curated row per canonical.

    Two files declare which canonicals exist, and both have to be read here or
    the loader drops rows that integrate.py legitimately produced:

    - `mlo_mapping.csv` (`Nombre Sugerido`) — the bulk of them.
    - `mlo_organism_scoped.csv` (`unified_mlo`) — the organism-conditional
      overrides. `plant_mtoc` exists **only** there: no source name maps to it
      unconditionally, because the label that produces it
      (`Centrosome/Spindle pole body`) means something else for every other
      clade.

    Their `Categoria`/`categoria` columns are no longer read: the classification
    comes from `mlo_axes.csv` (see load_axes()). The columns stay in those files
    as the provenance of the spatial axis — 121 of the 177 spatial values were
    derived from them — and must not be resurrected as a served field. The
    conflict check they needed is gone with them, replaced by a stricter
    property: a canonical cannot hold two classifications because the axes file
    cannot hold two rows for it.

    Declaring a canonical with no axes row is allowed here and reported, not
    fatal: three of the 180 declared terms reach no annotation and
    prune_unsupported_vocabulary() removes them later in the run. What must never
    happen is *serving* a term with no axes, which assert_axes_complete() checks
    after the prune.
    """
    canonicals: dict[str, str] = {}   # canonical -> "file:line" first seen

    def collect(filename: str, name_col: str) -> None:
        path = MAP_DIR / filename
        if not path.exists():
            return
        with open(path, newline="", encoding="utf-8") as f:
            for line_no, row in enumerate(csv.DictReader(f), start=2):
                unified = row[name_col].strip()
                if unified in SKIP_MLO:
                    continue
                canonicals.setdefault(unified, f"{filename}:{line_no}")

    collect("mlo_mapping.csv", "Nombre Sugerido")
    collect("mlo_organism_scoped.csv", "unified_mlo")

    axes = load_axes()

    orphan_axes = sorted(set(axes) - set(canonicals))
    if orphan_axes:
        raise SystemExit(
            f"[FATAL] mlo_axes.csv clasifica {len(orphan_axes)} términos que ningún "
            f"archivo de mapeo produce — el archivo quedó viejo:\n"
            + "\n".join(f"    {t}" for t in orphan_axes)
        )

    sin_ejes = sorted(set(canonicals) - set(axes))
    if sin_ejes:
        print(f"  [INFO] {len(sin_ejes)} canónicos declarados sin fila en mlo_axes.csv "
              f"(deberían quedar sin anotaciones y podarse): {', '.join(sin_ejes)}")

    rows = [
        (unified, *(axes.get(unified, {}).get(c) for c in AXIS_COLUMNS), MAPPING_VERSION)
        for unified in canonicals
    ]

    # Terms the current mapping no longer produces have to leave the table, or
    # the vocabulary keeps accumulating entries from older revisions. Safe here
    # because reset_owned_tables() has already cleared mlo_annotations and
    # mlo_definitions, the only tables holding a FK into it.
    con.execute("DELETE FROM mlo_vocabulary")
    # INSERT OR REPLACE, not OR IGNORE: a recurated axis has to land on a term
    # that already exists instead of being silently dropped.
    placeholders = ", ".join("?" * (len(AXIS_COLUMNS) + 2))
    con.executemany(
        f"INSERT OR REPLACE INTO mlo_vocabulary "
        f"(unified_mlo, {', '.join(AXIS_COLUMNS)}, mapping_version) VALUES ({placeholders})",
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


def migrate_schema(con: sqlite3.Connection) -> None:
    """Add columns that SCHEMA_MAIN gained after the DB was first created.

    Every CREATE in SCHEMA_MAIN is `IF NOT EXISTS`, so a column added to it
    never reaches an existing mlosmetadb.db. Without this, a rebuild over the
    shipped DB fails on the INSERT instead of picking up the new column. Same
    approach build_summary.py uses for the disorder columns on `proteins`.
    """
    existing = {r[1] for r in con.execute("PRAGMA table_info(mlo_annotations)")}
    if "evidence_type" not in existing:
        con.execute("ALTER TABLE mlo_annotations ADD COLUMN evidence_type TEXT")
        con.commit()
        print("  migración: mlo_annotations.evidence_type agregada")

    # mlo_vocabulary: `category` → los cuatro ejes (R1-ACT-06). Se migra en vez
    # de recrear la tabla porque mlo_annotations y mlo_definitions tienen una FK
    # hacia ella y esto corre antes de reset_owned_tables(), o sea con las hijas
    # todavía cargadas: un DROP TABLE con foreign_keys=ON fallaría acá.
    vocab_cols = {r[1] for r in con.execute("PRAGMA table_info(mlo_vocabulary)")}
    for col in AXIS_COLUMNS:
        if col not in vocab_cols:
            col_type = "INTEGER" if col == "taxonomic_support_n" else "TEXT"
            con.execute(f"ALTER TABLE mlo_vocabulary ADD COLUMN {col} {col_type}")
            print(f"  migración: mlo_vocabulary.{col} agregada")
    if "category" in vocab_cols:
        # Requiere SQLite 3.35+; el DROP es seguro porque load_mlo_vocabulary()
        # reescribe la tabla entera desde los archivos de mapeo en este mismo run.
        con.execute("ALTER TABLE mlo_vocabulary DROP COLUMN category")
        print("  migración: mlo_vocabulary.category eliminada (reemplazada por los cuatro ejes)")
    con.commit()


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
                nullable(row.get("evidence_type")),
                int(row.get("dataset_active", "1").strip() or 1),
                nullable(row.get("evidence")),
            ))

    con.executemany(
        "INSERT OR IGNORE INTO proteins (uniprot_id) VALUES (?)",
        [(uid,) for uid in protein_stubs],
    )
    con.executemany(
        """INSERT INTO mlo_annotations
           (uniprot_id, source_db, source_mlo, unified_mlo, source_role, unified_role, evidence_type, dataset_active, evidence)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        annotation_rows,
    )
    con.commit()
    return len(protein_stubs), len(annotation_rows)


def prune_merged_accessions(con: sqlite3.Connection) -> int:
    """Elimina las accesiones que UniProt fusionó y cuya sucesora ya está acá.

    integrate.py reasigna las anotaciones a la accesión vigente, así que la
    obsoleta queda en `proteins` sin ninguna anotación — huérfana, y rompiendo
    el invariante de que toda proteína tiene al menos una. Esta poda cierra eso.

    Es la única parte de build_db.py que borra de `proteins`, y el motivo es
    estrecho: la fila obsoleta describe la misma proteína que su sucesora, que
    ya está en la tabla con datos propios. No se pierde una proteína, se deja de
    contarla dos veces. Se borran también sus filas dependientes; medido antes
    de aplicarlo, eso cuesta ortólogos en 4 accesiones y PPI en 1, todo
    refetcheable con los scripts de siempre.
    """
    path = MAP_DIR / "uniprot_merged.csv"
    if not path.exists():
        return 0
    with open(path, newline="", encoding="utf-8") as f:
        obsoletas = [r["accesion_obsoleta"].strip() for r in csv.DictReader(f)]
    if not obsoletas:
        return 0

    marks = ",".join("?" * len(obsoletas))
    presentes = [r[0] for r in con.execute(
        f"SELECT uniprot_id FROM proteins WHERE uniprot_id IN ({marks})", obsoletas)]
    if not presentes:
        return 0

    marks = ",".join("?" * len(presentes))
    for tabla, col in (("sequence_features", "uniprot_id"), ("orthologs", "uniprot_id"),
                       ("ppi", "uniprot_id_a"), ("ppi", "uniprot_id_b"),
                       ("protein_summary", "uniprot_id")):
        try:
            con.execute(f"DELETE FROM {tabla} WHERE {col} IN ({marks})", presentes)
        except sqlite3.OperationalError:
            pass  # la tabla puede no existir todavía en una DB recién creada
    con.execute(f"DELETE FROM proteins WHERE uniprot_id IN ({marks})", presentes)
    con.commit()
    return len(presentes)


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


def assert_axes_complete(con: sqlite3.Connection) -> None:
    """Every served term must carry the three axes that apply to all of them.

    Runs after prune_unsupported_vocabulary(), so it asks about the terms that
    actually ship. `cell_type_context` is deliberately absent from the check —
    it applies to 34 of the 177 terms by design — and `taxonomic_scope` is
    absent because rho_body genuinely has nothing to derive it from
    (R1-ACT-17): its only protein, R7KIR7, is deleted in UniProt. Those two are
    NULL-able; a served term with no spatial_location, no physiological_state or
    no spatial_location_evidence means the axes file fell behind the mapping.
    """
    required = ["spatial_location", "spatial_location_evidence", "physiological_state"]
    missing = con.execute(
        f"""SELECT unified_mlo, {', '.join(required)} FROM mlo_vocabulary
            WHERE {' OR '.join(f'{c} IS NULL' for c in required)}
            ORDER BY unified_mlo"""
    ).fetchall()
    if missing:
        detail = "\n".join(f"    {r[0]}: " + ", ".join(
            f"{c}={v!r}" for c, v in zip(required, r[1:])) for r in missing)
        raise SystemExit(
            f"[FATAL] {len(missing)} términos servidos sin ejes obligatorios — "
            f"agregalos a database/mappings/mlo_axes.csv:\n{detail}"
        )


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
    migrate_schema(con)
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

    merged = prune_merged_accessions(con)
    if merged:
        print(f"Accesiones fusionadas podadas de proteins: {merged}")

    orphans = prune_unsupported_vocabulary(con)
    if orphans:
        print(f"Vocabulario sin soporte ({len(orphans)} términos, 0 anotaciones) — removidos:")
        for term in orphans:
            print(f"  - {term}")

    assert_axes_complete(con)

    print("Inicializando caches ...")
    for name in ("uniprot_cache.db", "interpro_cache.db", "mobidb_cache.db"):
        init_cache(name)

    print()
    print("=== Conteos finales ===")
    report(con, n_proteins, n_annotations)

    con.close()


if __name__ == "__main__":
    main()
