"""
Parser for PhasePro source file.

Input:
  database/raw/phasepro.tsv  (no header, positional columns)

Expected column positions (0-indexed):
  [2]  uniprot_id
  [3]  organism
  [10] pmid → evidence
  [14] mlo  (may be semicolon-separated → explode)

Output:
  database/interim/phasepro.tsv
"""

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "database" / "raw"
INTERIM = ROOT / "database" / "interim"

sys.path.insert(0, str(ROOT / "database"))
from schemas.intermediate import COLUMNS, NULL


def _log_drop(label: str, n: int, reason: str) -> None:
    if n > 0:
        print(f"  [DROP] {label}: {n} rows — {reason}")


def main() -> None:
    path = RAW / "phasepro.tsv"
    print(f"\n--- {path.name} ---")

    raw = pd.read_csv(path, sep="\t", header=None, dtype=str, keep_default_na=False)
    print(f"Number of columns: {len(raw.columns)}")
    print("\nFirst 2 rows with column indices:")
    for i, row in raw.head(2).iterrows():
        print(f"\nRow {i}:")
        for j in [2, 3, 10, 14]:
            print(f"  [{j}]: {repr(row[j])}")

    print(f"\nTotal rows loaded: {len(raw)}")

    df = raw.copy()

    # Rename relevant columns for clarity
    df = df.rename(columns={2: "uniprot_id", 3: "organism", 10: "pmid", 14: "mlo_raw"})

    # Strip whitespace
    for col in ["uniprot_id", "organism", "pmid", "mlo_raw"]:
        df[col] = df[col].str.strip()

    # Drop rows where uniprot_id is missing or empty
    mask_no_uid = df["uniprot_id"].isin(["", "_"])
    _log_drop("phasepro", mask_no_uid.sum(), "missing uniprot_id")
    df = df[~mask_no_uid].copy()

    # Fill empty mlo_raw with NotInformed (do NOT drop)
    mask_no_mlo = df["mlo_raw"].isin(["", "_"])
    if mask_no_mlo.sum() > 0:
        print(f"  [INFO] phasepro: {mask_no_mlo.sum()} rows with empty mlo column → 'NotInformed'")
    df.loc[mask_no_mlo, "mlo_raw"] = "NotInformed"

    # Explode mlo on "; "
    df["_mlo_list"] = df["mlo_raw"].apply(
        lambda x: [t.strip() for t in x.split(";") if t.strip()] if x != "NotInformed" else ["NotInformed"]
    )
    df = df.explode("_mlo_list").copy()
    df["_mlo_list"] = df["_mlo_list"].str.strip()

    # Fill empty tokens after explode with NotInformed (do NOT drop)
    mask_empty = df["_mlo_list"].isin(["", "_"])
    if mask_empty.sum() > 0:
        print(f"  [INFO] phasepro: {mask_empty.sum()} empty tokens after explode → 'NotInformed'")
    df.loc[mask_empty, "_mlo_list"] = "NotInformed"

    # Normalize evidence: the pmid column may contain parenthetical notes
    # e.g. "26474065 (research article), 29650703 (research article)"
    # → extract numeric PMID tokens only
    def _extract_pmids(val):
        import re
        val = str(val).strip()
        if not val or val == "NULL":
            return NULL
        pmids = re.findall(r'\b\d{7,9}\b', val)
        return ";".join(sorted(set(pmids))) if pmids else NULL

    df["evidence"] = df["pmid"].apply(_extract_pmids)
    df["organism"] = df["organism"].replace("", NULL)

    out = pd.DataFrame({
        "uniprot_id": df["uniprot_id"],
        "source_db":  "PhasePro",
        "source_mlo": df["_mlo_list"],
        "source_role": "driver",
        "evidence":   df["evidence"],
        "organism":   df["organism"],
    })

    out = out[COLUMNS].reset_index(drop=True)
    print(f"Rows produced: {len(out)}")

    out_path = INTERIM / "phasepro.tsv"
    out.to_csv(out_path, sep="\t", index=False)
    print(f"\n=== PhasePro total rows written: {len(out)} → {out_path} ===")


if __name__ == "__main__":
    main()
