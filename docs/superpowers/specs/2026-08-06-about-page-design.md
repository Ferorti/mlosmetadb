# Design: About page (stats, data origin, how-to-use, citations)

> **Correction (2026-08-08).** This document treats `PhaseDB` and `PhasePDB`
> as two source databases (or counts six sources where there are five). They
> were two ingestion tags for one resource, **PhaSepDB**, whose two parsers
> read byte-identical copies of the same export files — so every PhaSepDB
> annotation was loaded twice. The document is left as written because it
> records a past design decision; the tags no longer exist in the data. See
> `docs/issues/001-phasedb-phasepdb-duplicate-ingestion.md`.


**Date**: 2026-08-06
**Status**: approved, pending implementation plan
**Scope**: replaces the `AboutPage.vue` stub with a full page covering four
sections — interactive data statistics, data origin (source + annotation
databases with citations), a how-to-use carousel, and a citations section
with an interactive "which database should I cite" tool. Touches the
frontend (`AboutPage.vue` + new sub-components) and the backend (`/stats`
gains one field, one new `POST` endpoint is added).

---

## 0. Page structure

`frontend/src/pages/AboutPage.vue` becomes a real page: same wrapper
convention as `DownloadPage.vue`/`MlosPage.vue`
(`max-w-6xl mx-auto px-6 py-8`). Four `<section>` blocks with anchor ids
(`#stats`, `#data-origin`, `#how-to-use`, `#citations`), with a small sticky
in-page anchor nav at the top of the page (link to each section) — the page
is long enough that jumping straight to Citations matters.

`stats` (the `/stats` payload) is fetched once in `AboutPage.vue` on mount
via the same API accessor other pages already use, and passed down as a
prop to the stats sub-components — same `props: { stats: { type: Object,
default: null } }` + loading-skeleton convention as `StatBar.vue`/
`RoleCards.vue`/`OrganismGrid.vue`.

---

## 1. Data Statistics and Annotations (`#stats`)

### 1.1 Headline numbers

