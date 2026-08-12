"""Shared serving policy for MLOsMetaDB.

Single source of truth for what counts as "active"/visible in the served
dataset, as distinct from the raw provenance data in mlosmetadb.db.
Imported by both refactor/api/ (live request-time queries) and
refactor/scripts/build_summary.py (materialized protein_summary
aggregation) so that a policy change only has to happen in one file.

Domain rule (see docs/superpowers/specs/2026-08-04-refactor-api-phase-design.md
and REFACTOR_LOG.md Entry 4/11): dataset_active=0 is reserved for
deliberate scope exclusions where inclusion is biologically debatable.
A NULL unified_role or indeterminate MLO name is an annotation gap, never a
reason to exclude -- those rows always stay dataset_active=1 and fully visible.

**No row is excluded today.** DrLLPS Regulator was the only case, and the
biological audit closed it against us (R1-ACT-14): hiding those 1.389 rows
removed 501 proteins from the dataset outright, because a regulator annotation
was the only one they had. They are served since 2026-08-12 with unified_role
still NULL -- see regulator_annotation_clause() for what identifies them now.
The mechanism stays because the rule it encodes is still the rule: if a future
exclusion is argued for, it goes here and gets a row in docs/review/findings.csv,
not a WHERE clause in a query file.
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


def regulator_annotation_clause(alias: str = "ma") -> str:
    """SQL boolean expression, true iff a row is a curator-assigned regulator
    annotation -- DrLLPS's third role, which the project does not model as a
    unified_role.

    The discriminator is (evidence_type, source_role) and not source_db,
    because what makes the row a regulator claim is the KIND of assertion
    (a curator assigned the label; nothing was measured about residency), not
    which resource happens to publish it. If a second resource starts emitting
    regulator calls, it matches this clause without an edit.

    unified_role stays NULL for these rows -- 'regulator' is not a driver/client
    verdict, and writing it into the stored column was the option the project
    rejected (see BIOLOGY.md "Driver/Client/Regulator scope"). This predicate
    is filtering, which is this module's job; turning it into a display bucket
    is the query layer's (mlo_queries.py::get_mlo_stats)."""
    return f"({alias}.evidence_type = 'curator_assignment' AND {alias}.source_role = 'Regulator')"


EXCLUDED_MLO_SPATIAL_LOCATIONS: list[str] = ["unspecified"]
"""mlo_vocabulary.spatial_location values excluded from /mlos listings by default.

Reversed 2026-08-05 (frontend-phase audit, see REFACTOR_LOG.md): 'NotInformed'
showing up as a browsable organelle in Home/MlosPage's "Membraneless organelles"
grid reads as if it were a real MLO, which it isn't -- it's a placeholder several
source DBs use when they don't specify a compartment. Until 2026-08-12 this list
held the category value 'Unspecified'; the four-axis migration (R1-ACT-06) turned
that into spatial_location='unspecified', which NotInformed is still the only term
carrying.

'unspecified' is a curated value and not a gap: it asserts that the term names an
absent localization. A term whose spatial axis was never determined would carry
NULL and would NOT be hidden by this clause -- keeping those two apart is the same
distinction policy.py draws between dataset_active=0 and a NULL unified_role.

This clause is wired ONLY into mlo_queries.py::get_all_mlos (the /mlos listing),
so scope is deliberately narrow: it doesn't touch protein_summary
(build_summary.py never calls excluded_mlo_spatial_clause) or a protein's own
mlo_annotations list (protein_queries.py doesn't call it either) -- a protein's
"MLO Annotations" tab still shows its NotInformed rows for full provenance,
only the top-level browse grids hide the term. Change this list -- and
api/CLAUDE.md's policy section -- if that scope should change; no query file
should hardcode axis-based filtering independently of this."""


def excluded_mlo_spatial_clause(alias: str = "mv") -> tuple[str | None, list[str]]:
    """Returns (sql_clause, params) for excluding EXCLUDED_MLO_SPATIAL_LOCATIONS,
    or (None, []) when there's nothing to exclude (not the case today --
    the list holds 'unspecified') -- callers must skip adding the clause
    entirely when it's None, rather than appending a dead 'AND 1=1'-style
    no-op to every query.

    NULL-safe by construction: `spatial_location NOT IN ('unspecified')` is NULL
    for a NULL axis, so the row drops out of the listing. That is not what we
    want -- a term with an undetermined axis is a gap, not a placeholder -- hence
    the explicit IS NULL arm."""
    if not EXCLUDED_MLO_SPATIAL_LOCATIONS:
        return None, []
    placeholders = ",".join("?" * len(EXCLUDED_MLO_SPATIAL_LOCATIONS))
    return (
        f"({alias}.spatial_location IS NULL OR {alias}.spatial_location NOT IN ({placeholders}))",
        list(EXCLUDED_MLO_SPATIAL_LOCATIONS),
    )


CANONICAL_SOURCE_NAMES: dict[str, str] = {
    "PhaSepDB": "PhaSepDB",
    "DrLLPS": "DrLLPS",
    "LLPSDB": "LLPSDB",
    "PhasePro": "PhaSePro",
    "CDCODE": "CD-CODE",
}
"""Maps raw mlo_annotations.source_db ingestion tags to the canonical
display name used everywhere a source database is shown or cited (About
page charts, Data Sources section, and the /proteins/citations endpoint).
"PhaSepDB" carries a lowercase 'p' before DB -- verified against the
database's own Nucleic Acids Research paper title -- see
docs/superpowers/specs/2026-08-06-about-page-design.md section 2.

This map used to carry two extra keys, "PhaseDB" and "PhasePDB", which were
two ingestion tags for this single resource. They were a naming mistake, not
two databases: both parsers read identical files, so every PhaSepDB
annotation was loaded twice and every count that grouped by the raw tag was
inflated. The tags are gone from the data (one parser, one tag "PhaSepDB")
and must not be reintroduced here -- a display-name patch is not a substitute
for ingesting a source once."""


def canonical_source_case_sql(column: str = "source_db") -> str:
    """SQL CASE expression mapping `column`'s raw value to its canonical
    display name (see CANONICAL_SOURCE_NAMES), for use in a SELECT/GROUP BY.
    Falls back to the raw value via ELSE for any tag not in the map."""
    whens = " ".join(f"WHEN '{raw}' THEN '{canon}'" for raw, canon in CANONICAL_SOURCE_NAMES.items())
    return f"CASE {column} {whens} ELSE {column} END"
