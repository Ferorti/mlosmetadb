"""
integrate.py — Genera el dataset unificado de MLOsMetaDB.

Pasos:
  1. Concatena todos los archivos de database/interim/*.tsv
  2. Deduplica a una fila por (uniprot_id, source_db, source_mlo, source_role),
     uniendo los PMIDs — ver collapse_duplicates() más abajo
  3. Calcula unified_role + dataset_active por fila, según la tabla fija
     source_db/source_role documentada en BIOLOGY.md (no via role_mapping.tsv
     — ver compute_role_and_active() más abajo)
  4. Aplica mlo_mapping.tsv (source_mlo → unified_mlo) si está disponible
  5. Escribe database/mlosmetadb.tsv

unified_role es siempre exactamente 'driver' | 'client' | NULL (nunca
capitalizado, nunca el string 'unmapped'). unified_mlo, en cambio, sigue
usando 'unmapped' como valor centinela para filas sin cobertura en
mlo_mapping.csv — build_db.py descarta esas filas al cargar mlo_annotations,
así que 'unmapped' nunca llega a la DB para unified_mlo tampoco, pero la
palabra en sí sigue siendo válida como marcador intermedio en el TSV.

Uso:
  python3 integrate.py
"""

import csv as _csv
from pathlib import Path
import pandas as pd

ROOT    = Path(__file__).resolve().parent.parent
INTERIM = ROOT / "database" / "interim"
MAP_DIR = ROOT / "database" / "mappings"
OUT     = ROOT / "database" / "mlosmetadb.tsv"

INTERIM_COLS = ["uniprot_id", "source_db", "source_mlo", "source_role", "evidence", "organism"]


def load_interim() -> pd.DataFrame:
    files = sorted(INTERIM.glob("*.tsv"))
    frames = []
    for f in files:
        df = pd.read_csv(f, sep="\t", dtype=str, keep_default_na=False)
        missing = [c for c in INTERIM_COLS if c not in df.columns]
        if missing:
            print(f"  [WARN] {f.name} faltan columnas: {missing} — saltando")
            continue
        df = df[INTERIM_COLS]
        frames.append(df)
        print(f"  {f.name}: {len(df):>7} filas")
    combined = pd.concat(frames, ignore_index=True)
    print(f"\n  Total concatenado: {len(combined)} filas")
    return combined


NULL = "NULL"
DEDUP_KEY = ["uniprot_id", "source_db", "source_mlo", "source_role"]


def apply_uniprot_merges(df: pd.DataFrame, map_file: Path) -> pd.DataFrame:
    """Reescribe accesiones que UniProt fusionó hacia su accesión vigente.

    Las fuentes citan accesiones de distintas épocas, así que la misma proteína
    entra dos veces cuando una de ellas quedó obsoleta: 185 proteínas estaban en
    la base bajo una accesión fusionada *y* bajo su sucesora, con 301 filas
    colgando de la vieja y 171 pares (proteína, MLO) contados dos veces. Eso
    infla `COUNT(DISTINCT uniprot_id)`, que es exactamente lo que la API sirve
    por MLO.

    Corre ANTES de collapse_duplicates() a propósito: así las filas que quedan
    idénticas colapsan solas y sus PMIDs se unen, en vez de necesitar un paso
    de deduplicación aparte.

    El archivo se derivó de `inactiveReason.mergeDemergeTo` en
    uniprot_cache.db, no de una consulta nueva a la API.
    """
    if not map_file.exists():
        print(f"\n[INFO] {map_file.name} no encontrado — sin fusión de accesiones")
        return df

    print(f"\n=== Aplicando {map_file.name} ===")
    with open(map_file, newline="", encoding="utf-8") as f:
        merges = {r["accesion_obsoleta"].strip(): r["accesion_vigente"].strip()
                  for r in _csv.DictReader(f)}

    afectadas = df["uniprot_id"].isin(merges)
    n = int(afectadas.sum())
    df.loc[afectadas, "uniprot_id"] = df.loc[afectadas, "uniprot_id"].map(merges)
    print(f"  {len(merges)} accesiones obsoletas, {n} filas reasignadas a su accesión vigente")
    return df