A stat-tile row extending `StatBar.vue`'s visual style (`bg-[#EBF3FB]
border border-[#C8DFF2] rounded-lg`, `flex divide-x`) to 7 tiles instead of
5: proteins, annotations, MLOs, organisms, source databases, PPI
interactions, sequence features. All fields already exist in `/stats`
except source-database count, which is `Object.keys(by_source).length`
(same computation `StatBar.vue` already does).

Note: this count uses `unique_proteins_by_source` (canonical, merged
names), not `by_source` (raw ingestion tags) — see §4.1.

### 1.2 Three D3 charts

No bar/donut D3 code exists in the repo today — the four existing D3
components (`SequenceFeatureViewer.vue`, `ProteinFeatureTrack.vue`,
`OrthologTrackViewer.vue`, `ProteinPPI.vue`) are linear genomic tracks or a
force graph. New reusable component `frontend/src/components/about/
StatBarChart.vue` (horizontal bar) and `StatDonutChart.vue` (2-3 category
donut), following the **track-viewer mount idiom** used by the other three
(not `ProteinPPI.vue`'s append-new-svg/simulation idiom):

- `containerRef = ref(null)`, template-declared `<svg>`.
- `onMounted`: `ResizeObserver` on the container, initial `render(width)`.
- `onUnmounted`: disconnect the observer.
- `watch` on the chart's data prop (`{ deep: true }`): re-render at last
  known width.
- `render()`: `d3.select(containerRef.value).select('svg')`,
  `svg.selectAll('*').remove()`, full clear-and-redraw (no enter/update/exit
  — matches existing idiom).
- Colors: local hex constants per component, no shared palette module
  (matches existing convention — each D3 component owns its own colors).

Charts:

1. **Bar — proteins by source database.** Uses the new
   `mlo_annotations.unique_proteins_by_source` field (§4.1) — distinct
   proteins, not annotation rows. `PhaseDB` and `PhasePDB` are combined into
   a single "PhaSePDB" bar (see §2 — confirmed to be the same real
   database, tracked as two ingestion tags).
2. **Donut — Driver vs Component.** Uses `proteins.by_component_role`
   (protein-level, mutually exclusive — the same field `RoleCards.vue`
   already uses and documents the rationale for, in preference to the
   annotation-row-based `mlo_annotations.by_role`).
3. **Bar — top 10 organisms.** Uses `proteins.by_organism` (already capped
   at 10 server-side).

Interactivity: hover shows a tooltip with the exact count; click on a
bar/segment navigates to `/results?source_db=...` / `?role=...` /
`?organism=...`, mirroring the existing click-to-navigate behavior in
`RoleCards.vue`/`OrganismGrid.vue`. (Implemented as always-visible value
labels next to each bar/segment instead of a hover tooltip — simpler,
works on touch devices, and still shows the exact count.)

---

## 2. Data Origin (`#data-origin`)

Two card groups, in this order:

1. **LLPS source databases** (5): PhaSePDB, DrLLPS, LLPSDB, PhaSePro,
   CD-CODE.
2. **Annotation & enrichment databases** (5): UniProt, InterPro, MobiDB,
   BioGRID, OMA.

Content (name, description, citation with linked DOI) is supplied by the
user directly — see `docs/superpowers/specs/2026-08-06-about-page-sources.md`
(the reference doc pasted during brainstorming; copy its content verbatim
into the component, do not paraphrase).

Card style: `bg-white border border-gray-200 rounded-lg p-4`, 2-column grid
on desktop / 1-column on mobile. Citation rendered in the same style
`ApiPage.vue`'s citation section already uses (`text-sm text-gray-800`,
DOI linked in `text-[#185FA5] hover:underline`).

**PhaseDB/PhasePDB**: confirmed by the user these are the same real
database (PhaSePDB), tracked as two separate `source_db` ingestion tags in
`mlo_annotations` (`PhaseDB` = original ~5-source ingestion, `PhasePDB` =
added later, largest contributor — see `SCHEMA.md`). Data Origin shows
**one card** ("PhaSePDB"), not two.

Color badges for these 10 entries use a **new mapping local to the About
page** (e.g. defined inline in the Data Origin component), not a change to
the shared `SourceDbBadge.vue`. `SourceDbBadge.vue` is used elsewhere with
raw ingestion tags (`PhaseDB`, `PhasePDB`, `CDCODE`, etc. — it's also
missing a `PhasePDB` entry today, a pre-existing gap documented in
`SCHEMA.md`) and changing its key set risks regressions on pages that
already render those raw tags. Out of scope for this page — not touched.

---

## 3. How to Use (`#how-to-use`)

New component `frontend/src/components/about/HowToUseCarousel.vue`. No
carousel/tabs component exists anywhere in the repo — the closest
precedent is `ProteinPage.vue`'s inline tab pattern (`activeTab` ref +
`mountedTabs` Set + `v-show` panels, so panels stay mounted instead of
being destroyed/recreated). This component follows the same idiom: an
`activeSlide` index ref, `v-show` panels (not `v-if`), prev/next arrow
buttons, and dot indicators — no vertical scroll growth since the
container has a fixed height regardless of which slide is active.

Three slides, each with a title, 3-4 explanatory bullets, and a screenshot
area (fixed 16:9 aspect ratio):

1. Search/Home + Results & filters
2. Protein page + MLOs
3. Download + API

**Screenshot placeholder mechanism**: each slide references an image at a
predetermined path (`frontend/public/about/how-to-1.png`,
`how-to-2.png`, `how-to-3.png`). The `<img>` has an `@error` handler that
swaps in a dashed-border placeholder box ("Screenshot pending") when the
file is missing (404). This lets the user drop in real screenshots later
by adding files at those exact paths — no component code changes needed
when that happens.

---

## 4. Citations (`#citations`, always at the bottom of the page)

### 4.1 Backend changes

