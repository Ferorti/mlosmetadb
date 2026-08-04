"""
integrate.py — Genera el dataset unificado de MLOsMetaDB.

Pasos:
  1. Concatena todos los archivos de database/interim/*.tsv
  2. Calcula unified_role + dataset_active por fila, según la tabla fija
     source_db/source_role documentada en BIOLOGY.md (no via role_mapping.tsv
     — ver compute_role_and_active() más abajo)
  3. Aplica mlo_mapping.tsv (source_mlo → unified_mlo) si está disponible
  4. Escribe database/mlosmetadb.tsv

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

    # DrLLPS Regulator: stays in mlo_annotations (never dropped), but excluded
    # from the served/counted dataset by default.
    if source_db == "DrLLPS" and role == "Regulator":
        return None, 0

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


def main() -> None:
    print("=== Cargando archivos interim ===")
    df = load_interim()

    # ── Role + dataset_active ────────────────────────────────────────────────
    print(f"\n=== Calculando unified_role / dataset_active (tabla fija BIOLOGY.md) ===")
    role_active = df.apply(
        lambda r: compute_role_and_active(r["source_db"], r["source_role"]), axis=1
    )
    df["unified_role"] = role_active.map(lambda t: t[0])
    df["dataset_active"] = role_active.map(lambda t: t[1])

    # ── MLO mapping ───────────────────────────────────────────────────────────
    mlo_map = MAP_DIR / "mlo_mapping.csv"
    if mlo_map.exists():
        print(f"\n=== Aplicando {mlo_map.name} ===")
        df = apply_mapping(df, mlo_map, "source_mlo", "unified_mlo")
    else:
        print(f"\n[INFO] {mlo_map.name} no encontrado — unified_mlo = 'unmapped'")
        df["unified_mlo"] = "unmapped"

    # ── Orden final de columnas ───────────────────────────────────────────────
    final_cols = [
        "uniprot_id",
        "source_db",
        "source_mlo",
        "unified_mlo",
        "source_role",
        "unified_role",
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
    print(f"\n  dataset_active breakdown:")
    print(df["dataset_active"].value_counts().to_string())


if __name__ == "__main__":
    main()
