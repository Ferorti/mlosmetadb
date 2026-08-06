# API/Download Nav Sections Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the broken navbar API/About link, ship a static `/api` docs page, and add a filterable bulk-export endpoint (`GET /proteins/export`) plus a real `/download` page — leaving `AboutPage.vue` a stub, per the design spec.

**Architecture:** `ApiPage.vue` is fully static, no backend change. The export feature adds one new query function (`get_proteins_export`) and one new router endpoint to the existing `proteins` resource family, reusing the same `mlo_annotations`/`policy` join pattern `get_proteins_page` already uses so the export is filtered consistently with everything else on the site. `DownloadPage.vue` builds a URL from local filter state and navigates the browser to it, letting `Content-Disposition` trigger the native download — no fetch/Blob plumbing.

**Tech Stack:** FastAPI + aiosqlite (backend), Vue 3 Composition API + Tailwind (frontend). No new dependencies.

## Global Constraints

- Every query touching `mlo_annotations` must include `policy.active_annotation_clause()` — no query file hardcodes `dataset_active = 1` independently (see `api/CLAUDE.md`'s Serving policy section).
- `role` query param values are `driver` / `component` only — never `client` (see `policy.component_role_clause()`).
- `/proteins`'s existing single-value `source_db` param and `get_proteins_page`/`_build_proteins_conditions` are not modified — the new multi-value `IN (...)` behavior lives only in the new `get_proteins_export` function.
- Frontend: Vue 3 `<script setup>` only, Tailwind utility classes only, no new npm dependencies, data fetching only via `src/api/*.js` functions.
- Every error response keeps the existing uniform envelope: `{ "error": ..., "message": ... }`.
- Backend tests follow the existing `api/tests/conftest.py` fixture (`test_db`) verbatim — do not add or change rows in `FIXTURE`/`SCHEMA`; write new assertions against the existing four fixture proteins (`P35637`, `QREG01`, `PCLIENT`, `PNULLROLE`).

---

### Task 1: Navbar fix + static `/api` docs page

**Files:**
- Modify: `frontend/src/components/layout/AppNavbar.vue:22`
- Modify: `frontend/src/router/index.js`
- Create: `frontend/src/pages/ApiPage.vue`

**Interfaces:**
- Consumes: nothing new — static content only.
- Produces: route `/api` → `ApiPage.vue`, reachable from the navbar's "API" link.

- [ ] **Step 1: Fix the navbar link**

In `frontend/src/components/layout/AppNavbar.vue`, change line 22 from:

```html
<RouterLink to="/about"    active-class="text-white font-medium" class="text-blue-100 hover:text-white text-sm transition-colors">API</RouterLink>
```

to:

```html
<RouterLink to="/api"      active-class="text-white font-medium" class="text-blue-100 hover:text-white text-sm transition-colors">API</RouterLink>
```

(Leave the `About` `RouterLink` on line 24 untouched — it already correctly points to `/about`.)

- [ ] **Step 2: Add the `/api` route**

In `frontend/src/router/index.js`, add a new route entry after the `/mlos` route and before `/download`, matching the existing lazy-import style:

```js
  { path: '/api',         component: () => import('@/pages/ApiPage.vue') },
```

Full resulting `routes` array:

```js
const routes = [
  { path: '/',            component: HomePage },
  { path: '/results',     component: () => import('@/pages/ResultsPage.vue') },
  { path: '/protein/:id', component: () => import('@/pages/ProteinPage.vue') },
  { path: '/mlo/:mlo',    component: () => import('@/pages/MlosPage.vue') },
  { path: '/mlos',        component: () => import('@/pages/MlosPage.vue') },
  { path: '/api',         component: () => import('@/pages/ApiPage.vue') },
  { path: '/download',    component: () => import('@/pages/DownloadPage.vue') },
  { path: '/about',       component: () => import('@/pages/AboutPage.vue') },
]
```

- [ ] **Step 3: Write `ApiPage.vue`**

Create `frontend/src/pages/ApiPage.vue` with this exact content:

```vue
<script setup>
const BASE_URL = 'https://mlos.leloir.org.ar/api'

const ENDPOINTS = [
  { method: 'GET', path: '/protein/{uniprot_id}', purpose: 'Full protein record: metadata, MLO annotations, sequence features, PPI summary' },
  { method: 'GET', path: '/protein/{uniprot_id}/ppi', purpose: 'Full PPI partner list for one protein, with optional role/mlo filters and inter-partner edges' },
  { method: 'GET', path: '/protein/{uniprot_id}/orthologs', purpose: 'OMA-derived orthologs across the 9 target organisms' },
  { method: 'GET', path: '/proteins', purpose: 'Paginated protein list with filters (organism, taxon_id, mlo, role, source_db, uniprot_id) + facets' },
  { method: 'GET', path: '/mlo/{unified_mlo}', purpose: 'One MLO’s definitions (per source), aggregate stats, and paginated protein list' },
  { method: 'GET', path: '/mlos', purpose: 'Full canonical MLO vocabulary (no pagination)' },
  { method: 'GET', path: '/search', purpose: 'Basic search over gene names / UniProt IDs / protein names / MLO names' },
  { method: 'GET', path: '/search/advanced', purpose: 'Multi-filter search (gene, organism, taxon, mlo, role, source_db, sequence-feature filters)' },
  { method: 'GET', path: '/stats', purpose: 'Global counts — proteins, mlo_annotations, sequence_features, ppi' },
  { method: 'GET', path: '/organisms/search', purpose: 'Organism-name autocomplete (min 3 chars)' },
]

const ERROR_CODES = [
  { situation: 'Protein not in proteins', http: 404, error: 'protein_not_found' },
  { situation: 'MLO not in mlo_vocabulary', http: 404, error: 'mlo_not_found' },
  { situation: 'Invalid query parameter (bad sort_by, bad sort_order, etc.)', http: 422, error: 'invalid_parameter' },
  { situation: 'q shorter than the endpoint’s minimum length', http: 422, error: 'invalid_parameter' },
  { situation: 'No filters given to /search/advanced', http: 422, error: 'no_filters_provided' },
  { situation: 'mode=exact requested but FTS5 unavailable', http: 501, error: 'fts5_unavailable' },
  { situation: 'Any database error', http: 500, error: 'database_error' },
]

const CURL_EXAMPLE = `curl "${BASE_URL}/protein/A1ZBW4"`

const RESPONSE_EXAMPLE = `{
  "uniprot_id": "A1ZBW4",
  "gene_name": "HnRNP-K",
  "protein_name": null,
  "organism": "Drosophila melanogaster",
  "taxon_id": 7227,
  "sequence_length": 315,
  "disorder_mobidb_lite_dc": 0.502,
  "disorder_alphafold_dc": null,
  "mlo_annotations": [
    {
      "unified_mlo": "in_vitro_droplet",
      "category": "In vitro",
      "source_db": "LLPSDB",
      "source_mlo": "in vitro droplet",
      "unified_role": "driver",
      "evidence_pmids": ["32302572"]
    }
  ],
  "sequence_features": {
    "idrs": [
      { "start": 1, "end": 69, "score": null, "source": "MobiDB-lite" }
      // ... more IDR regions
    ],
    "domains": [
      { "start": 245, "end": 308, "label": "KH domain", "accession": "PF00013", "database": "pfam" }
    ],
    "lcds": [ /* ... */ ],
    "morfs": [],
    "plddt_regions": []
  },
  "ppi": {
    "total_partners": 0,
    "partners_in_mlosmetadb": 0,
    "interactions": null
  }
}`

const ERROR_EXAMPLE = `{ "error": "protein_not_found", "message": "No protein with UniProt ID 'Q92520'" }`
</script>

<template>
  <div class="max-w-6xl mx-auto px-6 py-8">
    <!-- Page header -->
    <div class="mb-6">
      <h1 class="text-2xl font-semibold text-gray-800">API</h1>
      <p class="text-sm text-gray-600 mt-1">
        MLOsMetaDB's REST API is public and read-only — no API key required, no rate
        limit enforced today.
      </p>
    </div>

    <!-- Base URL -->
    <section class="mb-8">
      <h2 class="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-2">Base URL</h2>
      <code class="block bg-gray-900 text-gray-100 text-sm rounded px-4 py-2 font-mono">{{ BASE_URL }}</code>
    </section>

    <!-- Endpoint table -->
    <section class="mb-8">
      <h2 class="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-2">Endpoints</h2>
      <div class="overflow-x-auto border border-gray-200 rounded-lg">
        <table class="w-full text-sm">
          <thead class="bg-gray-50 text-left text-gray-600">
            <tr>
              <th class="px-4 py-2 font-medium">Method</th>
              <th class="px-4 py-2 font-medium">Path</th>
              <th class="px-4 py-2 font-medium">Purpose</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="ep in ENDPOINTS" :key="ep.path" class="border-t border-gray-100">
              <td class="px-4 py-2 font-mono text-[#185FA5]">{{ ep.method }}</td>
              <td class="px-4 py-2 font-mono text-gray-800">{{ ep.path }}</td>
              <td class="px-4 py-2 text-gray-600">{{ ep.purpose }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Curl example -->
    <section class="mb-8">
      <h2 class="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-2">Example</h2>
      <pre class="bg-gray-900 text-gray-100 text-sm rounded px-4 py-3 overflow-x-auto"><code>{{ CURL_EXAMPLE }}</code></pre>
      <pre class="bg-gray-50 border border-gray-200 text-gray-800 text-xs rounded px-4 py-3 overflow-x-auto mt-2"><code>{{ RESPONSE_EXAMPLE }}</code></pre>
    </section>

    <!-- Error format -->
    <section class="mb-8">
      <h2 class="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-2">Error format</h2>
      <p class="text-sm text-gray-600 mb-2">
        Every error response, regardless of endpoint, has this shape:
      </p>
      <pre class="bg-gray-50 border border-gray-200 text-gray-800 text-xs rounded px-4 py-3 overflow-x-auto"><code>{{ ERROR_EXAMPLE }}</code></pre>
      <div class="overflow-x-auto border border-gray-200 rounded-lg mt-3">
        <table class="w-full text-sm">
          <thead class="bg-gray-50 text-left text-gray-600">
            <tr>
              <th class="px-4 py-2 font-medium">Situation</th>
              <th class="px-4 py-2 font-medium">HTTP</th>
              <th class="px-4 py-2 font-medium">error</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="ec in ERROR_CODES" :key="ec.error + ec.http" class="border-t border-gray-100">
              <td class="px-4 py-2 text-gray-600">{{ ec.situation }}</td>
              <td class="px-4 py-2 font-mono text-gray-800">{{ ec.http }}</td>
              <td class="px-4 py-2 font-mono text-[#185FA5]">{{ ec.error }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Citation -->
    <section class="mb-8">
      <h2 class="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-2">Citation</h2>
      <p class="text-sm text-gray-600">
        If you use this data in derived work, please cite:
      </p>
      <p class="text-sm text-gray-800 mt-1">
        Orti F, Fernández ML, Marino-Buslje C. <em>Protein Science.</em> 2024;33(1):e4858.
        <a href="https://doi.org/10.1002/pro.4858" class="text-[#185FA5] hover:underline" target="_blank" rel="noopener">
          https://doi.org/10.1002/pro.4858
        </a>
      </p>
    </section>

    <!-- Links out -->
    <section class="flex gap-3">
      <a
        href="/docs"
        target="_blank"
        rel="noopener"
        class="inline-flex items-center px-4 py-2 rounded bg-[#185FA5] text-white text-sm font-medium hover:bg-[#0F4A87] transition-colors"
      >
        Interactive docs (Swagger) →
      </a>
      <a
        href="/redoc"
        target="_blank"
        rel="noopener"
        class="inline-flex items-center px-4 py-2 rounded border border-[#185FA5] text-[#185FA5] text-sm font-medium hover:bg-[#EBF3FB] transition-colors"
      >
        Reference docs (ReDoc) →
      </a>
    </section>
  </div>
</template>
```

Note: the `’`/`→`/etc. escapes above are literal Unicode characters (’, →, —, ó) — write them as the actual UTF-8 characters in the file, not as the escape sequences.

- [ ] **Step 4: Manually verify in the browser**

Run:
```bash
cd frontend && npm run dev
```
Open `http://localhost:5173/` (or the port Vite prints), click "API" in the navbar, and confirm:
- URL becomes `/api` (not `/about`).
- The endpoint table, curl example, error table, citation, and both `/docs`/`/redoc` links render.
- Clicking "About" still goes to `/about` (unchanged stub).
- The two "links out" buttons open `/docs` and `/redoc` in a new tab (these routes are served by the FastAPI backend directly, so they 404 unless `api/main.py` is also running on the same origin the frontend proxies to — confirming this is a manual check, not a hard requirement of this task).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/layout/AppNavbar.vue frontend/src/router/index.js frontend/src/pages/ApiPage.vue
git commit -m "feat: fix API navbar link, add static /api docs page"
```

---

### Task 2: `get_proteins_export` query function

**Files:**
- Modify: `api/queries/protein_queries.py`
- Test: `api/tests/test_protein_queries.py`

**Interfaces:**
- Consumes: `policy.active_annotation_clause(alias)`, `policy.component_role_clause(alias)` (both already imported as `policy` at the top of `protein_queries.py`), `database.fetchall(sql, params)`.
- Produces: `async def get_proteins_export(organism: str | None, taxon_id: int | None, mlo: str | None, role: str | None, source_dbs: list[str] | None) -> list[dict]` — rows shaped like `get_proteins_page`'s SELECT (`uniprot_id, gene_name, protein_name, organism, sequence_length, reviewed, has_driver, has_client, source_db_count, mlo_count, mlos, source_dbs`), unpaginated (capped at 50,000 rows). Task 3 imports and calls this.

- [ ] **Step 1: Write the failing tests**

Append to `api/tests/test_protein_queries.py`:

```python
from queries.protein_queries import get_proteins_export


def test_get_proteins_export_no_filters_returns_all_proteins(test_db):
    rows = asyncio.run(get_proteins_export(None, None, None, None, None))
    ids = {r["uniprot_id"] for r in rows}
    assert ids == {"P35637", "PCLIENT", "PNULLROLE", "QREG01"}


def test_get_proteins_export_excludes_inactive_regulator_row(test_db):
    rows = asyncio.run(get_proteins_export(None, None, None, None, ["DrLLPS"]))
    assert rows == []


def test_get_proteins_export_source_db_filter_is_multi_value(test_db):
    rows = asyncio.run(get_proteins_export(None, None, None, None, ["PhaseDB", "CDCODE"]))
    ids = {r["uniprot_id"] for r in rows}
    assert ids == {"P35637", "PCLIENT", "PNULLROLE"}


def test_get_proteins_export_role_component_includes_null_and_client(test_db):
    rows = asyncio.run(get_proteins_export(None, None, None, "component", None))
    ids = {r["uniprot_id"] for r in rows}
    assert "PNULLROLE" in ids
    assert "PCLIENT" in ids
    assert "P35637" not in ids
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd api && python3 -m pytest tests/test_protein_queries.py -v -k export
```
Expected: all 4 new tests FAIL with `ImportError: cannot import name 'get_proteins_export'`.

- [ ] **Step 3: Implement `get_proteins_export`**

In `api/queries/protein_queries.py`, add this function right after `get_proteins_facets` ends (i.e. right before the `# ── single protein ──` comment block, after line 279's `return {"by_organism": ...}`):

```python
async def get_proteins_export(
    organism: str | None,
    taxon_id: int | None,
    mlo: str | None,
    role: str | None,
    source_dbs: list[str] | None,
) -> list[dict]:
    """Unpaginated protein list for bulk export. Deliberately NOT reusing
    _build_proteins_conditions: source_dbs here is a list matched via
    IN (...), while every caller of that helper takes a single source_db
    matched via '='. Sharing it would require source_dbs to participate in
    its needs_mlo/join decision too, which isn't worth threading through a
    function three other call sites already depend on."""
    conditions: list[str] = []
    params: list = []
    needs_mlo = any([mlo, role, source_dbs])

    from_clause = "FROM proteins p"
    if needs_mlo:
        active = policy.active_annotation_clause("ma")
        from_clause += f" JOIN mlo_annotations ma ON p.uniprot_id = ma.uniprot_id AND {active}"

    if organism:
        conditions.append("LOWER(p.organism) = LOWER(?)")
        params.append(organism)
    if taxon_id is not None:
        conditions.append("p.taxon_id = ?")
        params.append(taxon_id)
    if mlo:
        conditions.append("ma.unified_mlo = ?")
        params.append(mlo)
    if role:
        if role.lower() == "component":
            conditions.append(policy.component_role_clause("ma"))
        else:
            conditions.append("LOWER(ma.unified_role) = LOWER(?)")
            params.append(role)
    if source_dbs:
        placeholders = ",".join("?" * len(source_dbs))
        conditions.append(f"ma.source_db IN ({placeholders})")
        params.extend(source_dbs)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    return await fetchall(
        f"""
        WITH filtered AS (
            SELECT DISTINCT p.uniprot_id
            {from_clause} {where}
            ORDER BY p.uniprot_id
            LIMIT 50000
        )
        SELECT p.uniprot_id, p.gene_name, p.protein_name, p.organism,
               p.length AS sequence_length, p.reviewed,
               ps.has_driver, ps.has_client, ps.source_db_count, ps.mlo_count, ps.mlos,
               ps.source_dbs
        FROM filtered f
        JOIN proteins p          ON p.uniprot_id  = f.uniprot_id
        JOIN protein_summary ps  ON ps.uniprot_id = f.uniprot_id
        ORDER BY p.uniprot_id
        """,
        tuple(params),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd api && python3 -m pytest tests/test_protein_queries.py -v
```
Expected: all tests in the file PASS, including the 4 new ones and every pre-existing test (confirming no regression to `get_proteins_page`/`get_proteins_facets`, which this task did not touch).

- [ ] **Step 5: Commit**

```bash
git add api/queries/protein_queries.py api/tests/test_protein_queries.py
git commit -m "feat: add get_proteins_export query for bulk protein export"
```

---

### Task 3: `GET /proteins/export` endpoint

**Files:**
- Modify: `api/routers/proteins.py`
- Test: `api/tests/test_proteins_router.py`

**Interfaces:**
- Consumes: `get_proteins_export(organism, taxon_id, mlo, role, source_dbs) -> list[dict]` from Task 2; `_parse_mlos`, `_parse_source_dbs` (already defined in `proteins.py`, lines 58-71).
- Produces: route `GET /proteins/export` with query params `organism`, `taxon_id`, `mlo`, `role`, `source_db` (repeatable), `fields` (`basic`|`full`, default `full`), `format` (`tsv`|`json`, default `tsv`). Also produces two importable pure helpers Task 3's own tests use directly: `_build_export_record(row: dict, fields: str) -> dict` and `_records_to_tsv(records: list[dict], columns: list[str]) -> str`, plus the constants `_EXPORT_BASIC_FIELDS: list[str]` and `_EXPORT_FULL_FIELDS: list[str]`.

- [ ] **Step 1: Write the failing tests**

Append to `api/tests/test_proteins_router.py`:

```python
from routers.proteins import _build_export_record, _records_to_tsv, _EXPORT_BASIC_FIELDS, _EXPORT_FULL_FIELDS


def test_build_export_record_basic_omits_annotation_fields():
    row = {
        "uniprot_id": "P1", "gene_name": "G1", "protein_name": "N1", "organism": "Homo sapiens",
        "sequence_length": 100, "reviewed": 1, "has_driver": 1, "has_client": 0,
        "source_dbs": '["PhaseDB","CDCODE"]', "mlo_count": 2, "mlos": '["a","b"]',
    }
    record = _build_export_record(row, "basic")
    assert set(record.keys()) == set(_EXPORT_BASIC_FIELDS)


def test_build_export_record_full_parses_json_lists():
    row = {
        "uniprot_id": "P1", "gene_name": "G1", "protein_name": "N1", "organism": "Homo sapiens",
        "sequence_length": 100, "reviewed": 1, "has_driver": 1, "has_client": 0,
        "source_dbs": '["PhaseDB","CDCODE"]', "mlo_count": 2, "mlos": '["a","b"]',
    }
    record = _build_export_record(row, "full")
    assert set(record.keys()) == set(_EXPORT_FULL_FIELDS)
    assert record["mlos"] == ["a", "b"]
    assert record["source_dbs"] == ["PhaseDB", "CDCODE"]
    assert record["has_driver"] is True


def test_records_to_tsv_joins_lists_with_semicolon():
    records = [{"uniprot_id": "P1", "mlos": ["a", "b"], "source_dbs": ["PhaseDB", "CDCODE"]}]
    tsv = _records_to_tsv(records, ["uniprot_id", "mlos", "source_dbs"])
    lines = tsv.strip().split("\n")
    assert lines[0] == "uniprot_id\tmlos\tsource_dbs"
    assert lines[1] == "P1\ta;b\tPhaseDB;CDCODE"


def test_records_to_tsv_none_becomes_empty_string():
    tsv = _records_to_tsv([{"uniprot_id": "P1", "gene_name": None}], ["uniprot_id", "gene_name"])
    assert tsv.strip().split("\n")[1] == "P1\t"


def test_records_to_tsv_header_present_with_zero_rows():
    tsv = _records_to_tsv([], ["uniprot_id", "gene_name"])
    assert tsv.strip() == "uniprot_id\tgene_name"


def test_export_endpoint_json_default_returns_all_proteins(test_db):
    with TestClient(app) as client:
        r = client.get("/proteins/export")
    assert r.status_code == 200
    ids = {row["uniprot_id"] for row in r.json()}
    assert ids == {"P35637", "PCLIENT", "PNULLROLE", "QREG01"}


def test_export_endpoint_source_db_filter_excludes_inactive_regulator(test_db):
    with TestClient(app) as client:
        r = client.get("/proteins/export", params={"source_db": ["DrLLPS"]})
    assert r.status_code == 200
    assert r.json() == []


def test_export_endpoint_tsv_has_attachment_header_and_basic_columns(test_db):
    with TestClient(app) as client:
        r = client.get("/proteins/export", params={"format": "tsv", "fields": "basic"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/tab-separated-values")
    assert 'attachment; filename="mlosmetadb_export.tsv"' in r.headers["content-disposition"]
    header = r.text.split("\n")[0].split("\t")
    assert header == _EXPORT_BASIC_FIELDS


def test_export_endpoint_invalid_format_returns_422(test_db):
    with TestClient(app) as client:
        r = client.get("/proteins/export", params={"format": "xml"})
    assert r.status_code == 422
    assert r.json()["error"] == "invalid_parameter"


def test_export_endpoint_invalid_fields_returns_422(test_db):
    with TestClient(app) as client:
        r = client.get("/proteins/export", params={"fields": "everything"})
    assert r.status_code == 422
    assert r.json()["error"] == "invalid_parameter"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd api && python3 -m pytest tests/test_proteins_router.py -v -k "export"
```
Expected: all new tests FAIL — the pure-function tests with `ImportError`, the endpoint tests with 404 (route doesn't exist yet).

- [ ] **Step 3: Implement the endpoint**

In `api/routers/proteins.py`:

1. Add `get_proteins_export` to the existing import block from `queries.protein_queries` (after `get_proteins_facets,` on line 37):

```python
from queries.protein_queries import (
    get_ortholog_features,
    get_orthologs,
    get_protein_features,
    get_protein_meta,
    get_protein_mlo_annotations,
    get_proteins_export,
    get_proteins_facets,
    get_proteins_page,
    get_ppi_all,
    get_ppi_inter_edges,
    get_ppi_page,
    get_ppi_summary,
)
```

2. Add `from fastapi.responses import JSONResponse, Response` to the imports at the top of the file (alongside the existing `from fastapi import APIRouter, HTTPException, Query`).

3. Add these module-level constants and helper functions right after `_parse_source_dbs` (after line 71, before `_plddt_category`):

```python
_EXPORT_BASIC_FIELDS = ["uniprot_id", "gene_name", "protein_name", "organism", "sequence_length", "reviewed"]
_EXPORT_FULL_FIELDS = _EXPORT_BASIC_FIELDS + ["has_driver", "has_client", "source_dbs", "mlo_count", "mlos"]


def _build_export_record(row: dict, fields: str) -> dict:
    record = {
        "uniprot_id": row["uniprot_id"],
        "gene_name": row.get("gene_name"),
        "protein_name": row.get("protein_name"),
        "organism": row.get("organism"),
        "sequence_length": row.get("sequence_length"),
        "reviewed": row.get("reviewed"),
    }
    if fields == "full":
        record["has_driver"] = bool(row.get("has_driver", 0))
        record["has_client"] = bool(row.get("has_client", 0))
        record["source_dbs"] = _parse_source_dbs(row.get("source_dbs"))
        record["mlo_count"] = row.get("mlo_count", 0)
        record["mlos"] = _parse_mlos(row.get("mlos"))
    return record


def _records_to_tsv(records: list[dict], columns: list[str]) -> str:
    lines = ["\t".join(columns)]
    for record in records:
        values = []
        for col in columns:
            v = record.get(col)
            if isinstance(v, list):
                values.append(";".join(v))
            elif v is None:
                values.append("")
            else:
                values.append(str(v))
        lines.append("\t".join(values))
    return "\n".join(lines) + "\n"
```

4. Add the endpoint itself at the end of the file (after `list_proteins`, i.e. after the final `return ProteinsResponse(...)` block):

```python
@router.get("/proteins/export")
async def export_proteins(
    organism: str | None = None,
    taxon_id: int | None = None,
    mlo: str | None = None,
    role: str | None = None,
    source_db: list[str] | None = Query(default=None),
    fields: str = Query(default="full"),
    format: str = Query(default="tsv"),
):
    if fields not in {"basic", "full"}:
        raise HTTPException(422, {"error": "invalid_parameter", "message": "fields must be 'basic' or 'full'"})
    if format not in {"tsv", "json"}:
        raise HTTPException(422, {"error": "invalid_parameter", "message": "format must be 'tsv' or 'json'"})

    try:
        rows = await get_proteins_export(organism, taxon_id, mlo, role, source_db)
    except aiosqlite.Error:
        raise HTTPException(500, {"error": "database_error", "message": "Internal database error"})

    records = [_build_export_record(r, fields) for r in rows]
    columns = _EXPORT_BASIC_FIELDS if fields == "basic" else _EXPORT_FULL_FIELDS

    if format == "json":
        return JSONResponse(content=records)

    tsv_body = _records_to_tsv(records, columns)
    return Response(
        content=tsv_body,
        media_type="text/tab-separated-values",
        headers={"Content-Disposition": 'attachment; filename="mlosmetadb_export.tsv"'},
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd api && python3 -m pytest tests/test_proteins_router.py -v
```
Expected: all tests in the file PASS, including every pre-existing test.

Then run the full backend suite to confirm no regressions anywhere:
```bash
cd api && python3 -m pytest -v
```
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add api/routers/proteins.py api/tests/test_proteins_router.py
git commit -m "feat: add GET /proteins/export bulk export endpoint"
```

---

### Task 4: `DownloadPage.vue`

**Files:**
- Modify: `frontend/src/api/proteins.js`
- Modify: `frontend/src/pages/DownloadPage.vue` (replaces the 5-line stub)

**Interfaces:**
- Consumes: `GET /proteins/export` from Task 3; `searchOrganisms(q, limit)` from `frontend/src/api/proteins.js` (already exists, used the same way `FilterSidebar.vue` uses it).
- Produces: `buildExportUrl(params: object) -> string` in `frontend/src/api/proteins.js`, consumed only by `DownloadPage.vue`.

- [ ] **Step 1: Add `buildExportUrl` to `src/api/proteins.js`**

Append to `frontend/src/api/proteins.js`:

```js
export function buildExportUrl(params = {}) {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === '') continue
    if (Array.isArray(value)) {
      value.forEach(v => search.append(key, v))
    } else {
      search.append(key, value)
    }
  }
  return `/api/proteins/export?${search.toString()}`
}
```

- [ ] **Step 2: Write `DownloadPage.vue`**

Replace the full contents of `frontend/src/pages/DownloadPage.vue` with:

```vue
<script setup>
import { ref, computed } from 'vue'
import { searchOrganisms, buildExportUrl } from '@/api/proteins'