def _merge_evidence(values) -> str:
    """Union of PMIDs across duplicate rows, order preserved, NULL if none.

    Several sources emit one row per supporting publication for the same
    annotation (PhaSepDB's exports do it for every row), which is the same
    annotation cited N times, not N annotations. The documented interim
    contract is one row per annotation with the PMIDs semicolon-separated —
    exactly what DrLLPS and LLPSDB already produce — so nothing is lost by
    collapsing: every PMID survives in `evidence`.
    """
    seen: set[str] = set()
    pmids: list[str] = []
    for value in values:
        for pmid in str(value).split(";"):
            pmid = pmid.strip()
            if not pmid or pmid == NULL or pmid in seen:
                continue
            seen.add(pmid)
            pmids.append(pmid)
    return ";".join(pmids) if pmids else NULL


def _first_real(values) -> str:
    for value in values:
        value = str(value).strip()
        if value and value != NULL:
            return value
    return NULL


def collapse_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """One row per (uniprot_id, source_db, source_mlo, source_role).

    Applied uniformly to every source — no per-database special cases. The
    role stays in the key on purpose: a protein that is a driver of an MLO
    *and* a component of it carries two distinct pieces of evidence, and both
    rows are kept (see BIOLOGY.md, "Driver vs. Component").
    """
    before = len(df)
    df = (
        df.groupby(DEDUP_KEY, dropna=False, sort=False)
          .agg(evidence=("evidence", _merge_evidence), organism=("organism", _first_real))
          .reset_index()[INTERIM_COLS]
    )
    print(f"  {before} → {len(df)} filas ({before - len(df)} duplicadas colapsadas)")
    return df


def apply_mapping(df: pd.DataFrame, map_file: Path, source_col: str, unified_col: str) -> pd.DataFrame:
    # Use csv.reader to handle unquoted commas in later fields (only cols 0 and 1 are needed)
    lookup = {}
    if map_file.suffix == ".csv":
        with open(map_file, newline="", encoding="utf-8") as f:
            reader = _csv.reader(f)
            header = next(reader)
            for row in reader:
                if len(row) >= 2:
                    lookup[row[0]] = row[1]
    else:
        mapping = pd.read_csv(map_file, sep="\t", dtype=str, keep_default_na=False)
        mapping.columns = mapping.columns.str.strip()
        src, tgt = mapping.columns[0], mapping.columns[1]
        lookup = dict(zip(mapping[src], mapping[tgt]))

    df[unified_col] = df[source_col].map(lookup)
    n_unmapped = df[unified_col].isna().sum()
    if n_unmapped:
        print(f"  [WARN] {map_file.name}: {n_unmapped} filas sin cobertura → 'unmapped'")
        df[unified_col] = df[unified_col].fillna("unmapped")
    else:
        print(f"  {map_file.name}: cobertura completa")
    return df


def apply_organism_scoped(df: pd.DataFrame, map_file: Path) -> pd.DataFrame:
    """Redirect unified_mlo for source labels whose meaning depends on organism.

    mlo_mapping.csv maps a source name to exactly one canonical, which cannot
    express a label that denotes different structures in different clades.
    DrLLPS's 'Centrosome/Spindle pole body' is one: 775 of its 910 rows are
    human, mouse, Drosophila or C. elegans, none of which has a spindle pole
    body, yet all 910 landed on the fungal term and made the metazoan
    centrosome proteome disappear into it.

    mlo_mapping.csv still carries the default (the majority reading), and this
    step only overrides the rows whose organism matches. source_mlo is never
    rewritten — the DB keeps the label the source actually used.

    Known imprecision: the 12 Arabidopsis rows of this label fall through to
    the centrosome default, and plants are acentrosomal. The audit's rule only
    covers fungal vs. metazoan, and inventing a third destination would go
    past what the finding supports.
    """
    if not map_file.exists():
        print(f"\n[INFO] {map_file.name} no encontrado — sin overrides por organismo")
        return df

    print(f"\n=== Aplicando {map_file.name} ===")
    with open(map_file, newline="", encoding="utf-8") as f:
        rules = [
            (r["source_mlo"].strip(), r["organism_contains"].strip(), r["unified_mlo"].strip())
            for r in _csv.DictReader(f)
        ]

    for source_mlo, organism_contains, unified_mlo in rules:
        hit = (df["source_mlo"] == source_mlo) & df["organism"].str.contains(organism_contains, na=False)
        n = int(hit.sum())
        df.loc[hit, "unified_mlo"] = unified_mlo
        print(f"  {source_mlo!r} + organismo ~ {organism_contains!r} → {unified_mlo}: {n} filas")
        if not n:
            print(f"    [WARN] la regla no matcheó ninguna fila — ¿el nombre fuente cambió?")
    return df


