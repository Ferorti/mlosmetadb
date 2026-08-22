# Frontend Visual Redesign (system v3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-skin the four pages covered by the Claude Design mockups
(Home, Search Results, Protein Page, MLO detail) with the new visual
system (color/type/layout tokens), and build the MLO detail page that
today doesn't exist as a separate view — without changing any category,
role, axis, identifier, filter contract, or URL/query-param behavior
that's already real.

**Architecture:** Token-first: add the new Tailwind color/font tokens once
(Task 1), unify the two divergent feature-color palettes (Task 2), then
restyle outward from the app shell to each page's components, file by
file. The one new piece of application logic is the MLO detail page
(Tasks 14-15), which wires the already-existing but dead `getMlo()` call
into a new route/component — everything else is markup/class changes with
no new data flow.

**Tech Stack:** Vue 3 `<script setup>`, Tailwind CSS v3, Vue Router v4,
D3.js v7, `@tanstack/vue-table` v8. No TypeScript. No frontend test runner
exists in this repo (`package.json` has no vitest/jest/`@vue/test-utils`)
— see Global Constraints for how verification works instead.

**Spec:** [docs/superpowers/specs/2026-08-22-frontend-visual-redesign-design.md](../specs/2026-08-22-frontend-visual-redesign-design.md)

## Global Constraints

- **No automated frontend test suite exists.** Every task's "verify" step
  is manual/visual, not `pytest`/`vitest`. Do the static checks you can
  (grep for the old hex/class values to confirm they're gone, read the
  diff back) but the actual "does it render right" check requires a
  running dev server.
- **Never run `npm run dev` / `npm run build` / `npm install` yourself.**
  The user runs these and reports back (established project convention).
  End each task by asking the user to run `npm run dev` and check the
  specific page/section this task touched, rather than claiming the task
  visually verified.
- **No data, category, role, axis, identifier, filter param, sort key, or
  URL-state contract changes.** If a task description below ever seems to
  imply one, stop and re-read the spec's §0 priority rule before
  proceeding — it doesn't, but the constraint applies to every step.
- **Every color/font/spacing value comes from the tokens defined in Task
  1**, or is copied verbatim from a value already used elsewhere in the
  codebase (documented per-task below). No new hex codes invented ad hoc.
- **One commit per task minimum**, so the user can check out any
  intermediate state. Use `git add <specific files>`, never `git add -A`.
- Every copy string (role descriptions, source blurbs, tooltips) that
  this plan uses is copied verbatim from where it already lives in the
  code — never from the `.dc.html` mockups' placeholder text. Each task
  names its exact source.
- Branch: `frontend/visual-redesign` (already created and checked out).
  All commits in this plan go there.

---

### Task 1: Design tokens — Tailwind config and fonts

**Files:**
- Modify: `frontend/tailwind.config.js`
- Modify: `frontend/index.html:9`

**Interfaces:**
- Produces: Tailwind color tokens `ink`, `ink2`, `ink3`, `muted`, `navy`,
  `brand`, `surface`, `page`, `border.strong`/`border.DEFAULT`/`border.soft`,
  `track`, `feature.idr`/`feature.domain`/`feature.lcd`/`feature.morf`,
  `regulator` — every later task's Tailwind classes (`bg-navy`,
  `text-brand`, `border-border`, etc.) assume these exist.
- Produces: `fontFamily.mono` set to IBM Plex Mono, `fontFamily.display`
  set to Archivo, `fontFamily.sans` (default) set to IBM Plex Sans.

- [ ] **Step 1: Replace the color/fontFamily block in `tailwind.config.js`**

Current file (`frontend/tailwind.config.js:1-17`):

```js
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js}'],
  theme: {
    extend: {
      colors: {
        brand: {
          blue:  '#185FA5',
          green: '#3B6D11',
          amber: '#854F0B',
          teal:  '#0F6E56',
        }
      }
    }
  },
  plugins: []
}
```

Replace with:

```js
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js}'],
  theme: {
    extend: {
      colors: {
        ink:       '#16181C',
        ink2:      '#4A4E55',
        ink3:      '#4E5762',
        muted:     '#5F6874',
        navy:      '#0E2136',
        brand:     '#1560A8',
        surface:   '#FFFFFF',
        page:      '#F7F9FC',
        border: {
          strong:  '#D2D9E3',
          DEFAULT: '#DFE4EC',
          soft:    '#E9EDF4',
        },
        track:     '#E8ECF3',
        feature: {
          idr:     '#B8362B',
          domain:  '#2C7A6B',
          lcd:     '#98A2B3',
          morf:    '#6B4E8F',
        },
        // Kept as-is from the pre-redesign palette (RoleBadge.vue), not
        // part of the document's 4-color feature encoding -- a distinct
        // axis (protein role), already AA-verified against its own
        // #F6EFE4 background. See spec §1.3.
        regulator: '#854F0B',
      },
      fontFamily: {
        sans:    ['"IBM Plex Sans"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono:    ['"IBM Plex Mono"', 'ui-monospace', 'monospace'],
        display: ['Archivo', '"IBM Plex Sans"', 'ui-sans-serif', 'sans-serif'],
      },
    }
  },
  plugins: []
}
```

`brand.blue`/`brand.green`/`brand.amber`/`brand.teal` (the old nested
object) are removed. Grep confirms exactly two files use them
(`RoleBadge.vue`, `RoleCards.vue`) — both are rewritten in Task 4 to the
new flat token names, so no other file breaks.

- [ ] **Step 2: Update the Google Fonts link in `index.html`**

Current (`frontend/index.html:9`):

```html
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500&display=swap" rel="stylesheet">
```

Replace with:

```html
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&family=Archivo:wght@600;700&display=swap" rel="stylesheet">
```

- [ ] **Step 3: Verify no other file references the removed `brand.*` keys**

Run: `grep -rn "brand-blue\|brand-green\|brand-amber\|brand-teal\|brand\.blue\|brand\.green\|brand\.amber\|brand\.teal" frontend/src`

Expected: only `frontend/src/components/ui/RoleBadge.vue` and
`frontend/src/components/browse/RoleCards.vue` — both fixed in Task 4.
If anything else matches, note it and fix it in that same step (don't
defer silently).

- [ ] **Step 4: Commit**

```bash
git add frontend/tailwind.config.js frontend/index.html
git commit -m "style: add v3 design tokens (color, IBM Plex Mono, Archivo)"
```

No visual change yet — nothing consumes the new tokens until Task 2+.

---

### Task 2: Unify sequence-feature colors, drop in-track labels, add a legend

**Why drop in-track labels**: the document's own feature-class colors are
darker/more saturated than the old palette, and the LCD color
(`feature.lcd` `#98A2B3`) fails WCAG AA for text rendered on top of it in
either black or white (~2:1 and ~2.6:1 contrast, both under the 4.5:1 the
document itself requires in §2). None of the four mockups put text labels
on the colored track bars — Home/Protein Page/MLO Page all use bars +
tooltip + a separate legend row below. Matching that removes the
contrast problem instead of picking a marginal color, and it's a pure
visual decision within the document's authority (§0 rule 3).

**Files:**
- Modify: `frontend/src/composables/useProteinFeatures.js:20-25`
- Modify: `frontend/src/components/results/SequenceFeatureViewer.vue:14-30`
- Modify: `frontend/src/components/protein/ProteinFeatureTrack.vue:25-113`
- Modify: `frontend/src/components/protein/ProteinOverview.vue:105-121`

**Interfaces:**
- Consumes: `feature.idr`/`domain`/`lcd`/`morf` tokens from Task 1.
- Produces: `FEATURE_COLORS` (unchanged export shape:
  `{ IDR, LCD, Domain, MoRF }`, new hex values) — consumed by
  `ProteinFeatureTable.vue` (Task 10) and `ProteinOverview.vue`'s legend.

- [ ] **Step 1: `useProteinFeatures.js` — new `FEATURE_COLORS`**

Replace (`frontend/src/composables/useProteinFeatures.js:20-25`):

```js
export const FEATURE_COLORS = {
  IDR:    '#F5A0A0',
  LCD:    '#FAC775',
  Domain: '#86C865',
  MoRF:   '#C4B5FD',
}
```

with:

```js
export const FEATURE_COLORS = {
  IDR:    '#B8362B',
  LCD:    '#98A2B3',
  Domain: '#2C7A6B',
  MoRF:   '#6B4E8F',
}
```

- [ ] **Step 2: `SequenceFeatureViewer.vue` — unify `TRACK`/`COMPACT`**

Replace (`frontend/src/components/results/SequenceFeatureViewer.vue:15-22`):

```js
const TRACK = {
  height:   34,
  baseline: { y: 16, color: '#e2e8f0', width: 1.5 },
  IDR:    { color: '#f4d3d3', h: 10, y: 12, textColor: '#7F1D1D' },
  LCD:    { color: '#FAC775', h: 18, y: 8,  textColor: '#7C2D12' },
  DOMAIN: { color: '#acc7ff', h: 18, y: 8,  textColor: '#ffffff' },
  LLPS:   { color: '#60A5FA', h: 4,  y: 30 },
}
```

with:

```js
const TRACK = {
  height:   34,
  baseline: { y: 16, color: '#DFE4EC', width: 1.5 },
  IDR:    { color: '#B8362B', h: 10, y: 12 },
  LCD:    { color: '#98A2B3', h: 18, y: 8 },
  DOMAIN: { color: '#2C7A6B', h: 18, y: 8 },
  LLPS:   { color: '#60A5FA', h: 4,  y: 30 },
}
```

Replace (`frontend/src/components/results/SequenceFeatureViewer.vue:24-30`):

```js
const COMPACT = {
  height:   20,
  baseline: { y: 10, color: '#e2e8f0', width: 1.5 },
  IDR:    { color: '#f4d3d3', h: 7,  y: 6, textColor: '#7F1D1D' },
  LCD:    { color: '#FAC775', h: 7, y: 4, textColor: '#7C2D12' },
  DOMAIN: { color: '#bed1f9', h: 7, y: 6, textColor: '#ffffff' },
}
```

with:

```js
const COMPACT = {
  height:   20,
  baseline: { y: 10, color: '#DFE4EC', width: 1.5 },
  IDR:    { color: '#B8362B', h: 7, y: 6 },
  LCD:    { color: '#98A2B3', h: 7, y: 4 },
  DOMAIN: { color: '#2C7A6B', h: 7, y: 6 },
}
```

`textColor` is dropped from every entry — `drawRegion()` already only
draws a label `if (label)` is truthy, and the two call sites that pass a
non-null label are `props.domains.forEach(r => drawRegion(svg, x, r,
t.DOMAIN, props.compact ? null : r.label))` (full mode only) and the
commented-out LCD line. Compact mode (used in Search Results rows) never
labels regions today, so this step only removes the *full*-mode domain
label. Since `t.DOMAIN.textColor` no longer exists, `drawRegion()`'s
`.attr('fill', style.textColor)` on the text branch would break — fix
that in the same step:

Replace (`frontend/src/components/results/SequenceFeatureViewer.vue:104-115`):

```js
  if (label) {
    const fitted = fitLabel(label, rw)
    if (fitted) {
      g.append('text')
        .attr('x', rx + rw / 2).attr('y', style.y + style.h / 2)
        .attr('text-anchor', 'middle').attr('dominant-baseline', 'middle')
        .attr('fill', style.textColor)
        .attr('font-size', '10.5px').attr('font-weight', '600')
        .attr('font-family', 'ui-sans-serif, system-ui, sans-serif')
        .text(fitted)
    }
  }
```

with (drop the in-bar label entirely — full-mode domain names are still
available via the tooltip `onMouseMove()` already builds):

```js
  // No in-bar text label -- see Task 2's rationale (LCD's fill fails
  // WCAG AA for overlaid text). Name/range is still available on hover
  // via the tooltip built in onMouseMove().
```

