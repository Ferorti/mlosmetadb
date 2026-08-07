# Design: linked protein sequence viewer (track ↔ sequence ↔ table ↔ structure)

**Date**: 2026-08-07
**Status**: approved, pending implementation plan
**Branch**: `feature/protein-sequence-viewer`
**Scope**: restructures the Overview section of `ProteinPage.vue` from a
two-column layout into four stacked bands, adds a monospace sequence
renderer, and links all four views (D3 feature track, sequence, feature
table, AlphaFold structure) through a shared hover/pin state. Touches the
frontend (`ProteinPage.vue`, `ProteinFeatureTrack.vue`, `MolStarViewer.vue`,
plus four new files), the backend (two lines: one query column, one schema
field), and `index.html` (pin the Mol\* version).

---

## 0. Feasibility findings

Three facts were established by reading the code, the database, and the
shipped Mol\* bundle before this design was written. Each one changed the
plan.

### 0.1 The sequence is in the database but not in the API

`proteins.sequence` is populated and consistent:

```
15879 proteins total
15405 with a non-null sequence (97%)
15405 where LENGTH(sequence) == length  (100% of those)
P35637 (FUS) → 526 aa, MASNDYTQQATQSYGAYPTQPGQGYSQQSSQPYGQQSYSG...
```

But `get_protein_meta()` (`api/queries/protein_queries.py:349`) does not
select it, and `ProteinDetail` (`api/models/schemas.py:130`) does not
declare it. Rendering a sequence therefore requires a backend change, not
just a frontend one. The 474 proteins without a sequence need a graceful
fallback (see §5).

### 0.2 Mol\* can highlight residue ranges through a public API

The CDN bundle loaded by `index.html`
(`https://cdn.jsdelivr.net/npm/molstar@latest/build/viewer/molstar.js`)
exports `Viewer`, `PluginExtensions`, `ExtensionMap`, `lib`, `version`, and
the debug/production toggles. The `Viewer` class carries a method built for
exactly this use case:

```js
viewer.structureInteractivity({
  elements: [{ beg_label_seq_id: 287, end_label_seq_id: 365 }],
  action: 'highlight',        // 'highlight' | 'select' | 'focus', or an array
  applyGranularity: false,
})
```

Internally it resolves `StructureElement.Loci.fromSchema(structure, elements)`
and dispatches to `plugin.managers.interactivity.lociHighlights.highlight()`
or `lociSelects.select()`. The MVS component schema it accepts was verified
in the bundle to support `label_seq_id`, `auth_seq_id`, `residue_index`,
`beg_label_seq_id`/`end_label_seq_id`, `beg_auth_seq_id`/`end_auth_seq_id`,
and the chain/entity/atom-level fields.

This means **no npm dependency and no reliance on library internals**. The
bundle additionally exports `molstar.lib.structure`
(`StructureElement`, `StructureProperties`, `StructureSelection`, …) should
the reverse direction (hover on structure → highlight row) ever be wanted;
it is out of scope here.

Consequences accepted in this design:

- **Highlighting is monochrome.** `highlight` uses Mol\*'s single global
  highlight color and `select` its selection color. Per-feature-type
  coloring in 3D would require overpaint on the representation, which is
  persistent state rather than a hover effect, and is explicitly deferred.
- **`@latest` must be pinned.** Depending on `structureInteractivity` while
  tracking `molstar@latest` means an upstream release can break the protein
  page with no commit on our side. `index.html` pins an explicit version as
  part of this work.

### 0.3 The feature table deduplicates domains; the track does not

`ProteinFeatureTrack.vue:35` collapses domains by accession for the table,
while the SVG (`ProteinFeatureTrack.vue:138`) draws every instance. This
breaks 1:1 linking, and it is not a rare case:

```
proteins with at least one domain:                    11440
… with at least one repeated domain accession:         3109  (27%)
```

Resolution: §3.3.

---

## 1. Layout

The Overview section goes from two columns to four stacked bands:

```
┌─────────────────────────────────────────────────────────────┐
│  SEQUENCE FEATURES                                    526 aa │
│  [═══ D3 track SVG, full width, 80 px ═══════════════════]   │
│  IDRs: 80% · LCD: 27% · 2 domains · 526 aa                   │
├─────────────────────────────────────────────────────────────┤
│  PROTEIN SEQUENCE                                     526 aa │
│    1  MDTEGFGELL QQAEQLAAET EGISELPHVE RNLQEIQQAG ERLRSRTL…  │
│  121  RTFGMAEEYH RESMLVEWEQ VKQRILHTLL ASGEDALDFT QESEPSYI…  │
├──────────────────────────────┬──────────────────────────────┤
│  ALPHAFOLD STRUCTURE         │  FEATURES                     │
│  ┌────────────────────────┐  │  ● Domain                     │
│  │      Mol* 520×420      │  │    PF00076  287  365  RRM     │
│  └────────────────────────┘  │  ● Intrinsically Disordered   │
│  View in AlphaFold DB →      │    IDR  1  286  MobiDB-lite   │
└──────────────────────────────┴──────────────────────────────┘
```

