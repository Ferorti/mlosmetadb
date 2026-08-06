import sys
from pathlib import Path

REFACTOR_ROOT = Path(__file__).resolve().parent.parent
if str(REFACTOR_ROOT) not in sys.path:
    sys.path.insert(0, str(REFACTOR_ROOT))

from policy import (
    EXCLUDED_MLO_CATEGORIES,
    active_annotation_clause,
    component_role_clause,
    excluded_mlo_category_clause,
)


def test_active_annotation_clause_default_alias():
    assert active_annotation_clause() == "ma.dataset_active = 1"


def test_active_annotation_clause_custom_alias():
    assert active_annotation_clause("x") == "x.dataset_active = 1"
    assert active_annotation_clause("ma2") == "ma2.dataset_active = 1"


def test_excluded_mlo_categories_excludes_unspecified_by_default():
    # Reversed 2026-08-05 (frontend-phase audit, commit e799f6a, REFACTOR_LOG.md
    # Entry 14): 'NotInformed' (category='Unspecified') was leaking into the
    # /mlos browse grid as if it were a real organelle. Was [] through the api/
    # phase (Entry 11) -- see policy.py's own docstring for the full rationale.
    assert EXCLUDED_MLO_CATEGORIES == ["Unspecified"]


def test_excluded_mlo_category_clause_excludes_unspecified_by_default():
    clause, params = excluded_mlo_category_clause("mv")
    assert clause == "mv.category NOT IN (?)"
    assert params == ["Unspecified"]


def test_excluded_mlo_category_clause_is_noop_when_empty(monkeypatch):
    monkeypatch.setattr("policy.EXCLUDED_MLO_CATEGORIES", [])
    clause, params = excluded_mlo_category_clause("mv")
    assert clause is None
    assert params == []


def test_component_role_clause_default_alias():
    assert (
        component_role_clause()
        == "(ma.unified_role IS NULL OR LOWER(ma.unified_role) != 'driver')"
    )


def test_component_role_clause_custom_alias():
    assert (
        component_role_clause("x")
        == "(x.unified_role IS NULL OR LOWER(x.unified_role) != 'driver')"
    )