The now-unused `label` parameter and `fitLabel()`/`CHAR_WIDTH`/
`MIN_CHARS` become dead code — remove `fitLabel()` (lines 35-47) and the
two now-unused constants (lines 32-33), and drop the `label` argument
from both `drawRegion()` call sites (`props.idrRegions.forEach(r =>
drawRegion(svg, x, r, t.IDR))`, `props.domains.forEach(r => drawRegion(svg,
x, r, t.DOMAIN))`) and from `drawRegion()`'s own signature
(`function drawRegion(svg, x, region, style)`).

- [ ] **Step 3: `ProteinFeatureTrack.vue` — same treatment**

Replace `LAYERS` (`frontend/src/components/protein/ProteinFeatureTrack.vue:25-30`):

```js
const LAYERS = {
  IDR:    { y: CENTER_Y - 10, h: 20, textFill: '#7F1D1D' },
  LCD:    { y: CENTER_Y - 6,  h: 12, textFill: '#7C2D12' },
  Domain: { y: CENTER_Y - 14, h: 28, textFill: '#ffffff' },
  MoRF:   { y: CENTER_Y - 21, h: 7,  textFill: '#6B21A8' },
}
```

with:

```js
const LAYERS = {
  IDR:    { y: CENTER_Y - 10, h: 20 },
  LCD:    { y: CENTER_Y - 6,  h: 12 },
  Domain: { y: CENTER_Y - 14, h: 28 },
  MoRF:   { y: CENTER_Y - 21, h: 7 },
}
```

Remove `spanLabel()` (lines 48-53) and `fitLabel()`/`LABEL_SIZE`/
`CHAR_W`/`MIN_CHARS` (lines 32-46) — same rationale, the tooltip in
`showTooltip()` (lines 227-243) already carries type/label/range/source
on hover, unchanged. Remove the label-drawing block inside `render()`
(lines 102-112):

```js
    const fitted = fitLabel(spanLabel(span, rw), rw)
    if (fitted) {
      g.append('text')
        .attr('x', rx + rw / 2).attr('y', layer.y + layer.h / 2)
        .attr('text-anchor', 'middle').attr('dominant-baseline', 'middle')
        .attr('fill', layer.textFill)
        .attr('font-size', `${LABEL_SIZE}px`).attr('font-weight', '600')
        .attr('font-family', 'ui-sans-serif, system-ui, sans-serif')
        .attr('pointer-events', 'none')
        .text(fitted)
    }
```

Also restyle the background bar and sequence-length label to the new
tokens (`frontend/src/components/protein/ProteinFeatureTrack.vue:75-82`
and `123-130`): `fill('#F8FAFC')` → `fill('#F7F9FC')` (the `page` token),
`stroke('#E2E8F0')` → `stroke('#DFE4EC')` (`border.DEFAULT`), and the
length label's `fill('#484E59')` → `fill('#4E5762')` (`ink3`). The
residue marker stroke (`#185FA5`, line 119) and the active/pinned
`stroke` colors in `applyActive()` (`#185FA5`, `#1e293b`, lines 205-208)
become `#1560A8` (`brand`) and `#16181C` (`ink`) respectively.

- [ ] **Step 4: Add the feature legend to `ProteinOverview.vue`**

The old track had no separate legend (labels lived in-bar). Add one
below Band 1, matching the mock's pattern (`Protein Page.dc.html:133-138`)
and reusing `FEATURE_TYPE_LABELS` already exported by
`useProteinFeatures.js:27-32`. Insert after the `<div v-if="stats">`
line in `ProteinOverview.vue` (currently line 119):

```vue
      <div v-if="hasFeatures" class="flex flex-wrap gap-6 mt-4 pt-3 border-t border-border-soft">
        <div
          v-for="group in groups"
          :key="group.type"
          class="flex items-center gap-2 font-mono text-[11px] text-ink2"
        >
          <span class="w-[9px] h-[9px]" :style="{ background: group.color }"></span>
          {{ group.label }}
        </div>
      </div>
```

`groups` is already returned by `useProteinFeatures()` and destructured
at the top of `ProteinOverview.vue:22` — no new prop or import needed.

- [ ] **Step 5: Verify old hex values are gone**

Run: `grep -rn "#F5A0A0\|#FAC775\|#86C865\|#C4B5FD\|#f4d3d3\|#acc7ff\|#bed1f9\|#7F1D1D\|#7C2D12\|#6B21A8" frontend/src`

Expected: no matches.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/composables/useProteinFeatures.js \
        frontend/src/components/results/SequenceFeatureViewer.vue \
        frontend/src/components/protein/ProteinFeatureTrack.vue \
        frontend/src/components/protein/ProteinOverview.vue
git commit -m "style: unify sequence-feature color palette, drop in-track labels for contrast"
```

Ask the user to run `npm run dev` and check a protein with sequence
features (e.g. FUS / `P35637`) on `/protein/P35637` — track and compact
result-row bars should show the new darker colors, no text drawn on the
bars, and a legend row under the main track.

---

### Task 3: App shell — navbar, footer, banner

**Files:**
- Modify: `frontend/src/components/layout/AppNavbar.vue`
- Modify: `frontend/src/components/layout/AppFooter.vue`
- Modify: `frontend/src/components/layout/AnnouncementBanner.vue`

**Interfaces:**
- Consumes: `navy`, `brand`, `ink3` tokens from Task 1.

- [ ] **Step 1: `AppNavbar.vue` — solid navy, no gradient**

Replace the gradient background (`frontend/src/components/layout/AppNavbar.vue:14`):

```html
  <nav class="sticky top-0 z-50 bg-gradient-to-r from-[#1B4F8A] to-[#2B7CD8]">
```

with:

```html
  <nav class="sticky top-0 z-50 bg-navy">
```

This directly satisfies spec §7's "cosas que el rediseño sacó a
propósito: gradiente azul en el header." Update the link colors
(lines 29-33, 56-61) from `text-blue-100`/`hover:text-white`/
`active-class="text-white font-medium"` to `text-[#A6B6C6]`/
`hover:text-[#EEF2F7]`/`active-class="text-[#EEF2F7] font-medium"`
(matches the mock's exact nav link tone) — keep every `RouterLink`'s
`to=` target unchanged. Mobile dropdown background (line 55)
`bg-[#1B4F8A]` → `bg-navy`. The `v2` label (line 24) `text-blue-200` →
`text-[#7F93A8]`.

- [ ] **Step 2: `AppFooter.vue` — same navy, restyled columns**

Replace (`frontend/src/components/layout/AppFooter.vue:2`):

```html
  <footer class="bg-[#1B3D6F] py-6 px-8">
```

with:

```html
  <footer class="bg-navy py-8 px-8">
```

Text tone updates: `text-blue-100` (line 3) → `text-[#8FA1B4]`,
`text-blue-200` (lines 5, 16, 22) → `text-[#EEF2F7]`, link colors
`text-blue-300 hover:text-white` (lines 11, 17, 18) →
`text-[#8FA1B4] hover:text-[#EEF2F7]`. Copy is unchanged (citation,
contact emails, version line) — only classes move.

- [ ] **Step 3: `AnnouncementBanner.vue` — leave as-is**

The banner's amber warning palette (`#FAEEDA`/`#EF9F27`/`#633806`) is not
part of the document — it's a status/alert color, not a brand or
feature-class color, and the document doesn't define an alert palette.
No change to this file. (Recorded here so the task isn't silently
skipped without a reason.)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/layout/AppNavbar.vue frontend/src/components/layout/AppFooter.vue
git commit -m "style: solid navy shell (navbar/footer), drop the blue gradient header"
```

Ask the user to run `npm run dev` and check the navbar/footer on any
page — solid navy, no gradient, links in the muted blue-gray tone.

---

### Task 4: `RoleBadge.vue` and `RoleCards.vue` — new tokens, same copy

**Files:**
- Modify: `frontend/src/components/ui/RoleBadge.vue`
- Modify: `frontend/src/components/browse/RoleCards.vue`

**Interfaces:**
- Consumes: `brand`, `regulator` tokens from Task 1.
- Produces: no change to `RoleBadge`'s public `role` prop or `labels`/
  `titles` maps — every consumer (`ResultsPanel.vue`, `ProteinHeader.vue`,
  `ProteinMLOs.vue`) keeps working unchanged.

- [ ] **Step 1: `RoleBadge.vue` — recolor, keep every label/title string**

Replace `styles` (`frontend/src/components/ui/RoleBadge.vue:16-20`):

```js
const styles = {
  driver:    'bg-[#E8F1FB] text-[#185FA5] border-[#BFD7F0]',
  client:    'bg-[#EDF3E7] text-[#3B6D11] border-[#CBDCB8]',
  regulator: 'bg-[#F6EFE4] text-[#854F0B] border-[#E5D3B3]',
}
```

with:

```js
const styles = {
  driver:    'bg-[#E8F1FB] text-brand border-[#BFD7F0]',
  client:    'bg-[#EEF1EC] text-ink3 border-border',
  regulator: 'bg-[#F6EFE4] text-regulator border-[#E5D3B3]',
}
```

`client` moves off the old brand-green (`#3B6D11`, not part of the new
palette) to the neutral `ink3` tone the document uses for "Component" in
every mockup's role column (`roleColor: role === "Driver" ? blue :
gray`). `labels` and `titles` (lines 21-30) are untouched — same three
strings, same regulator tooltip text.

- [ ] **Step 2: `RoleCards.vue` — recolor bar/count classes, keep every description string**

Replace the three `countClass` values
(`frontend/src/components/browse/RoleCards.vue:23,29,35`):

```js
      countClass: 'text-brand-blue',
```
```js
      countClass: 'text-gray-500',
```
```js
      countClass: 'text-amber-600',
```

with:

```js
      countClass: 'text-brand',
```
```js
      countClass: 'text-ink3',
```
```js
      countClass: 'text-regulator',
```

Replace the top-bar color logic (`frontend/src/components/browse/RoleCards.vue:59-63`):

```html
        <div :class="[
          'h-[3px] -mx-5 -mt-5 mb-4',
          card.role === 'driver' ? 'bg-brand-blue' :
          card.role === 'component' ? 'bg-gray-300' : 'bg-amber-500'
        ]"></div>
```

with:

```html
        <div :class="[
          'h-[3px] -mx-5 -mt-5 mb-4',
          card.role === 'driver' ? 'bg-brand' :
          card.role === 'component' ? 'bg-border-strong' : 'bg-regulator'
        ]"></div>
```

No line in `cards` (the `label`/`description` strings, lines 15-37) is
touched — "LLPS Drivers"/"MLO Components"/"MLO Regulators" and their
three description sentences stay exactly as they are, since they're the
canonical role copy this whole redesign reuses in Task 15's MLO detail
page too.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ui/RoleBadge.vue frontend/src/components/browse/RoleCards.vue
git commit -m "style: recolor role badge/cards to v3 tokens, no copy changes"
```

Ask the user to run `npm run dev`, open `/`, and check the "Browse by
component role" cards plus any driver/regulator badge on a protein page —
same three descriptions, new colors.

---

### Task 5: Home page — hero, search checkboxes, role cards kept

**Files:**
- Modify: `frontend/src/pages/HomePage.vue`
- Modify: `frontend/src/components/search/SearchBox.vue`

**Interfaces:**
- Consumes: `navy`, `brand`, `ink`/`ink2`/`ink3` tokens; `RoleCards`,
  `SearchBox` components unchanged in props/emits.
- Produces: no change to `handleSearch`/`searchExample` — Task 6 (Search
  Results filters) and this task don't touch query-building logic.

