"""
Parser for LLPSDB source files.

Inputs:
  database/raw/llpsdb_entries.csv
  database/raw/llpsdb_proteins.csv

Output:
  database/interim/llpsdb.tsv
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
    # --- Load entries ---
    path_e = RAW / "llpsdb_entries.csv"
    path_p = RAW / "llpsdb_proteins.csv"

    print(f"\n--- {path_e.name} ---")
    entries = pd.read_csv(path_e, dtype=str, keep_default_na=False)
    entries = _strip_all(entries)
    print("Columns:", list(entries.columns))
    print("First 2 rows (join-key columns):")
    print(entries[["PSID", "Protein ID", "PMID"]].head(2).to_string(index=False))
    print(f"Total rows loaded: {len(entries)}")

    print(f"\n--- {path_p.name} ---")
    proteins = pd.read_csv(path_p, dtype=str, keep_default_na=False)
    proteins = _strip_all(proteins)
    print("Columns:", list(proteins.columns))
    print("First 2 rows (join-key columns):")
    print(proteins[["PID", "Uniprot ID", "Species"]].head(2).to_string(index=False))
    print(f"Total rows loaded: {len(proteins)}")

    # --- Verify join key format ---
    entries_keys = entries["Protein ID"].dropna().unique()
    proteins_keys = proteins["PID"].dropna().unique()
    print(f"\nJoin key samples — entries['Protein ID']: {entries_keys[:5]}")
    print(f"Join key samples — proteins['PID']:        {proteins_keys[:5]}")

    # Some Protein IDs are compound (e.g. "p0001;p0226") — explode them so each
    # component can join individually to proteins.csv
    compound_mask = entries["Protein ID"].str.contains(";", na=False)
    n_compound = compound_mask.sum()
    if n_compound > 0:
        print(f"  [INFO] {n_compound} rows have compound Protein ID — exploding to individual IDs")
    entries = entries.copy()
    entries["Protein ID"] = entries["Protein ID"].apply(
        lambda x: [p.strip() for p in x.split(";")] if isinstance(x, str) else [x]
    )
    entries = entries.explode("Protein ID")

    # --- Join ---
    merged = entries.merge(
        proteins[["PID", "Uniprot ID", "Species"]],
        left_on="Protein ID",
        right_on="PID",
        how="inner",
    )
    print(f"\nRows after join: {len(merged)}")

    # --- Drop rows with missing uniprot_id ---
    mask_no_uid = merged["Uniprot ID"].isin(["", "_"])
    _log_drop("llpsdb", mask_no_uid.sum(), "missing uniprot_id")
    merged = merged[~mask_no_uid].copy()

    # --- Deduplicate by uniprot_id, collecting all PMIDs ---
    def collect_pmids(pmid_series):
        pmids = []
        for val in pmid_series:
            val = str(val).strip()
            if val and val not in ("", "NULL", "nan"):
                pmids.append(val)
        return ";".join(sorted(set(pmids))) if pmids else NULL

    deduped = (
        merged.groupby("Uniprot ID", sort=False)
        .agg(
            evidence=("PMID", collect_pmids),
            organism=("Species", "first"),
        )
        .reset_index()
        .rename(columns={"Uniprot ID": "uniprot_id"})
    )

    out = pd.DataFrame({
        "uniprot_id": deduped["uniprot_id"],
        "source_db":  "LLPSDB",
        "source_mlo": "in vitro droplet",
        "source_role": "driver",
        "evidence":   deduped["evidence"],
        "organism":   deduped["organism"].replace("", NULL),
    })

    out = out[COLUMNS].reset_index(drop=True)
    print(f"Rows produced (unique uniprot_id): {len(out)}")

    out_path = INTERIM / "llpsdb.tsv"
    out.to_csv(out_path, sep="\t", index=False)
    print(f"\n=== LLPSDB total rows written: {len(out)} → {out_path} ===")


if __name__ == "__main__":
    main()