**`/stats` gains one field.** `mlo_annotations.unique_proteins_by_source`
(`dict[str, int]`) — `COUNT(DISTINCT uniprot_id) GROUP BY source_db` over
`mlo_annotations`, same `policy.active_annotation_clause` filter the
existing `by_source` query already applies. Added to `_compute_stats()` in
`api/main.py`, and to the `MloAnnotationStats` Pydantic model in
`api/models/schemas.py` (`unique_proteins_by_source: dict[str, int] = {}`).
This is what feeds chart 1.1.1 above with a scientifically accurate
per-database *protein* count instead of an annotation-row count.

**New endpoint**: `POST /proteins/citations`, added to the existing
`api/routers/proteins.py` (same resource family as `/proteins`, not a new
router file — matches how `/proteins/export` was added in the prior
About/Download/API round).

```
POST /proteins/citations
body:     {"uniprot_ids": ["P12345", "Q9Y2Y0", ...]}
response: {"by_source": {"PhaSePDB": 10, "PhaSePro": 3, ...}}
```

- Request model `CitationCheckRequest` (`api/models/schemas.py`):
  `uniprot_ids: list[str]`, validated via a `field_validator` that strips
  whitespace, uppercases, dedupes, and caps the list at 500 entries
  (`HTTPException(422, {"error": "invalid_parameter", ...})` above that,
  matching the existing validation-error convention in `proteins.py`).
  Empty list also 422s.
- Response model `CitationCheckResponse`: `by_source: dict[str, int]`.
- New query function `get_source_dbs_for_uniprot_ids(uniprot_ids:
  list[str]) -> list[dict]` in `api/queries/protein_queries.py`, following
  the existing `IN (...)` idiom (`get_ortholog_features`,
  `get_ppi_inter_edges`): `SELECT DISTINCT uniprot_id, source_db FROM
  mlo_annotations WHERE uniprot_id IN (...) AND {policy clause}`.
- IDs the user pastes that don't match any protein in the DB are **ignored
  silently** — no "unmatched" list surfaced in the response or the UI (per
  user decision).
- Canonical display-name mapping (`PhaseDB`→`PhaSePDB`, `PhasePDB`→
  `PhaSePDB`, `CDCODE`→`CD-CODE`, etc.) is applied in the router when
  aggregating query rows into `by_source` — the same mapping used by the
  Data Origin cards (§2), kept in one place and reused, not duplicated.

### 4.2 Frontend content, top to bottom

1. **Cite MLOsMetaDB** — the existing citation block (Ortí F, Fernández
   ML, Marino-Buslje C. *Protein Science.* 2024;33(1):e4858,
   `https://doi.org/10.1002/pro.4858`), same text as `README.md`/
   `AppFooter.vue`/`ApiPage.vue`.
2. **Original paper** — the same block duplicated verbatim, with an
   inline (non-visible) code comment flagging it as a placeholder to be
   replaced once the source paper is available. Per user: no visible "TBD"
   styling on the page itself, just a maintainer-facing comment.
3. **Interactive citation checker**: a `<textarea>` for pasting UniProt IDs
   (comma/space/newline-separated), a "Check" button, and a result line
   rendered as badges, e.g. `PhaSePro (3)` `PhaSePDB (10)`. Calls the new
   `POST /proteins/citations` endpoint via a new function in
   `frontend/src/api/proteins.js` (or wherever protein API calls live).
4. **Full citation list** — all 10 entries from §2 (5 LLPS + 5 annotation
   databases), always visible regardless of whether the checker tool was
   used, for complete attribution.

---

## Out of scope (deliberately deferred)

- **Fixing `SourceDbBadge.vue`'s missing `PhasePDB` color entry** — a
  pre-existing gap (documented in `SCHEMA.md`), not touched by this page;
  the About page uses its own local color/label mapping instead (§2).
- **Any UI for surfacing which pasted UniProt IDs didn't match** anything
  in the database — explicitly rejected by the user in favor of silent
  ignoring.
- **BibTeX export** for any citation — only the existing plain-text
  citation format is used; no new citation format is introduced.
- **Editing `mlo_annotations`/ingestion to merge the `PhaseDB`/`PhasePDB`
  tags** into one — this spec only changes *display*, not the underlying
  data model. If the two tags should actually be merged at the data layer,
  that's a separate, deliberate decision outside this page's scope.