This task and Task 6 rebuild `HomePage.vue`'s template in two passes to
keep each commit reviewable: this one is the hero band (logo, title,
search, examples) plus keeping "Browse by component role" as a
navigable-card section (the mock's Home doesn't include a role-browse
section, but dropping it would remove a working navigation path with no
data-correctness reason to — see spec §0's "todo lo real se mantiene").
Task 6 replaces "Browse by MLO"/"Model organisms" with the coverage
matrix + organism ranking + source-database table + get-the-data cards.

- [ ] **Step 1: Rewrite the hero section**

Replace `frontend/src/pages/HomePage.vue:39-74` (the whole `<section
class="bg-[#EBF3FB]...">` hero block) with:

```vue
    <!-- Hero + Search -->
    <section class="bg-surface border-b border-border">
      <div class="max-w-[1080px] mx-auto px-8 pt-[70px] pb-9">

        <h1 class="font-display font-bold text-[52px] leading-[1.05] tracking-[-0.035em] text-ink max-w-[15ch]">
          Proteins in membraneless organelles
        </h1>
        <p class="mt-5 text-[17px] leading-relaxed text-ink2 max-w-[56ch]">
          A meta-database of proteins associated with membraneless organelles
          involved in liquid-liquid phase separation. Integrates proteins from
          PhaSepDB, DrLLPS, PhaSePro, LLPSDB and CD-CODE.
        </p>

        <div class="mt-[34px] max-w-[660px]">
          <SearchBox
            :show-search-options="true"
            :initial-query="''"
            @search="handleSearch"
          />
          <div class="flex items-center gap-3 mt-3 font-mono text-[11.5px] text-muted">
            <span>TRY</span>
            <button class="text-brand hover:text-ink hover:underline" @click="searchExample('FUS')">FUS</button>
            <button class="text-brand hover:text-ink hover:underline" @click="searchExample('P35637')">P35637</button>
          </div>
        </div>

      </div>
    </section>
```

The paragraph copy is the existing hero copy from
`HomePage.vue:52-57` (just no longer split across `<span>` tags for
partial styling — the document's rule is one text color per paragraph,
`ink2`, no bolded sub-spans). The title line changes from "MLOsMetaDB"
(logo + h1) to the mock's descriptive H1 ("Proteins in membraneless
organelles") — this is copy the mock introduces that has no prior
"real" version to preserve (the old H1 was just the product name, already
shown in the navbar), so using the mock's descriptive title here is a
legitimate UX choice, not a data change. The `loguito_horizontal.svg`
logo stays in the navbar (Task 3) and is not repeated on Home.

- [ ] **Step 2: `SearchBox.vue` — chips become real checkboxes**

Read `frontend/src/components/search/SearchBox.vue` in full before this
step (it wasn't included in this plan's file survey — locate the
"Drivers only"/"Exact match" chip markup by grepping
`grep -n "Drivers only\|Exact match" frontend/src/components/search/SearchBox.vue`).
Replace whatever chip/pill markup renders those two options with real
`<input type="checkbox">` elements, following the doc's §6 rule and the
Home mock's exact markup pattern:

```vue
<label class="flex items-center gap-1.5 text-[13px] text-ink3 cursor-pointer">
  <input type="checkbox" :checked="driversOnly" @change="$emit('update:driversOnly', $event.target.checked)"
         class="accent-brand w-3.5 h-3.5 m-0" />
  LLPS drivers only
</label>
```

(adjust the exact `v-model`/emit wiring to match whatever prop/emit
names `SearchBox.vue` already uses for these two options — do not rename
the emitted event or prop, only the template markup and classes.) Keep
both checkboxes functionally forwarding to the same `handleSearch`
payload (`role`, `mode`) `HomePage.vue:22-28` already reads — no change
to that function.

- [ ] **Step 3: Keep "Browse by component role" as a card section**

`frontend/src/pages/HomePage.vue:83-92` (the `<RoleCards>` section)
keeps its `<RoleCards :stats="stats" />` call and copy paragraph
unchanged in this task — only the heading treatment changes to match the
new system (mono eyebrow removed, section header rule per doc §3):

Replace:
```vue
      <h2 class="text-base font-semibold text-[#1B3D6F] border-l-[3px] border-[#2B7CD8] pl-3 mb-1">
        Browse by component role
      </h2>
      <p class="text-sm text-gray-600 pl-3 mb-4">
        You can also reach proteins without naming one: pick the role they play across their annotations.
      </p>
```
with:
```vue
      <div class="flex items-baseline gap-3.5 border-b border-border pb-[11px] mb-5">
        <h2 class="font-sans text-[17px] font-medium tracking-[-0.01em] text-ink">Browse by component role</h2>
      </div>
      <p class="text-[13.5px] text-ink3 max-w-[64ch] mb-6">
        You can also reach proteins without naming one: pick the role they play across their annotations.
      </p>
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/HomePage.vue frontend/src/components/search/SearchBox.vue
git commit -m "style: rebuild Home hero + checkboxed search options, keep role-browse cards"
```

Ask the user to run `npm run dev`, open `/`, and check the hero (title,
search box with real checkboxes, TRY examples) and the role cards
section below it.

---

### Task 6: Home page — source table, organism ranking, MLO coverage matrix, data cards

**Files:**
- Modify: `frontend/src/pages/HomePage.vue`
- Modify: `frontend/src/api/stats.js` (read-only check, see Step 1)
- Modify: `frontend/src/api/mlos.js` (read-only check, see Step 1)

**Interfaces:**
- Consumes: `getStats()` → `StatsResponse.mlo_annotations.
  unique_proteins_by_source` (per-source protein counts, real field,
  `api/models/schemas.py:313`), `StatsResponse.proteins.by_organism`
  (already consumed today via `statsData.proteins.by_organism` in
  `FilterSidebar.vue:37`); `getMlos()` → `MloListItem[]` (`protein_count`,
  `sources[]`, `definitions[].source_name`, all already used by
  `MlosPage.vue`).
- Produces: no new API functions — this task only adds template/script
  code to `HomePage.vue` that calls the two already-imported/available
  functions.

- [ ] **Step 1: Confirm the two fields this task depends on**

Run: `grep -n "unique_proteins_by_source" api/models/schemas.py api/queries/*.py`

Expected: the field exists on `MloAnnotationStats` (already confirmed
during planning, `api/models/schemas.py:313`) and is populated by
whatever function builds `/stats`'s response — read that function now
(`grep -rn "unique_proteins_by_source" api/` to find the builder) and
confirm it returns one count per one of the 5 real `source_db` tags
(`PhaSepDB`, `DrLLPS`, `LLPSDB`, `PhasePro`, `CDCODE`). If it does not
(e.g. returns fewer/differently-named keys), stop and adjust Step 3
below to match reality rather than assuming the shape — do not fabricate
missing keys.

- [ ] **Step 2: Import `getMlos` and fetch it alongside stats**

`HomePage.vue` currently only calls `getStats()`
(`frontend/src/pages/HomePage.vue:14-17`). Add:

```js
import { getMlos } from '@/api/mlos'
```

and extend the `onMounted` fetch:

```js
const mlos = ref([])

onMounted(async () => {
  const [statsRes, mlosRes] = await Promise.all([getStats(), getMlos()])
  stats.value = statsRes.data
  mlos.value  = mlosRes.data.mlos ?? []
})
```

(replacing the existing single-await `onMounted`, `HomePage.vue:14-17`.)

- [ ] **Step 3: Replace "Browse by MLO" + "Model organisms" with the three new sections**

Replace `frontend/src/pages/HomePage.vue:94-113` (the MloBadges section
and the OrganismGrid section) with four sections: a two-column
source-databases + organisms row, a coverage-matrix table, and the
get-the-data cards.

```vue
    <!-- Source databases + Model organisms -->
    <section class="max-w-[1080px] mx-auto px-8 pb-16 grid grid-cols-1 md:grid-cols-2 gap-14 items-start">
      <div>
        <div class="border-b border-border pb-[11px] mb-5">
          <h2 class="font-sans text-[17px] font-medium tracking-[-0.01em] text-ink">Source databases</h2>
        </div>
        <table class="w-full border-collapse text-[13.5px]">
          <tbody>
            <tr v-for="src in sourceRows" :key="src.name" class="border-b border-border-soft">
              <td class="py-[11px] pr-3"><span class="font-medium text-ink">{{ src.name }}</span></td>
              <td class="py-[11px] px-3 text-[13px] text-ink3">{{ src.blurb }}</td>
              <td class="py-[11px] pl-3 text-right font-mono text-xs text-ink whitespace-nowrap">{{ formatCount(src.count) }}</td>
            </tr>
          </tbody>
        </table>
        <p class="mt-4 text-[12.5px] leading-relaxed text-ink3 max-w-[64ch]">
          Entries are merged on UniProt accession. Where sources disagree on an
          organelle name, both the unified term and the original string are kept.
        </p>
      </div>

      <div>
        <div class="flex items-baseline gap-3.5 border-b border-border pb-[11px] mb-5">
          <h2 class="font-sans text-[17px] font-medium tracking-[-0.01em] text-ink">Model organisms</h2>
          <span class="font-mono text-[11px] text-muted">{{ organismRows.length }} species</span>
        </div>
        <div class="flex flex-col gap-3">
          <div v-for="o in organismRows" :key="o.name" class="grid grid-cols-[1fr_74px] gap-3.5 items-start">
            <div>
              <span class="text-[13.5px] italic text-ink">{{ o.name }}</span>
              <div class="h-[5px] bg-track rounded-[1px] mt-1">
                <div class="h-[5px] bg-brand rounded-[1px]" :style="{ width: o.pct + '%' }"></div>
              </div>
            </div>
            <div class="font-mono text-xs text-ink text-right leading-[18px]">{{ formatCount(o.count) }}</div>
          </div>
        </div>
      </div>
    </section>

    <!-- Organelle coverage -->
    <section class="max-w-[1080px] mx-auto px-8 pb-16">
      <div class="flex items-baseline justify-between gap-5 border-b border-border pb-[11px] mb-3">
        <div class="flex items-baseline gap-3.5">
          <h2 class="font-sans text-[17px] font-medium tracking-[-0.01em] text-ink">Organelle coverage</h2>
          <span class="font-mono text-[11px] text-muted">top {{ coverageRows.length }} of {{ mlos.length }} unified terms</span>
        </div>
        <RouterLink to="/mlos" class="font-mono text-[11.5px] text-brand hover:text-ink hover:underline">All organelles →</RouterLink>
      </div>
      <p class="text-[13.5px] text-ink3 max-w-[64ch] mb-6">
        A mark shows the organelle is annotated in that database. Hover a mark for the term the source itself uses.
      </p>
      <table class="w-full border-collapse">
        <thead>
          <tr>
            <th class="text-left pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 tracking-[0.07em]">ORGANELLE</th>
            <th class="text-left px-3 pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 tracking-[0.07em]">COMPARTMENT</th>
            <th v-for="c in SOURCE_ORDER" :key="c" class="text-center px-2 pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 w-[78px]">{{ c }}</th>
            <th class="text-right pl-3 pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 tracking-[0.07em]">PROTEINS</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in coverageRows" :key="row.unified_mlo" class="border-b border-border-soft">
            <td class="py-[11px] pr-3 text-[13.5px]">
              <RouterLink :to="`/mlo/${row.unified_mlo}`" class="text-ink hover:text-brand">{{ formatMlo(row.unified_mlo) }}</RouterLink>
            </td>
            <td class="py-[11px] px-3 font-mono text-[11px] text-muted">{{ spatialLocationLabel(row.spatial_location) }}</td>
            <td v-for="cell in row.cells" :key="cell.source" :title="cell.title" class="py-[11px] px-2 text-center">
              <span v-if="cell.on" class="inline-block w-[7px] h-[7px] rounded-full bg-ink"></span>
              <span v-else class="inline-block w-[7px] h-px bg-border-strong"></span>
            </td>
            <td class="py-[11px] pl-3 text-right font-mono text-xs text-ink">{{ formatCount(row.protein_count) }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <!-- Get the data -->
    <section class="max-w-[1080px] mx-auto px-8 pb-24">
      <div class="border-b border-border pb-[11px] mb-6">
        <h2 class="font-sans text-[17px] font-medium tracking-[-0.01em] text-ink">Get the data</h2>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
        <RouterLink to="/api" class="block border border-border p-[22px] text-ink hover:border-ink transition-colors">
          <div class="text-[15px] font-medium tracking-[-0.005em]">REST API</div>
          <div class="mt-[7px] text-[13px] leading-relaxed text-ink3">Query proteins, organelles and annotations as JSON. No key required.</div>
          <div class="mt-3.5 font-mono text-[11px] text-brand">Documentation →</div>
        </RouterLink>
        <RouterLink to="/data" class="block border border-border p-[22px] text-ink hover:border-ink transition-colors">
          <div class="text-[15px] font-medium tracking-[-0.005em]">Bulk download</div>
          <div class="mt-[7px] text-[13px] leading-relaxed text-ink3">Full database as TSV, with the source annotation preserved per row.</div>
          <div class="mt-3.5 font-mono text-[11px] text-brand">Files and schema →</div>
        </RouterLink>
        <RouterLink to="/data" class="block border border-border p-[22px] text-ink hover:border-ink transition-colors">
          <div class="text-[15px] font-medium tracking-[-0.005em]">Term mapping</div>
          <div class="mt-[7px] text-[13px] leading-relaxed text-ink3">The table that maps every source organelle name to its unified term.</div>
          <div class="mt-3.5 font-mono text-[11px] text-brand">Browse mapping →</div>
        </RouterLink>
      </div>
    </section>
```

`REST API`/`Bulk download`/`Term mapping` route to `/api` and `/data`
(the two real routes from `router/index.js:10-11` — there is no separate
`/data#mapping` anchor to link to specifically, so both download-shaped
cards point at `/data`, which is where `DataPage.vue` already lives per
`frontend/CLAUDE.md`'s directory map).

- [ ] **Step 4: Add the script-side computed properties backing the template above**

Add to `HomePage.vue`'s `<script setup>`, after the existing imports:

```js
import { formatMlo, formatCount, formatOrganism } from '@/utils/format'
import { spatialLocationLabel } from '@/utils/mloAxes'

const SOURCE_ORDER = ['CDCODE', 'DrLLPS', 'LLPSDB', 'PhasePro', 'PhaSepDB']

// Real per-source blurbs, copied verbatim from
// components/unification/SourcesSection.vue:26-30 -- not the mock's
// invented text (spec §2.2).
const SOURCE_BLURBS = {
  CDCODE:   'Community-editable database of biomolecular condensates.',
  DrLLPS:   'Scaffold, regulator, and client proteins involved in LLPS.',
  LLPSDB:   'Proteins with LLPS behavior observed in vitro, with experimental conditions.',
  PhaSepDB: 'Manually curated database of proteins linked to LLPS.',
  PhasePro: 'Proteins and regions experimentally validated as LLPS drivers.',
}
const SOURCE_DISPLAY_NAMES = { CDCODE: 'CD-CODE', DrLLPS: 'DrLLPS', LLPSDB: 'LLPSDB', PhaSepDB: 'PhaSepDB', PhasePro: 'PhasePro' }

const sourceRows = computed(() => {
  const counts = stats.value?.mlo_annotations?.unique_proteins_by_source ?? {}
  return SOURCE_ORDER.map(key => ({
    name:  SOURCE_DISPLAY_NAMES[key],
    blurb: SOURCE_BLURBS[key],
    count: counts[key] ?? 0,
  }))
})

const organismRows = computed(() => {
  const byOrg = stats.value?.proteins?.by_organism ?? {}
  const entries = Object.entries(byOrg).sort((a, b) => b[1] - a[1])
  const max = entries[0]?.[1] ?? 1
  return entries.slice(0, 8).map(([name, count]) => ({
    name: formatOrganism(name), count, pct: Math.round((count / max) * 100),
  }))
})

const coverageRows = computed(() => {
  return [...mlos.value]
    .sort((a, b) => (b.protein_count ?? 0) - (a.protein_count ?? 0))
    .slice(0, 14)
    .map(m => ({
      unified_mlo:   m.unified_mlo,
      spatial_location: m.spatial_location,
      protein_count: m.protein_count,
      cells: SOURCE_ORDER.map(src => {
        const def = (m.definitions ?? []).find(d => d.source_db === src)
        return {
          source: src,
          on:     !!def,
          title:  def ? `${src}: ${def.source_name ?? def.definition ?? ''}` : `${src}: not annotated`,
        }
      }),
    }))
})
```

`computed` must already be imported from `'vue'` in `HomePage.vue` (it
currently only imports `ref, onMounted` — add `computed` to that
import). `spatialLocationLabel` is the real axis label function from
`mloAxes.js:52-54`, not an invented "compartment" string.

- [ ] **Step 5: Verify no leftover reference to `MloBadges`/`OrganismGrid`**

Run: `grep -n "MloBadges\|OrganismGrid" frontend/src/pages/HomePage.vue`

Expected: no matches (both imports and their `<template>` usages were
removed in Step 3). The two component files themselves
(`MloBadges.vue`, `OrganismGrid.vue`) are left on disk untouched — they
may still be useful elsewhere or later; deleting unused files is out of
scope for a visual redesign unless the user asks.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/HomePage.vue
git commit -m "feat(home): source table, organism ranking, MLO coverage matrix, data cards"
```

Ask the user to run `npm run dev`, open `/`, and check all three new
sections render with real counts (not zeros/blanks) and that hovering a
coverage-matrix dot shows the source's own term in the tooltip.

---

### Task 7: `FilterSidebar.vue` — mono headers, checkbox affordance, same filters

**Files:**
- Modify: `frontend/src/components/search/FilterSidebar.vue`

**Interfaces:**
- Consumes: `applyFilter(key, value)`/`removeFilter(key)` — unchanged,
  still emit `update:filters` with the same shape `ResultsPage.vue`
  already reads.
- No new filter keys, no facet count invented where `props.facets` is
  null (unchanged TODO at line 14-16, left in place).

**Explicitly not done here** (see spec §3.3): no `/search/facets`
integration, no `spatial_location`/"COMPARTMENT" facet, no `Regulator`
role option — none of those work against the real API today.

- [ ] **Step 1: Section header style**

Replace the repeated header-button pattern (four instances, e.g.
`frontend/src/components/search/FilterSidebar.vue:190-198`):

```html
        <button
          class="flex items-center justify-between w-full text-xs font-semibold text-gray-700 uppercase tracking-wide py-2"
          @click="open.role = !open.role"
        >
          LLPS role
```

with (repeat for `organelle`, `organism`, `features` sections at their
own line numbers, 227-235, 285-293, 346-354):

```html
        <button
          class="flex items-center justify-between w-full font-mono text-[10.5px] text-ink3 tracking-[0.07em] py-2 border-b border-border pb-[9px]"
          @click="open.role = !open.role"
        >
          LLPS ROLE
```

(section labels go uppercase in the mono font per doc §3's "Encabezado
de sección" rule — same four labels, just cased/font-changed:
"LLPS ROLE", "ORGANELLE", "ORGANISM", "MOLECULAR FEATURES".)

- [ ] **Step 2: Option rows — add real checkboxes**

The current role/organelle/organism option rows are plain clickable
`<div>`s with no input element (e.g.
`frontend/src/components/search/FilterSidebar.vue:210-220`). Per doc §6
("Si un control se muestra, tiene que funcionar" / real checkboxes for
binary choices) and given these are still single-select-per-section
today (clicking one hides the rest, per `frontend/CLAUDE.md`'s
documented FilterSidebar behavior), render each option row with a
checkbox that's visually real but semantically radio-like (only one can
be "checked" at a time within a section, matching the existing
one-at-a-time apply behavior — do not silently upgrade this to true
multi-select, since `/search/advanced` only accepts one value per filter
key, confirmed in `_build_advanced_clauses`):

```html
              <label
                v-for="opt in roleOptions"
                :key="opt.v"
                class="flex items-center gap-2 py-1 cursor-pointer text-[13px] text-ink3 hover:text-ink"
              >
                <input type="checkbox" :checked="false" @change="applyFilter('role', opt.v)"
                       class="accent-brand w-[13px] h-[13px] m-0 flex-shrink-0" />
                <span class="flex-1">{{ opt.l }}</span>
                <span v-if="facets?.by_role?.[opt.v] != null" class="font-mono text-[11px] text-muted">{{ facets.by_role[opt.v].toLocaleString() }}</span>
              </label>
```

`:checked="false"` is intentional and not a bug: these rows only render
inside `v-if="!filters.role"` (the option list disappears the instant a
filter is applied, replaced by the active chip — existing behavior,
`FilterSidebar.vue:207-222`), so a rendered checkbox is by definition
still unchecked. Apply the equivalent change to the organelle
(`displayedMlos`, lines 254-264) and organism (`displayedOrgs`/
`orgSearchResults`, lines 314-339) option rows, keeping their existing
`@click="applyFilter(...)"` handlers moved to `@change` on the new
`<input>`.

- [ ] **Step 3: Active-filter chip and border tokens**

Replace every `bg-[#E6F1FB] border border-[#B5D4F4] text-[#185FA5]`
chip class (4 occurrences: lines 202, 240, 298, 392) with
`bg-[#E8F1FB] border border-[#BFD7F0] text-brand` (matches `RoleBadge`'s
driver chip exactly, Task 4). Replace `border-gray-100`/`border-gray-200`
section dividers (lines 189, 227, 285, 346, 252, 310, 380) with
`border-border-soft`/`border-border`. Replace focus rings
`focus:border-[#185FA5]` (lines 252, 310, 380) with
`focus:border-brand`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/search/FilterSidebar.vue
git commit -m "style: mono section headers + real checkboxes in FilterSidebar, same filter contract"
```

Ask the user to run `npm run dev`, open `/results`, and confirm every
filter (role, organelle, organism, molecular features, Pfam text input)
still applies exactly as before — only the visual treatment changed.

---

### Task 8: `ResultsPanel.vue` — single table, drop cards view

**Files:**
- Modify: `frontend/src/components/results/ResultsPanel.vue`

**Interfaces:**
- Consumes: same props as today (`results`, `total`, `page`, `perPage`,
  `loading`, `query`, `activeFilters`, `error`, `downloadLoading`), same
  emits (`page-change`, `remove-filter`, `download`). `ResultsPage.vue`
  is **not** modified by this task — the props/emits contract is
  unchanged, so its `<ResultsPanel ... />` call site needs no edit.
- Produces: removes the `viewMode` ref and the cards/table toggle
  entirely — always renders the table.

This is the biggest structural change in the plan (spec §3.1: "esto
reemplaza el toggle cards/tabla actual"). TanStack Table's column-based
model can't easily express a cell containing D3-rendered proportional
bands sized relative to the row set's max length (the `scale`/`bands`
logic in the mock needs the full result set to compute one shared
`MAXLEN`, which a per-cell TanStack `cell:` renderer doesn't have direct
access to) — so this task replaces the `@tanstack/vue-table` markup with
plain `<table>` markup driven by a `computed`, keeping the existing
sort-select/pagination/download controls as-is. `@tanstack/vue-table`
stays a dependency (still used nowhere else after this — confirmed by
`frontend/CLAUDE.md`: "imported by ResultsPanel.vue and nowhere else" —
leave the npm dependency in `package.json`; removing an unused
dependency is a separate decision from a visual redesign and the plan
doesn't touch `package.json`).

- [ ] **Step 1: Remove `viewMode` and the TanStack imports/columns**

Delete `frontend/src/components/results/ResultsPanel.vue:2,32` (the
`useVueTable`-family import and `const viewMode = ref('cards')`), and
delete the whole "TanStack Table" block (lines 193-236: `col`,
`columns`, `tableData`, `table`).

- [ ] **Step 2: Add the shared-scale computed the architecture column needs**

Add to `<script setup>`, replacing the deleted TanStack block:

```js
const MAX_LENGTH = computed(() =>
  Math.max(1, ...resultsWithFeatures.value.map(r => r.protein.sequence_length || 0))
)

function architectureBands(entry) {
  const len = entry.protein.sequence_length
  if (!len) return []
  const band = (start, end, color, label) => ({
    key: `${label}-${start}`,
    title: `${label} ${start}–${end}`,
    style: {
      position: 'absolute', top: 0, bottom: 0,
      left:  `${((start - 1) / len) * 100}%`,
      width: `${((end - start + 1) / len) * 100}%`,
      background: color, borderRadius: '1px',
    },
  })
  const idr = entry.idrRegions.map(r => band(r.start, r.end, '#B8362B', 'IDR'))
  const dom = entry.domains.map(r => band(r.start, r.end, '#2C7A6B', 'Domain'))
  return [...idr, ...dom]
}
```

`resultsWithFeatures` already computes `idrRegions`/`domains` per row
(`ResultsPanel.vue:94-108`, unchanged) — this reuses it rather than
re-parsing.

- [ ] **Step 3: Replace the view-mode toggle in the header bar**

Delete the "Cards / Table toggle" block
(`frontend/src/components/results/ResultsPanel.vue:257-273`) entirely —
no replacement control, since there's only one view now.

- [ ] **Step 4: Replace both the "Card (row) view" and "Table view" template blocks with one table**

Delete `frontend/src/components/results/ResultsPanel.vue:369-510` (both
`<template v-else-if="viewMode === 'cards'">` and `<template v-else>`
blocks) and replace with:

```vue
      <!-- Results table -->
      <template v-else>
        <div class="overflow-x-auto -mx-6">
          <table class="w-full border-collapse">
            <thead>
              <tr>
                <th class="text-left px-3 pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 tracking-[0.07em]">PROTEIN</th>
                <th class="text-left px-3 pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 tracking-[0.07em] w-[210px]">ARCHITECTURE</th>
                <th class="text-right px-3 pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 tracking-[0.07em] w-[58px]">LENGTH</th>
                <th class="text-right px-3 pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 tracking-[0.07em] w-[52px]">MLOS</th>
                <th class="text-center px-3 pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 tracking-[0.07em] w-[96px]">SOURCES</th>
                <th class="text-right pl-3 pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 tracking-[0.07em] w-[82px]">ROLE</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="entry in resultsWithFeatures"
                :key="entry.protein.uniprot_id"
                class="border-b border-border-soft hover:bg-page cursor-pointer transition-colors"
                @click="goToProtein(entry.protein.uniprot_id)"
              >
                <td class="align-top px-3 py-3.5">
                  <div class="flex items-baseline gap-2">
                    <span class="text-[15px] font-semibold tracking-[-0.01em]" :class="titleColor(entry.protein)">
                      {{ entry.protein.gene_name || entry.protein.uniprot_id }}
                    </span>
                    <span class="font-mono text-[11.5px] text-ink3">{{ entry.protein.uniprot_id }}</span>
                  </div>
                  <div class="text-[13px] text-ink2 mt-0.5">{{ entry.protein.protein_name }}</div>
                  <div class="text-[12.5px] italic text-muted mt-0.5">{{ shortOrganism(entry.protein.organism) }}</div>
                  <div v-if="displayMlos(entry.protein).length" class="text-[12.5px] text-ink3 mt-1.5">
                    {{ visibleMlos(entry.protein).map(formatMlo).join(' · ') }}
                    <button
                      v-if="displayMlos(entry.protein).length > 10 && !expandedRows.has(entry.protein.uniprot_id)"
                      class="text-muted hover:underline"
                      @click.stop="expandedRows.add(entry.protein.uniprot_id)"
                    >+{{ displayMlos(entry.protein).length - 10 }} more</button>
                  </div>
                </td>
                <td class="align-top px-3 py-3.5">
                  <div class="relative h-3 bg-track rounded-[1px]" :style="{ width: entry.protein.sequence_length ? (entry.protein.sequence_length / MAX_LENGTH * 100) + '%' : '0%' }">
                    <div v-for="b in architectureBands(entry)" :key="b.key" :title="b.title" :style="b.style"></div>
                  </div>
                  <div v-if="entry.featureStatsShort" class="font-mono text-[10.5px] text-ink3 mt-1.5">{{ entry.featureStatsShort }}</div>
                </td>
                <td class="align-top px-3 py-3.5 text-right font-mono text-xs text-ink">{{ formatCount(entry.protein.sequence_length) }}</td>
                <td class="align-top px-3 py-3.5 text-right font-mono text-xs text-ink">{{ displayMlos(entry.protein).length }}</td>
                <td class="align-top px-3 py-3.5">
                  <div class="flex gap-1.5 justify-center">
                    <span
                      v-for="src in SOURCE_ORDER"
                      :key="src"
                      :title="entry.protein.source_dbs?.includes(src) ? src : `${src}: not annotated`"
                      class="inline-block"
                      :class="entry.protein.source_dbs?.includes(src) ? 'w-[7px] h-[7px] rounded-full bg-ink' : 'w-[7px] h-px bg-border-strong mt-[3px]'"
                    ></span>
                  </div>
                </td>
                <td class="align-top pl-3 py-3.5 text-right font-mono text-[11px]" :class="entry.protein.has_driver ? 'text-brand' : 'text-ink3'">
                  {{ entry.protein.has_driver ? 'Driver' : 'Component' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="flex flex-wrap gap-6 mt-6 pt-4 border-t border-border-soft font-mono text-[11px] text-ink2">
          <div class="flex items-center gap-2"><span class="w-[9px] h-[9px] bg-feature-idr"></span>Disordered region</div>
          <div class="flex items-center gap-2"><span class="w-[9px] h-[9px] bg-feature-domain"></span>Pfam domain</div>
          <div class="flex items-center gap-2"><span class="w-[9px] h-[9px] rounded-full bg-ink"></span>Annotated in source</div>
          <div class="text-ink3">Bars share one scale · widest = {{ formatCount(MAX_LENGTH) }} aa · source order {{ SOURCE_ORDER.join(' · ') }}</div>
        </div>
      </template>
```

`goToProtein`, `titleColor`, `shortOrganism`, `displayMlos`,
`visibleMlos`, `expandedRows`, `formatMlo`, `formatCount` are all
already defined/imported in this file (lines 39-47, 178-191, `import {
formatMlo, formatCount, filterMlos } from '@/utils/format'` at line 13)
— no new imports needed except `SOURCE_ORDER`, added as a local
constant: `const SOURCE_ORDER = ['CDCODE', 'DrLLPS', 'LLPSDB',
'PhasePro', 'PhaSepDB']` (same 5 real tags used everywhere else in this
plan). The `ROLE` column's two-color scheme (brand / ink3) matches spec
§3.2's decision — no third "Regulator" color here, since
`protein.has_driver` is the only role signal this endpoint returns per
row.

- [ ] **Step 5: Restyle filter chips and pagination controls to the new tokens**

Replace `bg-[#EBF3FB] text-[#185FA5] ... border-[#C8DFF2]`
(`ResultsPanel.vue:309`) with `bg-[#E8F1FB] text-brand border-[#BFD7F0]`
(same chip style as Task 4/7, for consistency). Replace
`bg-[#1B3D6F]`/`border-[#1B3D6F]` pagination active-page classes (lines
538) with `bg-navy border-navy`.

- [ ] **Step 6: Verify the removed identifiers are gone**

Run: `grep -n "viewMode\|useVueTable\|createColumnHelper\|FlexRender" frontend/src/components/results/ResultsPanel.vue`

Expected: no matches.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/results/ResultsPanel.vue
git commit -m "feat(results): single table view (architecture/sources/role columns), drop cards view"
```

Ask the user to run `npm run dev`, open `/results` with an active
search, and confirm: the table renders one row per protein with visibly
different-width architecture bars proportional to length, hovering a bar
shows the IDR/Domain tooltip, hovering a source dot shows which DB, and
clicking a row still navigates to `/protein/:id`.

---

### Task 9: `ProteinHeader.vue` and `ProteinPage.vue` tab nav

**Files:**
- Modify: `frontend/src/components/protein/ProteinHeader.vue`
- Modify: `frontend/src/pages/ProteinPage.vue`

**Interfaces:**
- No prop/emit changes to either component.

- [ ] **Step 1: `ProteinHeader.vue` — title, metadata line, role pill**

Replace the title row (`frontend/src/components/protein/ProteinHeader.vue:42-48`):

```html
    <h1 class="text-xl text-gray-800 mb-1">
      <span class="font-semibold">{{ titleLeft }}</span>
      <template v-if="titleRight">
        <span class="text-gray-400"> · </span>
        <span class="font-normal text-gray-600">{{ titleRight }}</span>
      </template>
    </h1>
```

with:

```html
    <div class="flex items-baseline gap-3.5 flex-wrap">
      <h1 class="font-display font-bold text-[42px] leading-none tracking-[-0.035em] text-ink">{{ titleLeft }}</h1>
      <span v-if="titleRight" class="text-[19px] text-ink2 tracking-[-0.01em]">{{ titleRight }}</span>
    </div>
```

Replace the metadata line (lines 50-58) classes
`text-sm text-[#484E59]` → `font-mono text-[12.5px] text-ink3`, and the
accession span's `font-mono text-gray-800` → `text-ink`. Replace the
role badge block (lines 60-73) — the pill currently comes from
`RoleBadge`; the mock's header uses a bordered outline pill instead of
the filled badge style. Since `RoleBadge.vue` is reused elsewhere with
its filled style intentionally (results table, MLO tables), don't change
`RoleBadge.vue` itself again here — instead render the header's own pill
inline, matching the mock, only for the `driver` case (the only role
`displayRole` computes, `ProteinHeader.vue:13-16`):

```vue
    <div v-if="sourceDbs.length" class="flex flex-wrap gap-2 mt-3 items-center">
      <div v-if="displayRole" class="inline-flex items-center gap-1.5 border border-brand text-brand rounded-[2px] px-2.5 py-1 text-xs font-medium">
        <span class="w-1.5 h-1.5 bg-brand rounded-full"></span>LLPS driver
      </div>
      <SourceDbBadge
        v-for="src in sourceDbs"
        :key="src"
        :source="src"
        :href="sourceHref(src)"
      />
    </div>
```

"LLPS driver" here matches `RoleBadge.vue`'s existing `driver` label
text (`labels.driver = 'LLPS Driver'`, `RoleBadge.vue:23`, lowercased to
match the mock's exact header casing — same words, not new copy).

- [ ] **Step 2: `ProteinPage.vue` — tab nav restyle**

Replace the sticky nav (`frontend/src/pages/ProteinPage.vue:91-102`):

```html
      <div class="sticky top-14 z-10 bg-white border-b border-slate-200 mb-6">
        <nav class="flex">
          <a
            v-for="tab in TABS"
            :key="tab.id"
            :href="`#${tab.id}`"
            class="px-4 py-3 text-sm font-medium text-[#484E59] border-b-2 border-transparent hover:text-[#185FA5] hover:border-[#185FA5] transition-colors"
          >
            {{ tab.label }}
          </a>
        </nav>
      </div>
```

with:

```html
      <div class="sticky top-14 z-10 bg-surface border-b border-border mb-6">
        <nav class="flex gap-7">
          <a
            v-for="tab in TABS"
            :key="tab.id"
            :href="`#${tab.id}`"
            class="pb-3 text-[14px] font-medium tracking-[-0.005em] text-ink3 border-b-2 border-transparent hover:text-ink transition-colors"
          >
            {{ tab.label }}
          </a>
        </nav>
      </div>
```

`TABS`' three labels ("Overview", "MLO Annotations", "Interactions",
`ProteinPage.vue:14-18`) are unchanged. This nav has no active-tab state
today (it's scroll-anchor links, not a real tab switcher — all three
sections render simultaneously, per the file's own comment at lines
20-26) so there's no "active" style to add; a future task could add
`IntersectionObserver`-driven active-tab styling but that's new behavior,
out of scope here.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/protein/ProteinHeader.vue frontend/src/pages/ProteinPage.vue
git commit -m "style: protein header (Archivo title, outline driver pill) + tab nav restyle"
```

Ask the user to run `npm run dev`, open `/protein/P35637`, and check the
header (large title, driver pill) and the sticky section nav.

---

### Task 10: Feature table, sequence block restyle

**Files:**
- Modify: `frontend/src/components/protein/ProteinFeatureTable.vue`
- Modify: `frontend/src/components/protein/ProteinSequence.vue`

**Interfaces:**
- No prop/emit changes to either component.

- [ ] **Step 1: `ProteinFeatureTable.vue` — mono group headers, token colors**

Replace `rowClass()` (`frontend/src/components/protein/ProteinFeatureTable.vue:12-16`):

```js
function rowClass(feature) {
  if (props.pinnedId === feature.id)  return 'bg-[#E8F1FB]'
  if (props.hoveredId === feature.id) return 'bg-slate-100'
  return ''
}
```

with:

```js
function rowClass(feature) {
  if (props.pinnedId === feature.id)  return 'bg-[#E8F1FB]'
  if (props.hoveredId === feature.id) return 'bg-page'
  return ''
}
```

Replace the group-header row (lines 23-33) text classes
`text-[#484E59] font-medium text-[10px]` → `font-mono text-[10.5px]
text-ink2 tracking-[0.07em]` (matches doc's "PFAM DOMAINS" style
uppercase mono label — note the group `label` strings from
`useProteinFeatures.js:27-32` are already capitalized words like
"Domain"/"Intrinsically Disordered Region", not uppercase; leave the
casing exactly as `FEATURE_TYPE_LABELS` already defines it, only the
CSS `tracking`/font changes — do not force `text-transform: uppercase`
since that would change how already-correct label text displays).
Replace border colors `border-slate-100`/`border-slate-50` (lines 24,
41, 60) with `border-border-soft`. Replace text tones
`text-[#484E59]`/`text-gray-700` (lines 47, 66, 69) with `text-ink3`/
`text-ink2` respectively.

- [ ] **Step 2: `ProteinSequence.vue` — border/background tokens only**

`ProteinSequence.vue` itself has no hardcoded stray colors needing
token swaps in its own markup — its container border/background comes
from the parent (`ProteinOverview.vue:129`:
`class="rounded border border-slate-200 bg-slate-50/60 px-3 py-2
overflow-x-auto"`). Change that parent wrapper to:

```html
      <div class="border border-border bg-page px-3.5 py-3 overflow-x-auto">
```

(drop `rounded` — doc §3: "sin bordes redondeados mayores a 2px", and a
sequence block has no rounding in any mockup). Inside
`ProteinSequence.vue` itself, update the residue-number/gutter text
color (`text-[#484E59]`, lines 251, 258) to `text-ink3`, and the pin
outline color (`#185FA5`, lines 235, 246) to `#1560A8` (same brand hex,
already correct — no change needed there, listed for completeness).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/protein/ProteinFeatureTable.vue \
        frontend/src/components/protein/ProteinOverview.vue \
        frontend/src/components/protein/ProteinSequence.vue
git commit -m "style: feature table + sequence block token colors, square sequence container"
```

Ask the user to run `npm run dev`, open `/protein/P35637`, and check the
feature table (group headers, row highlight on hover) and the sequence
block's border/background.

---

### Task 11: `ProteinMLOs.vue` — source matrix instead of per-row source text

**Files:**
- Modify: `frontend/src/components/protein/ProteinMLOs.vue`

**Interfaces:**
- Consumes: same `mloAnnotations`/`uniprotId` props, unchanged.
- Consumes: `dedupedAnnotations` (existing computed, unchanged) —
  restructured into a per-organelle × per-source-db matrix instead of
  one row per annotation.

This is a real structural change (spec §4.2's "matriz de fuentes"),
matching the Protein Page mock's "MLO annotations" tab table exactly
(5 fixed source columns instead of a `source_db` text column repeated
per row). It keeps every existing rule this component encodes: dedup key
`(unified_mlo, source_db, source_mlo)`, `NotInformed` filtering, and the
role-per-group logic (`groupRole()`).

- [ ] **Step 1: Replace `groupedRows` with a per-organelle matrix**

Replace `groupedRows` (`frontend/src/components/protein/ProteinMLOs.vue:63-105`):

```js
const groupedRows = computed(() => {
  if (!dedupedAnnotations.value.length) return []

  const groups = {}
  for (const ann of dedupedAnnotations.value) {
    const key = ann.unified_mlo
    if (!groups[key]) groups[key] = []
    groups[key].push(ann)
  }

  for (const mlo of Object.keys(groups)) {
    groups[mlo].sort((a, b) => {
      const ai = SOURCE_ORDER.indexOf(a.source_db)
      const bi = SOURCE_ORDER.indexOf(b.source_db)
      return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi)
    })
  }

  // Sort groups: driver annotations first, then by number of source DBs desc
  const sortedEntries = Object.entries(groups).sort(([, annsA], [, annsB]) => {
    const aIsDriver = annsA.some(a => a.unified_role === 'driver') ? 0 : 1
    const bIsDriver = annsB.some(b => b.unified_role === 'driver') ? 0 : 1
    if (aIsDriver !== bIsDriver) return aIsDriver - bIsDriver
    return annsB.length - annsA.length
  })

  const rows = []
  let groupIndex = 0
  for (const [, anns] of sortedEntries) {
    anns.forEach((ann, i) => {
      rows.push({
        isFirstInGroup: i === 0,
        groupIndex,
        unified_mlo:  ann.unified_mlo,
        displayRole:  i === 0 ? groupRole(anns) : null,
        source_db:    ann.source_db,
        source_mlo:   ann.source_mlo,
      })
    })
    groupIndex++
  }
  return rows
})
```

with (keep `groupRole()`, lines 41-61, unchanged — it's still called
per-organelle group below):

```js
const MATRIX_SOURCES = ['CDCODE', 'DrLLPS', 'LLPSDB', 'PhasePro', 'PhaSepDB']

const matrixRows = computed(() => {
  if (!dedupedAnnotations.value.length) return []

  const groups = {}
  for (const ann of dedupedAnnotations.value) {
    const key = ann.unified_mlo
    if (!groups[key]) groups[key] = []
    groups[key].push(ann)
  }

  const sortedEntries = Object.entries(groups).sort(([, annsA], [, annsB]) => {
    const aIsDriver = annsA.some(a => a.unified_role === 'driver') ? 0 : 1
    const bIsDriver = annsB.some(b => b.unified_role === 'driver') ? 0 : 1
    if (aIsDriver !== bIsDriver) return aIsDriver - bIsDriver
    return annsB.length - annsA.length
  })

  return sortedEntries.map(([unified_mlo, anns]) => ({
    unified_mlo,
    displayRole: groupRole(anns),
    cells: MATRIX_SOURCES.map(src => {
      const ann = anns.find(a => a.source_db === src)
      return {
        source: src,
        on:     !!ann,
        title:  ann ? `${src}: ${ann.source_mlo}` : `${src}: not annotated`,
      }
    }),
  }))
})
```

`SOURCE_ORDER` (line 11, the old 5-tag display-order constant used only
by the deleted per-row sort) becomes unused by this file — remove it if
nothing else in the file references it (`grep -n "SOURCE_ORDER"
frontend/src/components/protein/ProteinMLOs.vue` should show only the
declaration after this edit; if so, delete the declaration too).
`SOURCE_COLORS`/`sourceColor()` (lines 13-23) are also now unused (the
old per-row colored source-name text is gone) — remove them.

- [ ] **Step 2: Replace the table template**

Replace `frontend/src/components/protein/ProteinMLOs.vue:131-169` (the
`<table>` block) with:

```vue
      <table class="w-full border-collapse">
        <thead>
          <tr>
            <th class="text-left pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 tracking-[0.07em]">ORGANELLE</th>
            <th v-for="src in MATRIX_SOURCES" :key="src" class="text-center px-2 pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 w-[78px]">{{ src }}</th>
            <th class="text-right pl-3 pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 tracking-[0.07em]">ROLE</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in matrixRows" :key="row.unified_mlo" class="border-b border-border-soft">
            <td class="py-[11px] pr-3 text-[13.5px]">
              <RouterLink :to="`/mlo/${row.unified_mlo}`" class="text-ink hover:text-brand">{{ formatMlo(row.unified_mlo) }}</RouterLink>
            </td>
            <td v-for="cell in row.cells" :key="cell.source" :title="cell.title" class="py-[11px] px-2 text-center">
              <span v-if="cell.on" class="inline-block w-[7px] h-[7px] rounded-full bg-ink"></span>
              <span v-else class="inline-block w-[7px] h-px bg-border-strong"></span>
            </td>
            <td class="py-[11px] pl-3 text-right">
              <RoleBadge v-if="row.displayRole" :role="row.displayRole" />
            </td>
          </tr>
        </tbody>
      </table>
```

The header count line (`totalAnnotations`/`groupCount`,
`ProteinMLOs.vue:107-108, 116-119`) stays as-is (still real counts of
`dedupedAnnotations`/distinct organelles — the matrix collapses display,
not the underlying dedup). The intro paragraph
(`ProteinMLOs.vue:127-129`, "Table of annotations in source databases
...") is replaced to describe the new shape:

```vue
      <p class="text-[13.5px] text-ink3 max-w-[62ch] mb-6">
        A mark shows the organelle is annotated for this protein in that
        database. Hover a mark for the name the source itself uses.
      </p>
```

(matches the Protein Page mock's MLO-tab intro sentence pattern exactly,
adapted from generic "the source" to this protein specifically since
that's what the underlying data actually is — same sentence structure
already vetted for the Home coverage matrix in Task 6.)

- [ ] **Step 3: Verify removed identifiers are gone**

Run: `grep -n "groupedRows\|sourceColor\|SOURCE_COLORS" frontend/src/components/protein/ProteinMLOs.vue`

Expected: no matches.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/protein/ProteinMLOs.vue
git commit -m "feat(protein): source matrix in MLO annotations tab, replaces per-row source text"
```

Ask the user to run `npm run dev`, open `/protein/P35637`, click "MLO
Annotations", and check: one row per organelle, a filled dot under each
source that annotated it (with the source's own term in the tooltip),
role badge only where every annotation for that organelle is a regulator
call or at least one is a driver (existing `groupRole()` logic,
unchanged).

---

### Task 12: `ProteinPPI.vue` restyle

**Files:**
- Modify: `frontend/src/components/protein/ProteinPPI.vue`

**Interfaces:**
- No change to `getProteinPpi()` call, filter state, or graph data
  logic — this task only touches classes/colors in the template, plus
  the stats-header line (Step 1).

- [ ] **Step 1: Keep the BioGRID/STRING line's real count, restyle only**

Per spec §4.2's corrected finding: keep both external links, keep the
real `total_partners` count, only update classes. Replace
(`frontend/src/components/protein/ProteinPPI.vue:363-387`) the stats
header block's text classes: `text-sm text-[#484E59]` → `text-[13.5px]
text-ink3`; `font-semibold text-gray-800` → `font-semibold text-ink`;
link classes `text-[#185FA5] hover:underline` → `text-brand
hover:underline` (both BioGRID and STRING links, lines 378, 380);
`text-gray-400`/`text-gray-500` (lines 376, 369) → `text-muted`;
`text-xs text-gray-400` intro paragraph (line 384) → `text-[12.5px]
text-muted`. No copy string in this block changes.

- [ ] **Step 2: Filter pills and table**

Replace the role-filter pill group
(`frontend/src/components/protein/ProteinPPI.vue:393-401`) active/
inactive classes `bg-[#1B3D6F] text-white` / `bg-white text-gray-600
hover:bg-gray-50` with `bg-navy text-surface` / `bg-surface text-ink3
hover:text-ink`, and border `border-gray-200` → `border-border`. Table
header (lines 443-450) `bg-gray-50` → `bg-page`, `text-gray-500` →
`text-ink3`, and switch to mono per doc §4: add `font-mono text-[10.5px]
tracking-[0.07em]` to each `<th>`, removing `font-medium`. Row borders
`border-gray-100`/`border-gray-200` (lines 453, 466) → `border-border-
soft`. Role cell colors (line 481-483) `text-[#185FA5]`/`text-[#854F0B]`/
`text-gray-400` → `text-brand`/`text-regulator`/`text-ink3` (values, not
new copy — "Driver"/"Regulator"/"Component" strings unchanged).

- [ ] **Step 3: Graph legend and node colors**

Replace node-color function (`frontend/src/components/protein/ProteinPPI.vue:172-177`):

```js
function nodeColor(d) {
  if (d.isCenter)      return '#1B3D6F'
  if (d.has_driver)    return '#60A5FA'
  if (d.has_regulator) return '#854F0B'
  return '#9CA3AF'
}
```

with:

```js
function nodeColor(d) {
  if (d.isCenter)      return '#0E2136'
  if (d.has_driver)    return '#1560A8'
  if (d.has_regulator) return '#854F0B'
  return '#9CA3AF'
}
```

(navy for the query protein, brand blue for driver partners, the same
kept regulator amber, unchanged gray for components — `#9CA3AF` isn't a
document token, but it's a plain neutral gray already used for
"unremarkable/default" and the document doesn't ban all grays outside
its named list, only the specific ones it retired; leaving it is lower
risk than inventing a new gray with no spec backing). Update the legend
swatches (lines 531, 534, 537, 540) to match: `bg-[#1B3D6F]` →
`bg-navy`, `bg-[#60A5FA]` → `bg-brand`, `bg-[#854F0B]` stays (kept
regulator token, matches Task 1's `regulator` — could also write
`bg-regulator` here for consistency, do that instead of the literal
hex). Center-label fill (line 247) `#1B3D6F` → `#0E2136`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/protein/ProteinPPI.vue
git commit -m "style: PPI tab tokens (table, pills, graph colors), same BioGRID/STRING copy"
```

Ask the user to run `npm run dev`, open `/protein/P35637`, click
"Interactions", and check the table/graph colors match the new tokens
and the "N total known · BioGRID / STRING" line still shows the real
count with both working external links.

---

### Task 13: Router — split `/mlo/:mlo` from `/mlos`

**Files:**
- Modify: `frontend/src/router/index.js`
- Create: `frontend/src/pages/MloDetailPage.vue` (empty scaffold, filled in Task 14)

**Interfaces:**
- Produces: `/mlo/:mlo` now resolves to a distinct component from
  `/mlos`. `MlosPage.vue`'s own internal logic (which never reads
  `route.params.mlo`, confirmed during planning) is untouched by this
  task — it keeps working as the all-MLOs browse list exactly as today,
  just now only reachable at `/mlos` and via `ProteinMLOs.vue`/Home's
  `RouterLink :to="/mlo/${row.unified_mlo}"` calls, which is what those
  links already pointed at (no link text/target changes anywhere else in
  this plan).

- [ ] **Step 1: Split the route**

Replace `frontend/src/router/index.js:8`:

```js
  { path: '/mlo/:mlo',    component: () => import('@/pages/MlosPage.vue') },
```

with:

```js
  { path: '/mlo/:mlo',    component: () => import('@/pages/MloDetailPage.vue') },
```

Line 9 (`{ path: '/mlos', component: () => import('@/pages/MlosPage.vue') }`)
is unchanged.

- [ ] **Step 2: Scaffold `MloDetailPage.vue`**

Create `frontend/src/pages/MloDetailPage.vue`:

```vue
<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { getMlo } from '@/api/mlos'
import LoadingSpinner from '@/components/ui/LoadingSpinner.vue'

const route = useRoute()
const detail = ref(null)
const loading = ref(true)
const error = ref(false)

async function load(mlo) {
  loading.value = true
  error.value = false
  try {
    const res = await getMlo(mlo)
    detail.value = res.data
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

watch(() => route.params.mlo, (mlo) => { if (mlo) load(mlo) }, { immediate: true })
</script>

<template>
  <div class="max-w-[1080px] mx-auto px-8 py-10">
    <LoadingSpinner v-if="loading" />
    <div v-else-if="error" class="py-24 text-center text-sm text-ink3">
      MLO not found.
    </div>
  </div>
</template>
```

This is a deliberately minimal scaffold — real content is Task 14. It
exists as its own commit so routing can be verified independently of the
page's content.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/router/index.js frontend/src/pages/MloDetailPage.vue
git commit -m "feat(mlo): split /mlo/:mlo route to a new detail page, wire getMlo()"
```

Ask the user to run `npm run dev`, navigate to `/mlo/stress_granule`,
and confirm it no longer shows the full MLO list — either a brief
loading spinner then a blank page (expected, Task 14 fills it in) or the
"MLO not found" message for a bad slug, and that `/mlos` still shows the
full browsable list exactly as before.

---

### Task 14: `MloDetailPage.vue` — real content

**Files:**
- Modify: `frontend/src/pages/MloDetailPage.vue`

**Interfaces:**
- Consumes: `MloDetail` shape from `GET /mlo/{unified_mlo}`
  (`api/models/schemas.py:255-259`): `unified_mlo`, `spatial_location`,
  `taxonomic_scope`, `physiological_state`, `cell_type_context`,
  `spatial_location_evidence`, `taxonomic_support_n`, `definitions[]`
  (`{source_db, source_name, definition}`), `stats` (`{total_proteins,
  by_source, by_role, organisms}`), `proteins` (`{page, per_page, total,
  items[]}`, each item `{uniprot_id, gene_name, organism, unified_role,
  sources[], disorder_mobidb_lite_dc, disorder_alphafold_dc, idr_regions,
  lcr_regions, domains}`).
- Every field this task renders is one of the fields listed above —
  cross-check against spec §5.3 before adding anything not in this list.

- [ ] **Step 1: Header — axes, provenance caveats, stats**

Replace the `<template>` in `frontend/src/pages/MloDetailPage.vue`
(created in Task 13) with:

```vue
<script setup>
import { ref, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { getMlo } from '@/api/mlos'
import { formatMlo, formatCount } from '@/utils/format'
import {
  spatialLocationLabel, spatialLocationNote, isSpatialLocationProvisional,
  taxonomicScopeLabel, taxonomicScopeNote, isTaxonomicScopeThin,
  physiologicalStateLabel, cellTypeContextLabel,
} from '@/utils/mloAxes'
import RoleBadge from '@/components/ui/RoleBadge.vue'
import LoadingSpinner from '@/components/ui/LoadingSpinner.vue'

const route = useRoute()
const detail = ref(null)
const loading = ref(true)
const error = ref(false)
const roleFilter = ref('all')   // 'all' | 'driver' | 'component'

async function load(mlo) {
  loading.value = true
  error.value = false
  try {
    const res = await getMlo(mlo, roleFilter.value === 'all' ? {} : { role: roleFilter.value })
    detail.value = res.data
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

watch(() => route.params.mlo, (mlo) => { if (mlo) load(mlo) }, { immediate: true })
watch(roleFilter, () => load(route.params.mlo))

const MATRIX_SOURCES = ['CDCODE', 'DrLLPS', 'LLPSDB', 'PhasePro', 'PhaSepDB']

const headerStats = computed(() => {
  if (!detail.value) return []
  const s = detail.value.stats
  const sourceCount = Object.keys(s.by_source ?? {}).length
  return [
    { value: formatCount(s.total_proteins), label: 'PROTEINS' },
    { value: formatCount(s.by_role?.driver ?? 0), label: 'LLPS DRIVERS' },
    { value: sourceCount, label: 'SOURCES' },
  ]
})

// 3 real buckets (driver/regulator/component) -- NOT 4, see spec §5.3.
// component already absorbs NULL-role rows server-side
// (mlo_queries.py::get_mlo_stats()'s CASE `else` branch).
const roleRows = computed(() => {
  if (!detail.value) return []
  const by = detail.value.stats.by_role ?? {}
  const max = Math.max(1, ...Object.values(by))
  const ROLE_META = {
    driver:    { label: 'LLPS Drivers',    color: '#1560A8', description: 'Proteins with direct experimental evidence of driving liquid-liquid phase separation and/or MLO formation. Annotated as driver or scaffold in at least one source database.' },
    component: { label: 'MLO Components',  color: '#4E5762', description: 'Proteins associated with membraneless organelles without direct evidence of driving phase separation. Includes clients and proteins whose role no source determined.' },
    regulator: { label: 'MLO Regulators',  color: '#854F0B', description: 'Proteins a curator annotated as regulating an organelle rather than driving or residing in it. Curator-assigned in at least one source database.' },
  }
  return Object.entries(ROLE_META)
    .filter(([key]) => by[key] != null)
    .map(([key, meta]) => ({ ...meta, count: by[key], pct: Math.round((by[key] / max) * 100) }))
})

const termRows = computed(() => (detail.value?.definitions ?? []).map(d => ({
  source: d.source_db, term: d.source_name ?? d.definition ?? '—',
})))

const proteinRows = computed(() => (detail.value?.proteins?.items ?? []).map(p => ({
  uniprot_id: p.uniprot_id, gene_name: p.gene_name, organism: p.organism,
  role: p.unified_role, disorder: p.disorder_mobidb_lite_dc,
  sources: p.sources ?? [],
})))
</script>

<template>
  <div v-if="loading" class="max-w-[1080px] mx-auto px-8 py-16"><LoadingSpinner /></div>
  <div v-else-if="error" class="max-w-[1080px] mx-auto px-8 py-24 text-center text-sm text-ink3">
    MLO not found.
  </div>

  <template v-else-if="detail">
    <div class="bg-surface border-b border-border">
      <div class="max-w-[1080px] mx-auto px-8 pt-8 pb-9">
        <div class="font-mono text-[11.5px] text-ink3 mb-4">
          <RouterLink to="/mlos" class="text-brand hover:underline">MLOs</RouterLink>
          / {{ spatialLocationLabel(detail.spatial_location) }} / {{ formatMlo(detail.unified_mlo) }}
        </div>

        <div class="flex justify-between items-start gap-11 flex-wrap">
          <div>
            <h1 class="font-display font-bold text-[42px] leading-none tracking-[-0.035em] text-ink">{{ formatMlo(detail.unified_mlo) }}</h1>
            <div class="mt-4 font-mono text-xs text-ink3 flex gap-4 flex-wrap items-center">
              <span :title="spatialLocationNote(detail) || undefined" class="flex items-center gap-1.5"
                    :class="isSpatialLocationProvisional(detail) ? 'text-[#854F0B]' : ''">
                {{ spatialLocationLabel(detail.spatial_location) }}
                <span v-if="isSpatialLocationProvisional(detail)">· provisional</span>
              </span>
              <span v-if="detail.physiological_state">{{ physiologicalStateLabel(detail.physiological_state) }}</span>
              <span v-if="detail.cell_type_context">{{ cellTypeContextLabel(detail.cell_type_context) }}</span>
              <span v-if="detail.taxonomic_scope" :title="taxonomicScopeNote(detail)"
                    :class="isTaxonomicScopeThin(detail) ? 'text-[#854F0B]' : ''">
                {{ taxonomicScopeLabel(detail.taxonomic_scope) }}
                ({{ detail.taxonomic_support_n }}{{ isTaxonomicScopeThin(detail) ? ', thin' : '' }})
              </span>
            </div>
          </div>
          <div class="flex gap-9 flex-shrink-0">
            <div v-for="s in headerStats" :key="s.label">
              <div class="font-display font-semibold text-[28px] leading-none tracking-[-0.02em] text-ink">{{ s.value }}</div>
              <div class="font-mono text-[10.5px] text-ink3 tracking-[0.07em] mt-[7px]">{{ s.label }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <main class="max-w-[1080px] mx-auto px-8 py-11">
      <!-- Source terms mapped here -->
      <section class="mb-[62px]">
        <div class="flex items-baseline gap-3.5 border-b border-border pb-[11px] mb-3">
          <h2 class="text-[17px] font-medium tracking-[-0.01em] text-ink">Source terms mapped here</h2>
          <span class="font-mono text-[11px] text-muted">{{ termRows.length }} strings</span>
        </div>
        <p class="text-[13.5px] text-ink3 max-w-[64ch] mb-5">
          Every string below was collapsed into the unified term
          <em>{{ formatMlo(detail.unified_mlo) }}</em>. The original wording is
          preserved on each annotation, so a mapping decision can always be
          traced back.
        </p>
        <table class="w-full border-collapse">
          <thead>
            <tr>
              <th class="text-left pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 tracking-[0.07em]">SOURCE</th>
              <th class="text-left px-3 pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 tracking-[0.07em]">TERM AS WRITTEN IN THE SOURCE</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(t, i) in termRows" :key="i" class="border-b border-border-soft">
              <td class="py-2.5 pr-3 font-mono text-[11.5px] text-ink3 whitespace-nowrap">{{ t.source }}</td>
              <td class="py-2.5 px-3 text-[13.5px] text-ink">{{ t.term }}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <!-- Roles -->
      <section class="mb-[62px]" v-if="roleRows.length">
        <div class="border-b border-border pb-[11px] mb-5">
          <h2 class="text-[17px] font-medium tracking-[-0.01em] text-ink">Roles</h2>
        </div>
        <div class="flex flex-col gap-3.5">
          <div v-for="r in roleRows" :key="r.label">
            <div class="flex justify-between items-baseline gap-3">
              <span class="text-[13.5px] text-ink">{{ r.label }}</span>
              <span class="font-mono text-xs text-ink">{{ formatCount(r.count) }}</span>
            </div>
            <div class="h-[5px] bg-track rounded-[1px] mt-1.5">
              <div class="h-[5px] rounded-[1px]" :style="{ background: r.color, width: r.pct + '%' }"></div>
            </div>
            <div class="text-[12.5px] text-ink3 mt-1.5">{{ r.description }}</div>
          </div>
        </div>
      </section>

      <!-- Proteins -->
      <section>
        <div class="flex justify-between items-baseline gap-5 border-b border-border pb-[11px] mb-4.5">
          <div class="flex items-baseline gap-3.5">
            <h2 class="text-[17px] font-medium tracking-[-0.01em] text-ink">Proteins</h2>
            <span class="font-mono text-[11px] text-muted">{{ proteinRows.length }} shown of {{ formatCount(detail.stats.total_proteins) }}</span>
          </div>
          <div class="flex gap-2">
            <button
              v-for="opt in [['all','All'],['driver','Drivers'],['component','Components']]"
              :key="opt[0]"
              class="font-mono text-[11.5px] px-3 py-1.5 rounded-[2px]"
              :class="roleFilter === opt[0] ? 'border border-ink bg-ink text-page' : 'border border-border-strong text-ink2'"
              @click="roleFilter = opt[0]"
            >{{ opt[1] }}</button>
          </div>
        </div>
        <table class="w-full border-collapse">
          <thead>
            <tr>
              <th class="text-left pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 tracking-[0.07em]">GENE</th>
              <th class="text-right px-3 pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 tracking-[0.07em] w-[74px]">DISORDER</th>
              <th class="text-center px-3 pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 tracking-[0.07em] w-[96px]">SOURCES</th>
              <th class="text-right pl-3 pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 tracking-[0.07em] w-[82px]">ROLE</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in proteinRows" :key="p.uniprot_id" class="border-b border-border-soft">
              <td class="py-2.5 pr-3">
                <RouterLink :to="`/protein/${p.uniprot_id}`" class="text-[14px] font-medium text-ink hover:text-brand">{{ p.gene_name || p.uniprot_id }}</RouterLink>
                <span class="block font-mono text-[10.5px] text-muted mt-0.5">{{ p.uniprot_id }}</span>
              </td>
              <td class="py-2.5 px-3 text-right font-mono text-xs text-ink">{{ p.disorder != null ? Math.round(p.disorder * 100) + '%' : '—' }}</td>
              <td class="py-2.5 px-3">
                <div class="flex gap-1.5 justify-center">
                  <span v-for="src in MATRIX_SOURCES" :key="src" :title="p.sources.includes(src) ? src : `${src}: not annotated`"
                        class="inline-block" :class="p.sources.includes(src) ? 'w-[7px] h-[7px] rounded-full bg-ink' : 'w-[7px] h-px bg-border-strong mt-[3px]'"></span>
                </div>
              </td>
              <td class="py-2.5 pl-3 text-right">
                <RoleBadge v-if="p.role" :role="p.role" />
              </td>
            </tr>
          </tbody>
        </table>
      </section>
    </main>
  </template>
</template>
```

Every value rendered above traces to a field in the `MloDetail` shape
listed in this task's Interfaces block — no GO term, no "reversible"
tag, no per-species counts, no related-organelles section, no per-term
protein counts in the source-terms table (spec §5.3's five cuts). The
`ROLE` pill filter reuses `get_mlo_proteins_page`'s existing `role` query
param (`api/routers/mlos.py:34`, already accepts `role: str | None`) via
`getMlo(mlo, { role })` — `api/mlos.js:32`'s `getMlo(mlo, params = {})`
already forwards arbitrary params, no change needed there.

- [ ] **Step 2: Verify no cut field leaked back in**

Run: `grep -n "GO:\|reversible\|Related organelles\|species" frontend/src/pages/MloDetailPage.vue`

Expected: no matches (the word "species" specifically should not appear
— this page has no per-organism breakdown, unlike Home's organism
ranking which legitimately uses real per-organism counts from a
different endpoint).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/MloDetailPage.vue
git commit -m "feat(mlo): build MLO detail page content from real /mlo/{id} fields only"
```

Ask the user to run `npm run dev`, open `/mlo/stress_granule`, and
check: header shows all 4 axes with the provisional/thin-taxonomy
caveats where applicable, source-terms table lists real per-source
strings, roles section shows 2-3 bars (never a 4th "Unclassified"),
proteins table filters correctly by the Drivers/Components/All pills,
and every organelle link from `ProteinMLOs.vue` (Task 11) and Home's
coverage matrix (Task 6) now lands on this real page instead of the full
list.

---

### Task 15: `MlosPage.vue` (list) restyle

**Files:**
- Modify: `frontend/src/pages/MlosPage.vue`

**Interfaces:**
- No change to any of `MlosPage.vue`'s existing state/computed/API
  calls — `AXIS_FILTERS`, `axisFilters`, `selectedSources`, `sortBy`,
  `filtered`, `getMlos()`. Only template classes change.

This page is not one of the four mockups (the mocks only show the
single-MLO detail, now Task 14) — it gets the same token treatment as
everything else, keeping its existing list/filter/expand-collapse
behavior exactly as documented in `frontend/CLAUDE.md`.

- [ ] **Step 1: Header, filter bar, and card-row token pass**

Replace the header block (`frontend/src/pages/MlosPage.vue:4-7`) tokens:
`text-gray-800` → `text-ink`, `text-gray-600` → `text-ink3`. Replace the
filter bar container (line 10) `bg-white border border-gray-200
rounded-lg` → `bg-surface border border-border` (drop `rounded-lg` per
doc §3's no-rounded-corners-over-2px rule). Replace focus/border colors
throughout (`focus:border-[#185FA5]` at lines 32, 73 → `focus:border-
brand`; source-chip active state at lines 47-51,
`bg-[#185FA5]`/`border-[#185FA5]` → `bg-brand`/`border-brand`). Replace
the list container (line 104) `bg-white border border-gray-200 rounded-
lg` → `bg-surface border border-border`. Replace row hover
`hover:bg-slate-50` (line 108) → `hover:bg-page`, row divider
`border-gray-100` → `border-border-soft`.

- [ ] **Step 2: Axis badges — keep provisional/thin logic, retone colors**

The location badge's dashed-border "provisional" treatment
(`MlosPage.vue:128-138`) and the taxonomic thin-support styling (lines
164-169) are the exact caveats spec §0/§5.3 require preserving — do not
remove the `isSpatialLocationProvisional`/`isTaxonomicScopeThin`
conditionals or the dashed border. Only retone: `bg-slate-100
text-slate-600` (line 132) → `bg-page text-ink3`, `border-slate-300`/
`border-slate-200` (line 133) → `border-border-strong`/`border-border`,
`text-slate-400` (line 137) → `text-muted`. Physiological-state badge
(`bg-amber-50 text-[#854F0B] border-amber-200`, line 141) and cell-type
badge (`bg-teal-50 text-[#0F6E56] border-teal-200`, line 147) are left
as-is — these use colors outside the document's token set for two axes
the document never mentions styling, and inventing new tokens for them
isn't warranted by anything in the spec; changing them risks losing
the working distinction between axes for no documented reason.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/MlosPage.vue
git commit -m "style: retone MlosPage list to v3 tokens, keep all filter/expand behavior"
```

Ask the user to run `npm run dev`, open `/mlos`, and confirm every
filter (axis dropdowns, source chips, sort, text search) and the
expand/collapse-per-row behavior work exactly as before — only colors
and corner radii changed. Also click "Explore ... proteins" and confirm
it still navigates to `/results?mlo=...` (unchanged, `MlosPage.vue:189`).

---

### Task 16: Final cross-file sweep

**Files:** none new — verification only.

- [ ] **Step 1: Confirm no orphaned old hex values remain in touched files**

Run:
```bash
grep -rn "#1B4F8A\|#2B7CD8\|#1B3D6F\|#EBF3FB\|#C8DFF2\|#185FA5\|#484E59" \
  frontend/src/pages frontend/src/components \
  --include="*.vue" | grep -v "OLD/"
```

Any hit here is either (a) a file this plan didn't touch (out of scope —
Download/About/Data/Api pages, per spec §6's explicit "fuera de
alcance"; leave them) or (b) a missed spot in a file this plan did touch
— fix (b) inline with the same token mapping used in that file's task,
and commit as `style: fix missed v3 token in <file>`.

- [ ] **Step 2: Confirm route/prop contracts are untouched**

Run: `grep -n "path:" frontend/src/router/index.js`

Expected: same 8 routes as before this plan, with `/mlo/:mlo` now
pointing at `MloDetailPage.vue` (Task 13) and every other path
unchanged.

- [ ] **Step 3: Final ask to the user**

Ask the user to run `npm run build` (not `npm run dev` this time — a
production build catches template errors `npm run dev`'s HMR can mask)
and report any errors. This is the one point in the whole plan where a
build failure would mean an earlier task has a real bug (a typo'd class,
a removed identifier still referenced) rather than a intentional design
choice — if it fails, find which task's diff caused it via `git bisect`
or by re-reading that task's file, fix, and commit a follow-up fix tied
to that task's description.

---

## Self-review notes

- **Spec coverage**: §1 (tokens) → Task 1. §2 (Home) → Tasks 5-6. §3
  (Search Results) → Tasks 7-8. §4 (Protein Page) → Tasks 2, 9-12. §5
  (MLO detail) → Tasks 13-14. §5.3's "MlosPage list restyle separately"
  → Task 15. §7 ("cosas que el rediseño sacó a propósito") → gradient
  removed in Task 3; role-card colored top borders is Task 4 (kept the
  bar, retoned it — the document's list is about *not reintroducing* the
  old per-card top-border-color pattern from a prior design, not about
  removing all top bars; `RoleCards.vue`'s bar already existed
  pre-redesign as a single-purpose per-role divider, not the pattern the
  doc names — left as a judgment call in Task 4, flagged here for the
  user to veto if the reading is wrong); hero-embedded source links —
  confirmed absent in the current hero copy already (Task 5's replacement
  paragraph has no inline source links); repeated category labels
  row-by-row — fixed by Task 8/11's matrix pattern; truncated organism
  names — `formatOrganism()`/`shortOrganism()` already handle this,
  untouched; low-contrast grays — every `text-gray-400`-tier class this
  plan touches is retoned to `ink3`/`muted`, never left at the old
  `text-gray-400`.
- **Placeholder scan**: no task step says "handle appropriately" or
  defers a decision without stating the decision — every color/copy/
  structure choice is written out.
- **Type/name consistency checked**: `MATRIX_SOURCES` (Task 11, Task 14)
  and `SOURCE_ORDER` (Task 6, Task 8) are the same 5-tag list declared
  independently per-file (matches this codebase's existing pattern —
  `MlosPage.vue`'s own `SOURCE_DBS` is also a local per-file constant,
  not a shared import, per `frontend/CLAUDE.md`'s documented "four lists
  need the new tag" convention) — noted so a future source-DB addition
  updates all of them, consistent with the existing convention this plan
  didn't invent.
