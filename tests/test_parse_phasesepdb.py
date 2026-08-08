"""Tests for parsers/parse_phasesepdb.py.

Runs the parser against a hand-written subset of each input file, following the
project's test-before-batch rule: the behaviours asserted here are the ones a
full run is expected to reproduce at scale.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "parsers"))

import parse_phasesepdb as parser


DETAIL_HEADER = "Gene Name,UniProt ID,Organism,MLO,PubMed ID\n"
ENTRIES_HEADER = "uniprot_id\tmlo_normalized\tpmid\torganism\n"
SUMMARY_HEADER = "UniProt ID,MLO Types\n"


@pytest.fixture
def run_parser(tmp_path, monkeypatch):
    """Point the parser at a temp raw/ and interim/, return its output frame."""
    raw = tmp_path / "raw"
    interim = tmp_path / "interim"
    raw.mkdir()
    interim.mkdir()
    monkeypatch.setattr(parser, "RAW", raw)
    monkeypatch.setattr(parser, "INTERIM", interim)

    def _run(detail: str, entries: str, summary: str = ""):
        (raw / "phasedb_detail.csv").write_text(DETAIL_HEADER + detail)
        (raw / "phasedb_mlo_entries.tsv").write_text(ENTRIES_HEADER + entries)
        (raw / "phasepdb_summary_database_2026-03-20.csv").write_text(SUMMARY_HEADER + summary)
        parser.main()
        return pd.read_csv(interim / "phasesepdb.tsv", sep="\t",
                           dtype=str, keep_default_na=False)

    return _run


def test_every_row_is_tagged_phasepdb_once(run_parser):
    out = run_parser(
        detail="FUS,P35637,Homo sapiens,Nucleolus,111\n",
        entries="P35637\tStress granule\t222\tHomo sapiens\n",
    )
    assert set(out["source_db"]) == {"PhaSepDB"}
    assert parser.SOURCE_DB == "PhaSepDB"


def test_detail_rows_are_drivers_and_entries_rows_are_clients(run_parser):
    out = run_parser(
        detail="FUS,P35637,Homo sapiens,Nucleolus,111\n",
        entries="Q00001\tStress granule\t222\tHomo sapiens\n",
    )
    roles = dict(zip(out["uniprot_id"], out["source_role"]))
    assert roles == {"P35637": "driver", "Q00001": "client"}


def test_a_protein_in_both_datasets_keeps_both_rows(run_parser):
    """The exclusion the retired parse_phasepdb.py applied, and this one must not.

    Being a curated driver of an MLO and being detected as one of its
    components are two separate observations; dropping the second because the
    first exists discards real evidence.
    """
    out = run_parser(
        detail="FUS,P35637,Homo sapiens,Nucleolus,111\n",
        entries="P35637\tNucleolus\t222\tHomo sapiens\n",
    )
    rows = out[out["uniprot_id"] == "P35637"]
    assert len(rows) == 2
    assert set(rows["source_role"]) == {"driver", "client"}
    assert set(rows["evidence"]) == {"111", "222"}


def test_empty_mlo_falls_back_to_the_summary_export(run_parser):
    out = run_parser(
        detail="FUS,P35637,Homo sapiens,,111\n",
        entries="",
        summary="P35637,Stress granule\n",
    )
    assert list(out["source_mlo"]) == ["Stress granule"]


def test_empty_mlo_with_no_summary_entry_becomes_notinformed(run_parser):
    out = run_parser(
        detail="FUS,P35637,Homo sapiens,,111\n",
        entries="",
        summary="Q99999,Nucleolus\n",
    )
    assert list(out["source_mlo"]) == ["NotInformed"]


def test_empty_mlo_normalized_becomes_notinformed(run_parser):
    out = run_parser(detail="", entries="Q00001\t\t222\tHomo sapiens\n")
    assert list(out["source_mlo"]) == ["NotInformed"]


def test_compound_mlo_strings_explode_into_one_row_each(run_parser):
    out = run_parser(
        detail="FUS,P35637,Homo sapiens,Cajal body; Nucleolus,111\n",
        entries="",
    )
    assert sorted(out["source_mlo"]) == ["Cajal body", "Nucleolus"]
    # the PMID follows every exploded row
    assert set(out["evidence"]) == {"111"}


def test_summary_fallback_is_exploded_too(run_parser):
    out = run_parser(
        detail="FUS,P35637,Homo sapiens,,111\n",
        entries="",
        summary="P35637,Cajal body; Nucleolus\n",
    )
    assert sorted(out["source_mlo"]) == ["Cajal body", "Nucleolus"]


@pytest.mark.parametrize("bad_id", ["_", ""])
def test_rows_without_a_usable_uniprot_id_are_dropped(run_parser, bad_id):
    out = run_parser(
        detail=f"X,{bad_id},Homo sapiens,Nucleolus,111\n",
        entries=f"{bad_id}\tStress granule\t222\tHomo sapiens\n",
    )
    assert len(out) == 0


def test_a_missing_mlo_never_drops_the_row(run_parser):
    """BIOLOGY.md: NotInformed is a curated value, not a discard marker."""
    out = run_parser(detail="FUS,P35637,Homo sapiens,,\n", entries="")
    assert len(out) == 1
    assert out.iloc[0]["source_mlo"] == "NotInformed"


def test_missing_pmid_and_organism_become_the_null_sentinel(run_parser):
    out = run_parser(detail="FUS,P35637,,Nucleolus,\n", entries="")
    assert out.iloc[0]["evidence"] == parser.NULL
    assert out.iloc[0]["organism"] == parser.NULL


def test_output_matches_the_intermediate_column_contract(run_parser):
    out = run_parser(
        detail="FUS,P35637,Homo sapiens,Nucleolus,111\n",
        entries="",
    )
    assert list(out.columns) == parser.COLUMNS


def test_whitespace_is_stripped_from_every_field(run_parser):
    out = run_parser(
        detail="FUS, P35637 , Homo sapiens , Nucleolus , 111 \n",
        entries="",
    )
    row = out.iloc[0]
    assert row["uniprot_id"] == "P35637"
    assert row["source_mlo"] == "Nucleolus"
    assert row["organism"] == "Homo sapiens"
