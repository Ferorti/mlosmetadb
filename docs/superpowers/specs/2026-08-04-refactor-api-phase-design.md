# Design: `api/` phase of the MLOsMetaDB refactor

Status: approved by user, pending write of implementation plan.
Related: `refactor/REFACTOR_LOG.md` (data-layer phase, Entries 0-10), `BIOLOGY.md`, `SCHEMA.md`, `refactor/CLAUDE.md`.

## Context

`refactor/` is being built as the future clean root of MLOsMetaDB, migrated
incrementally out of the audited old repo layout. The data-layer phase
(`database/` + `scripts/` + `parsers/`) is complete and verified (see
`REFACTOR_LOG.md` Entries 0-10). This spec covers the next phase: `api/`.

Unlike the data-layer phase, this is **not a build-from-scratch phase**.
A full, working FastAPI backend already exists at the repo root (`api/`):
`main.py`, `config.py`, `database.py`, `models/`, `queries/`, `routers/`
(`mlos.py`, `organisms.py`, `proteins.py`, `search.py`, `stats.py`), backed
by 10 endpoints, an in-memory SQLite load pattern (source DB lives on
BeeGFS, high random-I/O latency), FTS5 search with LIKE fallback, and a
uniform error envelope. It currently points at `database/mlosmetadb.db`
(the old, uncorrected DB).

The problem is **schema drift**: the corrected DB built during the
data-layer phase (`refactor/database/mlosmetadb.db`) changed
`mlo_annotations.unified_role` from inconsistent `'Driver'`/`'Client'`/
`'unmapped'` values to clean `'driver'`/`'client'`/`NULL`, and added a
`dataset_active` column that the existing API code has never seen or
filtered on.

## Scope decision

Port the existing `api/` code into `refactor/api/` as-is (same directory
structure, same endpoints, same query/router/model separation), applying
targeted fixes for schema drift, then update docs to reflect the corrected
end state. This is **not** a rewrite — the existing separation of concerns
is sound and a rewrite is not justified by the actual problem (data drift,
not architectural rot).

## Domain rule governing all fixes (clarified by user during this design)

This is the rule every fix below must respect:

- **`dataset_active=0`** is reserved *only* for deliberate scope exclusions
  where inclusion is biologically debatable. Today this means exactly one
  case: DrLLPS Regulator rows (proteins not necessarily MLO-resident). Kept
  in the DB for full provenance, excluded from what's served/counted by
  default.
- **`NULL` `unified_role` or indeterminate/`NULL` MLO name is an annotation
  gap** — data not available or not known — **never** a decision to
  exclude. These rows must always stay `dataset_active=1` and remain in the
  served dataset, displayed with no role badge (per `frontend/CLAUDE.md`'s
  existing contract: `unified_role: null → no role badge`), never dropped
  from the DB or hidden from results.

Concretely: CD-CODE rows (`unified_role=NULL`, `dataset_active=1`) are
annotation gaps and stay fully visible. DrLLPS Regulator rows
(`unified_role=NULL`, `dataset_active=0`) are a scope exclusion and are
filtered out of served results, while remaining queryable in the raw DB for
provenance.

## Findings from auditing the existing `api/` code (not just docs)

Confirmed by direct code reading and live SQLite inspection of both DBs
(old `database/mlosmetadb.db` vs. new `refactor/database/mlosmetadb.db`):

1. **`dataset_active` is never referenced anywhere in `api/`** (`grep -rn
   "dataset_active" api/` → zero hits). Once pointed at the new DB, every
   endpoint touching `mlo_annotations` will silently include the 1,390
   `dataset_active=0` (DrLLPS Regulator) rows that should be excluded by
   default: `/protein/{id}` annotations, `/proteins` role/mlo/source_db
   filters and facets, `/mlo/{id}` stats and protein list, `/mlos` counts,
   `/search/advanced` filters, `/stats` aggregates.