def compute_role_and_active(source_db: str, source_role: str) -> tuple:
    """Map (source_db, source_role) -> (unified_role, dataset_active).

    Fixed per-source table from BIOLOGY.md ("Role assignment by source
    database" / "Driver/Client/Regulator scope"), not a generic lookup file
    — dataset_active depends on the (source_db, source_role) *combination*
    (e.g. DrLLPS+Regulator vs. DrLLPS+Client), which a flat source_role-only
    mapping (role_mapping.tsv) cannot express. role_mapping.tsv is kept in
    database/mappings/ for historical reference but is no longer read here.

    Returns unified_role as exactly 'driver', 'client', or None — never
    capitalized, never 'unmapped'.
    """
    role = (source_role or "").strip()

    # DrLLPS Regulator: served like any other annotation since 2026-08-12
    # (R1-ACT-14). It used to return dataset_active=0, which hid 1.389 rows and
    # made 501 proteins vanish from the dataset entirely — they had no other
    # active annotation. unified_role stays NULL because regulator is not a
    # driver/client claim; what identifies these rows is
    # evidence_type='curator_assignment' together with source_role='Regulator',
    # which is how the API buckets them (policy.regulator_annotation_clause).
    # Kept as an explicit branch rather than falling through to the [WARN]
    # default: the pair is recognized, and the reason it has no unified_role is
    # biological, not an unhandled case.
    if source_db == "DrLLPS" and role == "Regulator":
        return None, 1

    # CD-CODE has no structured role data at all — always NULL, still active.
    if source_db == "CDCODE":
        return None, 1

    role_lower = role.lower()
    if role_lower in ("client",):
        return "client", 1
    if role_lower in ("driver", "scaffold"):
        return "driver", 1

    # Anything else unrecognized: no role signal, but still part of the
    # dataset (mirrors the CD-CODE default) — log so it doesn't pass silently.
    print(f"  [WARN] unrecognized (source_db={source_db!r}, source_role={role!r}) — unified_role=NULL, dataset_active=1")
    return None, 1


EVIDENCE_TYPE = {
    # (source_db, source_role) -> evidence_type
    # Verified exhaustive and homogeneous per resource by the external audit
    # (docs/review/ultima/evidence_type_mapping.csv). Every combination present
    # in database/interim/*.tsv is listed; a new one raises the NULL count that
    # tests/test_dataset_invariants.py asserts is zero.
    ("LLPSDB",   "driver"):      "in_vitro_llps",
    ("PhasePro", "driver"):      "in_vitro_llps",
    ("PhaSepDB", "client"):      "cellular_localisation",
    ("PhaSepDB", "driver"):      "cellular_requirement",
    ("DrLLPS",   "Scaffold"):    "curator_assignment",
    ("DrLLPS",   "Client"):      "curator_assignment",
    ("DrLLPS",   "Regulator"):   "curator_assignment",
    ("CDCODE",   "NotInformed"): "membership_only",
}


def compute_evidence_type(source_db: str, source_role: str) -> str | None:
    """What kind of claim the row is making, independent of driver/client.

    `unified_role` collapses five vocabularies into two values, which hides that
    the underlying assertions are not comparable: a PhaSePro "driver" means a
    purified protein phase-separates in a buffer, while a PhaSepDB "driver"
    means perturbing it disrupts the condensate in cells. PhaSepDB and PhaSePro
    agree on only 58.6% of the annotations they share, and that 41% of
    disagreement is this difference, not curation noise — many proteins do the
    first and are clients in the second.

    Five values, not the three the audit first proposed, because PhaSepDB emits
    two different claims depending on the role:

    - `in_vitro_llps`         — purified protein phase-separates; no cellular claim
    - `cellular_localisation` — reported present in the condensate in cells
    - `cellular_requirement`  — perturbing it disrupts the condensate in cells
    - `curator_assignment`    — curator-assigned, and protein-scoped in DrLLPS:
                                the same label propagates to every MLO of that
                                protein, so it is not a per-compartment claim
    - `membership_only`       — the resource asserts membership and makes no role
                                claim at all

    `membership_only` is the one that changes how the data reads: it makes
    explicit that the 42% of rows with no role are CD-CODE's declared scope, not
    a gap in our ingestion.
    """
    evidence_type = EVIDENCE_TYPE.get((source_db, (source_role or "").strip()))
    if evidence_type is None:
        print(f"  [WARN] sin evidence_type para (source_db={source_db!r}, source_role={source_role!r})")
    return evidence_type


