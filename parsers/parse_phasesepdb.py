"""
Parser for PhaSepDB, the project's single parser for this source.

PhaSepDB used to be ingested twice, by `parse_phasedb.py` (source_db
"PhaseDB") and `parse_phasepdb.py` (source_db "PhasePDB"), as if it were two
different resources. It never was: the two parsers read byte-identical copies
of the same two export files, so every PhaSepDB annotation was loaded twice
under two different names. This file replaces both of them; `PhaseDB` and
`PhasePDB` are retired tags and must not reappear as source_db values.

PhaSepDB publishes two datasets, and a protein can legitimately appear in
both — as a driver of one MLO and as a component of another, or of the same
one. Both annotations are kept, exactly as for every other source: the row
grain is (uniprot_id, source_db, source_mlo, source_role).

Inputs (all under database/raw/ — the filenames keep the historical
`phasedb_`/`phasepdb_` prefixes because raw/ is frozen, but all three are
PhaSepDB exports):
  phasedb_detail.csv                          → source_role = "driver" (fixed)
  phasedb_mlo_entries.tsv                     → source_role = "client" (fixed)
  phasepdb_summary_database_2026-03-20.csv    → fallback MLO names only

Output:
  database/interim/phasesepdb.tsv
"""

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "database" / "raw"
INTERIM = ROOT / "database" / "interim"

sys.path.insert(0, str(ROOT / "database"))
from schemas.intermediate import COLUMNS, NULL

SOURCE_DB = "PhaSepDB"


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


def _explode_mlo(df: pd.DataFrame) -> pd.DataFrame:
    """Split '; '-separated compound MLO strings into one row per MLO."""
    df["source_mlo"] = df["source_mlo"].str.split("; ")
    df = df.explode("source_mlo").reset_index(drop=True)
    df["source_mlo"] = df["source_mlo"].str.strip()
    return df


# ---------------------------------------------------------------------------
# Sub-parser 1: detail export — drivers
# ---------------------------------------------------------------------------

def _load_summary_mlo_types() -> dict[str, str]:
    """Return {UniProt ID → MLO Types} for proteins with a non-empty MLO Types
    field, used to recover an MLO name when the detail export leaves it blank."""
    path = RAW / "phasepdb_summary_database_2026-03-20.csv"
    summ = _strip_all(pd.read_csv(path, dtype=str, keep_default_na=False))
    has_mlo = summ[~summ["MLO Types"].isin(["", "_"])]
    return dict(zip(has_mlo["UniProt ID"], has_mlo["MLO Types"]))


def parse_detail() -> pd.DataFrame:
    path = RAW / "phasedb_detail.csv"
    print(f"\n--- {path.name} (drivers) ---")

    raw = _strip_all(pd.read_csv(path, dtype=str, keep_default_na=False))
    print("Columns:", list(raw.columns))
    print(f"Total rows loaded: {len(raw)}")

    summary_mlo = _load_summary_mlo_types()

    df = raw.copy()

    mask_no_uid = df["UniProt ID"].isin(["", "_"]) | df["UniProt ID"].isna()
    _log_drop("detail", mask_no_uid.sum(), "missing uniprot_id")
    df = df[~mask_no_uid].copy()

    # Empty MLO: fall back to the summary export's MLO Types, then NotInformed
    mask_no_mlo = df["MLO"].isin(["", "_"]) | df["MLO"].isna()
    df.loc[mask_no_mlo, "MLO"] = df.loc[mask_no_mlo, "UniProt ID"].map(summary_mlo).fillna("NotInformed")
    if mask_no_mlo.sum() > 0:
        n_notinformed = (mask_no_mlo & (df["MLO"] == "NotInformed")).sum()
        n_fallback = mask_no_mlo.sum() - n_notinformed
        print(f"  [INFO] {mask_no_mlo.sum()} rows with empty MLO: "
              f"{n_fallback} got the MLO Types fallback, {n_notinformed} → 'NotInformed'")

    out = pd.DataFrame({
        "uniprot_id":  df["UniProt ID"],
        "source_db":   SOURCE_DB,
        "source_mlo":  df["MLO"],
        "source_role": "driver",
        "evidence":    _normalize_evidence(df["PubMed ID"]),
        "organism":    df["Organism"].replace("", NULL),
    })

    out = _explode_mlo(out)[COLUMNS]
    print(f"Rows produced: {len(out)}")
    return out


# ---------------------------------------------------------------------------
# Sub-parser 2: mlo_entries export — components/clients
# ---------------------------------------------------------------------------

def parse_mlo_entries() -> pd.DataFrame:
    path = RAW / "phasedb_mlo_entries.tsv"
    print(f"\n--- {path.name} (clients) ---")

    raw = _strip_all(pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False))
    print("Columns:", list(raw.columns))
    print(f"Total rows loaded: {len(raw)}")

    df = raw.copy()

    mask_no_uid = df["uniprot_id"].isin(["", "_"]) | df["uniprot_id"].isna()
    _log_drop("mlo_entries", mask_no_uid.sum(), "missing/placeholder uniprot_id")
    df = df[~mask_no_uid].copy()

    # A protein already present in the detail export is NOT excluded here.
    # Being a driver of an MLO and being detected as one of its components are
    # two different experimental observations; both are kept, and the merge
    # rule in scripts/integrate.py is the same one every other source gets.
    mask_no_mlo = df["mlo_normalized"].isin(["", "_"]) | df["mlo_normalized"].isna()
    if mask_no_mlo.sum() > 0:
        print(f"  [INFO] {mask_no_mlo.sum()} rows with empty mlo_normalized → 'NotInformed'")
    df.loc[mask_no_mlo, "mlo_normalized"] = "NotInformed"

    out = pd.DataFrame({
        "uniprot_id":  df["uniprot_id"],
        "source_db":   SOURCE_DB,
        "source_mlo":  df["mlo_normalized"],
        "source_role": "client",
        "evidence":    _normalize_evidence(df["pmid"]),
        "organism":    df["organism"].replace("", NULL),
    })

    out = _explode_mlo(out)[COLUMNS]
    print(f"Rows produced: {len(out)}")
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    drivers = parse_detail()
    clients = parse_mlo_entries()

    combined = pd.concat([drivers, clients], ignore_index=True)

    out_path = INTERIM / "phasesepdb.tsv"
    combined.to_csv(out_path, sep="\t", index=False)

    print(f"\n=== {SOURCE_DB} total rows written: {len(combined)} → {out_path} ===")
    print(f"  Drivers (detail):        {len(drivers):>7}")
    print(f"  Clients (mlo_entries):   {len(clients):>7}")
    print(f"  UniProt únicos totales:  {combined['uniprot_id'].nunique():>7}")
    print("  Organisms:")
    print(combined["organism"].value_counts().head(5).to_string())


if __name__ == "__main__":
    main()