2. **`_normalize_role()` actively produces wrong output against the new
   schema**, not just stale behavior. Duplicated in
   `api/routers/mlos.py:32` and `api/routers/proteins.py:113`:
   ```python
   _COMPONENT_ROLES = {"client", "unknown", "unmapped"}
   def _normalize_role(role):
       return "component" if role and role.lower() in _COMPONENT_ROLES else role
   ```
   Against the new DB this collapses `'client'` → `'component'` in the
   `unified_role` field returned to the frontend — but
   `frontend/CLAUDE.md`'s already-live contract expects a real `'client'`
   value (renders a green badge via `RoleBadge.vue`). This function must be
   **deleted**, not patched — raw passthrough (`'driver'`/`'client'`/
   `None`) is what the frontend actually wants. Confirmed via
   `grep -rn "unified_role\|component" frontend/src` that the frontend
   derives its own "component" UI concept client-side from `has_driver`
   (see `ResultsPage.vue:119`, `RoleCards.vue`), never from a literal
   `'component'` string returned by the API — so deleting the function
   introduces no frontend regression.

3. **`refactor/scripts/build_summary.py`'s `_build_mlo_aggregates()`
   (line 141) has the same missing filter**, independently of the API:
   ```sql
   SELECT uniprot_id, MAX(CASE WHEN LOWER(unified_role)='driver' ...), ...
   FROM mlo_annotations
   GROUP BY uniprot_id
   ```
   No `dataset_active` filter. `has_driver`/`has_client` happen to be
   unaffected (NULL role never matches `'driver'`/`'client'` regardless of
   `dataset_active`), but `mlo_count`/`source_db_count`/`mlos`/
   `source_dbs` are **not** — a protein annotated only via a DrLLPS
   Regulator row would incorrectly surface that `source_db`/`unified_mlo`
   in `protein_summary`. Note: `refactor/scripts/CLAUDE.md` already
   *claims* this filter exists — this is a real doc/code mismatch to fix
   alongside the code, not just a documentation gap.

4. **`NotInformed`/`category='Unspecified'`** MLO bucket (~3,027 rows) has
   no filtering anywhere in `api/` today. `SCHEMA.md` states this filtering
   "belongs in the API/frontend layer" but it doesn't exist yet anywhere.
   **User decision: keep current behavior** — no exclusion, no special
   grouping, mixed in with real MLOs as today. The policy layer still gets
   an extension point for this (see below) in case this changes later, but
   it defaults to a no-op.

5. **`protein_summary.has_driver` casing discrepancy between
   `CLAUDE_api.md` and `SCHEMA.md`** — resolved by reading
   `build_summary.py`'s actual code: it already uses
   `LOWER(unified_role)='driver'`/`'client'`, case-insensitive. No code fix
   needed here — just a stale-docs issue, resolved when docs are updated
   (see Docs section).

## Policy layer design

**Location**: `refactor/policy.py` — a new single module at the `refactor/`
root, importable by both `refactor/scripts/build_summary.py` and
`refactor/api/` (same `sys.path.insert` pattern parsers already use for
`schemas.intermediate`). This is the single place that encodes "what counts
as visible/active/driver/client" — the fix for the duplication exposed by
findings #1-#3 above.

**Contents**:
- `ACTIVE_ANNOTATION_FILTER = "dataset_active = 1"` — SQL fragment reused
  in every `WHERE`/`JOIN` touching `mlo_annotations`, in both live API
  queries and `build_summary.py`'s aggregation.
