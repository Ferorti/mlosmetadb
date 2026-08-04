"""
Parser for PhasePDB source files.

Inputs:
  databases_input_data/phasepdb/phasepdb_summary_database_2026-03-20.csv
    → used as fallback: MLO Types field for proteins with empty MLO in detail
  databases_input_data/phasepdb/phasepdb_detail_database_2026-03-20.csv
    → one row per (protein, MLO); all proteins phase-separate → source_role = "driver"
  databases_input_data/phasepdb/phasepdb_mlo_entries_from_script.tsv
    → high-throughput screen entries; proteins NOT in detail → source_role = "client"

Output:
  database/interim/phasepdb.tsv
"""

import sys
from pathlib import Path

import pandas as pd

ROOT    = Path(__file__).resolve().parents[1]
DBI     = ROOT / "database" / "databases_input_data" / "phasepdb"
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


def _normalize_evidence(series: pd.Series) -> pd.Series:
    return series.fillna(NULL).astype(str).str.strip().replace("", NULL)


# ---------------------------------------------------------------------------
# Sub-parser 1: phasepdb_detail (drivers)
# ---------------------------------------------------------------------------

def _load_summary_mlo_types() -> dict[str, str]:
    """Return {UniProt ID → MLO Types} for proteins that have a non-empty MLO Types field."""
    path = DBI / "phasepdb_summary_database_2026-03-20.csv"
    summ = pd.read_csv(path, dtype=str, keep_default_na=False)
    summ = _strip_all(summ)
    has_mlo = summ[~summ["MLO Types"].isin(["", "_"])]
    return dict(zip(has_mlo["UniProt ID"], has_mlo["MLO Types"]))


def parse_detail() -> pd.DataFrame:
    path = DBI / "phasepdb_detail_database_2026-03-20.csv"
    print(f"\n--- {path.name} ---")

    raw = pd.read_csv(path, dtype=str, keep_default_na=False)
    raw = _strip_all(raw)
    print(f"Total rows loaded: {len(raw)}")

    # Build summary MLO Types fallback for proteins with empty MLO in detail
    summary_mlo = _load_summary_mlo_types()

    df = raw.copy()

    mask_no_uid = df["UniProt ID"].isin(["", "_"]) | df["UniProt ID"].isna()
    _log_drop("detail", mask_no_uid.sum(), "missing uniprot_id")
    df = df[~mask_no_uid].copy()

    mask_no_mlo = df["MLO"].isin(["", "_"]) | df["MLO"].isna()
    # Use summary MLO Types as fallback; remaining empties → NotInformed
    df.loc[mask_no_mlo, "MLO"] = df.loc[mask_no_mlo, "UniProt ID"].map(summary_mlo).fillna("NotInformed")
    n_fallback = (mask_no_mlo & df["MLO"].isin(summary_mlo.values())).sum()
    n_notinformed = (mask_no_mlo & (df["MLO"] == "NotInformed")).sum()
    if mask_no_mlo.sum() > 0:
        print(f"  [INFO] {mask_no_mlo.sum()} rows with empty MLO: {n_fallback} got MLO Types fallback, {n_notinformed} → 'NotInformed'")

    out = pd.DataFrame({
        "uniprot_id":  df["UniProt ID"],
        "source_db":   "PhasePDB",
        "source_mlo":  df["MLO"],
        "source_role": "driver",
        "evidence":    _normalize_evidence(df["PubMed ID"]),
        "organism":    df["Organism"].replace("", NULL),
    })

    # Explode compound MLO strings ("Cajal body; Nucleolus" → two rows)
    out["source_mlo"] = out["source_mlo"].str.split("; ")
    out = out.explode("source_mlo").reset_index(drop=True)
    out["source_mlo"] = out["source_mlo"].str.strip()

    out = out[COLUMNS]
    print(f"Rows produced: {len(out)}")
    return out


# ---------------------------------------------------------------------------
# Sub-parser 2: phasepdb_mlo_entries (clients only — proteins not in detail)
# ---------------------------------------------------------------------------

def parse_mlo_entries(detail_ids: set) -> pd.DataFrame:
    path = DBI / "phasepdb_mlo_entries_from_script.tsv"
    print(f"\n--- {path.name} ---")

    raw = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)
    raw = _strip_all(raw)
    print(f"Total rows loaded: {len(raw)}")

    df = raw.copy()

    mask_no_uid = df["uniprot_id"].isin(["", "_"]) | df["uniprot_id"].isna()
    _log_drop("mlo_entries", mask_no_uid.sum(), "missing/placeholder uniprot_id")
    df = df[~mask_no_uid].copy()

    # Keep only proteins NOT already in the detail file (avoid duplicates)
    mask_client = ~df["uniprot_id"].isin(detail_ids)
    n_skipped = (~mask_client).sum()
    if n_skipped > 0:
        print(f"  [SKIP] {n_skipped} rows already annotated in detail → excluded")
    df = df[mask_client].copy()

    mask_no_mlo = df["mlo_normalized"].isin(["", "_"]) | df["mlo_normalized"].isna()
    if mask_no_mlo.sum() > 0:
        print(f"  [INFO] {mask_no_mlo.sum()} rows with empty mlo_normalized → 'NotInformed'")
    df.loc[mask_no_mlo, "mlo_normalized"] = "NotInformed"

    out = pd.DataFrame({
        "uniprot_id":  df["uniprot_id"],
        "source_db":   "PhasePDB",
        "source_mlo":  df["mlo_normalized"],
        "source_role": "client",
        "evidence":    _normalize_evidence(df.get("pmid", pd.Series(NULL, index=df.index))),
        "organism":    df["organism"].replace("", NULL),
    })

    # Explode compound MLO strings in mlo_normalized (rare but possible)
    out["source_mlo"] = out["source_mlo"].str.split("; ")
    out = out.explode("source_mlo").reset_index(drop=True)
    out["source_mlo"] = out["source_mlo"].str.strip()

    out = out[COLUMNS]
    print(f"Rows produced (clients only): {len(out)}")
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    part1 = parse_detail()
    detail_ids = set(part1["uniprot_id"].unique())

    part2 = parse_mlo_entries(detail_ids)

    combined = pd.concat([part1, part2], ignore_index=True)

    out_path = INTERIM / "phasepdb.tsv"
    combined.to_csv(out_path, sep="\t", index=False)

    print(f"\n=== PhasePDB total rows written: {len(combined)} → {out_path} ===")
    print(f"  Drivers (detail):         {len(part1):>7}")
    print(f"  Clients (mlo_entries):    {len(part2):>7}")
    print(f"  UniProt únicos totales:   {combined['uniprot_id'].nunique():>7}")
    print(f"  Organisms:")
    print(combined["organism"].value_counts().head(5).to_string())


if __name__ == "__main__":
    main()
