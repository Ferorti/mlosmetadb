# Design: `frontend/` phase of the MLOsMetaDB refactor

Status: approved by user, pending write of implementation plan.
Related: `refactor/REFACTOR_LOG.md` (data-layer phase Entries 0-10, `api/`
phase Entry 11-13), `refactor/api/CLAUDE.md`, `refactor/api/API_EXAMPLES.md`,
`frontend/DEVLOG.md`, `frontend/CLAUDE.md`, `refactor/CLAUDE.md`.

## Context

`refactor/` is the future clean root of MLOsMetaDB. The data-layer phase and
the `api/` phase are both complete and verified (Entries 0-13). This spec
covers the next and final planned phase: `frontend/` (Vue 3 SPA).

Unlike a from-scratch build, a full, working frontend already exists at the
repo root (`frontend/`): HomePage, ResultsPage, ProteinPage, MlosPage all
implemented (not placeholders — `frontend/CLAUDE.md`'s "Current
implementation status" section is stale on this point; `frontend/DEVLOG.md`'s
dated session log is the source of truth). `DownloadPage`/`AboutPage` are
genuine 5-line stubs.

Initial framing considered this a mechanical port like `api/` was. Live
auditing (see Findings) showed the surface was larger than that: real bugs
only visible once pointed at fully-populated real data, not just schema
drift. Rather than open-ended redesign, the user chose to close this
session's scope back down to **mechanical port**, deferring known
UX/completeness gaps to later frontend development work done *after* the
port, on the theory that those gaps exist in `frontend/` today regardless and
aren't made worse by porting them forward as-is.

## Scope decision

Port `frontend/` into `refactor/frontend/` as-is (same directory structure,
same components/pages/composables), applying only the fixes already found
and applied live against `refactor/api/` during this session's audit (see
Findings — these are already committed to `frontend/` at the repo root, not
hypothetical), plus whatever additional wiring breaks when verifying the
currently-unverified endpoints against the real API. No redesign, no new
features, no resolving the explicitly-deferred items below.

## Findings from auditing the existing `frontend/` against the live `refactor/api/`

Confirmed by running `frontend/` (`npm run dev`, by the user) against
`refactor/api/` (`:8765`) with the real, fully-populated
`refactor/database/mlosmetadb.db`, and by direct code/SQL inspection.
**All of the following are already fixed and committed** (commits `c8f176c`,
`e799f6a`, `7188677` on `audit/full-repo-review`) — listed here so the port
plan doesn't attempt to re-discover or re-fix them:

1. **`proteins.gene_name`/`organism`/`length` were NULL for all 15,879
   rows** (REFACTOR_LOG Entry 13) — a data-pipeline gap, not a frontend bug,
   but it silently broke gene-name search (`/search?q=FUS` → 0 hits) and the
   D3 sequence-feature track (`sequenceLength` NULL → early-return, nothing
   rendered) across every page that uses either. Fixed by backfilling
   `proteins` from the already-cached UniProt responses (`fetch_uniprot.py`
   gained a `backfill_from_cache()` step it was missing).
2. **Home's "MLO Components" card showed 23,230**, more than
   `proteins.total` (15,879) — `RoleCards.vue` read
   `mlo_annotations.by_role` (annotation-row buckets, not mutually exclusive:
   a protein with both a driver-role and a client-role annotation counts in
   both buckets). Fixed: `/stats` gained `proteins.by_component_role`
   (has_driver-based, mutually exclusive; driver + component == total),
   `RoleCards.vue` now reads that instead.
3. **`/proteins?mlo=X`'s `facets.by_role` was wrong whenever combined with an
   MLO/source_db filter** (p_granule: facet showed 46 drivers, real
   MLO-scoped count is 26) — `protein_queries.get_proteins_facets` and
   `search_queries.get_advanced_search_facets` computed driver/component from
   `protein_summary.has_driver`, a *global* per-protein flag ("driver of ANY
   MLO"), not scoped to the MLO actually being filtered on. Fixed via a
   shared `_scoped_role_counts()` helper that checks the role on the matching
   `mlo_annotations` row itself.
4. **Home's organism grid (`OrganismGrid.vue`) used hardcoded placeholder
   counts** (e.g. C. elegans: 534/41 shown vs. 950/82 real) — never wired to
   live data despite `GET /stats` having existed the whole time. Fixed:
   `/stats` gained `proteins.by_organism_drivers`; `OrganismGrid.vue` now
   looks up both from `props.stats.proteins.*` (name matching tolerant of the
   `"(strain ...)"` suffix some DB organism strings carry). `MloBadges.vue`
   was already correctly wired to live `GET /mlos` — no change needed there.
5. **Sort and the organelle/role/feature filters silently did nothing
   whenever a free-text search (`q`) was active** — `ResultsPage.vue`'s
   `runSearch()` routed plain-text queries through `GET /search` (FTS5),
   which accepts only `q`/`mode` and silently ignores everything else.
   Fixed two ways: `/search/advanced` gained `sort_by`/`sort_order` support
   (reusing `protein_queries._build_sort`), and `ResultsPage.vue` now
   escalates to `/search/advanced` whenever `role`/`mlo`/`sort_by`/
   `feature_type`/`feature_accession` is engaged during a text search.
6. **"NotInformed" displayed as if it were a real browsable organelle** on
   Home and `MlosPage` — it's a placeholder several source DBs (not just
   CD-CODE) use when they don't specify a compartment. Fixed narrowly:
   `policy.EXCLUDED_MLO_CATEGORIES = ["Unspecified"]`, wired only into
   `mlo_queries.get_all_mlos` (the `/mlos` listing) — a protein's own MLO
   Annotations tab still shows its NotInformed rows for provenance. Also
   `formatMlo('NotInformed')` now renders `'No MLO associated'` wherever it
   still surfaces.

