# PPI Evidence Robustness Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a frontend-only "evidence robustness" filter to `ProteinPPI.vue`'s
partner table/graph, so a user can separate partners backed by ≥2 independent
methods or ≥2 independent studies from partners backed by a single
high-throughput screen (79.4% of all pairs in the current dataset).

**Architecture:** Pure frontend change in one file. `PpiPartner.experimental_systems`
and `PpiPartner.pubmed_ids` already travel in the `/protein/{id}/ppi` response, so
robustness is computed client-side in a `computed()` alongside the existing
`filterRole`/`filterMlo` filters. No API, schema, or SQL changes.

**Tech Stack:** Vue 3 Composition API (`<script setup>`), Tailwind CSS v3 — matches
the rest of `ProteinPPI.vue`. No test runner exists for the frontend (confirmed in
`frontend/CLAUDE.md`); verification is manual, against the dev server.

**Spec:** `docs/review/ppi_evidence_filter/DESIGN_PPI_EVIDENCE_ROBUSTNESS_FILTER.md`
(§2 for the filter rule, §4 for the concrete frontend changes this plan implements).
Supporting data/figures: `docs/review/ppi_evidence_filter/`.

## Global Constraints

- Scope is `frontend/src/components/protein/ProteinPPI.vue` only — do not touch
  `api/`, `PpiPartner`, or any SQL query (per spec §0/§3: nothing is required in
  the backend for the methods+studies axes).
- Do not implement the `throughput`/`has_low_throughput` axis (spec §3) — it
  requires an API/schema change and is explicitly deferred to a second pass.
- Do not touch `INTER_EDGE_DEFAULT_THRESHOLD` or any graph hairball logic (spec
  §4.5) — orthogonal to this change.
- Default filter state is "all" (no filtering) — matches `filterMlo`'s default,
  per spec §5. Do not change `filterRole`'s existing `'driver'` default.
- No automated frontend tests exist in this repo — verify by reading the
  rendered dev-server output, not by writing a test file.
- This file (`ProteinPPI.vue`) has unrelated uncommitted changes already in the
  working tree (graph hover/click/collision fixes, unrelated to this feature).
  Do not revert or clean them up — build the new filter on top of the file as it
  currently stands, and keep this feature's commit scoped to only the filter
  change (do not fold the pre-existing unrelated diff into your commit).

---

### Task 1: Evidence robustness filter in `ProteinPPI.vue`

**Files:**
- Modify: `frontend/src/components/protein/ProteinPPI.vue`

**Interfaces:**
- Consumes: `PpiPartner.experimental_systems: string[]`,
  `PpiPartner.pubmed_ids: string[]` (already present on every item in
  `allPartners.value`, confirmed in `api/models/schemas.py:196-205`).
- Produces: `filterEvidence` ref (`'all' | 'robust' | 'weak'`), consumed only
  inside this file's `filteredPartners` computed. No other component imports
  from `ProteinPPI.vue`, so no downstream interface to preserve.

This is a single self-contained UI task — add the ref, extend the filter
computed, extend the reset helper, add the toggle control, and enrich the
Evidence column — verified together against the running dev server since
there is no test runner to gate a narrower slice.

- [ ] **Step 1: Add the `filterEvidence` ref next to the other filters**

In the `// ── filters ──` block (`ProteinPPI.vue:20-27`), add a third filter
ref right after `filterMlo`:

```js
const filterRole   = ref('driver')   // 'all' | 'driver' | 'regulator' | 'component'
const filterMlo    = ref('')         // unified_mlo slug or ''
const filterEvidence = ref('all')    // 'all' | 'robust' | 'weak' -- see isRobust()
const showInterEdges = ref(true)     // partner-partner edges on, or hub-only
```

- [ ] **Step 2: Add an `isRobust()` helper**

Add this function right before `filteredPartners` (before line 64, after
`partnerRole()`). Factored out as its own function (not inlined into the
computed) so the same rule can be reused by the Evidence column in Step 5
without recomputing the two `Set`s twice per row.

