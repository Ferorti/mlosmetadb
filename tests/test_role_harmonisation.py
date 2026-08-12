"""Anti-drift test for database/mappings/role_harmonisation.csv.

This file exists so build_unification_stats.py has a single place to look up
`category` (driver/regulator/component) per (source_db, source_role) without
integrate.py having to be restructured around a lookup table it architecturally
can't use (dataset_active depends on the source_db+source_role combination, not
source_role alone — see scripts/CLAUDE.md). This test is the guarantee that the
CSV and integrate.py's compute_role_and_active()/compute_evidence_type() never
drift apart, and that the CSV covers exactly the pairs integrate.py recognizes.
"""

import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from integrate import EVIDENCE_TYPE, compute_evidence_type, compute_role_and_active

CSV_PATH = REPO_ROOT / "database" / "mappings" / "role_harmonisation.csv"


def _load_rows() -> list[dict]:
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _expected_category(source_db: str, source_role: str, unified_role: str | None) -> str:
    if unified_role == "driver":
        return "driver"
    if source_db == "DrLLPS" and source_role == "Regulator":
        return "regulator"
    return "component"


def test_csv_has_exactly_eight_rows():
    rows = _load_rows()
    assert len(rows) == 8


def test_pair_set_matches_integrate_evidence_type_exactly():
    csv_pairs = {(r["source_db"], r["source_role"]) for r in _load_rows()}
    assert csv_pairs == set(EVIDENCE_TYPE.keys())


def test_each_row_matches_integrate_functions():
    for row in _load_rows():
        source_db = row["source_db"]
        source_role = row["source_role"]

        expected_unified_role, _ = compute_role_and_active(source_db, source_role)
        csv_unified_role = None if row["unified_role"] == "NULL" else row["unified_role"]
        assert csv_unified_role == expected_unified_role, (
            f"{source_db}/{source_role}: csv unified_role={csv_unified_role!r} "
            f"!= compute_role_and_active={expected_unified_role!r}"
        )

        expected_evidence_type = compute_evidence_type(source_db, source_role)
        assert row["evidence_type"] == expected_evidence_type, (
            f"{source_db}/{source_role}: csv evidence_type={row['evidence_type']!r} "
            f"!= compute_evidence_type={expected_evidence_type!r}"
        )

        expected_category = _expected_category(source_db, source_role, expected_unified_role)
        assert row["category"] == expected_category, (
            f"{source_db}/{source_role}: csv category={row['category']!r} "
            f"!= expected={expected_category!r}"
        )
        assert row["category"] in ("driver", "regulator", "component")
