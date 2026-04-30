"""
integrate.py — Genera el dataset unificado de MLOsMetaDB.

Pasos:
  1. Concatena todos los archivos de database/interim/*.tsv
  2. Aplica role_mapping.tsv si está disponible
  3. Aplica mlo_mapping.tsv si está disponible
  4. Escribe database/mlosmetadb.tsv

Mientras los mappings no estén completos, las columnas unified_mlo
y unified_role quedan como "unmapped" para las filas sin cobertura.

Uso:
  python3 integrate.py
"""

import csv as _csv
from pathlib import Path
import pandas as pd

ROOT    = Path(__file__).resolve().parent
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



def main() -> None:
    print("=== Cargando archivos interim ===")
    df = load_interim()

    # ── Role mapping ──────────────────────────────────────────────────────────
    role_map = MAP_DIR / "role_mapping.tsv"
    if role_map.exists():
        print(f"\n=== Aplicando {role_map.name} ===")
        df = apply_mapping(df, role_map, "source_role", "unified_role")
    else:
        print(f"\n[INFO] {role_map.name} no encontrado — unified_role = 'unmapped'")
        df["unified_role"] = "unmapped"

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
    print(f"\n  unified_role coverage:")
    unmapped_rol = (df["unified_role"] == "unmapped").sum()
    print(f"    mapeadas:   {len(df) - unmapped_rol:>7}  ({100*(len(df)-unmapped_rol)/len(df):.1f}%)")
    print(f"    unmapped:   {unmapped_rol:>7}  ({100*unmapped_rol/len(df):.1f}%)")


if __name__ == "__main__":
    main()