def main() -> None:
    print("=== Cargando archivos interim ===")
    df = load_interim()

    # ── Accesiones fusionadas ─────────────────────────────────────────────────
    # Antes del colapso: así las filas que quedan idénticas se unen solas.
    df = apply_uniprot_merges(df, MAP_DIR / "uniprot_merged.csv")

    # ── Deduplicación ─────────────────────────────────────────────────────────
    print("\n=== Colapsando filas duplicadas (uniprot_id, source_db, source_mlo, source_role) ===")
    df = collapse_duplicates(df)

    # ── Role + dataset_active ────────────────────────────────────────────────
    print(f"\n=== Calculando unified_role / dataset_active (tabla fija BIOLOGY.md) ===")
    role_active = df.apply(
        lambda r: compute_role_and_active(r["source_db"], r["source_role"]), axis=1
    )
    df["unified_role"] = role_active.map(lambda t: t[0])
    df["dataset_active"] = role_active.map(lambda t: t[1])

    print(f"\n=== Calculando evidence_type (tabla fija, ver compute_evidence_type) ===")
    df["evidence_type"] = df.apply(
        lambda r: compute_evidence_type(r["source_db"], r["source_role"]), axis=1
    )

    # ── MLO mapping ───────────────────────────────────────────────────────────
    mlo_map = MAP_DIR / "mlo_mapping.csv"
    if mlo_map.exists():
        print(f"\n=== Aplicando {mlo_map.name} ===")
        df = apply_mapping(df, mlo_map, "source_mlo", "unified_mlo")
    else:
        print(f"\n[INFO] {mlo_map.name} no encontrado — unified_mlo = 'unmapped'")
        df["unified_mlo"] = "unmapped"

    df = apply_organism_scoped(df, MAP_DIR / "mlo_organism_scoped.csv")

    # ── Orden final de columnas ───────────────────────────────────────────────
    final_cols = [
        "uniprot_id",
        "source_db",
        "source_mlo",
        "unified_mlo",
        "source_role",
        "unified_role",
        "evidence_type",
        "dataset_active",
        "evidence",
        "organism",
    ]
    df = df[final_cols]

    # ── Escribir output ───────────────────────────────────────────────────────
    df.to_csv(OUT, sep="\t", index=False)

    print(f"\n=== Dataset unificado escrito: {OUT} ===")
    print(f"  Filas totales:      {len(df):>7}")
    print(f"  UniProt únicos:     {df['uniprot_id'].nunique():>7}")
    print(f"\n  Filas por source_db:")
    print(df["source_db"].value_counts().to_string())
    print(f"\n  unified_mlo coverage:")
    unmapped_mlo = (df["unified_mlo"] == "unmapped").sum()
    print(f"    mapeadas:   {len(df) - unmapped_mlo:>7}  ({100*(len(df)-unmapped_mlo)/len(df):.1f}%)")
    print(f"    unmapped:   {unmapped_mlo:>7}  ({100*unmapped_mlo/len(df):.1f}%)")
    print(f"\n  unified_role breakdown (never 'unmapped', never capitalized):")
    print(df["unified_role"].fillna("NULL").value_counts().to_string())
    print(f"\n  evidence_type breakdown (nunca debe haber NULL):")
    print(df["evidence_type"].fillna("NULL").value_counts().to_string())
    print(f"\n  dataset_active breakdown:")
    print(df["dataset_active"].value_counts().to_string())


if __name__ == "__main__":
    main()
