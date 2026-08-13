# Data unification section — Phase 3a (frontend MVP) design

**Source spec:** `docs/review/unification_section/INFORME_SECCION_UNIFICACION.md`.
Phases 1 (data layer) and 2 (API exposure) are complete and merged — see
`2026-08-12-unification-stats-phase1-design.md` and `-phase2-design.md`.
This document covers Phase 3a only: a standalone frontend page rendering
the six figures and two downloadable tables, **without** the report's
cross-figure interactivity (click-a-source filters everything else,
click-a-MLO opens a filtered table) — that's Phase 3b, a separate later
spec, once 3a's content and layout are validated.

## Decisions made in brainstorming, and why

**Own page, not a 5th section of `AboutPage.vue`.** An approved-but-unbuilt
spec (`2026-08-06-about-page-design.md`) already claims `AboutPage.vue` for
four unrelated sections (stats/data-origin/how-to-use/citations) aimed at
onboarding + citation. "Data unification" targets a different reader
(someone auditing dataset reliability) and is dense enough on its own
(6 charts + 2 tables) to justify its own route rather than growing an
already-large page plan. The About spec is untouched by this document.

**D3 v7, not Plotly/Vega-Lite** (the source report's own suggestion).
`frontend/CLAUDE.md`: "No new npm dependencies without checking if
Tailwind + native Vue solves it first." D3 is already a dependency, used in
4 existing components, and the (also unbuilt) About-page spec already
established the pattern new bar/histogram D3 components in this codebase
should follow — reusing it here keeps one charting idiom project-wide
instead of two.

**MVP first (3a): no cross-figure interactivity.** The report specifies
real cross-component state (F1 source-click filtering the rest of the
section, F5 MLO-click opening a filtered table) — real design surface
across 6+ components. Ship static-per-component content first, validate
layout and copy, add cross-filtering as 3b once 3a is live.

**Tables are browsable, not just download links.** Hand-rolled table +
`.slice()` pagination (matching `ProteinPPI.vue`'s existing convention —
`ResultsPanel.vue` is the only TanStack Table consumer in this codebase,
and its scale doesn't justify pulling that pattern in here too), sortable
by column, with a download button alongside. Per-column filters
(`unified_mlo`, discordance pattern, source) are **3b**, not 3a.

**No frontend test suite exists** (`frontend/package.json` has no
`vitest`/`jest`/any test runner). Verification for this phase is: code
review here, then the user runs `npm run dev` themselves and checks the
page in a browser — per this project's standing instruction, Claude never
runs `npm run dev`/`build` directly.

---

## Routing and navigation

- New route: `{ path: '/unification', component: UnificationPage }` in
  `frontend/src/router/index.js`, lazy-loaded like every route except `/`.
- New page file: `frontend/src/pages/UnificationPage.vue`. Wrapper
  `max-w-6xl mx-auto px-6 py-8`, matching `DownloadPage.vue`/`MlosPage.vue`.
- New nav link in `AppNavbar.vue` (placed after "Download", before "About" —
  matching the report's framing as a methodology/transparency page, adjacent
  to Download rather than buried after About). Footer link optional, added
  if `AppFooter.vue`'s existing link list has room without crowding — not a
  hard requirement of this phase.
- Page title / `<title>` tag equivalent: "Data unification — MLOsMetaDB"
  (this SPA has no per-route `<title>` mechanism today — check
  `router/index.js` for a `meta.title` convention before inventing one; if
  none exists, skip it rather than adding a new cross-cutting mechanism for
  one page).

## Data fetching

New `frontend/src/api/unification.js`:

```js
import client from './client'

export async function getUnificationStats() {
  const { data } = await client.get('/unification/stats')
  return data
}

export function discrepantPairsExportUrl() {
  return `${import.meta.env.BASE_URL}api/unification/discrepant-pairs/export`
}

export function mloTermMappingExportUrl() {
  return `${import.meta.env.BASE_URL}api/unification/mlo-term-mapping/export`
}
```

The two `*ExportUrl()` functions are **not** fetched via axios — like
`buildExportUrl()` in `src/api/proteins.js`, they produce a URL the
browser navigates to directly (an `<a href>` / `window.location`), so they
must apply `BASE_URL` themselves rather than going through `client.js`'s
`baseURL`. This is the exact gotcha `DEPLOY.md` documents for
`/proteins/export` — getting it wrong means the download link 404s under
`VITE_BASE=/v2/` in production while working fine in local dev.

`UnificationPage.vue` fetches once in `onMounted()`, holds `stats`/`loading`/
`error` refs (same convention as `AboutPage.vue`'s planned `stats` prop
pattern), and passes `stats` down as a prop to each section component.
A `503` (artifact not built yet — see Phase 2's design) renders a plain
"This section is not available yet" message, not a broken page.

## Section components (`frontend/src/components/unification/`)

Each is a `<script setup>` component taking a slice of `stats` as a prop,
following the existing D3 "track-viewer mount idiom"
(`containerRef` + `ResizeObserver` + full clear-and-redraw on
`watch(prop, { deep: true })`, per-component local color constants — see
`ProteinFeatureTrack.vue` for the canonical example of this idiom already
in the codebase).

### 1. `SourcesSection.vue` (F1 — `f1_source_contribution`)

Grouped horizontal bar chart: one group per `source_db` (5 groups), 3 bars
per group (`annotations`, `proteins`, `source_terms`) — `unified_terms` is
available in the data but not charted (redundant with the vocabulary
section's own numbers; avoid showing the same fact twice in two shapes).
Value label at the end of each bar (matches the About-page spec's decision
to use always-visible labels instead of hover tooltips — works on touch,
no interaction required to read the number).

Copy (adapted from the report's §7, interpolated — **never hardcode a
number in the template**, always read it from the fetched `stats` prop):

> **Sources.** {{ n_annotations }} annotations, {{ n_proteins }} proteins,
> {{ n_unified_mlo_terms }} unified MLO terms. Contributions are uneven:
> CD-CODE and DrLLPS supply most annotations, PhasePro and LLPSDB few but
> with in vitro evidence.

Plus the report's CD-CODE PMID note as a small caption under the chart:
"CD-CODE contributes 0 PMIDs — its evidence is condensate membership, not
a per-annotation citation."

### 2. `ProteinOverviewSection.vue` (F2 — `f2_protein_source_combos`)

**Simplified from a true UpSet plot** (matrix of dots below the bars) to a
horizontal bar list: each row is one combination (`combo_label`,
`n_proteins`), sorted descending, **top 12 + one "other" bar** summing the
rest (the array has 23 real combos today — aggregating client-side here,
not in the API, since "top 12" is a display decision, not a data one).
Each bar's label states its sources as text (`combo_label`, e.g.
"CDCODE+DrLLPS") rather than a dot-matrix, which is the actual UpSet-plot
part being deferred — a true dot matrix is real additional work with no
payoff until 3a's simpler version is validated with the user.

Copy:
> **Protein overlap.** {{ proteins_multi_source }} proteins
> ({{ pct_multi_source }}%) are reported by two or more sources;
> {{ proteins_single_source }} by a single one. Overlap is not redundancy
> to be discarded — it is corroboration, and it is quantified here.

(`pct_multi_source` computed client-side:
`round(proteins_multi_source / n_proteins * 100)`, not stored in the API
payload — a derived display value, not a new backend field.)

### 3. `VocabularySection.vue` (F3 — `f3_vocab_collapse`)

Left: histogram of `n_source_names` across all 177 terms (bucket by
value, e.g. 1, 2, 3, 4-5, 6-10, 11+ — the real distribution is heavily
right-skewed per Phase 1's verified data, so equal-width buckets would be
mostly empty). Right: horizontal bar list of the top 10 terms by
`n_source_names` (the array is already sorted this way).

Copy:
> **MLO vocabulary.** {{ n_source_entries }} source entries were mapped
> onto {{ n_unified_mlo_terms }} unified terms ({{ collapse_ratio }}×
> collapse). The full mapping is downloadable below.

("every unified term links back to its source names" from the report's
copy is a Phase 3b feature — the downloadable `mlo_term_mapping.csv`
already IS that full mapping, so 3a's copy says "downloadable below"
instead of promising an in-page link-back interaction that doesn't exist
yet.)

### 4. `RoleHarmonisationSection.vue` (F4 — `f4_role_mapping`)

Grouped bar chart: one group per `category` (driver / regulator /
component — 3 groups), one bar per `(source_db, source_role)` pair
within its group, labeled with `evidence_type`. Matches the report's
description exactly ("barras agrupadas por categoría destino").

Copy (the report's own driver-evidence-type count is corrected here —
Phase 1 verified 3 distinct evidence types for `driver`, not 2 as the
report's draft prose says):

> **Role harmonisation.** Sources use eight different role labels backed
> by different kinds of evidence, mapped onto three categories: **driver**
> (drives phase separation), **regulator** (modulates it without being a
> constituent driver), **component** (present in the MLO, with no driver
> or regulator evidence assigned by any source). "Component" is used in
> the restricted sense of this third class — drivers and regulators are of
> course also components of the condensate. A "client" label in one source
> and no role in another often reflects each database's curation policy
> rather than different experimental evidence, which is why the third
> category isn't called "client".

Use `stats.summary.cat3_evidence_type_counts` (already computed and
verified in Phase 1: `{component: 3, driver: 3, regulator: 1}`) if the copy
needs to state the count of evidence types per category — do not hardcode
"three" or "two" in prose.

### 5. `AgreementSection.vue` (F5 + F6 — the report's single "Agreement &
discrepancy" block)

- **F5, left**: stacked bar, concordant vs. discordant, over
  `shared_pairs`. A second stacked/grouped bar (or a small legend list)
  breaks down `disc_patterns` (4 keys: `component|driver`,
  `component|regulator`, `component|driver|regulator`, `driver|regulator`).
- **F5, right**: horizontal bar list, `f5b_discrepancy_by_mlo`, all rows
  (or top 15 + "other" if the full list is visually too long — decide at
  implementation time based on how it actually renders; the report doesn't
  cap this one).
- **F6**: a small 6-row table (not a chart — 6 data points don't need one),
  columns `db_a`, `db_b`, `n_a`, `n_b`, `shared`, `jaccard`, from
  `f6_pmid_overlap_sources`. Above it, the independent-vs-shared split as
  two stat callouts (`pairs_independent_pub`, `pairs_shared_pub`,
  `pairs_pmid_comparable` as the denominator) rather than a chart — it's
  two numbers, not a distribution.

Copy:
> **Agreement & discrepancy.** Of {{ shared_pairs }} protein–MLO pairs
> annotated by more than one source, {{ pct_concordant }}% receive the
> same category from all of them and {{ discordant_pairs }}
> ({{ pct_discordant }}%) do not. Discrepancies concentrate in the
> best-studied MLOs, where more sources have an opinion. All discordant
> pairs are listed below, with the role each source assigns and its
> evidence type. MLOsMetaDB does not arbitrate: it shows both claims.

> **Evidence.** {{ unique_pmids }} unique PMIDs back the annotations.
> Where two sources annotate the same protein–MLO pair and both cite
> literature, {{ pct_independent }}% cite different publications — the
> agreement is mostly independent, not the same paper propagated across
> databases. CD-CODE is excluded from this comparison: it records
> condensate membership without a per-annotation citation.

(`pct_concordant`/`pct_discordant`/`pct_independent` are all client-side
derived from the raw counts already in `stats`, matching the "never
hand-write a figure" rule from the source report.)

## Downloadable tables

### `DiscrepantPairsTable.vue`

Columns: `uniprot_id` (links to `/protein/:id`, matching existing
convention elsewhere in the app), `gene_name`, `unified_mlo`, `sources`,
`categories`, `source_roles`, `evidence_types`. `pmids_per_source` is
available in the CSV but not rendered as a column in the MVP table (it's
dense, semicolon/equals-packed data meant for the downloaded file, not
inline display — showing it in-page would need its own parsing/formatting
pass, deferred). Hand-rolled `<table>`, client-side `.slice()` pagination
(50 rows/page, matching `DEFAULT_PER_PAGE`'s value elsewhere in this
codebase for consistency), sortable by clicking a column header (ascending/
descending toggle, no server round-trip needed once loaded).

This row-level data is **not** part of `unification_stats.json` — Phase 1's
design deliberately left the full discordant-pairs list out of the JSON to
avoid duplicating `discrepant_pairs.csv`'s grain (see that design doc's F5
section), and Phase 2 didn't add a paginated JSON endpoint for it either,
since the report only asked for a downloadable table, not an API. So this
component fetches the CSV directly and parses it client-side
(`d3.csvParse` — already a D3 dependency, no new package), once on mount,
holds the parsed rows in a ref, and paginates/sorts in-memory from there.

**Two different ways of reaching the same endpoint, for two different
purposes** — don't conflate them:
- The **in-page parse fetch** goes through the existing `client` axios
  instance (`client.get('/unification/discrepant-pairs/export', {responseType:
  'text'})`), same as every other API call in this app — `client.js`'s
  `baseURL` already handles the `BASE_URL` prefix, so no manual URL
  building is needed here.
- The **download button** (`<a :href="discrepantPairsExportUrl() /* or
  mloTermMappingExportUrl() */" download>`) is a browser-navigated link,
  which bypasses axios entirely — this is the one that needs the manual
  `import.meta.env.BASE_URL`-prefixed URL from `unification.js`, for the
  exact reason `buildExportUrl()` does in `proteins.js`.

Both point at the same server-side file, so what downloads always matches
what's displayed, but the two call sites are not interchangeable — using
the plain `/unification/...`-relative axios call for the `<a href>` would
break under `VITE_BASE=/v2/`.

### `MloTermMappingTable.vue`

Same pattern: fetch `mlo-term-mapping/export`'s CSV, `d3.csvParse`,
paginate/sort client-side. Columns: `unified_mlo`, `source_db`,
`source_mlo`, `annotations`, `proteins`, `definition` (truncated with a
"show more" toggle if long — `mlo_definitions` entries can run to a
paragraph, matching how `MlosPage.vue` already truncates definitions).

## Loading and error states

`UnificationPage.vue`: three states — loading skeleton (`LoadingSpinner.vue`,
already exists), `503`/error ("This section isn't available yet"), and
loaded. Each table component has its own independent loading state for its
CSV fetch (the JSON and the two CSVs load in parallel, not sequentially —
there's no dependency between them).

## Out of scope for Phase 3a (deferred to 3b or later)

- All cross-figure interactivity: F1 source-click filtering the rest of
  the section, F2 combo-click showing a protein list, F3 term-click
  showing source names, F4 hover showing the source's role definition, F5
  MLO-click filtering `DiscrepantPairsTable` to that MLO.
- A true UpSet dot-matrix for F2 (shipped as a bar list in 3a).
- Per-column filters on either table (`unified_mlo`, discordance pattern,
  source toggle for `DiscrepantPairsTable`).
- Any navbar/footer visual redesign beyond adding the one new link.
- `AboutPage.vue`'s own approved-but-unbuilt spec — untouched, separate
  work.