**Not yet verified** — `API_EXAMPLES.md` explicitly flags `/protein/{id}/ppi`,
`/protein/{id}/orthologs`, `/mlos`, `/search`, `/search/advanced`, and
`/organisms/search` as never exercised end-to-end during the `api/` phase's
own verification. The port's verification step (below) must exercise all six
against real data for the first time.

## Verification plan

Following this project's test-before-batch / verification-before-completion
conventions, same shape as the `api/` phase's:

- Boot `refactor/frontend/` (`npm run dev`, run by the user, never by Claude
  — established project convention) pointed at a running `refactor/api/`.
- Exercise the standard `TEST_PROTEINS` (FUS/P35637, hnRNP A1/P09651,
  eIF4A3/P38919, RBM14/Q9NQC3, and the known-404 FMR1/Q92520) through every
  page: HomePage, ResultsPage (with and without filters, with and without a
  free-text query), ProteinPage (all 4 tabs — Overview, MLO Annotations,
  Interactions, Orthologs), MlosPage.
- Specifically confirm the six previously-unverified endpoints (PPI,
  Orthologs, `/mlos`, `/search`, `/search/advanced`, `/organisms/search`)
  render correctly against real data, not just return 200.
- Confirm the `O23702` case (only annotation is `dataset_active=0`) renders
  an empty/reasonable MLO Annotations state, and `Q92520` (FMR1, 404) renders
  the not-found state — both already verified at the API layer
  (`API_EXAMPLES.md`), need the same check at the UI layer.

## Explicitly deferred (not this phase — documented as known follow-ups)

- `RoleBadge.vue` has no style for `'client'` (falls through to a generic
  gray badge) despite `frontend/CLAUDE.md` documenting brand-green for it.
- `MlosPage.vue`: `SOURCE_DBS` is a hardcoded list of 5; the organism filter
  is a disabled "coming soon" `<select>`.
- Unused Vite scaffold cruft: `HelloWorld.vue`, `TheWelcome.vue`,
  `WelcomeItem.vue`, `components/icons/*`, `views/AboutView.vue`,
  `views/HomeView.vue`, `stores/counter.js` — carry them over or drop them,
  decided during implementation (mechanical, not a design decision).
- Deeper quality review of `ProteinPage.vue`'s Interactions/Orthologs tabs
  beyond "does it render and paginate" — not audited to that depth this
  session.

## Docs to update (after code is ported and verified)

- `refactor/frontend/CLAUDE.md` (new) — same format as `refactor/api/
  CLAUDE.md`: directory structure, API wiring conventions, the "Current
  implementation status" table written accurately from the start (learn from
  `frontend/CLAUDE.md`'s drift — this table must be kept current or removed
  in favor of pointing at `DEVLOG.md`), and the "Explicitly deferred" list
  above as a real, visible pending-work section.
- `refactor/frontend/DEVLOG.md` (new) — first entry points at this spec and
  `REFACTOR_LOG.md` Entry 14.
- `refactor/REFACTOR_LOG.md` — new Entry 14: port narrative, restating
  findings 1-6 above (already fixed pre-port, carried forward) plus whatever
  new wiring gaps the previously-unverified endpoints turn up.
- `refactor/CLAUDE.md` — update the directory map and the "Cross-project
  conventions" section's frontend stack note; remove the "`frontend/` is a
  separate, later phase — it doesn't exist under `refactor/` yet" line.

## Out of scope for this phase

- Everything in "Explicitly deferred" above.
- The eventual repo-root cutover (`OLD/` + promoting `refactor/*` to the
  actual root, becoming the new `main`) — a distinct, later phase, planned
  only after this port is complete and verified.