const SOURCE_DBS = ['PhaseDB', 'PhasePDB', 'DrLLPS', 'LLPSDB', 'PhasePro', 'CDCODE']

const organism = ref('')
const orgSearch = ref('')
const orgSearchResults = ref([])
const role = ref('')
const selectedSources = ref([])
const fields = ref('full')
const format = ref('tsv')

async function onOrganismSearch() {
  if (orgSearch.value.length < 3) {
    orgSearchResults.value = []
    return
  }
  try {
    const res = await searchOrganisms(orgSearch.value)
    orgSearchResults.value = res.data.results ?? []
  } catch {
    orgSearchResults.value = []
  }
}

function selectOrganism(name) {
  organism.value = name
  orgSearch.value = ''
  orgSearchResults.value = []
}

function clearOrganism() {
  organism.value = ''
}

function toggleSourceDb(db) {
  selectedSources.value = selectedSources.value.includes(db)
    ? selectedSources.value.filter(d => d !== db)
    : [...selectedSources.value, db]
}

const downloadUrl = computed(() => buildExportUrl({
  organism: organism.value || null,
  role: role.value || null,
  source_db: selectedSources.value,
  fields: fields.value,
  format: format.value,
}))

function download() {
  window.location.href = downloadUrl.value
}
</script>

<template>
  <div class="max-w-6xl mx-auto px-6 py-8">
    <!-- Page header -->
    <div class="mb-6">
      <h1 class="text-2xl font-semibold text-gray-800">Download</h1>
      <p class="text-sm text-gray-600 mt-1">Export a filtered slice of the protein dataset.</p>
    </div>

    <div class="bg-white border border-gray-200 rounded-lg px-4 py-4 space-y-5 max-w-2xl">
      <!-- Organism filter -->
      <div>
        <label class="text-xs font-semibold text-gray-700 uppercase tracking-wide block mb-1.5">Organism</label>
        <div v-if="organism" class="mb-1.5">
          <span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs bg-[#E6F1FB] border border-[#B5D4F4] text-[#185FA5] font-medium">
            <em>{{ organism }}</em>
            <button @click="clearOrganism" class="opacity-60 hover:opacity-100 transition-opacity" aria-label="Remove organism filter">×</button>
          </span>
        </div>
        <div v-else>
          <input
            v-model="orgSearch"
            type="text"
            placeholder="Search organisms… (e.g. Homo sapiens)"
            class="w-full text-sm border border-gray-200 rounded px-2 py-1.5 focus:outline-none focus:border-[#185FA5]"
            @input="onOrganismSearch"
          />
          <div v-if="orgSearch.length >= 3" class="mt-1">
            <div
              v-for="result in orgSearchResults"
              :key="result.organism"
              class="flex items-center justify-between py-1 cursor-pointer hover:text-[#185FA5] text-sm text-gray-600"
              @click="selectOrganism(result.organism)"
            >
              <span>{{ result.organism }}</span>
              <span class="text-xs text-gray-500">{{ result.protein_count }}</span>
            </div>
            <div v-if="orgSearchResults.length === 0" class="text-xs text-gray-500 py-1">No organisms found.</div>
          </div>
        </div>
      </div>

      <!-- Role filter -->
      <div>
        <label class="text-xs font-semibold text-gray-700 uppercase tracking-wide block mb-1.5">Role</label>
        <select v-model="role" class="text-sm text-gray-700 border border-gray-200 rounded px-2 py-1.5 bg-white focus:outline-none focus:border-[#185FA5]">
          <option value="">All roles</option>
          <option value="driver">Drivers only</option>
          <option value="component">Non-drivers</option>
        </select>
      </div>

      <!-- Source DB filter -->
      <div>
        <label class="text-xs font-semibold text-gray-700 uppercase tracking-wide block mb-1.5">Source database</label>
        <div class="flex items-center gap-1.5 flex-wrap">
          <button
            v-for="db in SOURCE_DBS"
            :key="db"
            @click="toggleSourceDb(db)"
            :class="[
              'text-xs px-2 py-0.5 rounded-full border transition-colors',
              selectedSources.includes(db)
                ? 'bg-[#185FA5] text-white border-[#185FA5]'
                : 'bg-white text-gray-600 border-gray-300 hover:border-[#185FA5] hover:text-[#185FA5]',
            ]"
          >
            {{ db }}
          </button>
        </div>
        <p class="text-xs text-gray-500 mt-1">No selection means all sources.</p>
      </div>

      <!-- Fields -->
      <div>
        <label class="text-xs font-semibold text-gray-700 uppercase tracking-wide block mb-1.5">Fields</label>
        <div class="flex gap-4 text-sm text-gray-700">
          <label class="flex items-center gap-1.5 cursor-pointer">
            <input type="radio" value="basic" v-model="fields" class="accent-[#185FA5]" />
            Basic (identity only)
          </label>
          <label class="flex items-center gap-1.5 cursor-pointer">
            <input type="radio" value="full" v-model="fields" class="accent-[#185FA5]" />
            With annotations
          </label>
        </div>
      </div>

      <!-- Format -->
      <div>
        <label class="text-xs font-semibold text-gray-700 uppercase tracking-wide block mb-1.5">Format</label>
        <div class="flex gap-4 text-sm text-gray-700">
          <label class="flex items-center gap-1.5 cursor-pointer">
            <input type="radio" value="tsv" v-model="format" class="accent-[#185FA5]" />
            TSV
          </label>
          <label class="flex items-center gap-1.5 cursor-pointer">
            <input type="radio" value="json" v-model="format" class="accent-[#185FA5]" />
            JSON
          </label>
        </div>
      </div>

      <!-- Download button -->
      <div class="pt-2">
        <button
          @click="download"
          class="inline-flex items-center px-4 py-2 rounded bg-[#185FA5] text-white text-sm font-medium hover:bg-[#0F4A87] transition-colors"
        >
          Download
        </button>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 3: Manually verify in the browser**

