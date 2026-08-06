"""
Parser for DrLLPS source file.

Input:
  database/raw/drllps_llps.tsv

Output:
  database/interim/drllps.tsv
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


def _normalize_references(series: pd.Series) -> pd.Series:
    """Normalize comma-separated PMIDs to semicolon-separated strings."""
    def _fix(val):
        if pd.isna(val) or str(val).strip() == "":
            return NULL
        parts = [p.strip() for p in str(val).replace(";", ",").split(",") if p.strip()]
        return ";".join(parts) if parts else NULL
    return series.apply(_fix)


def main() -> None:
    path = RAW / "drllps_llps.tsv"
    print(f"\n--- {path.name} ---")

    raw = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)
    raw = _strip_all(raw)

    print("Columns:", list(raw.columns))
    print("First 2 rows:")
    print(raw[["DrLLPS ID", "UniProt ID", "Species", "Condensate", "LLPS Type", "References"]].head(2).to_string(index=False))
    print(f"Total rows loaded: {len(raw)}")

    df = raw.copy()

    # Drop rows where UniProt ID is missing or empty
    mask_no_uid = df["UniProt ID"].isin(["", "_"])
    _log_drop("drllps", mask_no_uid.sum(), "missing uniprot_id")
    df = df[~mask_no_uid].copy()

    # Explode Condensate on ", "
    df["_mlo_list"] = df["Condensate"].apply(
        lambda x: [t.strip() for t in x.split(",") if t.strip()] if x else []
    )
    df = df.explode("_mlo_list").copy()
    df["_mlo_list"] = df["_mlo_list"].str.strip()

    # Map "Droplet" → "in vitro droplet"
    df.loc[df["_mlo_list"] == "Droplet", "_mlo_list"] = "in vitro droplet"

    # Keep "Others" and all other tokens as-is (do NOT drop)

    # Fill empty tokens after explode with NotInformed (do NOT drop)
    mask_no_mlo = df["_mlo_list"].isin(["", "_"])
    if mask_no_mlo.sum() > 0:
        print(f"  [INFO] drllps: {mask_no_mlo.sum()} empty tokens after explode → 'NotInformed'")
    df.loc[mask_no_mlo, "_mlo_list"] = "NotInformed"

    out = pd.DataFrame({
        "uniprot_id": df["UniProt ID"],
        "source_db":  "DrLLPS",
        "source_mlo": df["_mlo_list"],
        "source_role": df["LLPS Type"].replace("", NULL),
        "evidence":   _normalize_references(df["References"]),
        "organism":   df["Species"].replace("", NULL),
    })

    out = out[COLUMNS].reset_index(drop=True)
    print(f"Rows produced: {len(out)}")

    out_path = INTERIM / "drllps.tsv"
    out.to_csv(out_path, sep="\t", index=False)
    print(f"\n=== DrLLPS total rows written: {len(out)} → {out_path} ===")


if __name__ == "__main__":
    main()
