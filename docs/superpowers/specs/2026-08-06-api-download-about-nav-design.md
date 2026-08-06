# Design: API, Download, and About nav sections

**Date**: 2026-08-06
**Status**: approved, pending implementation plan
**Scope**: fixes the broken `API`/`About` navbar links, builds a real `/api`
docs page and a `/download` bulk-export page (frontend + one new backend
endpoint). `AboutPage.vue` stays a stub — deliberately deferred until API and
Download are finished, since About is expected to grow into
About + Help + Stats once there's more to reference (see "Out of scope").

---

## 1. Navbar fix

**Problem**: [`AppNavbar.vue`](../../../frontend/src/components/layout/AppNavbar.vue)
has both "API" and "About" `RouterLink`s pointing at `/about` — there is no
`/api` route. `About`'s own link is correct; `API`'s is the bug.

**Fix**:
- Add `{ path: '/api', component: () => import('@/pages/ApiPage.vue') }` to
  `frontend/src/router/index.js`, lazy-loaded like every route except `/`.
- Change the "API" `RouterLink`'s `to` from `/about` to `/api` in
  `AppNavbar.vue`. No other change to the navbar.

---

## 2. `/api` page

**Purpose**: a human-friendly overview for someone who wants to consume the
API programmatically, that gets them to real answers fast without
duplicating what FastAPI already generates for free. FastAPI's default
`/docs` (Swagger UI) and `/redoc` are live today (`api/main.py` never
overrides `docs_url`/`redoc_url`) — this page complements them, it does not
replace or re-implement them.

**Nature**: fully static content, hardcoded in the component. No API calls
from this page — it's documentation *about* the API, not a consumer of it.
No new backend work.

### Content sections (in order)

1. **Intro** — 1-2 sentences: what the API is, that it's public/read-only,
   no API key required, no rate limit enforced today.
2. **Base URL** — `https://mlos.leloir.org.ar/api`, displayed as a copyable
   code block.
3. **Endpoint table** — the 10 rows from `api/CLAUDE.md`'s Endpoints table
   (method, path, one-line purpose), reproduced verbatim so the two stay in
   sync by inspection when `api/CLAUDE.md` changes.
4. **Curl example** — one real example: `GET /protein/{uniprot_id}` request
   and a trimmed response, sourced from `api/API_EXAMPLES.md`.
5. **Error format** — the error-envelope shape (`{ "error": ..., "message":
   ... }`) and the HTTP-code table from `api/CLAUDE.md`'s "Error envelope"
   section.
6. **Citation notice** — the citation block from the root `README.md` (Orti
   F, Fernández ML, Marino-Buslje C. *Protein Science.* 2024;33(1):e4858),
   framed as "if you use this data in derived work, please cite".
7. **Links out** — two prominent buttons/links to `/docs` and `/redoc` for
   full interactive reference.

### Component

- New file `frontend/src/pages/ApiPage.vue`. Single-file page component, no
  new sub-components needed — content is static enough to inline.