Measurements:

- Bands 1–2 span the full `max-w-6xl` content width.
- Band 3 keeps the current split: `w-[520px] flex-shrink-0` for the
  structure, `flex-1 min-w-0` for the table, `flex gap-6 items-start`.
- The track keeps its 80 px height; only its width changes. The extra width
  materially improves domain labels, which `fitLabel()` currently truncates
  to `RNA recogn…` at the present column width.
- The stats line (`buildFeatureStats()`) stays directly under the track.

The section anchors (`#overview`, `#mlos`, `#interactions`) and the sticky
nav in `ProteinPage.vue` are unchanged.

## 2. Sequence rendering

- **Line width**: the largest of 120, 60, or 30 residues per line that fits,
  always grouped in blocks of 10 separated by a space. The choice is a real
  fit test — measured monospace character width against measured container
  width, re-evaluated on resize — not a viewport media query. 120 is the
  desktop case; 30 exists so narrow phones degrade to a smaller line rather
  than overflowing horizontally.
- **Numbering**: start-of-line residue number, right-aligned, in the gutter.
  With a fixed line width the numbers are predictable (1, 121, 241, … at
  120/line).
- **No per-residue DOM nodes.** Monospace character width is constant, so
  mouse position converts to a residue index arithmetically, and feature
  regions are painted as absolutely-positioned overlay rectangles. For
  titin this is ~290 nodes instead of 34350.
- **Long sequences collapse.** Above 1500 aa the block renders the first few
  lines with a `Show full sequence (N aa)` expander. This affects 421
  proteins; the other 97% render in full with no extra gesture.

Length distribution that drove the threshold:

```
max length:      34350 aa (Q8WZ42, titin)
> 2000 aa:         421 proteins
> 5000 aa:          26
> 10000 aa:          1
```

## 3. Components

`ProteinFeatureTrack.vue` currently does three jobs in ~400 lines: it parses
features, draws the SVG, and renders the table. Since the track and the
table now live in different bands, they are separated.

| File | Role |
|---|---|
| `components/protein/ProteinOverview.vue` *(new)* | Section container. Owns the hover/pin state and the unified feature list. Moves ~60 lines of layout out of `ProteinPage.vue`. |
| `composables/useProteinFeatures.js` *(new)* | Normalizes IDR/LCD/domain/MoRF into one array. Reuses `utils/parseFeatures.js`; does not replace it. |
| `components/protein/ProteinFeatureTrack.vue` | Reduced to the SVG. Receives the normalized list, emits `hover`/`select`, receives the active feature. |
| `components/protein/ProteinFeatureTable.vue` *(new)* | The existing table, extracted. |
| `components/protein/ProteinSequence.vue` *(new)* | Monospace block per §2. |
| `components/viewers/MolStarViewer.vue` | Gains `defineExpose({ highlightRange, selectRange, clear })`. |
| `pages/ProteinPage.vue` | Renders `<ProteinOverview>` in place of the current two-column block. |

### 3.1 Normalized feature shape

`useProteinFeatures(sequenceFeatures, sequenceLength)` returns a flat array:

```js
{
  id,          // stable: `${type}:${accession ?? label ?? source}:${start}-${end}`
  type,        // 'IDR' | 'LCD' | 'Domain' | 'MoRF'
  ranges,      // [{ start, end }] — one entry except for grouped domains (§3.3)
  label,
  accession,
  source,
  color,       // from the existing TYPE_COLORS constant
}
```

Source filtering stays exactly as today: the track and the table both show
only `MobiDB-lite` IDRs and `MobiDB-lite-sub` LCDs, all domain instances,
and all MoRFs. `plddt_region` features remain unrendered in both views.

### 3.2 `MolStarViewer.vue` and the "do not modify" rule

`frontend/CLAUDE.md` states "Do not modify internals of
`MolStarViewer.vue`". The change here adds a public three-method API
wrapping `viewer.structureInteractivity()` and touches neither the load
path nor the lifecycle. **This was raised with the user and explicitly
approved.** `frontend/CLAUDE.md` is updated in the same change to record
that the component now has an exposed API, so the rule is not silently
contradicted by the code.

### 3.3 Repeated domain accessions

Chosen resolution: **keep the deduplicated row, link one-to-many.**

- One table row per accession, as today.
- Its `ranges` array carries every instance.
- Hovering the row highlights all instances at once in the track, the
  sequence, and the structure. Seeing where a domain repeats along the
  protein is itself informative.
