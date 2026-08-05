# Refactor `frontend/` Phase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the existing, working `frontend/` Vue 3 SPA into `refactor/frontend/`, verifying every endpoint it calls against the real `refactor/api/` (including the six endpoints never exercised end-to-end during the `api/` phase's own verification), fixing any wiring gaps found, then updating docs to match the corrected end state.

**Architecture:** Straight directory port (`frontend/` → `refactor/frontend/`, same `src/api/`/`components/`/`pages/`/`composables/`/`utils/` layout, no restructuring), dropping only dead Vite-scaffold cruft that nothing imports. No new features, no redesign — see `docs/superpowers/specs/2026-08-05-refactor-frontend-phase-design.md` for why this phase's scope was deliberately narrowed from an initial open-ended redesign consideration down to a mechanical port.

**Tech Stack:** Vue 3 (Composition API, `<script setup>` only), Vite 4, Tailwind CSS v3, Vue Router v4, Axios, D3.js v7, `@tanstack/vue-table`, plain JavaScript (no TypeScript, no test framework — this project has none for the frontend; verification is API-contract-based via `curl` plus a final human visual pass, matching this project's existing `npm run dev`-based convention).

## Global Constraints

- **Hard rule of the whole `refactor/` effort**: nothing outside `refactor/` is ever modified. `frontend/` at the repo root is the read-only source to copy from — **except** that this session already applied and committed five live bug fixes directly to `frontend/` during the pre-plan audit (commits `e799f6a`, `7188677`; see the design spec's Findings section). Those fixes are copied forward as part of this port like anything else in `frontend/` — they are not re-implemented, only carried over.
- **Claude never runs `npm`** (project convention, confirmed earlier this session): `npm install`, `npm run dev`, `npm run build` are always run by the user, who reports back errors or confirms success. Every task below that needs the dev server running says so explicitly and asks the user to run it — never attempts it via Bash.
- **API contract verification, not unit tests**: this codebase has zero frontend test files. "Test" in each task below means: `curl` the real `refactor/api/` endpoint (already running on `:8765` per this session, or restarted per Task 0), compare the JSON shape field-by-field against what the component's `<script setup>` destructures/binds, and fix any mismatch found. The final human-in-the-loop check (Task 5) is the user actually looking at the rendered page.
- **Explicitly deferred, do not fix in this plan** (from the design spec — these are pre-existing gaps in `frontend/` today, carried forward as documented known issues, not blockers): `RoleBadge.vue` has no style for `'client'`; `MlosPage.vue`'s `SOURCE_DBS` is a hardcoded list of 5 and its organism filter is a disabled "coming soon" `<select>`; deeper quality review of the Interactions/Orthologs tabs beyond "renders correctly against real data" is out of scope.
- **`TEST_PROTEINS` convention**: FUS (`P35637`), hnRNP A1 (`P09651`), eIF4A3 (`P38919`), RBM14 (`Q9NQC3`), FMR1 (`Q92520`, a confirmed pre-existing 404 — zero rows in `proteins`/`mlo_annotations`, not a bug). Plus `O23702`, whose only annotation is `dataset_active=0` (must render an empty MLO-annotations state, not crash or leak the excluded row).

---

## File Structure

```
refactor/
├── frontend/                          # NEW — ported from repo-root frontend/
│   ├── src/
│   │   ├── api/                       # ported unchanged (client.js, proteins.js, mlos.js, search.js, stats.js)
│   │   ├── components/
│   │   │   ├── layout/                # ported unchanged
│   │   │   ├── search/                # ported unchanged (SearchBox.vue, FilterSidebar.vue)
│   │   │   ├── browse/                # ported, already fixed (RoleCards.vue, OrganismGrid.vue), MloBadges.vue unchanged
│   │   │   ├── results/               # ported unchanged
│   │   │   ├── protein/               # ported, verified this phase (ProteinPPI.vue, ProteinOrthologs.vue, OrthologTrackViewer.vue, ProteinFeatureTrack.vue, ProteinHeader.vue, ProteinMLOs.vue)
│   │   │   ├── viewers/               # ported unchanged (MolStarViewer.vue — do not modify internals)
│   │   │   └── ui/                    # ported unchanged (RoleBadge.vue, SourceDbBadge.vue, StatBar.vue, LoadingSpinner.vue)
│   │   ├── pages/                     # ported, already fixed (ResultsPage.vue), rest unchanged
│   │   ├── composables/               # ported unchanged (useProtein.js)
│   │   ├── utils/                     # ported, already fixed (format.js)
│   │   ├── data/                      # ported unchanged (mlos.js, stats.json)
│   │   ├── router/                    # ported unchanged
│   │   ├── config.js                  # ported unchanged
│   │   ├── assets/                    # ported unchanged (main.css, base.css, organism SVGs, logo.svg)
│   │   ├── App.vue, main.js            # ported unchanged
│   │   # NOT ported (dead Vite scaffold, zero imports anywhere — confirmed via grep):
│   │   # components/HelloWorld.vue, components/TheWelcome.vue, components/WelcomeItem.vue,
│   │   # components/icons/*, views/AboutView.vue, views/HomeView.vue, stores/counter.js
│   ├── index.html, vite.config.js, tailwind.config.js, postcss.config.js   # ported unchanged
│   ├── package.json                    # ported unchanged
│   ├── CLAUDE.md                       # NEW (not copied from frontend/CLAUDE.md — that file's
│   │                                    # "Current implementation status" section is stale)
│   └── DEVLOG.md                       # NEW (first entry only, points at frontend/DEVLOG.md
│                                        # for full pre-port history and at this plan for the port itself)
└── REFACTOR_LOG.md                     # Entry 14 appended
```

---

### Task 0: Confirm `refactor/api/` is running and reachable

**Files:** none — this is an environment check, no commit.

**Interfaces:**
- Produces: a running `refactor/api/` on `127.0.0.1:8765`, which every later task's `curl` steps depend on.

- [ ] **Step 1: Check for an existing server**

```bash
ps aux | grep "uvicorn main:app" | grep -v grep
curl -s --noproxy '*' "http://127.0.0.1:8765/stats" | python3 -c "import json,sys; print(json.load(sys.stdin)['proteins']['total'])"
```

Expected: a running process, and `15879` printed (or close to it if the DB was rebuilt since). If nothing is running:

```bash
cd /path/to/mlosmetadb/refactor/api
nohup python3 -m uvicorn main:app --host 127.0.0.1 --port 8765 > /tmp/refactor-api-8765.log 2>&1 &
disown
sleep 4
curl -s --noproxy '*' "http://127.0.0.1:8765/stats" | python3 -c "import json,sys; print(json.load(sys.stdin)['proteins']['total'])"
```

Note the `--noproxy '*'` — this environment has `HTTP_PROXY`/`HTTPS_PROXY` set, which otherwise routes `127.0.0.1` requests through a Squid proxy that can't reach it, silently returning a Squid error page instead of a connection error.

- [ ] **Step 2: No commit for this task** — it's an environment check, not a code change.

---

### Task 1: Port `frontend/` → `refactor/frontend/`

**Files:**
- Create: `refactor/frontend/` (entire tree copied from `frontend/`, minus the exclusions below)

**Interfaces:**
- Produces: a working `refactor/frontend/` tree, importable/buildable exactly like the original (`vite.config.js`'s `outDir: '../api/static'` and dev-proxy target `http://localhost:8765` both already resolve correctly with zero edits, by the same one-directory-deeper construction as `refactor/api/config.py`'s `DB_PATH` in the `api/` phase).

- [ ] **Step 1: Copy the tree, excluding dead scaffold and build artifacts**

```bash
cd /path/to/mlosmetadb
mkdir -p refactor/frontend
rsync -a \
  --exclude='node_modules' \
  --exclude='dist' \
  --exclude='src/components/HelloWorld.vue' \
  --exclude='src/components/TheWelcome.vue' \
  --exclude='src/components/WelcomeItem.vue' \
  --exclude='src/components/icons' \
  --exclude='src/views' \
  --exclude='src/stores/counter.js' \
  --exclude='CLAUDE.md' \
  --exclude='DEVLOG.md' \
  frontend/ refactor/frontend/
```

The scaffold files are excluded because `grep -rln "HelloWorld\|TheWelcome\|WelcomeItem\|IconCommunity\|IconDocumentation\|IconEcosystem\|IconSupport\|IconTooling\|AboutView\|HomeView\|stores/counter" frontend/src --include="*.vue" --include="*.js"` (run during this plan's own research) returns **zero references outside the files themselves** — they are dead `create-vue` scaffold, never wired into `App.vue` or `router/index.js`. `CLAUDE.md`/`DEVLOG.md` are excluded because Task 5 writes fresh replacements (the existing `frontend/CLAUDE.md`'s "Current implementation status" table is stale — ProteinPage/MlosPage are marked as placeholders when they're actually fully implemented, per this session's own audit — a fresh file avoids copying that staleness forward).

- [ ] **Step 2: Verify the copy is complete and nothing extra came along**

```bash
diff -rq frontend/ refactor/frontend/ \
  --exclude=node_modules --exclude=dist \
  --exclude=HelloWorld.vue --exclude=TheWelcome.vue --exclude=WelcomeItem.vue \
  --exclude=icons --exclude=views --exclude=counter.js \
  --exclude=CLAUDE.md --exclude=DEVLOG.md
```

Expected: no output (identical trees modulo the excluded paths).

- [ ] **Step 3: Confirm `vite.config.js`'s path math resolves correctly with zero edits**

```bash
cat refactor/frontend/vite.config.js
```

Confirm `build.outDir` reads `'../api/static'` and `server.proxy['/api'].target` reads `'http://localhost:8765'`. Both already resolve correctly purely by `refactor/frontend/` sitting one level deeper (sibling to `refactor/api/`), exactly as `refactor/api/config.py`'s `DB_PATH` did in the `api/` phase — **do not add a path-fixup here if these values are already correct**, that would be an unnecessary edit to code that already does the right thing by construction.

- [ ] **Step 4: Ask the user to install dependencies and boot the dev server** (Claude never runs `npm`)

Tell the user:
> "Corré esto y confirmame si arranca sin errores:
> ```bash
> cd refactor/frontend
> npm install
> npm run dev
> ```
> Debería levantar en `localhost:5173` (o el próximo puerto libre) — avisame el resultado."

Wait for their confirmation before proceeding. If `npm install`/`npm run dev` errors, read the error together and fix the specific file it points at before continuing — do not guess ahead of the actual error.

- [ ] **Step 5: Commit**

```bash
git add refactor/frontend
git commit -m "$(cat <<'EOF'
refactor: port frontend/ into refactor/frontend/ (unmodified copy)

Straight copy of the working Vue 3 SPA, excluding dead create-vue
scaffold that nothing imports (HelloWorld.vue, TheWelcome.vue,
WelcomeItem.vue, components/icons/, views/, stores/counter.js --
confirmed zero references via grep) and the stale CLAUDE.md/DEVLOG.md
(fresh replacements land in a later task). No code changes yet --
vite.config.js's outDir and dev-proxy target already resolve correctly
by construction, one directory deeper than the original.
EOF
)"
```

---

### Task 2: Verify + fix ProteinPage's Interactions (PPI) and Orthologs tabs

**Files:**
- Modify (only if a mismatch is found): `refactor/frontend/src/components/protein/ProteinPPI.vue`, `refactor/frontend/src/components/protein/ProteinOrthologs.vue`, `refactor/frontend/src/components/protein/OrthologTrackViewer.vue`

**Interfaces:**
- Consumes: `GET /protein/{id}/ppi`, `GET /protein/{id}/orthologs` (both flagged in `API_EXAMPLES.md` as never verified end-to-end).
- Produces: no signature changes — these are leaf UI components with no other file depending on their internals.

- [ ] **Step 1: Capture the real PPI response shape**

```bash
curl -s --noproxy '*' "http://127.0.0.1:8765/protein/P35637/ppi?limit=500" | python3 -m json.tool | head -60
curl -s --noproxy '*' "http://127.0.0.1:8765/protein/P35637/ppi?limit=500" | python3 -c "
import json,sys
d = json.load(sys.stdin)
print('top-level keys:', list(d.keys()))
print('item keys:', list(d['items'][0].keys()))
print('has inter_edges:', 'inter_edges' in d, 'count:', len(d.get('inter_edges', [])))
"
```

Expected (already confirmed during this plan's research): top-level keys `uniprot_id, total, total_returned, items, inter_edges`; each item has `partner_uniprot_id, partner_gene, has_driver, mlos, experimental_systems, evidence_count, pubmed_ids`.

- [ ] **Step 2: Compare against `ProteinPPI.vue`'s expectations**

Read `refactor/frontend/src/components/protein/ProteinPPI.vue`. Confirm every field it reads off each partner object (`p.partner_uniprot_id`, `p.partner_gene`, `p.has_driver`, `p.mlos`, `p.experimental_systems`) and off the top-level response (`res.data.items`, `res.data.inter_edges`) is present in Step 1's real output with the same name and type (`mlos` an array of strings, `experimental_systems` an array of strings, `has_driver` a boolean). Also confirm `props.protein.ppi.total_partners`/`partners_in_mlosmetadb` (read from the already-loaded `/protein/{id}` response, not this endpoint) are present — check via:

```bash
curl -s --noproxy '*' "http://127.0.0.1:8765/protein/P35637" | python3 -c "import json,sys; print(json.load(sys.stdin)['ppi'])"
```

Expected: `{"total_partners": ..., "partners_in_mlosmetadb": ..., "interactions": null}` (the third field is intentionally unused by `ProteinPPI.vue`, which fetches its own data via `getProteinPpi` instead).

- [ ] **Step 3: Fix any mismatch found**

If a field name or shape differs from what the component expects, fix it in the component (not the API — the API's shape is the one just verified as the source of truth for this task; if the API itself looks wrong against `API_EXAMPLES.md`'s documented contract, stop and flag it rather than silently patching around it). There is no known mismatch as of this plan's writing — this step exists for whatever the live check turns up.

- [ ] **Step 4: Repeat Steps 1-3 for Orthologs**

```bash
curl -s --noproxy '*' "http://127.0.0.1:8765/protein/P35637/orthologs" | python3 -m json.tool
```

Expected top-level keys: `uniprot_id, total, organisms, orthologs`; each ortholog has `ortholog_id, organism, taxon_id, og_id, sources, in_db, gene_name, protein_name, length, disorder_mobidb_lite_dc, disorder_alphafold_dc, sequence, features`. Compare against `refactor/frontend/src/components/protein/ProteinOrthologs.vue`'s destructuring (`data.total`, `data.organisms`, `data.orthologs`, and per-ortholog `o.ortholog_id/organism/gene_name/length/disorder_mobidb_lite_dc/sources/in_db/features`) and `OrthologTrackViewer.vue`'s `tracks` prop shape (`id, organism, geneLabel, length, idrs, lcds, domains, morfs, isReference`, built by `ProteinOrthologs.vue`'s `tracks` computed). Fix any mismatch found the same way as Step 3.

- [ ] **Step 5: Ask the user to visually confirm both tabs**

> "`refactor/frontend/` corriendo — abrí `/protein/P35637`, click en la tab **Interactions**: ¿se ve la tabla de partners + el grafo D3? Click en **Orthologs**: ¿se ve la tabla comparativa + el visor de features por ortólogo? Contame si algo se ve roto o vacío cuando no debería."

Fix anything they report, re-running Steps 1-4's curl comparison against the specific field involved before guessing at a fix.

- [ ] **Step 6: Commit** (only if any fix was needed — if Steps 1-5 found nothing to fix, skip the commit, note "verified, no changes needed" in this plan's tracking, and move to Task 3)

```bash
git add refactor/frontend/src/components/protein/
git commit -m "$(cat <<'EOF'
fix: <specific field/shape mismatch found in PPI or Orthologs tab>

Found verifying refactor/frontend/ against the real refactor/api/ --
these two endpoints were never exercised end-to-end during the api/
phase's own verification (see API_EXAMPLES.md).
EOF
)"
```

---

### Task 3: Verify + fix `/mlos`, `/search`, `/search/advanced`, `/organisms/search` wiring

**Files:**
- Modify (only if a mismatch is found): `refactor/frontend/src/pages/MlosPage.vue`, `refactor/frontend/src/components/search/FilterSidebar.vue`, `refactor/frontend/src/pages/ResultsPage.vue`, `refactor/frontend/src/api/mlos.js`, `refactor/frontend/src/api/search.js`, `refactor/frontend/src/api/proteins.js`

**Interfaces:**
- Consumes: `GET /mlos`, `GET /search`, `GET /search/advanced`, `GET /organisms/search` (the remaining four of the six endpoints `API_EXAMPLES.md` flagged as never verified — PPI/Orthologs were Task 2).
- Produces: no signature changes.

- [ ] **Step 1: `/mlos` — verify against `MlosPage.vue`**

```bash
curl -s --noproxy '*' "http://127.0.0.1:8765/mlos" | python3 -c "
import json,sys
d = json.load(sys.stdin)
print('top-level keys:', list(d.keys()))
print('mlo item keys:', list(d['mlos'][0].keys()))
"
```

Expected: top-level `{"mlos": [...]}`; each item has `unified_mlo, category, protein_count, driver_count, sources, definitions` (the last being a list of `{source_db, source_name, definition}`). Confirm `refactor/frontend/src/pages/MlosPage.vue`'s `onMounted` (`res.data.mlos`) and template (`mlo.unified_mlo`, `mlo.category`, `mlo.protein_count`, `mlo.driver_count`, `mlo.sources`, `mlo.definitions`) match exactly. Also confirm `"NotInformed"` does **not** appear in the response (the `policy.EXCLUDED_MLO_CATEGORIES` fix from this session's audit, already committed):

```bash
curl -s --noproxy '*' "http://127.0.0.1:8765/mlos" | python3 -c "
import json,sys
names = [m['unified_mlo'] for m in json.load(sys.stdin)['mlos']]
assert 'NotInformed' not in names, 'NotInformed leaked into /mlos!'
print('OK, NotInformed correctly excluded,', len(names), 'MLOs listed')
"
```

- [ ] **Step 2: `/organisms/search` — verify against `FilterSidebar.vue`'s organism autocomplete**

```bash
curl -s --noproxy '*' "http://127.0.0.1:8765/organisms/search?q=hom" | python3 -m json.tool
curl -s --noproxy '*' "http://127.0.0.1:8765/organisms/search?q=ab"
```

Expected: `q=hom` (3 chars) returns `{"query": "hom", "results": [{"organism": ..., "protein_count": ...}, ...]}`; `q=ab` (2 chars) returns a 422 `invalid_parameter` error (min length 3). Confirm `refactor/frontend/src/components/search/FilterSidebar.vue`'s `onOrganismSearch()` already guards `orgSearch.value.length < 3` before calling `searchOrganisms` (it does, per this plan's research — this is a check, not expected to need a fix) and reads `res.data.results` (matches).

- [ ] **Step 3: `/search` and `/search/advanced` — verify against `ResultsPage.vue`'s text-search path**

```bash
curl -s --noproxy '*' "http://127.0.0.1:8765/search?q=FUS&mode=fuzzy" | python3 -c "
import json,sys
d = json.load(sys.stdin)
print('keys:', list(d.keys()))
print('proteins[0] keys:', list(d['proteins'][0].keys()) if d['proteins'] else 'no protein hits')
"
curl -s --noproxy '*' "http://127.0.0.1:8765/search/advanced?gene_name=FUS&sort_by=mlo_count&sort_order=desc" | python3 -c "
import json,sys
d = json.load(sys.stdin)
print('keys:', list(d.keys()))
print('facets:', d['facets'])
"
```

Expected: `/search` returns `{query, mode, total_hits, proteins, mlos}` with each protein having the full `ProteinSummary` shape (`uniprot_id, gene_name, protein_name, organism, sequence_length, disorder_mobidb_lite_dc, disorder_alphafold_dc, reviewed, idr_regions, lcr_regions, domains, has_driver, has_client, source_db_count, source_dbs, mlo_count, mlos, match_field`). `/search/advanced` returns the same `ProteinsResponse` shape as `/proteins` (`total, page, per_page, filters_applied, facets, proteins`), now with working `sort_by`/`sort_order` (this session's fix, already committed). Confirm `ResultsPage.vue`'s `runSearch()` and `ResultsPanel.vue`'s row rendering destructure exactly these fields — no new mismatch expected here (this exact path was live-tested extensively during this session's audit), but re-verify since the component is being checked fresh in its ported location.

- [ ] **Step 4: Fix any mismatch found**

Same rule as Task 2 Step 3: fix the frontend component to match the verified real API shape, not the other way around, unless the API itself contradicts its own documented contract in `API_EXAMPLES.md` — in that case stop and flag rather than silently patching.

- [ ] **Step 5: Ask the user to visually confirm**

> "Confirmá en el navegador: `/mlos` (grilla completa, sin 'NotInformed'), buscar un organismo en el sidebar de Results (3+ letras), y una búsqueda de texto ('FUS') con un sort aplicado. ¿Todo se ve bien?"

- [ ] **Step 6: Commit** (only if a fix was needed, same convention as Task 2 Step 6)

```bash
git add refactor/frontend/src/
git commit -m "$(cat <<'EOF'
fix: <specific field/shape mismatch found in /mlos, /search, or /organisms/search wiring>

Found verifying refactor/frontend/ against the real refactor/api/ --
these were never exercised end-to-end during the api/ phase's own
verification (see API_EXAMPLES.md).
EOF
)"
```

---

### Task 4: Full `TEST_PROTEINS` + edge-case regression pass

**Files:** none expected — this is a verification task. Any fix found gets committed against the specific file it touches, same pattern as Tasks 2-3.

**Interfaces:**
- Consumes: everything ported/fixed in Tasks 1-3.
- Produces: a signed-off end-to-end pass across every page, the input the final review (Task 6) treats as evidence the port actually works, not just that individual endpoints returned 200.

- [ ] **Step 1: Ask the user to walk every page for every `TEST_PROTEINS` case**

> "Última pasada completa antes de documentar. Con `refactor/frontend/` corriendo contra `refactor/api/`:
> 1. **Home** (`/`) — stats, role cards, organism grid, MLO grid (sin 'NotInformed').
> 2. **Results** (`/results`, `/results?role=driver`, y una búsqueda de texto) — filas, sort, filtros (organela, rol, organismo).
> 3. **`/protein/P35637`** (FUS) — las 4 tabs: Overview (AlphaFold + D3 track), MLO Annotations, Interactions, Orthologs.
> 4. **`/protein/O23702`** — su única anotación es `dataset_active=0`; la tab MLO Annotations debería verse vacía/razonable, no romper.
> 5. **`/protein/Q92520`** (FMR1) — 404 esperado (gap de datos preexistente, no un bug).
> 6. **`/mlos`** y un click en una MLO específica (`/mlo/nucleolus` o similar).
>
> Contame cualquier cosa que se vea rota, vacía cuando no debería, o distinta a lo que ya vimos en `frontend/` durante la auditoría de esta sesión."

- [ ] **Step 2: For anything reported, diagnose with the same curl-first method as Tasks 2-3**

Never guess a fix without first reproducing via `curl` against the specific endpoint involved, exactly as this session did for every bug found during the live audit (the `p_granule` facet bug, the `/search` sort bug, the `proteins` metadata gap, etc. — all found and fixed this way, not by inspection alone).

- [ ] **Step 3: Fix, commit each fix individually** (same commit-message convention as Tasks 2-3 — describe the specific bug found and fixed, not "fixed regression issues")

- [ ] **Step 4: Once the user confirms everything looks correct, this task is done — no separate commit for the pass itself, only for whatever fixes it produced**

---

### Task 5: Write `refactor/frontend/CLAUDE.md`, `DEVLOG.md`, update `REFACTOR_LOG.md` and `refactor/CLAUDE.md`

**Files:**
- Create: `refactor/frontend/CLAUDE.md`
- Create: `refactor/frontend/DEVLOG.md`
- Modify: `refactor/REFACTOR_LOG.md` (append Entry 14)
- Modify: `refactor/CLAUDE.md` (directory map, "Where to look" table, cross-project conventions section)

**Interfaces:**
- Consumes: the final, verified state from Tasks 1-4 (this task documents facts about already-working code, it does not change behavior).
- Produces: nothing consumed by later tasks — this is the last content task before the final review.

- [ ] **Step 1: Write `refactor/frontend/CLAUDE.md`**

Base it on `frontend/CLAUDE.md`'s structure (Stack, Directory structure, API endpoint→file mapping, Null handling, URL state, Routes, Layout/visual design, Color palette, Component conventions, What NOT to do) but with two corrections learned this session:
- The "Current implementation status" section must list `ProteinPage.vue`/`MlosPage.vue` as **done** (172 and 260 lines respectively, fully implemented — not placeholders, the mistake `frontend/CLAUDE.md` made). Only `DownloadPage.vue`/`AboutPage.vue` are genuine stubs.
- Add an explicit "Known deferred issues" section listing exactly the four items from the design spec's "Explicitly deferred" section (RoleBadge `'client'` style, `MlosPage.vue`'s hardcoded `SOURCE_DBS`/disabled organism filter, and the two just-confirmed-fine-but-worth-a-note items if Tasks 2-3 found nothing to fix there).
- Remove the stale `stores/`/`composables/useSearch.js`/`useMlos.js`/Pinia references — per this session's own file-tree audit, `stores/counter.js` was dead scaffold (dropped in Task 1) and only `composables/useProtein.js` actually exists; there is no `stores/search.js`/`protein.js`/`mlo.js`, no `useSearch.js`/`useMlos.js`. Document what's actually there, not the originally-planned-but-never-built structure.

- [ ] **Step 2: Write `refactor/frontend/DEVLOG.md`**

First entry, pointing at `frontend/DEVLOG.md` (full pre-port session history) and this plan (the port itself):

```markdown
# MLOsMetaDB Frontend — Dev Log (refactor/)

## 2026-08-05 — Port from frontend/ into refactor/frontend/

Ported per `docs/superpowers/plans/2026-08-05-refactor-frontend-phase.md`.
Full pre-port development history: `frontend/DEVLOG.md` (not copied forward
verbatim — that file's history belongs to the pre-refactor code; this file
starts fresh at the port).

See `refactor/REFACTOR_LOG.md` Entry 14 for the port narrative and
verification evidence.
```

- [ ] **Step 3: Append `refactor/REFACTOR_LOG.md` Entry 14**

Follow the exact narrative style of Entries 11-13 (each fix with before/after, verification evidence, any incident disclosed in full). Must cover: the port itself (Task 1), the dead-scaffold exclusion decision and why, every fix found during Tasks 2-4 with its curl-verified before/after (or "verified, no fix needed" for endpoints that checked out clean), and the five fixes from this session's pre-plan audit (already logged in this session's commits `e799f6a`/`7188677` — cross-reference them here rather than re-describing from scratch).

- [ ] **Step 4: Update `refactor/CLAUDE.md`**

- Remove: `` `frontend/` (Vue 3 SPA) is not part of this phase yet. `` (currently the last line of the "Directory map" section).
- Add `frontend/` to the directory map tree and add a `frontend/CLAUDE.md` row to the "Where to look" table (`| Frontend SPA structure, API wiring, deferred issues | [frontend/CLAUDE.md](frontend/CLAUDE.md) |`).
- Update the "Cross-project conventions" → "Frontend (later phase)" bullet to drop "(later phase)" — it's no longer later, it exists.

- [ ] **Step 5: Commit**

```bash
git add refactor/frontend/CLAUDE.md refactor/frontend/DEVLOG.md refactor/REFACTOR_LOG.md refactor/CLAUDE.md
git commit -m "$(cat <<'EOF'
docs: refactor/frontend/ CLAUDE.md + DEVLOG.md, REFACTOR_LOG Entry 14

Written from the actual verified end state (Tasks 1-4), not from the
original frontend/CLAUDE.md's plan-not-reality "Current implementation
status" table -- ProteinPage.vue/MlosPage.vue are fully implemented,
not placeholders; stores/ and most planned composables were never
built. refactor/CLAUDE.md updated to drop the "frontend/ doesn't exist
yet" note now that it does.
EOF
)"
```

---

### Task 6: Final full-branch review

**Files:** none — review only, no code changes unless the review finds something.

**Interfaces:**
- Consumes: the complete diff of every commit from this plan (Tasks 1-5) plus the pre-plan audit commits (`e799f6a`, `7188677`, and the design-spec commit `d21f978`).
- Produces: either a clean bill of health, or a list of findings to fix before this phase is considered done — mirroring the `api/` phase's own final-reviewer step (see `REFACTOR_LOG.md` Entry 11's "Also disclosed here, flagged by the final reviewer" note — that review caught something the phase's own tasks missed).

- [ ] **Step 1: Dispatch a review pass over the full diff**

Compare the entire `refactor/frontend/` tree against `frontend/` (excluding the deliberate scaffold drop from Task 1) plus every `refactor/api/`, `refactor/policy.py` change made during this phase, against:
- The design spec (`docs/superpowers/specs/2026-08-05-refactor-frontend-phase-design.md`) — does every finding it lists have a corresponding fix, carried forward correctly?
- This plan's Global Constraints — nothing outside `refactor/` modified except the five pre-committed `frontend/` fixes explicitly called out as an approved exception; no `npm` command ever run by Claude; every fix is curl-verified before being called done.
- `refactor/api/API_EXAMPLES.md` — are the six previously-unverified endpoints now demonstrably exercised (Tasks 2-3's evidence)?

- [ ] **Step 2: Fix anything the review finds**, following the same curl-first, commit-per-fix pattern as every prior task.

- [ ] **Step 3: If the review is clean, log that fact in `REFACTOR_LOG.md` Entry 14** (append to the entry from Task 5, don't create a new one) — one sentence, e.g. "Final full-branch review (Task 6): clean, no additional findings." If it found something, describe what and how it was fixed, matching the transparency convention every other entry in this log follows.

- [ ] **Step 4: Commit** (only if Step 2 produced changes beyond the Entry 14 update)

```bash
git add -A
git commit -m "$(cat <<'EOF'
docs: log final full-branch review result in REFACTOR_LOG Entry 14
EOF
)"
```

This is the last task of the `frontend/` phase. The next phase (not part of this plan) is the repo-root cutover — `OLD/` + promoting `refactor/*` to the actual root, becoming the new `main` — planned separately once this phase is verified complete.