- Follows the existing page-body convention (`max-w-6xl mx-auto px-6` per
  `frontend/CLAUDE.md`'s layout notes), Tailwind utility classes only.

---

## 3. `/download` page + bulk export endpoint

### 3.1 Problem this solves

There is no clean, public, filterable bulk-export of the dataset today:

- `database/mlosmetadb.tsv` is the **pre-enrichment, pre-policy** integration
  input to `scripts/build_db.py` — no UniProt metadata, no sequence
  features, no PPI, no orthologs, and it includes `dataset_active=0` rows
  unfiltered. Not fit to serve as-is.
- `database/mlosmetadb.db` (252 MB) has everything, but also internal cache
  tables (`oma_cache`, `interpro_cache`, `mobidb_cache`, `uniprot_cache`)
  that aren't part of the public dataset, and likewise carries
  `dataset_active=0` rows unfiltered.

Decision (per user): build a real, filterable, on-demand export instead of
shipping either file. Grain is **one row per protein** (same shape as
`ProteinSummary`, what `/proteins` already returns) — not one row per
protein×MLO×source_db annotation. This means the new backend piece is an
unpaginated variant of an existing, well-understood query, not a new query
shape.

### 3.2 Backend: `GET /proteins/export`

New endpoint, added to the existing `api/routers/proteins.py` (same
resource family as `/proteins`, not a new router file).

**Query params**:

| Param | Values | Behavior |
|---|---|---|
| `organism` | exact organism string | same semantics as `/proteins`'s `organism` (`LOWER(p.organism) = LOWER(?)`) |
| `taxon_id` | int | same as `/proteins` |
| `mlo` | unified_mlo slug | same as `/proteins` |
| `role` | `driver` \| `component` | same as `/proteins` (no `client` value — `component` means "not driver, including NULL", via `policy.component_role_clause()`) |
| `source_db` | one or more, e.g. `?source_db=PhaseDB&source_db=CDCODE` | **new behavior**: `IN (...)` over all given values. `/proteins`'s existing `source_db` param stays single-value; this is a new param handled only inside the export query function, not a change to the existing one. |
| `fields` | `basic` \| `full` (default `full`) | column selection, see 3.3 |
| `format` | `tsv` \| `json` (default `tsv`) | output format, see 3.4 |

**New query function**: `get_proteins_export(...)` in
`api/queries/protein_queries.py`. Implementation note: factor the WHERE-clause
assembly shared with `get_proteins_page` (the `organism`/`taxon_id`/`mlo`/
`role` conditions block, lines ~94-111 today) into a small private helper
both functions call, rather than duplicating those conditions — the
`source_db` handling diverges (single-value `=` vs `IN`) so it's built
separately in each function. `get_proteins_export` drops `LIMIT`/`OFFSET`
entirely, with a defensive internal cap (`LIMIT 50000`) — unreachable today
at 15,879 proteins, purely a guard against a future data-scale surprise, not
a real product limit.

The query joins through `mlo_annotations` exactly like `get_proteins_page`
already does, which means `policy.active_annotation_clause` is inherited
automatically — the export is consistent with what the rest of the site
shows, by construction, not by a separate filter someone has to remember to
add.

### 3.3 `fields` column selection

- **`basic`**: `uniprot_id`, `gene_name`, `protein_name`, `organism`,
  `sequence_length`, `reviewed`.
- **`full`**: everything in `basic`, plus `has_driver`, `has_client`,
  `source_dbs`, `mlo_count`, `mlos`.

Sequence-feature fields (`idr_regions`, `lcr_regions`, `domains`) are
excluded from both — they're nested JSON blobs, not flat scalars, and don't
belong in a bulk tabular export. If per-protein feature detail is ever
wanted in a bulk export, that's a separate follow-up, not part of this spec.

### 3.4 `format` output

- **`tsv`**: `StreamingResponse`, `media_type="text/tab-separated-values"`,
  `Content-Disposition: attachment; filename="mlosmetadb_export.tsv"`.
  List-valued columns (`source_dbs`, `mlos`) are joined with `;` — same
  convention `formatPmids` already uses on the frontend for semicolon-joined
  lists, so the export format matches an existing precedent instead of
  inventing a new one.
- **`json`**: plain `JSONResponse`, an array of objects (`list[dict]`), list
  columns stay as real JSON arrays (no join). No pagination envelope
  (`total`/`page`/`filters_applied`) — this is a flat export, not a paged
  listing.

### 3.5 Frontend: `DownloadPage.vue`

Replaces the 5-line stub. Sections, top to bottom:

1. **Organism filter** — autocomplete, same pattern `FilterSidebar.vue`
   already uses (`searchOrganisms` from `src/api/proteins.js`), because the
   backend filter is an exact match, not a `LIKE` — free text would silently
   return zero rows on any typo/partial string.
2. **Role filter** — `<select>`: "All roles" (no param) / "Drivers only"
   (`role=driver`) / "Non-drivers" (`role=component`).
3. **Source DB filter** — checkboxes for the 6 source DBs (PhaseDB,
   PhasePDB, DrLLPS, LLPSDB, PhasePro, CD-CODE), multi-select, maps to
   repeated `source_db=` params.
4. **Fields toggle** — "Basic" / "With annotations" radio, maps to
   `fields=basic`/`fields=full`.
5. **Format toggle** — "TSV" / "JSON" radio, maps to `format=tsv`/`json`.
6. **Download button** — builds the query string from current UI state and
   sets `window.location.href` to `/api/proteins/export?...`. The browser
   handles the actual download natively via `Content-Disposition`; no
   fetch/Blob/loading-spinner plumbing needed since this is a GET navigation,
   not an XHR.

No new composable — this page's filter state is local `ref()`s, same as
`MlosPage.vue`'s filter bar (not URL-synced, per existing convention that
only `ResultsPage.vue` follows the URL-state pattern).

---

## Out of scope (deliberately deferred)

- **`AboutPage.vue`** stays a stub. Per user: About is expected to absorb
  Help and Stats content once API and Download exist to reference, so
  building it now would mean redoing it. Revisit after this spec ships.
- **Per-protein annotation-grain bulk export** (one row per protein × MLO ×
  source_db, matching `mlo_annotations`' own grain) — user explicitly chose
  protein-grain only for this round.
- **Per-protein feature/PPI/ortholog detail in the bulk export** — nested
  data, doesn't fit a flat tabular export; not requested.
- **Embedding Swagger UI inside the SPA** — considered and rejected in favor
  of linking out to FastAPI's existing `/docs`/`/redoc`.
- **Any change to `/proteins`'s existing `source_db` param** — the new
  multi-value `IN (...)` behavior is added only to the new export query
  function, not retrofitted onto the existing paginated endpoint.