Run the backend and frontend dev servers:
```bash
cd api && python3 -m uvicorn main:app --host 127.0.0.1 --port 8010
```
```bash
cd frontend && npm run dev
```
Open the frontend dev URL, navigate to `/download` (via the navbar's "Download" link), and confirm:
- The organism search box returns results after typing 3+ characters (try "Homo").
- Selecting an organism shows a removable chip and hides the search box; the × clears it.
- Clicking source-DB chips toggles their selected (blue) state.
- Clicking "Download" with default filters (TSV, full fields, no organism/role/source filters) triggers a browser file download named `mlosmetadb_export.tsv`; open it and confirm it has a header row (`uniprot_id\tgene_name\t...`) and multiple data rows.
- Change Format to JSON and Download again; confirm the browser opens/downloads a JSON array of objects (exact filename may vary by browser since the JSON branch doesn't set `Content-Disposition` — that's expected, only the TSV branch forces a download).
- Set Role to "Drivers only" and Download again (TSV); spot-check a few rows have non-empty `has_driver` truthy values (`True`) if Fields is "With annotations".

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/proteins.js frontend/src/pages/DownloadPage.vue
git commit -m "feat: build filterable bulk-export Download page"
```

---

## Plan Self-Review

**Spec coverage:**
- Navbar fix → Task 1, Step 1. ✅
- `/api` page (intro, base URL, endpoint table, curl example, error format, citation, links out) → Task 1, Step 3. ✅
- `GET /proteins/export` (organism/taxon_id/mlo/role/multi-value source_db, fields, format, policy-consistent filtering, 50k cap) → Task 2 + Task 3. ✅
- TSV `Content-Disposition` attachment, semicolon-joined lists → Task 3, Step 3. ✅
- JSON format, real lists (no join) → Task 3, Step 3 (`format == "json"` branch returns `records` before any TSV join happens). ✅
- `DownloadPage.vue` filters (organism autocomplete, role, source_db multi-select, fields, format, download button navigating via `window.location.href`) → Task 4. ✅
- Out-of-scope items (AboutPage stub, annotation-grain export, feature/PPI/ortholog detail in export, embedded Swagger UI, no change to `/proteins`'s single-value `source_db`) → none of these appear in any task. ✅

**Placeholder scan:** no TBD/TODO; every step has literal code, exact file paths, and runnable commands.

**Type consistency:** `get_proteins_export`'s 5th parameter is named `source_dbs` (list) consistently across Task 2's definition, Task 2's tests, and Task 3's call site (`get_proteins_export(organism, taxon_id, mlo, role, source_db)` — the router's local variable is `source_db`, a `list[str] | None` from `Query(default=None)`, passed positionally into the `source_dbs` parameter; names differ across the module boundary but the type and position match). `_build_export_record`/`_records_to_tsv`/`_EXPORT_BASIC_FIELDS`/`_EXPORT_FULL_FIELDS` are used identically in Task 3's implementation and its own tests. `buildExportUrl` is defined in Task 4 Step 1 and consumed in Task 4 Step 2 with matching signature (object of params, array values repeated).