```js
// A partner's evidence is "robust" when it clears at least one of two
// independent corroboration axes: more than one distinct experimental
// method, or more than one distinct supporting publication. A single method
// from a single paper (79.4% of all BioGRID pairs in the current dataset --
// see docs/review/ppi_evidence_filter/) is usually one high-throughput
// AP-MS/BioID screen, not independently confirmed evidence. Two dataset
// hubs (SUCLG2, Q9UGI0) show the single-method threshold alone would be
// wrong: both are ~2,800-partner hubs sustained by one deep single-method
// study each, which is strong evidence despite n_methods == 1 -- hence the
// OR on pubmed count rather than a method-count-only rule.
function isRobust(p) {
  return new Set(p.experimental_systems).size >= 2
      || new Set(p.pubmed_ids).size >= 2
}
```

- [ ] **Step 3: Extend `filteredPartners` with the evidence filter**

In `filteredPartners` (`ProteinPPI.vue:64-72`), add a third condition after
the existing `filterMlo` block:

```js
const filteredPartners = computed(() => {
  let list = allPartners.value
  if (filterRole.value !== 'all') list = list.filter(p => partnerRole(p) === filterRole.value)
  if (filterMlo.value) {
    const mlo = filterMlo.value
    list = list.filter(p => p.mlos.includes(mlo))
  }
  if (filterEvidence.value === 'robust') {
    list = list.filter(isRobust)
  } else if (filterEvidence.value === 'weak') {
    list = list.filter(p => !isRobust(p))
  }
  return list
})
```

- [ ] **Step 4: Include the new filter in `resetFilters()`**

`resetFilters()` (`ProteinPPI.vue:392-395`) currently only resets
`filterRole`/`filterMlo`. Add the third:

```js
function resetFilters() {
  filterRole.value = 'all'
  filterMlo.value  = ''
  filterEvidence.value = 'all'
}
```

- [ ] **Step 5: Show study count in the Evidence column, not just method count**

`shortSystems()` (`ProteinPPI.vue:397-407`) truncates to 2 abbreviated method
names but never surfaces how many distinct PubMed IDs back the partner —
exactly the number that lets a reader tell "SUCLG2-style single deep study"
apart from "one throwaway screen row" when `experimental_systems.length` is
already 1. Add a second helper reusing the same abbreviation map, and call
both from the template:

```js
function shortSystems(systems) {
  if (!systems?.length) return '—'
  const abbr = {
    'Affinity Capture-MS': 'AP-MS', 'Affinity Capture-Western': 'AP-WB',
    'Two-hybrid': 'Y2H', 'Co-purification': 'Co-purif',
    'Co-crystal Structure': 'Co-crystal', 'Biochemical Activity': 'Biochem.',
    'Proximity Label-MS': 'ProxLabel-MS',
  }
  const labels = [...new Set(systems.map(s => abbr[s] ?? s))]
  return labels.slice(0, 2).join(', ') + (labels.length > 2 ? ` +${labels.length - 2}` : '')
}

// Study count suffix for the Evidence column, e.g. "3 studies" / "1 study".
// Surfaced separately from shortSystems() because n_pubmed is one of the two
// independent robustness axes (see isRobust()) and is invisible from the
// method list alone -- a single-method partner backed by 12 papers reads
// identically to one backed by 1 paper without this.
function studyCountLabel(pubmedIds) {
  const n = new Set(pubmedIds).size
  if (!n) return null
  return n === 1 ? '1 study' : `${n} studies`
}
```

Update the Evidence `<td>` (`ProteinPPI.vue:543-548`) to show both:

```html
<td
  class="px-3 py-1.5 text-gray-500"
  :title="p.experimental_systems.join(', ')"
>
  {{ shortSystems(p.experimental_systems) }}
  <span v-if="studyCountLabel(p.pubmed_ids)" class="text-gray-400"> · {{ studyCountLabel(p.pubmed_ids) }}</span>
</td>
```