- Hovering any one instance in the track marks that single row.
- In the **Domain group only**, the row's `Start`/`End` columns are replaced
  by one `Range` column rendering `287–365, 512–590, 701–779`. For the 73%
  of proteins with no repeats this reads identically to today's two columns.
  The IDR, LCD, and MoRF groups keep their existing `Start`/`End` columns —
  those feature types are never grouped, so every row is already one range.

## 4. State and interactions

`ProteinOverview.vue` owns two refs; everything else derives from them.

```js
const hovered = ref(null)   // { kind: 'feature', id } | { kind: 'residue', pos } | null
const pinned  = ref(null)   // { kind: 'feature', id } | null
```

| Gesture | Track | Sequence | Table | Structure |
|---|---|---|---|---|
| Hover track region | highlight that region | background over the range | highlight the row | `highlight` the range |
| Hover table row | highlight the region(s) | background over the range(s) | highlight the row | `highlight` the range(s) |
| Hover residue in sequence | vertical line at that position | highlight that character | *(no effect)* | `highlight` that residue |
| Click region or row | pin in selection color | pin the background | pin the row | `select` the range(s) |
| Click background / second click | clear | clear | clear | `clear` |

Two deliberate exclusions:

- **Hovering a residue does not light up table rows**, even when the residue
  falls inside features. In FUS, residue 300 sits inside both a domain and
  an IDR; lighting two rows while sliding along the sequence flickers
  constantly. The vertical line on the track already communicates the
  positional relationship.
- **Residues cannot be pinned.** Pinning a single amino acid rarely helps.
  Sequence hover stays ephemeral.

Pin exists because pure hover makes the structure impossible to inspect:
moving the mouse toward the viewer to rotate a highlighted region clears the
very highlight you went there to see. Mol\* distinguishes highlight from
selection with different colors natively, so hover keeps working on top of a
pinned selection with no extra work.

**Throttling**: `mousemove` over the sequence is coalesced with
`requestAnimationFrame` and only emits when the residue index changes.
Without it, dragging across one 120-character line would fire ~120 Mol\*
calls in under a second.

The track's hit testing changes: today a single full-width transparent rect
(`ProteinFeatureTrack.vue:159`) infers hits from the mouse x-coordinate.
That same computation is reused to determine which region is under the
cursor, but it now emits a feature id rather than only feeding a tooltip.

## 5. Backend changes and degradation

Backend, two lines:

1. `get_protein_meta()` adds `sequence` to its `SELECT`
   (`api/queries/protein_queries.py:349`).
2. `ProteinDetail` adds `sequence: str | None`
   (`api/models/schemas.py:130`).

The response grows by the sequence length: 526 bytes for FUS, 34 KB for
titin. Acceptable — the endpoint already ships the full `sequence_features`
block.

Four independent degradation modes:

- **No sequence** (474 proteins, 3%): the sequence band is not rendered.
  Track, structure, and table stay linked.
- **No WebGL**: `MolStarViewer` shows its existing error message and the
  three exposed methods become no-ops. Track, sequence, and table stay
  linked.
- **No AlphaFold structure for the accession**: same as above.
- **No features but a sequence present**: the sequence renders without
  overlays, and residue hover still drives the structure.

## 6. Verification

Per `CLAUDE.md`'s test-before-batch and outcome-first conventions, this is
verified in the browser against three specific proteins before being called
done, with observed results recorded:

- **P35637 (FUS, 526 aa)** — base case. Non-repeating domains, one large
  IDR, two nested LCDs. Assert that PF00076 287–365 highlights exactly
  residues 287 through 365 in the sequence band and the corresponding span
  in the structure.
- **A protein with a repeated domain accession** (one of the 3109) — assert
  that hovering the row lights every instance in all three views and that
  the `Range` column lists them all.
- **Q8WZ42 (titin, 34350 aa)** — assert that the sequence collapses, that
  expanding does not freeze the browser, and that hover stays responsive
  once expanded.

**First implementation step, before any UI work**: confirm in the browser
that `label_seq_id` in AlphaFold's CIF starts at 1 and matches UniProt
numbering. The entire coordinate mapping rests on this assumption. It is
very likely true, but it is checked rather than assumed.

## 7. Explicitly out of scope

- Per-feature-type coloring of the 3D structure (overpaint). Deferred; §0.2.
- Camera focus on click (`action: ['select', 'focus']`). Reframing the
  camera on every row click is disorienting; if wanted later it belongs on
  its own button.
- Hover on the structure driving the sequence and table (the reverse
  direction). The exported `molstar.lib.structure` makes it possible; it was
  not requested.
- Colored residues in the sequence by default. The track is already the
  feature map; duplicating it in the sequence makes the letters harder to
  read. Color appears only as transient hover/pin background.
