# PPI partner list included the protein's own self-interaction; PPI role filter had no regulator bucket

**Labels:** `bug`, `feature`, `api`, `ppi`, `frontend`
**Severity:** medium (bug 1: a real UI defect, visible on any protein with a
self-interaction row) / low (feature: regulator was simply absent, not wrong).
**Status:** **resolved 2026-08-21.** Reported by the user directly against
the interaction graph in `ProteinPPI.vue`: the query protein renders as a
larger, darker, isolated node at the graph's center, and *also* as an
ordinary node somewhere else in the same network.

---

## Bug: self-interaction rows were never excluded from a protein's own partner list

### Root cause

`ppi` records BioGRID's self-interactions (a protein detected interacting
with itself -- typically evidence of homodimerization/oligomerization) as a
row with `uniprot_id_a = uniprot_id_b`. `get_ppi_summary`, `get_ppi_all` and
`get_ppi_page` (`api/queries/protein_queries.py`) never excluded these, so a
protein with such a row appeared as its own "partner": once as the graph's
pinned, larger, darker center node (`isCenter: true`, radius 16, navy), and
again as an ordinary partner node elsewhere in the force layout (radius 6-8,
blue/gray) -- exactly the duplication reported.

`get_ppi_inter_edges` (the function that draws edges *between* two partners,
excluding the hub) already carried `AND uniprot_id_a != uniprot_id_b` --
this was already understood to be needed there, just missed on the three
hub-facing functions.

### Evidence

Live `database/mlosmetadb.db`: 3,367 self-interaction rows, spanning 2,098
distinct proteins, always `in_db = 1`. A concrete, well-known example:
P04637 (p53, which homodimerizes/tetramerizes) carries 6 self-interaction
rows (Reconstituted Complex, Co-purification, Affinity Capture-Western,
FRET, Co-crystal Structure, Affinity Capture-MS across 4 distinct PMIDs).
Before the fix, `GET /protein/P04637/ppi` returned P04637 itself as one of
its 1,206 "partners"; `GET /protein/P04637` reported
`ppi.total_partners = 1972` (should be 1971) and every downstream
consumer -- the graph, the partner table, the driver/regulator counts --
inherited the same off-by-one duplication.

### What was done

Added `AND uniprot_id_b != uniprot_id_a` (or the CTE-scoped equivalent,
`p.uniprot_id_b != p.uniprot_id_a`) to `get_ppi_summary`'s two counts,
`get_ppi_all`'s partner CTE, and `get_ppi_page`'s partner CTE and count
query. No frontend change was needed for the duplicate-node symptom itself --
`ProteinPPI.vue` already builds its center node from `props.protein.uniprot_id`
and its partner nodes from the (now-corrected) API response, so removing the
bad row from the response removes the duplicate.

## Feature: regulators were absent from the PPI role filter and the interaction display

The user asked to add regulators to the available PPI roles, and to check
whether any PPI partners are actually regulators at all (they weren't sure).
They are: 672 proteins in the live DB are PPI partners, in MLOsMetaDB, and
regulator-only (curator-assigned regulator of some MLO, never a driver of
anything).

`GET /protein/{uniprot_id}/ppi`'s `role` filter only accepted `driver`/
`component` (`_VALID_PPI_ROLES` in `routers/proteins.py`, added in
docs/issues/003 finding 3) — a narrower vocabulary than `/proteins`,
`/search/advanced` and `/mlo/{id}`, which have all accepted `role=regulator`
for a while (`policy.regulator_annotation_clause()` +
`policy.regulator_only_role_clause()`, the mutually-exclusive "regulator,
never a driver" bucket also used for the home page's regulator card). Every
returned `PpiPartner` also had no way to say "this partner is a regulator" at
all -- only `has_driver`.

### What was done

1. **`role="regulator"` accepted** by `/protein/{uniprot_id}/ppi`
   (`_VALID_PPI_ROLES` now `{"driver", "component", "regulator"}`).
   `get_ppi_all` gained a matching branch, mirroring
   `_build_proteins_conditions`'s existing `role=="regulator"` handling
   exactly: `policy.regulator_annotation_clause("ma")` (the partner has a
   curator-assigned regulator annotation) AND
   `policy.regulator_only_role_clause("ps")` (never a driver anywhere) --
   the alias passed to the second clause is `"ps"` (protein_summary, already
   joined `ON ps.uniprot_id = pt.partner_uniprot_id`), since that clause only
   needs `{alias}.uniprot_id` as a join key, not any `mlo_annotations`-specific
   column. When `mlo` is also given, the regulator check is scoped to that
   MLO specifically, the same way the driver/component branches already were
   (docs/issues/003 finding 2).
2. **`has_regulator` added to `PpiPartner`** (`models/schemas.py`) and to
   `get_ppi_all`'s row query, as a plain `EXISTS` against `mlo_annotations`
   keyed to `pt.partner_uniprot_id` -- the general "has any regulator claim
   at all" flag (not mutually exclusive with `has_driver`), matching
   `ProteinSummary.has_regulator`/`_has_regulator_select()`'s existing display
   semantics elsewhere in the app. `get_ppi_page`/`PpiInteractionItem` was
   **not** touched: confirmed via `frontend/src/composables/useProtein.js`
   and `ProteinPage.vue` that nothing in the SPA sends `ppi_page`, so that
   endpoint has no consumer to extend.
3. **Frontend** (`ProteinPPI.vue`): added a `partnerRole(p)` helper
   (driver > regulator > component priority, matching how a
   driver-and-regulator partner is badged elsewhere in the app) used by both
   the role filter buttons (now Drivers / Regulators / Components / All
   roles) and the graph. `nodeColor`/`nodeRadius` gained a regulator branch
   (`#854F0B`, the same brand-amber used by `RoleBadge.vue` and
   `ResultsPanel.vue`'s existing regulator badge), the legend gained a
   regulator swatch, the partner table's role column and the graph tooltip
   both now show "Regulator" when applicable, and the stats header now
   reports a regulator count alongside the existing driver count.

## Verification

```
GET /protein/P04637/ppi                    -- before: 1206 items incl. P04637 itself
                                            -- after:  1205 items, P04637 absent
GET /protein/P04637                        -- before: ppi.total_partners = 1972
                                            -- after:  ppi.total_partners = 1971

GET /protein/Q04636/ppi                    -- Q06697 (CDC73) present as a partner,
                                               has_driver=false, has_regulator=true
GET /protein/Q04636/ppi?role=regulator     -- total 7, every item has_regulator=true
                                               and has_driver=false
```

Full suite: 131 passed in `tests/`, 146 passed in `api/tests/` (17 in the
purpose-built `api/tests/test_ppi.py`, up from 9 -- new fixture entities
`PREG01` (regulator-only) and a `P35637<->P35637` self-interaction row added
to `api/tests/conftest_ppi.py`).