- [ ] **Step 6: Add the three-state evidence toggle to the filters bar**

In the "Filters bar" block (`ProteinPPI.vue:441-469`), add a new toggle group
after the MLO `<select>` and before the "Reset" button, following the same
button-group pattern already used for `filterRole`:

```html
<!-- Evidence filter -->
<div class="inline-flex border border-border rounded overflow-hidden text-xs">
  <button
    v-for="opt in [['all','All evidence'],['robust','Multiple evidence'],['weak','Single evidence']]"
    :key="opt[0]"
    :class="filterEvidence === opt[0] ? 'bg-navy text-surface' : 'bg-surface text-ink3 hover:text-ink'"
    class="px-3 py-1.5 border-l border-border first:border-l-0 transition-colors"
    @click="filterEvidence = opt[0]"
  >{{ opt[1] }}</button>
</div>
```

Update the "Reset" button's `v-if` (`ProteinPPI.vue:465`) to also account for
the new filter, so it appears whenever any filter is non-default:

```html
<button
  v-if="filterRole !== 'all' || filterMlo || filterEvidence !== 'all'"
  class="text-xs text-brand hover:underline"
  @click="resetFilters"
>Reset filters</button>
```

Also add a one-line explainer under the existing stats-header paragraph
(`ProteinPPI.vue:435-437`, the `<p class="text-[12.5px] text-muted">` block)
so a first-time reader understands what "Multiple evidence" / "Single
evidence" means without opening a tooltip. Append this sentence to that
existing `<p>`, in the same tone as the sentence already there:

```
"Multiple evidence" partners have ≥2 independent experimental methods or ≥2 independent publications behind them; "Single evidence" partners rely on one method reported in one paper, typically a single high-throughput screen.
```

- [ ] **Step 7: Verify against the running dev server**

There is no automated frontend test suite (`frontend/CLAUDE.md`), so
verification is manual. Ask the user to run the dev server (do not run
`npm run dev`/`npm run build` yourself — see project convention), then check:

1. Open a protein page with a hub-like partner count (e.g. a protein with
   many partners, ideally one dominated by single-method evidence per the
   design doc's hub list: NUDT21, CUL3, CCR4, VIRMA).
2. Confirm the three-state toggle renders next to the Role/MLO filters and
   defaults to "All evidence" (table/graph unchanged from before this change
   on first load).
3. Click "Multiple evidence" — table should shrink to only partners with
   ≥2 methods or ≥2 PubMed IDs; graph should update to match (same
   `filteredPartners` → `graphData` pipeline already in place).
4. Click "Single evidence" — should show the complement, and together with
   "Multiple evidence" the two counts should sum to the "All evidence" count.
5. Confirm the Evidence column now shows a study count (e.g. "AP-MS · 3
   studies") and that the count differs sensibly between single- and
   multi-evidence rows.
6. Click "Reset filters" with the evidence toggle non-default — confirm it
   returns to "All evidence" along with Role/MLO.
7. Spot-check a known single-deep-study hub if reachable (SUCLG2 / Q96I99,
   or Q9UGI0) — most of its partners should classify as "Single evidence"
   under the methods axis alone but the specific partners backed by that
   study's single PubMed ID will still show `n_pubmed == 1`, so if BioGRID
   for that pair truly has only one method and one paper, the pair legitimately
   lands in "Single evidence" under this two-axis rule — this is expected
   per spec §2 (the throughput axis that would rescue it is deferred), not a
   bug to fix in this task.

- [ ] **Step 8: Commit**

Stage only the filter-related hunks in `ProteinPPI.vue` if the file's
pre-existing unrelated diff (graph hover/click fixes) is still uncommitted —
confirm with the user how to handle mixed state before committing, since a
blanket `git add` on this file would fold two unrelated changes into one
commit.

```bash
git add frontend/src/components/protein/ProteinPPI.vue
git commit -m "feat(ppi): add evidence robustness filter to partner table"
```
