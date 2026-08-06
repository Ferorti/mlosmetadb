"""
Parser for PhaseDB source files.

Inputs:
  database/raw/phasedb_mlo_entries.tsv  → source_role = "client" (fixed)
  database/raw/phasedb_detail.csv       → source_role = "driver" (fixed)

Output:
  database/interim/phasedb.tsv
"""

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "database" / "raw"
INTERIM = ROOT / "database" / "interim"

sys.path.insert(0, str(ROOT / "database"))
from schemas.intermediate import COLUMNS, NULL


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _strip_all(df: pd.DataFrame) -> pd.DataFrame:
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].str.strip()
    return df


def _log_drop(label: str, n: int, reason: str) -> None:
    if n > 0:
        print(f"  [DROP] {label}: {n} rows — {reason}")


def _normalize_evidence(series: pd.Series) -> pd.Series:
    """Normalise PMID columns to semicolon-separated strings or NULL."""
    return series.fillna(NULL).astype(str).str.strip().replace("", NULL)


# ---------------------------------------------------------------------------
# Sub-parser 1: phasedb_mlo_entries.tsv
# ---------------------------------------------------------------------------

def parse_mlo_entries() -> pd.DataFrame:
    path = RAW / "phasedb_mlo_entries.tsv"
    print(f"\n--- {path.name} ---")

    raw = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)
    raw = _strip_all(raw)

    print("Columns:", list(raw.columns))
    print("First 2 rows:")
    print(raw.head(2).to_string(index=False))
    print(f"Total rows loaded: {len(raw)}")

    df = raw.copy()

    # Drop rows where uniprot_id is missing, empty, or placeholder "_"
    mask_no_uid = df["uniprot_id"].isin(["", "_"]) | df["uniprot_id"].isna()
    _log_drop("mlo_entries", mask_no_uid.sum(), "missing/placeholder uniprot_id")
    df = df[~mask_no_uid].copy()

    # Fill empty mlo_normalized with NotInformed (do NOT drop)
    mask_no_mlo = df["mlo_normalized"].isin(["", "_"]) | df["mlo_normalized"].isna()
    if mask_no_mlo.sum() > 0:
        print(f"  [INFO] mlo_entries: {mask_no_mlo.sum()} rows with empty mlo_normalized → 'NotInformed'")
    df.loc[mask_no_mlo, "mlo_normalized"] = "NotInformed"

    out = pd.DataFrame({
        "uniprot_id": df["uniprot_id"],
        "source_db":  "PhaseDB",
        "source_mlo": df["mlo_normalized"],
        "source_role": "client",
        "evidence":   _normalize_evidence(df["pmid"]),
        "organism":   df["organism"].replace("", NULL),
    })

    # Explode multi-MLO rows ("; "-separated values in source_mlo)
    out["source_mlo"] = out["source_mlo"].str.split("; ")
    out = out.explode("source_mlo").reset_index(drop=True)
    out["source_mlo"] = out["source_mlo"].str.strip()

    out = out[COLUMNS]
    print(f"Rows produced: {len(out)}")
    return out


# ---------------------------------------------------------------------------
# Sub-parser 2: phasedb_detail.csv
# ---------------------------------------------------------------------------

def parse_detail() -> pd.DataFrame:
    path = RAW / "phasedb_detail.csv"
    print(f"\n--- {path.name} ---")

    raw = pd.read_csv(path, sep=",", dtype=str, keep_default_na=False)
    raw = _strip_all(raw)

    print("Columns:", list(raw.columns))
    print("First 2 rows:")
    print(raw.head(2).to_string(index=False))
    print(f"Total rows loaded: {len(raw)}")

    df = raw.copy()

    # Drop rows where UniProt ID is missing or empty
    mask_no_uid = df["UniProt ID"].isin(["", "_"]) | df["UniProt ID"].isna()
    _log_drop("detail", mask_no_uid.sum(), "missing uniprot_id")
    df = df[~mask_no_uid].copy()

    # Fill empty MLO with NotInformed (do NOT drop)
    mask_no_mlo = df["MLO"].isin(["", "_"]) | df["MLO"].isna()
    if mask_no_mlo.sum() > 0:
        print(f"  [INFO] detail: {mask_no_mlo.sum()} rows with empty MLO → 'NotInformed'")
    df.loc[mask_no_mlo, "MLO"] = "NotInformed"

    out = pd.DataFrame({
        "uniprot_id": df["UniProt ID"],
        "source_db":  "PhaseDB",
        "source_mlo": df["MLO"],
        "source_role": "driver",
        "evidence":   _normalize_evidence(df["PubMed ID"]),
        "organism":   df["Organism"].replace("", NULL),
    })

    # Explode multi-MLO rows ("; "-separated values in source_mlo)
    out["source_mlo"] = out["source_mlo"].str.split("; ")
    out = out.explode("source_mlo").reset_index(drop=True)
    out["source_mlo"] = out["source_mlo"].str.strip()

    out = out[COLUMNS]
    print(f"Rows produced: {len(out)}")
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    part1 = parse_mlo_entries()
    part2 = parse_detail()

    combined = pd.concat([part1, part2], ignore_index=True)

    out_path = INTERIM / "phasedb.tsv"
    combined.to_csv(out_path, sep="\t", index=False)

    print(f"\n=== PhaseDB total rows written: {len(combined)} → {out_path} ===")


if __name__ == "__main__":
    main()
