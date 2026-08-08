"""Tests for scripts/integrate.py's row-grain collapsing.

`collapse_duplicates()` is what enforces the dataset's row grain. It was added
after PhaSepDB turned out to be ingested twice (see
docs/issues/001-phasedb-phasepdb-duplicate-ingestion.md); before it, sources
that emit one row per supporting publication contributed one annotation row per
PMID, and nothing collapsed them.
"""

import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from integrate import INTERIM_COLS, collapse_duplicates


def _df(rows: list[tuple]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=INTERIM_COLS)


def test_identical_rows_collapse_to_one():
    out = collapse_duplicates(_df([
        ("P1", "PhaSepDB", "Nucleolus", "driver", "111", "Homo sapiens"),
        ("P1", "PhaSepDB", "Nucleolus", "driver", "111", "Homo sapiens"),
    ]))
    assert len(out) == 1
    assert out.iloc[0]["evidence"] == "111"


def test_one_row_per_pmid_becomes_one_row_with_every_pmid():
    """The shape both PhaSepDB exports emit: same annotation, N citations."""
    out = collapse_duplicates(_df([
        ("P1", "PhaSepDB", "Nucleolus", "driver", "111", "Homo sapiens"),
        ("P1", "PhaSepDB", "Nucleolus", "driver", "222", "Homo sapiens"),
        ("P1", "PhaSepDB", "Nucleolus", "driver", "333", "Homo sapiens"),
    ]))
    assert len(out) == 1
    assert out.iloc[0]["evidence"] == "111;222;333"


def test_driver_and_client_for_the_same_mlo_are_kept_as_two_rows():
    """The rule that makes the role part of the key.

    PhaSepDB publishes a driver dataset and an MLO-component dataset; a protein
    can be in both. Driving phase separation and being detected inside the
    condensate are two different observations, so neither row wins (see
    BIOLOGY.md, "Role assignment by source database").
    """
    out = collapse_duplicates(_df([
        ("P1", "PhaSepDB", "Nucleolus", "driver", "111", "Homo sapiens"),
        ("P1", "PhaSepDB", "Nucleolus", "client", "222", "Homo sapiens"),
    ]))
    assert len(out) == 2
    assert set(out["source_role"]) == {"driver", "client"}
    # and the two keep their own citations -- they are not pooled
    by_role = dict(zip(out["source_role"], out["evidence"]))
    assert by_role == {"driver": "111", "client": "222"}


def test_same_protein_and_mlo_from_two_sources_stays_two_rows():
    out = collapse_duplicates(_df([
        ("P1", "PhaSepDB", "Nucleolus", "driver", "111", "Homo sapiens"),
        ("P1", "DrLLPS", "Nucleolus", "driver", "222", "Homo sapiens"),
    ]))
    assert len(out) == 2


def test_pmid_lists_are_merged_and_deduplicated_in_first_seen_order():
    out = collapse_duplicates(_df([
        ("P1", "DrLLPS", "Nucleolus", "Scaffold", "111;222", "Homo sapiens"),
        ("P1", "DrLLPS", "Nucleolus", "Scaffold", "222;333", "Homo sapiens"),
    ]))
    assert out.iloc[0]["evidence"] == "111;222;333"


def test_null_evidence_is_dropped_when_a_real_pmid_exists():
    out = collapse_duplicates(_df([
        ("P1", "PhaSepDB", "Nucleolus", "driver", "NULL", "Homo sapiens"),
        ("P1", "PhaSepDB", "Nucleolus", "driver", "111", "Homo sapiens"),
    ]))
    assert out.iloc[0]["evidence"] == "111"


def test_null_evidence_survives_when_there_is_nothing_else():
    """CD-CODE's case: no per-annotation PMID at all."""
    out = collapse_duplicates(_df([
        ("P1", "CDCODE", "Nucleolus", "NULL", "NULL", "NULL"),
        ("P1", "CDCODE", "Nucleolus", "NULL", "NULL", "NULL"),
    ]))
    assert len(out) == 1
    assert out.iloc[0]["evidence"] == "NULL"


def test_organism_takes_the_first_real_value_over_null():
    out = collapse_duplicates(_df([
        ("P1", "PhaSepDB", "Nucleolus", "driver", "111", "NULL"),
        ("P1", "PhaSepDB", "Nucleolus", "driver", "222", "Homo sapiens"),
    ]))
    assert out.iloc[0]["organism"] == "Homo sapiens"


def test_no_pmid_is_ever_lost():
    """Property check: the union of PMIDs in must equal the union out."""
    rows = [("P1", "PhaSepDB", "Nucleolus", "driver", str(1000 + i), "Homo sapiens")
            for i in range(80)]
    out = collapse_duplicates(_df(rows))
    assert len(out) == 1
    assert set(out.iloc[0]["evidence"].split(";")) == {str(1000 + i) for i in range(80)}


def test_output_keeps_the_interim_column_contract():
    out = collapse_duplicates(_df([
        ("P1", "PhaSepDB", "Nucleolus", "driver", "111", "Homo sapiens"),
    ]))
    assert list(out.columns) == INTERIM_COLS


def test_collapsing_is_idempotent():
    once = collapse_duplicates(_df([
        ("P1", "PhaSepDB", "Nucleolus", "driver", "111", "Homo sapiens"),
        ("P1", "PhaSepDB", "Nucleolus", "driver", "222", "Homo sapiens"),
    ]))
    twice = collapse_duplicates(once)
    assert twice.to_dict("records") == once.to_dict("records")
