import sys
from pathlib import Path

REFACTOR_ROOT = Path(__file__).resolve().parent.parent
if str(REFACTOR_ROOT) not in sys.path:
    sys.path.insert(0, str(REFACTOR_ROOT))

from policy import (
    EXCLUDED_MLO_CATEGORIES,
    active_annotation_clause,
    excluded_mlo_category_clause,
)


def test_active_annotation_clause_default_alias():
    assert active_annotation_clause() == "ma.dataset_active = 1"


def test_active_annotation_clause_custom_alias():
    assert active_annotation_clause("x") == "x.dataset_active = 1"
    assert active_annotation_clause("ma2") == "ma2.dataset_active = 1"


def test_excluded_mlo_categories_empty_by_default():
    assert EXCLUDED_MLO_CATEGORIES == []


def test_excluded_mlo_category_clause_is_noop_by_default():
    clause, params = excluded_mlo_category_clause("mv")
    assert clause is None
    assert params == []


def test_excluded_mlo_category_clause_when_configured(monkeypatch):
    monkeypatch.setattr("policy.EXCLUDED_MLO_CATEGORIES", ["Unspecified"])
    clause, params = excluded_mlo_category_clause("mv")
    assert clause == "mv.category NOT IN (?)"
    assert params == ["Unspecified"]
