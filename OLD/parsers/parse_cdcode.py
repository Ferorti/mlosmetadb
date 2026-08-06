"""
Parser for CDCODE source file.

Input:
  database/raw/cdcode_protein2condensate.tsv

Output:
  database/interim/cdcode.tsv
"""

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "database" / "raw"
INTERIM = ROOT / "database" / "interim"

sys.path.insert(0, str(ROOT / "database"))
from schemas.intermediate import COLUMNS, NULL


def _strip_all(df: pd.DataFrame) -> pd.DataFrame:
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].str.strip()
    return df


def _log_drop(label: str, n: int, reason: str) -> None:
    if n > 0:
        print(f"  [DROP] {label}: {n} rows — {reason}")


def main() -> None:
    path = RAW / "cdcode_protein2condensate.tsv"
    print(f"\n--- {path.name} ---")

    raw = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)
    raw = _strip_all(raw)

    print("Columns:", list(raw.columns))
    print("First 2 rows:")
    print(raw.head(2).to_string(index=False))
    print(f"Total rows loaded: {len(raw)}")

    df = raw.copy()

    # Drop rows where uniprot_id is missing or empty
    mask_no_uid = df["uniprotkb_ac"].isin(["", "_"])
    _log_drop("cdcode", mask_no_uid.sum(), "missing uniprot_id")
    df = df[~mask_no_uid].copy()

    # Fill empty condensate_name with NotInformed (do NOT drop)
    mask_no_mlo = df["condensate_name"].isin(["", "_"])
    if mask_no_mlo.sum() > 0:
        print(f"  [INFO] cdcode: {mask_no_mlo.sum()} rows with empty condensate_name → 'NotInformed'")
    df.loc[mask_no_mlo, "condensate_name"] = "NotInformed"

    out = pd.DataFrame({
        "uniprot_id": df["uniprotkb_ac"],
        "source_db":  "CDCODE",
        "source_mlo": df["condensate_name"],
        "source_role": "NotInformed",
        "evidence":   NULL,
        "organism":   NULL,
    })

    out = out[COLUMNS].reset_index(drop=True)
    print(f"Rows produced: {len(out)}")

    out_path = INTERIM / "cdcode.tsv"
    out.to_csv(out_path, sep="\t", index=False)
    print(f"\n=== CDCODE total rows written: {len(out)} → {out_path} ===")


if __name__ == "__main__":
    main()