- `EXCLUDED_MLO_CATEGORIES: list[str] = []` — extension point for MLO
  category filtering. Empty today (per user decision in finding #4); the
  single place to change if this policy changes later.
- No role-string remapping — `unified_role` passes through unchanged
  (`'driver'`/`'client'`/`None`).

**Propagation rule**: changes to `policy.py` that affect materialized
columns (`protein_summary`) require re-running `build_summary.py` (fast,
DB fully in memory — not a pipeline rebuild). Changes that only affect live
API queries (e.g. a future `EXCLUDED_MLO_CATEGORIES` change) take effect on
API restart, no DB changes needed.

This was chosen over two alternatives considered and rejected:
- *Fully live computation* (no `protein_summary` materialization for
  policy-sensitive fields) — rejected: unnecessary query complexity for no
  real benefit, since DB is already fully loaded in RAM at API startup.
- *Leave `protein_summary` as-is, no shared policy module* — rejected:
  doesn't resolve the duplication that caused finding #3 to exist
  independently of finding #1 in the first place.

## Fixes to apply during the port

All applied as part of the copy, not as later patches:

1. Add `AND ma.dataset_active = 1` (via `policy.ACTIVE_ANNOTATION_FILTER`)
   everywhere `mlo_annotations` is touched:
   - `queries/mlo_queries.py`: `get_mlo_stats`, `get_mlo_proteins_page`,
     `get_all_mlos`
   - `queries/protein_queries.py`: `get_proteins_page`,
     `get_proteins_facets`, `get_protein_mlo_annotations`
   - `queries/search_queries.py`: `_build_advanced_clauses`/
     `advanced_search`/`get_advanced_search_facets`
   - `main.py`: `_compute_stats()`
2. Delete `_normalize_role()` from `routers/mlos.py` and
   `routers/proteins.py` — pass `unified_role` through unchanged.
3. Add `policy.ACTIVE_ANNOTATION_FILTER` to
   `build_summary.py`'s `_build_mlo_aggregates()` `FROM mlo_annotations`
   clause.
4. Reference `policy.EXCLUDED_MLO_CATEGORIES` in `mlo_queries.py`/
   `protein_queries.py` as a no-op extension point (empty list today).
5. `refactor/api/config.py`: `DB_PATH` points at
   `refactor/database/mlosmetadb.db` (not the repo-root `database/`).

## Verification plan

Following this project's established test-before-batch /
verification-before-completion conventions:

- Start `refactor/api/` pointed at `refactor/database/mlosmetadb.db`.
- `curl` the standard `TEST_PROTEINS` set (FUS/P35637, FMR1/Q92520, hnRNP
  A1/P09651, eIF4A3/P38919, RBM14/Q9NQC3) against `/protein/{id}`,
  `/mlo/{id}`, `/proteins?role=driver`, `/stats`. Confirm: no
  `dataset_active=0` row ever surfaces, `unified_role` is never
  `'component'`, `/stats` aggregate counts match the verified counts from
  `REFACTOR_LOG.md` Entry 8.
- Concretely measure how many proteins' `mlo_count`/`source_db_count` in
  `protein_summary` change before vs. after the `build_summary.py` fix —
  real evidence of finding #3's impact, not just theoretical.

## Docs to update (after code is corrected and verified)

- `refactor/api/CLAUDE.md` (new) — same format as
  `refactor/database/CLAUDE.md`/`refactor/scripts/CLAUDE.md`: endpoint
  conventions, and `policy.py`'s rules documented explicitly, including the
  domain rule from this spec's Context section.
- `refactor/api/API_EXAMPLES.md` (new) — regenerated against the real
  corrected DB — no more stale `"unified_role": "unmapped"` examples.
- `refactor/REFACTOR_LOG.md` — new Entry 11: full port narrative, each fix
  with before/after, verification evidence.
- `refactor/CLAUDE.md` — update the "Where to look" table to include
  `api/CLAUDE.md`; remove the note that `api/`/`frontend/` don't exist yet.
- Original root `api/CLAUDE_api.md`/`api/API_EXAMPLES.md` are **not**
  touched — hard rule: nothing outside `refactor/` is ever modified.

## Out of scope for this phase

- `frontend/` phase — separate, later, not started.
- OrthoDB v2 migration (`parse_orthologs.py`) — WIP, blocked on a
  memory/buffering issue, explicitly not run (see `REFACTOR_LOG.md`).
- `fetch_mobidb_orthologs.py`/`parse_mobidb_orthologs.py` — functional but
  never run against production; out of scope here since `orthologs`
  (OMA-based) is already the live, working ortholog source the existing
  API queries successfully.
- Exposing currently-unexposed columns (`proteins.lineage`, primary
  protein `sequence`, `ppi.throughput`, etc.) — no product need identified
  for this phase; not blocking, can be added later without architectural
  change.
