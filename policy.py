"""Shared serving policy for MLOsMetaDB.

Single source of truth for what counts as "active"/visible in the served
dataset, as distinct from the raw provenance data in mlosmetadb.db.
Imported by both refactor/api/ (live request-time queries) and
refactor/scripts/build_summary.py (materialized protein_summary
aggregation) so that a policy change only has to happen in one file.

Domain rule (see docs/superpowers/specs/2026-08-04-refactor-api-phase-design.md
and REFACTOR_LOG.md Entry 4/11): dataset_active=0 is reserved for
deliberate scope exclusions where inclusion is biologically debatable
(today: DrLLPS Regulator rows). A NULL unified_role or indeterminate MLO
name is an annotation gap, never a reason to exclude -- those rows always
stay dataset_active=1 and fully visible.
"""


def active_annotation_clause(alias: str = "ma") -> str:
    """SQL boolean expression, true iff an mlo_annotations row counts
    toward the served/default dataset. Use as a JOIN ON condition or a
    WHERE conjunct wherever mlo_annotations is queried."""
    return f"{alias}.dataset_active = 1"


def component_role_clause(alias: str = "ma") -> str:
    """SQL boolean expression for the `role=component` filter: true for
    every row that isn't a driver, INCLUDING NULL-role rows (CD-CODE and
    any other annotation gap). `NULL != 'driver'` evaluates to NULL (not
    true) in SQL, so a plain `!= 'driver'` silently drops NULL rows --
    this is the fix for that. "Component" means "not a driver," matching
    the frontend's existing description of this bucket (see
    frontend/src/components/browse/RoleCards.vue)."""
    return f"({alias}.unified_role IS NULL OR LOWER({alias}.unified_role) != 'driver')"


EXCLUDED_MLO_CATEGORIES: list[str] = ["Unspecified"]
"""mlo_vocabulary.category values excluded from /mlos listings by default.

Reversed 2026-08-05 (frontend-phase audit, see REFACTOR_LOG.md): 'NotInformed'
(category='Unspecified') showing up as a browsable organelle in Home/MlosPage's
"Membraneless organelles" grid reads as if it were a real MLO, which it isn't --
it's a placeholder several source DBs use when they don't specify a compartment.
This clause is wired ONLY into mlo_queries.py::get_all_mlos (the /mlos listing),
so scope is deliberately narrow: it doesn't touch protein_summary
(build_summary.py never calls excluded_mlo_category_clause) or a protein's own
mlo_annotations list (protein_queries.py doesn't call it either) -- a protein's
"MLO Annotations" tab still shows its NotInformed rows for full provenance,
only the top-level browse grids hide the category. Change this list --
and refactor/api/CLAUDE.md's policy section -- if that scope should change; no
query file should hardcode category-based filtering independently of this."""


def excluded_mlo_category_clause(alias: str = "mv") -> tuple[str | None, list[str]]:
    """Returns (sql_clause, params) for excluding EXCLUDED_MLO_CATEGORIES,
    or (None, []) when there's nothing to exclude (not the case today --
    the list holds 'Unspecified' since 2026-08-05) -- callers must skip
    adding the clause entirely when it's None, rather
    than appending a dead 'AND 1=1'-style no-op to every query."""
    if not EXCLUDED_MLO_CATEGORIES:
        return None, []
    placeholders = ",".join("?" * len(EXCLUDED_MLO_CATEGORIES))
    return f"{alias}.category NOT IN ({placeholders})", list(EXCLUDED_MLO_CATEGORIES)


CANONICAL_SOURCE_NAMES: dict[str, str] = {
    "PhaseDB": "PhaSePDB",
    "PhasePDB": "PhaSePDB",
    "DrLLPS": "DrLLPS",
    "LLPSDB": "LLPSDB",
    "PhasePro": "PhaSePro",
    "CDCODE": "CD-CODE",
}
"""Maps raw mlo_annotations.source_db ingestion tags to the canonical
display name used everywhere a source database is shown or cited (About
page charts, Data Origin cards, and the /proteins/citations endpoint).
PhaseDB and PhasePDB are two ingestion tags for the same real-world
database (PhaSePDB) -- see
docs/superpowers/specs/2026-08-06-about-page-design.md section 2."""


def canonical_source_case_sql(column: str = "source_db") -> str:
    """SQL CASE expression mapping `column`'s raw value to its canonical
    display name (see CANONICAL_SOURCE_NAMES), for use in a SELECT/GROUP BY.
    Falls back to the raw value via ELSE for any tag not in the map."""
    whens = " ".join(f"WHEN '{raw}' THEN '{canon}'" for raw, canon in CANONICAL_SOURCE_NAMES.items())
    return f"CASE {column} {whens} ELSE {column} END"
