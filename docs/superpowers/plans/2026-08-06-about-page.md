# About Page Implementation Plan

> **Correction (2026-08-08).** This document treats `PhaseDB` and `PhasePDB`
> as two source databases (or counts six sources where there are five). They
> were two ingestion tags for one resource, **PhaSepDB**, whose two parsers
> read byte-identical copies of the same export files — so every PhaSepDB
> annotation was loaded twice. The document is left as written because it
> records a past design decision; the tags no longer exist in the data. See
> `docs/issues/001-phasedb-phasepdb-duplicate-ingestion.md`.


> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `AboutPage.vue` stub with a full page: interactive data
statistics (D3 charts), data origin (source + annotation database cards with
citations), a how-to-use carousel, and a citations section with an
interactive "which database should I cite" tool backed by one new endpoint.

**Architecture:** Two small, additive backend changes (`/stats` gains one
field; one new `POST /proteins/citations` endpoint) plus seven new frontend
components assembled into `AboutPage.vue`. No existing shared component
(`StatBar.vue`, `SourceDbBadge.vue`, `RoleCards.vue`) is modified — the About
page gets its own local components/data so nothing used elsewhere regresses.

**Tech Stack:** FastAPI + aiosqlite + Pydantic v2 (backend), Vue 3
Composition API (`<script setup>`) + D3.js + Tailwind v3 (frontend), pytest
(backend tests only — no frontend test runner exists in this repo).

**Spec:** [`docs/superpowers/specs/2026-08-06-about-page-design.md`](../specs/2026-08-06-about-page-design.md),
citation content sourced from [`docs/superpowers/specs/2026-08-06-about-page-sources.md`](../specs/2026-08-06-about-page-sources.md).

## Global Constraints

- Backend: Python 3.11+, FastAPI + `aiosqlite`, raw SQL (no ORM). Every query
  touching `mlo_annotations` MUST include `policy.active_annotation_clause()`.
- Error envelope for every backend error response: `{"error": "...", "message": "..."}`.
  422 validation errors use `error: "invalid_parameter"`.
- Frontend: Vue 3 Composition API, `<script setup>` only (no Options API), no
  TypeScript, Tailwind v3 utility classes only. Data fetching only through
  `frontend/src/api/*.js` — never inline axios/fetch calls in components.
- **Never run `npm run build` or `npm run dev`.** The user runs the frontend
  dev server themselves and reports back. Every frontend task's verification
  step says what to ask the user to check, not a command to run yourself.
- Backend tests run with: `cd api && python3 -m pytest tests/ -v`
- No frontend test runner exists in this repo (`frontend/package.json` has no
  `test` script, no vitest/jest dependency) — frontend tasks are verified by
  reading the rendered output back or asking the user to check the dev server,
  not by an automated test suite.
- Git: short, imperative-mood commit subjects, one commit per task, never
  amend, never force-push.

---

### Task 1: `/stats` gains `unique_proteins_by_source`

**Files:**
- Modify: `api/models/schemas.py` (`MloAnnotationStats`)
- Modify: `api/main.py` (`_compute_stats`)
- Test: `api/tests/test_stats.py`

**Interfaces:**
- Produces: `/stats` response now includes
  `mlo_annotations.unique_proteins_by_source: dict[str, int]` — distinct
  protein count per `source_db`, as opposed to the existing `by_source`
  (annotation-row count). Consumed by Task 7 (`AboutStatsSection.vue`'s
  source-database bar chart).

- [ ] **Step 1: Write the failing test**

Open `api/tests/test_stats.py`. It currently reads:

```python
import asyncio

from main import _compute_stats


def test_compute_stats_mlo_annotations_excludes_inactive_row(test_db):
    stats = asyncio.run(_compute_stats())
    assert stats["mlo_annotations"]["total"] == 3
    assert stats["mlo_annotations"]["by_source"] == {"PhaseDB": 2, "CDCODE": 1}
    assert stats["mlo_annotations"]["unique_mlos"] == 3
```

Replace it with (adds an `import database` and a new test function; the
existing function is untouched):

```python
import asyncio

import database
from main import _compute_stats


def test_compute_stats_mlo_annotations_excludes_inactive_row(test_db):
    stats = asyncio.run(_compute_stats())
    assert stats["mlo_annotations"]["total"] == 3
    assert stats["mlo_annotations"]["by_source"] == {"PhaseDB": 2, "CDCODE": 1}
    assert stats["mlo_annotations"]["unique_mlos"] == 3


def test_compute_stats_unique_proteins_by_source_dedupes_multiple_annotations(test_db):
    async def _setup_and_run():
        conn = await database.get_db()
        await conn.execute(
            "INSERT INTO mlo_vocabulary (unified_mlo, category) VALUES ('extra_mlo', 'Cytoplasmic')"
        )
        await conn.execute(
            "INSERT INTO mlo_annotations (uniprot_id, source_db, unified_mlo, unified_role, dataset_active) "
            "VALUES ('P35637', 'PhaseDB', 'extra_mlo', 'driver', 1)"
        )
        await conn.commit()
        return await _compute_stats()

    stats = asyncio.run(_setup_and_run())
    # P35637 now has two ACTIVE PhaseDB rows (stress_granule + extra_mlo): by_source
    # (row count) must reflect both, but unique_proteins_by_source (protein count)
    # must still count P35637 once -- that's the whole point of the new field.
    assert stats["mlo_annotations"]["by_source"]["PhaseDB"] == 3
    assert stats["mlo_annotations"]["unique_proteins_by_source"]["PhaseDB"] == 2
    assert stats["mlo_annotations"]["unique_proteins_by_source"]["CDCODE"] == 1
```

- [ ] **Step 2: Run tests to verify the new one fails**

Run: `cd api && python3 -m pytest tests/test_stats.py -v`
Expected: the new test FAILS with `KeyError: 'unique_proteins_by_source'`
(or a `StatsResponse` validation error once the response model is checked —
either way, a clear failure, not a pass). The first (existing) test still
passes.

- [ ] **Step 3: Implement — add the query and field in `api/main.py`**

In `_compute_stats()`, find:

```python
    src_rows = await database.fetchall(
        f"SELECT source_db, COUNT(*) AS cnt FROM mlo_annotations WHERE {active} GROUP BY source_db"
    )
```

Add immediately after it:

```python
    unique_src_rows = await database.fetchall(
        f"SELECT source_db, COUNT(DISTINCT uniprot_id) AS cnt FROM mlo_annotations WHERE {active} GROUP BY source_db"
    )
```

Then in the returned dict, find:

```python
        "mlo_annotations": {
            "total": ann_total,
            "unique_mlos": unique_mlos,
            "by_source": {r["source_db"]: r["cnt"] for r in src_rows},
            "by_role": {r["role"]: r["cnt"] for r in role_rows},
        },
```

Replace with:

```python
        "mlo_annotations": {
            "total": ann_total,
            "unique_mlos": unique_mlos,
            "by_source": {r["source_db"]: r["cnt"] for r in src_rows},
            "unique_proteins_by_source": {r["source_db"]: r["cnt"] for r in unique_src_rows},
            "by_role": {r["role"]: r["cnt"] for r in role_rows},
        },
```

- [ ] **Step 4: Implement — add the field to the Pydantic model**

In `api/models/schemas.py`, find:

```python
class MloAnnotationStats(BaseModel):
    total: int
    unique_mlos: int
    by_source: dict[str, int]
    by_role: dict[str, int]
```

Replace with:

```python
class MloAnnotationStats(BaseModel):
    total: int
    unique_mlos: int
    by_source: dict[str, int]
    unique_proteins_by_source: dict[str, int] = {}
    by_role: dict[str, int]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd api && python3 -m pytest tests/test_stats.py -v`
Expected: both tests PASS.

- [ ] **Step 6: Run the full backend test suite to check for regressions**

Run: `cd api && python3 -m pytest tests/ -v`
Expected: all tests PASS (this field is additive with a default, so nothing
that already asserts on `/stats`'s shape should break).

- [ ] **Step 7: Commit**

```bash
git add api/main.py api/models/schemas.py api/tests/test_stats.py
git commit -m "feat: add unique_proteins_by_source to /stats"
```

---

### Task 2: `POST /proteins/citations` endpoint

**Files:**
- Modify: `api/models/schemas.py` (add `CitationCheckRequest`, `CitationCheckResponse`)
- Modify: `api/queries/protein_queries.py` (add `get_source_dbs_for_uniprot_ids`)
- Modify: `api/routers/proteins.py` (add canonical name map, aggregation helper, endpoint)
- Modify: `api/main.py` (CORS `allow_methods` must include `POST`, not just `GET`)
- Test: `api/tests/test_proteins_router.py`

**Interfaces:**
- Produces: `POST /proteins/citations` — body `{"uniprot_ids": ["P12345", ...]}`
  (max 500, deduped/uppercased/stripped server-side), response
  `{"by_source": {"PhaSePDB": 10, "PhaSePro": 3, ...}}`. IDs not found in the
  database are silently omitted from the result — never surfaced. Consumed
  by Task 4 (`checkCitations()`) and Task 10 (`CitationsSection.vue`).
- Canonical display names used by `by_source` keys: `PhaseDB`→`PhaSePDB`,
  `PhasePDB`→`PhaSePDB`, `DrLLPS`→`DrLLPS`, `LLPSDB`→`LLPSDB`,
  `PhasePro`→`PhaSePro`, `CDCODE`→`CD-CODE`. These exact strings must match
  the `name` fields used in Task 3's `aboutSources.js` — Task 10's frontend
  code renders whatever key the API returns directly as a label.

- [ ] **Step 1: Write the failing tests**

Add to the end of `api/tests/test_proteins_router.py` (it already imports
`TestClient` and `app` at the top — no new imports needed except `sqlite3`,
which is not currently imported there):

```python
import sqlite3

from fastapi.testclient import TestClient

from main import app
from routers.proteins import _build_export_record, _records_to_tsv, _EXPORT_BASIC_FIELDS, _EXPORT_FULL_FIELDS
```

(only the `import sqlite3` line is new — add it above the existing imports).

Then append these test functions:

```python
def test_citation_check_combines_phasedb_and_phasepdb_into_one_entry(test_db):
    conn = sqlite3.connect(test_db)
    conn.execute(
        "INSERT INTO mlo_vocabulary (unified_mlo, category) VALUES ('condensate_y', 'Cytoplasmic')"
    )
    conn.execute(
        "INSERT INTO proteins (uniprot_id, gene_name, organism, length) VALUES "
        "('PPDB01', 'PPDBTEST', 'Homo sapiens', 120)"
    )
    conn.execute(
        "INSERT INTO mlo_annotations (uniprot_id, source_db, unified_mlo, unified_role, dataset_active) "
        "VALUES ('PPDB01', 'PhasePDB', 'condensate_y', 'driver', 1)"
    )
    conn.commit()
    conn.close()

    with TestClient(app) as client:
        r = client.post("/proteins/citations", json={"uniprot_ids": ["P35637", "PPDB01", "PCLIENT"]})
    assert r.status_code == 200
    # P35637 and PCLIENT are tagged 'PhaseDB', PPDB01 is tagged 'PhasePDB' --
    # both must fold into the single 'PhaSePDB' display name.
    assert r.json()["by_source"] == {"PhaSePDB": 3}


def test_citation_check_ignores_unmatched_uniprot_ids(test_db):
    with TestClient(app) as client:
        r = client.post("/proteins/citations", json={"uniprot_ids": ["P35637", "NOTAREALID"]})
    assert r.status_code == 200
    assert r.json()["by_source"] == {"PhaSePDB": 1}


def test_citation_check_empty_list_returns_422(test_db):
    with TestClient(app) as client:
        r = client.post("/proteins/citations", json={"uniprot_ids": []})
    assert r.status_code == 422
    assert r.json()["error"] == "invalid_parameter"


def test_citation_check_too_many_ids_returns_422(test_db):
    ids = [f"P{i:05d}" for i in range(501)]
    with TestClient(app) as client:
        r = client.post("/proteins/citations", json={"uniprot_ids": ids})
    assert r.status_code == 422
    assert r.json()["error"] == "invalid_parameter"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd api && python3 -m pytest tests/test_proteins_router.py -k citation -v`
Expected: all four FAIL — `POST /proteins/citations` doesn't exist yet
(404, not the expected status codes).

- [ ] **Step 3: Implement — Pydantic models**

In `api/models/schemas.py`, add this new section right after the
`# ── /protein/{id}/orthologs ──` block (at the end of the file):

```python
# ── /proteins/citations ──────────────────────────────────────────────────────

class CitationCheckRequest(BaseModel):
    uniprot_ids: list[str]

    @field_validator("uniprot_ids")
    @classmethod
    def _clean_ids(cls, v: list[str]) -> list[str]:
        cleaned = []
        seen = set()
        for raw in v:
            uid = raw.strip().upper()
            if uid and uid not in seen:
                seen.add(uid)
                cleaned.append(uid)
        if not cleaned:
            raise ValueError("at least one non-empty uniprot_id is required")
        if len(cleaned) > 500:
            raise ValueError("at most 500 uniprot_ids allowed per request")
        return cleaned


class CitationCheckResponse(BaseModel):
    by_source: dict[str, int]
```

- [ ] **Step 4: Implement — query function**

In `api/queries/protein_queries.py`, add this function at the end of the
file:

```python
async def get_source_dbs_for_uniprot_ids(uniprot_ids: list[str]) -> list[dict]:
    if not uniprot_ids:
        return []
    ph = ",".join("?" * len(uniprot_ids))
    active = policy.active_annotation_clause("mlo_annotations")
    return await fetchall(
        f"""
        SELECT DISTINCT uniprot_id, source_db
        FROM mlo_annotations
        WHERE uniprot_id IN ({ph}) AND {active}
        """,
        tuple(uniprot_ids),
    )
```

- [ ] **Step 5: Implement — router endpoint**

In `api/routers/proteins.py`, find the imports block:

```python
from models.schemas import (
    DomainRegion,
    IdrRegion,
```

Change the opening to add the two new models alphabetically first:

```python
from models.schemas import (
    CitationCheckRequest,
    CitationCheckResponse,
    DomainRegion,
    IdrRegion,
```

Find:

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
```

Add the new query function right after `get_proteins_page,`:

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
    get_source_dbs_for_uniprot_ids,
```

Then, at the end of the file (after `export_proteins`), add:

```python
_CITATION_SOURCE_NAMES = {
    "PhaseDB": "PhaSePDB",
    "PhasePDB": "PhaSePDB",
    "DrLLPS": "DrLLPS",
    "LLPSDB": "LLPSDB",
    "PhasePro": "PhaSePro",
    "CDCODE": "CD-CODE",
}


def _aggregate_citation_sources(rows: list[dict]) -> dict[str, int]:
    by_source: dict[str, set] = {}
    for r in rows:
        display = _CITATION_SOURCE_NAMES.get(r["source_db"], r["source_db"])
        by_source.setdefault(display, set()).add(r["uniprot_id"])
    return {name: len(ids) for name, ids in by_source.items()}


@router.post("/proteins/citations", response_model=CitationCheckResponse)
async def check_citations(body: CitationCheckRequest):
    try:
        rows = await get_source_dbs_for_uniprot_ids(body.uniprot_ids)
    except aiosqlite.Error:
        raise HTTPException(500, {"error": "database_error", "message": "Internal database error"})

    return CitationCheckResponse(by_source=_aggregate_citation_sources(rows))
```

- [ ] **Step 6: Implement — allow POST in CORS**

In `api/main.py`, find:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["*"],
)
```

Replace with:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd api && python3 -m pytest tests/test_proteins_router.py -k citation -v`
Expected: all four PASS.

- [ ] **Step 8: Run the full backend test suite to check for regressions**

Run: `cd api && python3 -m pytest tests/ -v`
Expected: all tests PASS.

- [ ] **Step 9: Commit**

```bash
git add api/models/schemas.py api/queries/protein_queries.py api/routers/proteins.py api/main.py api/tests/test_proteins_router.py
git commit -m "feat: add POST /proteins/citations endpoint"
```

---

### Task 3: `aboutSources.js` data module

**Files:**
- Create: `frontend/src/data/aboutSources.js`

**Interfaces:**
- Produces: `MLOSMETADB_CITATION`, `ORIGIN_PAPER_CITATION` (objects with
  `authors`/`journal`/`year`/`url`), `LLPS_SOURCES`, `ANNOTATION_SOURCES`
  (arrays of `{ key, name, description, citationText, citationUrl, color }`,
  `color` only present on `LLPS_SOURCES` entries as
  `{ bg, text, border }`). `name` values on `LLPS_SOURCES` MUST exactly match
  the canonical display names Task 2's backend returns
  (`PhaSePDB`, `DrLLPS`, `LLPSDB`, `PhaSePro`, `CD-CODE`) — Task 7 and Task
  10 both key off this. Consumed by Task 7 (`AboutStatsSection.vue`, for
  chart colors), Task 8 (`DataOriginSection.vue`), Task 10
  (`CitationsSection.vue`).

- [ ] **Step 1: Create the file**

```javascript
export const MLOSMETADB_CITATION = {
  authors: 'Ortí F, Fernández ML, Marino-Buslje C.',
  journal: 'Protein Science.',
  year: '2024;33(1):e4858.',
  url: 'https://doi.org/10.1002/pro.4858',
}

// TODO: replace with the real source/origin paper once it's available.
// Deliberately duplicated from MLOSMETADB_CITATION as a placeholder per user
// request during the About page design brainstorming (see
// docs/superpowers/specs/2026-08-06-about-page-design.md, section 4.2).
export const ORIGIN_PAPER_CITATION = { ...MLOSMETADB_CITATION }

export const LLPS_SOURCES = [
  {
    key: 'phasepdb',
    name: 'PhaSePDB',
    description: 'PhaSePDB es una base de datos curada manualmente que reúne proteínas asociadas a la separación de fases líquido-líquido (LLPS), el proceso que subyace a la formación de orgánulos sin membrana encargados de concentrar proteínas y ácidos nucleicos. Reúne miles de proteínas no redundantes localizadas en distintos orgánulos, recopiladas a partir de la literatura publicada y de otras bases de datos, y para cada una ofrece un resumen funcional, las referencias bibliográficas correspondientes y las características de secuencia relacionadas con el comportamiento de LLPS; estas mismas características de secuencia se ponen a disposición también para otras proteínas humanas candidatas. A través de una interfaz en línea que permite explorar, buscar y descargar la información, PhaSePDB se propone como un recurso centralizado que facilita el estudio de la separación de fases.',
    citationText: 'You K, Huang Q, Yu C, Shen B, Sevilla C, Shi M, Hermjakob H, Chen Y, Li T. PhaSepDB: a database of liquid–liquid phase separation related proteins. Nucleic Acids Research. 2020;48(D1):D354–D359.',
    citationUrl: 'https://doi.org/10.1093/nar/gkz847',
    color: { bg: '#EBF3FB', text: '#1B4F8A', border: '#BFDBFE' },
  },
  {
    key: 'drllps',
    name: 'DrLLPS',
    description: 'DrLLPS es una base de datos integrativa dedicada a las proteínas involucradas en la separación de fases líquido-líquido, un mecanismo ubicuo para la organización espaciotemporal de reacciones bioquímicas mediante la formación de orgánulos sin membrana en células eucariotas. A partir de la literatura, sus autores recopilaron manualmente proteínas "scaffold" (impulsoras de LLPS), proteínas reguladoras que modulan el proceso y proteínas cliente potencialmente prescindibles para la formación de estos orgánulos, clasificándolas en decenas de condensados biomoleculares distintos; además, buscaron ortólogos potenciales de estas proteínas en más de 160 especies eucariotas. Para ocho organismos modelo, DrLLPS anota en detalle cada proteína asociada a LLPS integrando información proveniente de más de un centenar de recursos externos, cubriendo aspectos como regiones desordenadas, dominios, modificaciones postraduccionales, variantes genéticas, interacciones moleculares, localización subcelular y estructuras 3D, entre otros.',
    citationText: 'Ning W, Guo Y, Lin S, Mei B, Wu Y, Jiang P, Tan X, Zhang W, Chen G, Peng D, Chu L, Xue Y. DrLLPS: a data resource of liquid–liquid phase separation in eukaryotes. Nucleic Acids Research. 2020;48(D1):D288–D295.',
    citationUrl: 'https://doi.org/10.1093/nar/gkz1027',
    color: { bg: '#F1F5F9', text: '#484E59', border: '#CBD5E1' },
  },
  {
    key: 'llpsdb',
    name: 'LLPSDB',
    description: 'LLPSDB es una base de datos de acceso web que ofrece una colección curada de proteínas involucradas en la separación de fases líquido-líquido observada in vitro, junto con las condiciones experimentales específicas bajo las cuales dicho comportamiento fue reportado en la literatura publicada. Incluye cientos de entradas correspondientes a proteínas independientes y miles de condiciones experimentales concretas, y para cada caso reúne información biomolecular (secuencia proteica, modificaciones, ácidos nucleicos asociados, etc.), información específica del comportamiento de fase (condiciones experimentales, descripción del comportamiento observado) y anotaciones adicionales. Sus autores la presentan como la primera base de datos diseñada específicamente para proteínas relacionadas con LLPS, orientada a facilitar el estudio de la relación entre secuencia proteica y comportamiento de fase, así como el desarrollo de métodos predictivos.',
    citationText: 'Li Q, Peng X, Li Y, Tang W, Zhu J, Huang J, Qi Y, Zhang Z. LLPSDB: a database of proteins undergoing liquid–liquid phase separation in vitro. Nucleic Acids Research. 2020;48(D1):D320–D327.',
    citationUrl: 'https://doi.org/10.1093/nar/gkz778',
    color: { bg: '#D1FAE5', text: '#0F6E56', border: '#6EE7B7' },
  },
  {
    key: 'phasepro',
    name: 'PhaSePro',
    description: 'PhaSePro es una base de datos curada manualmente, de acceso abierto, dedicada a proteínas y regiones proteicas que actúan como impulsoras de la separación de fases líquido-líquido validadas experimentalmente, un proceso central en la formación de orgánulos sin membrana que participan en procesos celulares específicos como la biogénesis de ribosomas o la degradación de ARN. Sus autores señalan que, si bien numerosos estudios experimentales reportan nuevos casos de LLPS, la identificación computacional de proteínas impulsoras del proceso va rezagada, en parte por la ausencia de una base de datos dedicada; PhaSePro busca cubrir este vacío ofreciendo, además de la información curada, vocabularios controlados específicos para LLPS que estandarizan la forma en que se describen estos sistemas, accesibles mediante una interfaz web.',
    citationText: 'Mészáros B, Erdős G, Szabó B, Schád É, Tantos Á, Abukhairan R, Horváth T, Murvai N, Kovács OP, Kovács M, Tosatto SCE, Tompa P, Dosztányi Z, Pancsa R. PhaSePro: the database of proteins driving liquid–liquid phase separation. Nucleic Acids Research. 2020;48(D1):D360–D367.',
    citationUrl: 'https://doi.org/10.1093/nar/gkz848',
    color: { bg: '#F3E8FF', text: '#6B21A8', border: '#D8B4FE' },
  },
  {
    key: 'cdcode',
    name: 'CD-CODE',
    description: 'CD-CODE (Crowdsourcing Condensate Database and Encyclopedia) es una plataforma editable por la comunidad, desarrollada para integrar el conocimiento científico interdisciplinario sobre la función y composición de los condensados biomoleculares, cuyo descubrimiento transformó la comprensión de la compartimentalización intracelular de moléculas. Incluye una base de datos de condensados biomoleculares basada en la literatura, una enciclopedia de términos científicos relevantes del campo y una aplicación web de crowdsourcing que permite a la comunidad contribuir y actualizar la información. Según sus autores, la plataforma busca acelerar el descubrimiento y la validación de condensados biomoleculares, así como facilitar los esfuerzos por comprender su papel en la enfermedad y su potencial como blancos terapéuticos.',
    citationText: 'Rostam N, Ghosh S, Chow CFW, Hadarovich A, Landerer C, Ghosh R, Moon H, Hersemann L, Mitrea DM, Klein IA, Hyman AA, Toth-Petroczy A. CD-CODE: crowdsourcing condensate database and encyclopedia. Nature Methods. 2023;20(5):673–676.',
    citationUrl: 'https://doi.org/10.1038/s41592-023-01831-0',
    color: { bg: '#FEF3C7', text: '#854F0B', border: '#FAC775' },
  },
]

export const ANNOTATION_SOURCES = [
  {
    key: 'uniprot',
    name: 'UniProt',
    description: 'UniProt es la base de datos central de conocimiento sobre proteínas, que proporciona información curada y de alta calidad sobre secuencias, funciones, estructura y anotaciones biológicas de proteínas de todos los organismos.',
    citationText: 'The UniProt Consortium. UniProt: the Universal Protein Knowledgebase in 2025. Nucleic Acids Research. 2025;53(D1):D609–D617.',
    citationUrl: 'https://doi.org/10.1093/nar/gkae1010',
  },
  {
    key: 'interpro',
    name: 'InterPro',
    description: 'InterPro es un recurso que clasifica las proteínas en familias y predice la presencia de dominios y sitios funcionales importantes integrando múltiples bases de datos de firmas de secuencia.',
    citationText: 'Blum M, Andreeva A, Florentino LC, Chuguransky SR, Grego T, Hobbs E, Pinto BL, Orr A, Paysan-Lafosse T, Ponamareva I, Salazar GA, Bordin N, Bork P, Bridge A, Colwell L, Gough J, Haft DH, Letunic I, Llinares-López F, Marchler-Bauer A, Meng-Papaxanthos L, Mi H, Natale DA, Orengo CA, Pandurangan AP, Piovesan D, Rivoire C, Sigrist CJA, Thanki N, Thibaud-Nissen F, Thomas PD, Tosatto SCE, Wu CH, Bateman A. InterPro: the protein sequence classification resource in 2025. Nucleic Acids Research. 2025;53(D1):D444–D456.',
    citationUrl: 'https://doi.org/10.1093/nar/gkae1082',
  },
  {
    key: 'mobidb',
    name: 'MobiDB',
    description: 'MobiDB es una base de datos que anota y agrega evidencia sobre el desorden intrínseco y la movilidad conformacional de las proteínas, combinando datos experimentales, curados manualmente y predichos computacionalmente.',
    citationText: 'Piovesan D, Del Conte A, Clementel D, Monzon AM, Bevilacqua M, Aspromonte MC, Iserte JA, Orti FE, Marino-Buslje C, Tosatto SCE. MobiDB: 10 years of intrinsically disordered proteins. Nucleic Acids Research. 2023;51(D1):D438–D444.',
    citationUrl: 'https://doi.org/10.1093/nar/gkac1065',
  },
  {
    key: 'biogrid',
    name: 'BioGRID',
    description: 'BioGRID es un recurso biomédico integral que cataloga interacciones proteína-proteína, genéticas y químicas curadas manualmente a partir de la literatura publicada en múltiples organismos.',
    citationText: 'Oughtred R, Rust J, Chang C, Breitkreutz BJ, Stark C, Willems A, Boucher L, Leung G, Kolas N, Zhang F, Dolma S, Coulombe-Huntington J, Chatr-aryamontri A, Dolinski K, Tyers M. The BioGRID database: A comprehensive biomedical resource of curated protein, genetic, and chemical interactions. Protein Science. 2021;30(1):187–200.',
    citationUrl: 'https://doi.org/10.1002/pro.3978',
  },
  {
    key: 'oma',
    name: 'OMA (Orthologous MAtrix)',
    description: 'OMA es un recurso que infiere relaciones de ortología a gran escala entre genes de genomas completos, permitiendo identificar genes/proteínas equivalentes entre especies para estudios de genómica comparativa y evolución.',
    citationText: 'Altenhoff AM, Warwick Vesztrocy A, Bernard C, Train CM, Nicheperovich A, Prieto Baños S, Julca I, Moi D, Nevers Y, Majidian S, Dessimoz C, Glover NM. OMA orthology in 2024: improved prokaryote coverage, ancestral and extant GO enrichment, a revamped synteny viewer and more in the OMA Ecosystem. Nucleic Acids Research. 2024;52(D1):D513–D521.',
    citationUrl: 'https://doi.org/10.1093/nar/gkad1020',
  },
]
```

- [ ] **Step 2: Verify by reading it back**

Open the file and confirm: 5 entries in `LLPS_SOURCES`, 5 in
`ANNOTATION_SOURCES`, `name` values exactly `PhaSePDB`, `DrLLPS`, `LLPSDB`,
`PhaSePro`, `CD-CODE` (case-sensitive, matches Task 2's
`_CITATION_SOURCE_NAMES` values exactly).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/data/aboutSources.js
git commit -m "feat: add About page source/citation data module"
```

---

### Task 4: `checkCitations()` API function

**Files:**
- Modify: `frontend/src/api/proteins.js`

**Interfaces:**
- Produces: `checkCitations(uniprotIds: string[])` — returns the axios
  promise for `POST /proteins/citations`. Consumed by Task 10.

- [ ] **Step 1: Add the function**

In `frontend/src/api/proteins.js`, find:

```javascript
export function getProteinOrthologs(uniprotId) {
  return client.get(`/protein/${uniprotId}/orthologs`)
}
```

Add immediately after it:

```javascript
export function checkCitations(uniprotIds) {
  return client.post('/proteins/citations', { uniprot_ids: uniprotIds })
}
```

- [ ] **Step 2: Verify**

Read the file back and confirm the new export is present and doesn't
collide with any existing export name.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/proteins.js
git commit -m "feat: add checkCitations API call"
```

---

### Task 5: D3 chart components

**Files:**
- Create: `frontend/src/components/about/StatBarChart.vue`
- Create: `frontend/src/components/about/StatDonutChart.vue`

**Interfaces:**
- Produces: `StatBarChart` — prop `data: Array<{ label: string, value: number, color?: string }>`,
  emits `select(label: string)` on bar click.
  `StatDonutChart` — prop `data: Array<{ label: string, value: number, color?: string }>`,
  optional prop `size: number` (default 160), emits `select(label: string)`
  on segment click. Both follow the mount idiom already used by
  `SequenceFeatureViewer.vue` (containerRef + onMounted/ResizeObserver +
  watch + full clear-and-redraw), consumed by Task 7.

- [ ] **Step 1: Create `StatBarChart.vue`**

```vue
<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as d3 from 'd3'

const props = defineProps({
  data: { type: Array, required: true }, // [{ label, value, color }]
})
const emit = defineEmits(['select'])

const containerRef = ref(null)
let resizeObserver = null
let currentWidth = 0

const BAR_HEIGHT = 22
const BAR_GAP = 10
const LABEL_WIDTH = 110
const VALUE_PADDING = 44

function render(width) {
  if (!containerRef.value || width < 10 || !props.data.length) return
  currentWidth = width

  const height = props.data.length * (BAR_HEIGHT + BAR_GAP)
  const svg = d3.select(containerRef.value).select('svg')
  svg.attr('width', width).attr('height', height)
  svg.selectAll('*').remove()

  const chartWidth = Math.max(10, width - LABEL_WIDTH - VALUE_PADDING)
  const maxValue = d3.max(props.data, d => d.value) || 1
  const x = d3.scaleLinear().domain([0, maxValue]).range([0, chartWidth])

  const rows = svg.selectAll('g.row')
    .data(props.data)
    .enter()
    .append('g')
    .attr('class', 'row')
    .attr('transform', (d, i) => `translate(0, ${i * (BAR_HEIGHT + BAR_GAP)})`)
    .style('cursor', 'pointer')
    .on('click', (event, d) => emit('select', d.label))

  rows.append('text')
    .attr('x', LABEL_WIDTH - 8)
    .attr('y', BAR_HEIGHT / 2)
    .attr('text-anchor', 'end')
    .attr('dominant-baseline', 'middle')
    .attr('font-size', '12px')
    .attr('fill', '#484E59')
    .text(d => d.label)

  rows.append('rect')
    .attr('x', LABEL_WIDTH)
    .attr('y', 0)
    .attr('height', BAR_HEIGHT)
    .attr('width', d => x(d.value))
    .attr('rx', 3)
    .attr('fill', d => d.color || '#185FA5')

  rows.append('text')
    .attr('x', d => LABEL_WIDTH + x(d.value) + 8)
    .attr('y', BAR_HEIGHT / 2)
    .attr('dominant-baseline', 'middle')
    .attr('font-size', '12px')
    .attr('font-weight', '600')
    .attr('fill', '#1B3D6F')
    .text(d => d.value.toLocaleString())
}

onMounted(() => {
  if (!containerRef.value) return
  resizeObserver = new ResizeObserver(entries => {
    const w = entries[0].contentRect.width
    if (Math.abs(w - currentWidth) > 2) render(w)
  })
  resizeObserver.observe(containerRef.value)
  render(containerRef.value.clientWidth)
})

onUnmounted(() => {
  resizeObserver?.disconnect()
})

watch(() => props.data, () => render(currentWidth), { deep: true })
</script>

<template>
  <div ref="containerRef" class="w-full">
    <svg style="display:block; overflow:visible"></svg>
  </div>
</template>
```

- [ ] **Step 2: Create `StatDonutChart.vue`**

```vue
<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as d3 from 'd3'

const props = defineProps({
  data: { type: Array, required: true }, // [{ label, value, color }]
  size: { type: Number, default: 160 },
})
const emit = defineEmits(['select'])

const containerRef = ref(null)
let resizeObserver = null
let currentWidth = 0

function render(width) {
  if (!containerRef.value || width < 10 || !props.data.length) return
  currentWidth = width

  const size = Math.min(props.size, width)
  const radius = size / 2
  const innerRadius = radius * 0.6

  const svg = d3.select(containerRef.value).select('svg')
  svg.attr('width', width).attr('height', size)
  svg.selectAll('*').remove()

  const g = svg.append('g').attr('transform', `translate(${width / 2}, ${size / 2})`)

  const pie = d3.pie().value(d => d.value).sort(null)
  const arc = d3.arc().innerRadius(innerRadius).outerRadius(radius)

  const total = d3.sum(props.data, d => d.value)

  g.selectAll('path')
    .data(pie(props.data))
    .enter()
    .append('path')
    .attr('d', arc)
    .attr('fill', d => d.data.color || '#185FA5')
    .style('cursor', 'pointer')
    .on('click', (event, d) => emit('select', d.data.label))

  g.append('text')
    .attr('text-anchor', 'middle')
    .attr('dominant-baseline', 'middle')
    .attr('font-size', '20px')
    .attr('font-weight', '700')
    .attr('fill', '#1B3D6F')
    .text(total.toLocaleString())
}

onMounted(() => {
  if (!containerRef.value) return
  resizeObserver = new ResizeObserver(entries => {
    const w = entries[0].contentRect.width
    if (Math.abs(w - currentWidth) > 2) render(w)
  })
  resizeObserver.observe(containerRef.value)
  render(containerRef.value.clientWidth)
})

onUnmounted(() => {
  resizeObserver?.disconnect()
})

watch(() => props.data, () => render(currentWidth), { deep: true })
</script>

<template>
  <div class="flex flex-col items-center gap-2">
    <div ref="containerRef" class="w-full flex justify-center">
      <svg style="display:block; overflow:visible"></svg>
    </div>
    <div class="flex gap-4 text-xs">
      <div v-for="d in data" :key="d.label" class="flex items-center gap-1.5">
        <span class="w-2.5 h-2.5 rounded-full inline-block" :style="{ backgroundColor: d.color }"></span>
        <span class="text-gray-600">{{ d.label }} ({{ d.value.toLocaleString() }})</span>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 3: Verify**

These two components have no consumer yet (that's Task 7), so there's
nothing to render standalone. Read both files back and confirm they parse
as valid single-file components (matching `<script setup>` + `<template>`
structure used everywhere else in the codebase).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/about/StatBarChart.vue frontend/src/components/about/StatDonutChart.vue
git commit -m "feat: add reusable D3 bar/donut chart components"
```

---

### Task 6: `AboutHeadlineStats.vue`

**Files:**
- Create: `frontend/src/components/about/AboutHeadlineStats.vue`

**Interfaces:**
- Produces: prop `stats: Object | null` (raw `/stats` payload). Renders a
  7-tile summary strip. Consumed by Task 7.
- Consumes: `formatCount` from `@/utils/format` (already used by
  `StatBar.vue`/`RoleCards.vue`/`OrganismGrid.vue`).

- [ ] **Step 1: Create the file**

```vue
<script setup>
import { computed } from 'vue'
import { formatCount } from '@/utils/format'

const props = defineProps({
  stats: { type: Object, default: null }
})

const metrics = computed(() => {
  if (!props.stats) return null
  return [
    { value: formatCount(props.stats.proteins.total), label: 'proteins' },
    { value: formatCount(props.stats.mlo_annotations.total), label: 'annotations' },
    { value: formatCount(props.stats.mlo_annotations.unique_mlos), label: 'MLOs' },
    { value: formatCount(props.stats.proteins.total_organisms), label: 'organisms' },
    { value: formatCount(Object.keys(props.stats.mlo_annotations.by_source).length), label: 'source databases' },
    { value: formatCount(props.stats.ppi.total_interactions), label: 'PPI interactions' },
    { value: formatCount(props.stats.sequence_features.total), label: 'sequence features' },
  ]
})
</script>

<template>
  <div class="bg-[#EBF3FB] border border-[#C8DFF2] rounded-lg">
    <template v-if="metrics">
      <div class="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 divide-x divide-y sm:divide-y-0 divide-[#C8DFF2]">
        <div
          v-for="(m, i) in metrics"
          :key="i"
          class="flex flex-col items-center justify-center py-4 px-2"
        >
          <span class="text-xl font-bold text-[#1B3D6F] tabular-nums">{{ m.value }}</span>
          <span class="text-xs text-[#4A7BA7] uppercase tracking-wide mt-0.5 text-center">{{ m.label }}</span>
        </div>
      </div>
    </template>
    <template v-else>
      <div class="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 divide-x divide-y sm:divide-y-0 divide-[#C8DFF2]">
        <div
          v-for="i in 7"
          :key="i"
          class="flex flex-col items-center justify-center py-4 px-2 gap-2"
        >
          <div class="h-6 w-16 bg-[#C8DFF2] rounded animate-pulse"></div>
          <div class="h-3 w-14 bg-[#C8DFF2] rounded animate-pulse"></div>
        </div>
      </div>
    </template>
  </div>
</template>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/about/AboutHeadlineStats.vue
git commit -m "feat: add About page headline stats strip"
```

---

### Task 7: `AboutStatsSection.vue`

**Files:**
- Create: `frontend/src/components/about/AboutStatsSection.vue`

**Interfaces:**
- Consumes: `StatBarChart`/`StatDonutChart` (Task 5), `AboutHeadlineStats`
  (Task 6), `LLPS_SOURCES` from `@/data/aboutSources` (Task 3).
- Produces: prop `stats: Object | null`. This is the full `#stats` `<section>`,
  consumed by Task 11 (`AboutPage.vue`).

- [ ] **Step 1: Create the file**

```vue
<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import StatBarChart from './StatBarChart.vue'
import StatDonutChart from './StatDonutChart.vue'
import AboutHeadlineStats from './AboutHeadlineStats.vue'
import { LLPS_SOURCES } from '@/data/aboutSources'

const props = defineProps({
  stats: { type: Object, default: null }
})

const router = useRouter()

const SOURCE_COLORS = Object.fromEntries(LLPS_SOURCES.map(s => [s.name, s.color.text]))

const sourceData = computed(() => {
  if (!props.stats) return []
  const bySource = props.stats.mlo_annotations.unique_proteins_by_source ?? {}
  return Object.entries(bySource)
    .map(([label, value]) => ({ label, value, color: SOURCE_COLORS[label] || '#185FA5' }))
    .sort((a, b) => b.value - a.value)
})

const roleData = computed(() => {
  if (!props.stats) return []
  const r = props.stats.proteins.by_component_role
  return [
    { label: 'Driver', value: r.driver ?? 0, color: '#185FA5' },
    { label: 'Component', value: r.component ?? 0, color: '#9CA3AF' },
  ]
})

const organismData = computed(() => {
  if (!props.stats) return []
  return Object.entries(props.stats.proteins.by_organism ?? {})
    .map(([label, value]) => ({ label, value, color: '#0F6E56' }))
    .sort((a, b) => b.value - a.value)
})

function goToRole(label) {
  const role = label === 'Driver' ? 'driver' : 'component'
  router.push({ path: '/results', query: { role } })
}

function goToOrganism(label) {
  router.push({ path: '/results', query: { organism: label } })
}
</script>

<template>
  <section id="stats" class="scroll-mt-20">
    <h2 class="text-lg font-semibold text-gray-800 mb-3">Data Statistics and Annotations</h2>

    <AboutHeadlineStats :stats="stats" class="mb-6" />

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div class="bg-white border border-gray-200 rounded-lg p-4">
        <div class="text-sm font-semibold text-gray-700 mb-3">Proteins by source database</div>
        <!-- No click-to-navigate here: "PhaSePDB" combines two distinct raw
             source_db tags (PhaseDB + PhasePDB), so it can't map to a single
             /results?source_db=... value -- see about-page design spec §2. -->
        <StatBarChart :data="sourceData" />
      </div>

      <div class="bg-white border border-gray-200 rounded-lg p-4">
        <div class="text-sm font-semibold text-gray-700 mb-3">Driver vs. Component</div>
        <StatDonutChart :data="roleData" @select="goToRole" />
      </div>

      <div class="bg-white border border-gray-200 rounded-lg p-4">
        <div class="text-sm font-semibold text-gray-700 mb-3">Top 10 organisms</div>
        <StatBarChart :data="organismData" @select="goToOrganism" />
      </div>
    </div>
  </section>
</template>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/about/AboutStatsSection.vue
git commit -m "feat: add About page stats section"
```

---

### Task 8: `DataOriginSection.vue`

**Files:**
- Create: `frontend/src/components/about/DataOriginSection.vue`

**Interfaces:**
- Consumes: `LLPS_SOURCES`, `ANNOTATION_SOURCES` from `@/data/aboutSources`
  (Task 3).
- Produces: the full `#data-origin` `<section>`, no props needed. Consumed
  by Task 11.

- [ ] **Step 1: Create the file**

```vue
<script setup>
import { LLPS_SOURCES, ANNOTATION_SOURCES } from '@/data/aboutSources'
</script>

<template>
  <section id="data-origin" class="scroll-mt-20 mt-10">
    <h2 class="text-lg font-semibold text-gray-800 mb-3">Data Origin</h2>

    <h3 class="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">LLPS source databases</h3>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
      <div
        v-for="src in LLPS_SOURCES"
        :key="src.key"
        class="bg-white border border-gray-200 rounded-lg p-4"
      >
        <span
          class="text-xs px-2 py-0.5 rounded font-medium inline-block mb-2"
          :style="{ backgroundColor: src.color.bg, color: src.color.text, borderColor: src.color.border, borderStyle: 'solid', borderWidth: '1px' }"
        >{{ src.name }}</span>
        <p class="text-sm text-gray-600 leading-relaxed">{{ src.description }}</p>
        <p class="text-xs text-gray-800 mt-2">
          {{ src.citationText }}
          <a :href="src.citationUrl" target="_blank" rel="noopener" class="text-[#185FA5] hover:underline">{{ src.citationUrl }}</a>
        </p>
      </div>
    </div>

    <h3 class="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">Annotation & enrichment databases</h3>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div
        v-for="src in ANNOTATION_SOURCES"
        :key="src.key"
        class="bg-white border border-gray-200 rounded-lg p-4"
      >
        <span class="text-xs px-2 py-0.5 rounded font-medium inline-block mb-2 bg-gray-100 text-gray-700 border border-gray-200">{{ src.name }}</span>
        <p class="text-sm text-gray-600 leading-relaxed">{{ src.description }}</p>
        <p class="text-xs text-gray-800 mt-2">
          {{ src.citationText }}
          <a :href="src.citationUrl" target="_blank" rel="noopener" class="text-[#185FA5] hover:underline">{{ src.citationUrl }}</a>
        </p>
      </div>
    </div>
  </section>
</template>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/about/DataOriginSection.vue
git commit -m "feat: add About page Data Origin section"
```

---

### Task 9: `HowToUseCarousel.vue`

**Files:**
- Create: `frontend/src/components/about/HowToUseCarousel.vue`

**Interfaces:**
- Produces: the full `#how-to-use` `<section>`, no props needed. Consumed by
  Task 11. Expects screenshot files (added later by the user, not part of
  this plan) at `frontend/public/about/how-to-1.png`, `how-to-2.png`,
  `how-to-3.png` — falls back to a placeholder box if any are missing.

- [ ] **Step 1: Create the file**

```vue
<script setup>
import { ref } from 'vue'

const SLIDES = [
  {
    title: 'Search & Results',
    bullets: [
      "Use the search bar on the Home page to look up a gene name, UniProt ID, or organism.",
      'The Results page lists matching proteins with pagination and sortable columns.',
      'Use the filter sidebar to narrow by organism, LLPS role, MLO, or source database.',
      "Click any row to open that protein's full detail page.",
    ],
    image: '/about/how-to-1.png',
  },
  {
    title: 'Protein page & MLOs',
    bullets: [
      'The Overview tab shows the AlphaFold structure and sequence feature track (IDRs, domains).',
      'The MLO Annotations tab lists every membraneless organelle this protein is linked to, with its role per source database.',
      'The Interactions tab shows protein-protein interaction partners.',
      'Browse by MLO from the MLOs page to see every protein linked to a given organelle.',
    ],
    image: '/about/how-to-2.png',
  },
  {
    title: 'Download & API',
    bullets: [
      'The Download page lets you export a filtered slice of the dataset as TSV or JSON.',
      'Filter by organism, role, and source database before exporting.',
      'The API page documents the public REST endpoints for programmatic access.',
      'Full interactive API reference is available at /docs (Swagger UI).',
    ],
    image: '/about/how-to-3.png',
  },
]

const activeSlide = ref(0)
const mountedSlides = ref(new Set([0]))

function goTo(i) {
  activeSlide.value = i
  mountedSlides.value.add(i)
}

function next() {
  goTo((activeSlide.value + 1) % SLIDES.length)
}

function prev() {
  goTo((activeSlide.value - 1 + SLIDES.length) % SLIDES.length)
}

function onImageError(event) {
  event.target.style.display = 'none'
  event.target.nextElementSibling.style.display = 'flex'
}
</script>

<template>
  <section id="how-to-use" class="scroll-mt-20 mt-10">
    <h2 class="text-lg font-semibold text-gray-800 mb-3">How to Use</h2>

    <div class="bg-white border border-gray-200 rounded-lg p-4">
      <div class="h-[420px] relative">
        <div
          v-for="(slide, i) in SLIDES"
          v-show="activeSlide === i"
          :key="slide.title"
        >
          <template v-if="mountedSlides.has(i)">
            <h3 class="text-base font-semibold text-gray-800 mb-3">{{ slide.title }}</h3>
            <div class="flex gap-6">
              <ul class="flex-1 space-y-2 text-sm text-gray-600 list-disc list-inside">
                <li v-for="(b, bi) in slide.bullets" :key="bi">{{ b }}</li>
              </ul>
              <div class="w-[420px] flex-shrink-0">
                <div class="aspect-video rounded border border-gray-200 overflow-hidden relative">
                  <img
                    :src="slide.image"
                    :alt="slide.title"
                    class="w-full h-full object-contain bg-gray-50"
                    @error="onImageError"
                  />
                  <div
                    class="absolute inset-0 border-2 border-dashed border-gray-300 bg-gray-50 hidden items-center justify-center text-xs text-gray-400"
                  >
                    Screenshot pending
                  </div>
                </div>
              </div>
            </div>
          </template>
        </div>
      </div>

      <div class="flex items-center justify-center gap-4 mt-4 pt-3 border-t border-gray-100">
        <button @click="prev" class="text-gray-400 hover:text-[#185FA5]" aria-label="Previous slide">‹</button>
        <div class="flex gap-2">
          <button
            v-for="(slide, i) in SLIDES"
            :key="slide.title"
            class="w-2 h-2 rounded-full"
            :class="activeSlide === i ? 'bg-[#185FA5]' : 'bg-gray-300'"
            @click="goTo(i)"
            :aria-label="`Go to slide ${i + 1}`"
          ></button>
        </div>
        <button @click="next" class="text-gray-400 hover:text-[#185FA5]" aria-label="Next slide">›</button>
      </div>
    </div>
  </section>
</template>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/about/HowToUseCarousel.vue
git commit -m "feat: add About page how-to-use carousel"
```

---

### Task 10: `CitationsSection.vue`

**Files:**
- Create: `frontend/src/components/about/CitationsSection.vue`

**Interfaces:**
- Consumes: `checkCitations` from `@/api/proteins` (Task 4);
  `MLOSMETADB_CITATION`, `ORIGIN_PAPER_CITATION`, `LLPS_SOURCES`,
  `ANNOTATION_SOURCES` from `@/data/aboutSources` (Task 3).
- Produces: the full `#citations` `<section>`, no props needed. Consumed by
  Task 11.

- [ ] **Step 1: Create the file**

```vue
<script setup>
import { ref } from 'vue'
import { checkCitations } from '@/api/proteins'
import { MLOSMETADB_CITATION, ORIGIN_PAPER_CITATION, LLPS_SOURCES, ANNOTATION_SOURCES } from '@/data/aboutSources'

const idsInput = ref('')
const checking = ref(false)
const checkError = ref(false)
const results = ref(null)

function parseIds(text) {
  return [...new Set(
    text.split(/[\s,]+/).map(s => s.trim()).filter(Boolean)
  )]
}

async function runCheck() {
  const ids = parseIds(idsInput.value)
  if (!ids.length) return
  checking.value = true
  checkError.value = false
  results.value = null
  try {
    const res = await checkCitations(ids)
    results.value = Object.entries(res.data.by_source).sort((a, b) => b[1] - a[1])
  } catch {
    checkError.value = true
  } finally {
    checking.value = false
  }
}
</script>

<template>
  <section id="citations" class="scroll-mt-20 mt-10">
    <h2 class="text-lg font-semibold text-gray-800 mb-3">Citations</h2>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
      <div class="bg-white border border-gray-200 rounded-lg p-4">
        <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Cite MLOsMetaDB</p>
        <p class="text-sm text-gray-800">
          {{ MLOSMETADB_CITATION.authors }} <em>{{ MLOSMETADB_CITATION.journal }}</em> {{ MLOSMETADB_CITATION.year }}
          <a :href="MLOSMETADB_CITATION.url" target="_blank" rel="noopener" class="text-[#185FA5] hover:underline block mt-1">{{ MLOSMETADB_CITATION.url }}</a>
        </p>
      </div>
      <div class="bg-white border border-gray-200 rounded-lg p-4">
        <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Original paper</p>
        <p class="text-sm text-gray-800">
          {{ ORIGIN_PAPER_CITATION.authors }} <em>{{ ORIGIN_PAPER_CITATION.journal }}</em> {{ ORIGIN_PAPER_CITATION.year }}
          <a :href="ORIGIN_PAPER_CITATION.url" target="_blank" rel="noopener" class="text-[#185FA5] hover:underline block mt-1">{{ ORIGIN_PAPER_CITATION.url }}</a>
        </p>
      </div>
    </div>

    <div class="bg-white border border-gray-200 rounded-lg p-4 mb-8">
      <p class="text-sm font-semibold text-gray-700 mb-1">Which database should I cite?</p>
      <p class="text-xs text-gray-600 mb-3">Paste a list of UniProt IDs (comma, space, or newline separated) to see which source databases contributed annotations for them.</p>
      <textarea
        v-model="idsInput"
        rows="4"
        placeholder="P35637, Q9Y2Y0, ..."
        class="w-full text-sm border border-gray-200 rounded px-2 py-1.5 font-mono focus:outline-none focus:border-[#185FA5]"
      ></textarea>
      <div class="flex items-center justify-between mt-2">
        <button
          @click="runCheck"
          :disabled="checking || !idsInput.trim()"
          class="inline-flex items-center px-4 py-2 rounded bg-[#185FA5] text-white text-sm font-medium hover:bg-[#0F4A87] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {{ checking ? 'Checking…' : 'Check' }}
        </button>
        <p v-if="checkError" class="text-xs text-red-600">Could not check citations right now. Try again later.</p>
      </div>

      <div v-if="results" class="flex flex-wrap gap-2 mt-4">
        <span
          v-for="[name, count] in results"
          :key="name"
          class="text-xs px-2 py-1 rounded-full bg-[#EBF3FB] text-[#1B4F8A] border border-[#BFDBFE] font-medium"
        >{{ name }} ({{ count }})</span>
        <span v-if="!results.length" class="text-xs text-gray-500">None of these IDs matched a source database in MLOsMetaDB.</span>
      </div>
    </div>

    <div>
      <p class="text-sm font-semibold text-gray-700 mb-2">Full reference list</p>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-1 text-xs text-gray-600">
        <p v-for="src in [...LLPS_SOURCES, ...ANNOTATION_SOURCES]" :key="src.key">
          <span class="font-medium text-gray-700">{{ src.name }}:</span>
          {{ src.citationText }}
          <a :href="src.citationUrl" target="_blank" rel="noopener" class="text-[#185FA5] hover:underline">{{ src.citationUrl }}</a>
        </p>
      </div>
    </div>
  </section>
</template>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/about/CitationsSection.vue
git commit -m "feat: add About page citations section"
```

---

### Task 11: Assemble `AboutPage.vue`

**Files:**
- Modify: `frontend/src/pages/AboutPage.vue` (replaces the 5-line stub)

**Interfaces:**
- Consumes: `getStats` from `@/api/stats` (existing), `AboutStatsSection`
  (Task 7), `DataOriginSection` (Task 8), `HowToUseCarousel` (Task 9),
  `CitationsSection` (Task 10). This is the final task — after it, the page
  is feature-complete per the spec.

- [ ] **Step 1: Replace the stub**

Current content of `frontend/src/pages/AboutPage.vue`:

```vue
<template>
  <div class="flex items-center justify-center py-32 text-2xl font-semibold text-gray-400">
    About
  </div>
</template>
```

Replace the entire file with:

```vue
<script setup>
import { ref, onMounted } from 'vue'
import { getStats } from '@/api/stats'
import AboutStatsSection from '@/components/about/AboutStatsSection.vue'
import DataOriginSection from '@/components/about/DataOriginSection.vue'
import HowToUseCarousel from '@/components/about/HowToUseCarousel.vue'
import CitationsSection from '@/components/about/CitationsSection.vue'

const stats = ref(null)

onMounted(async () => {
  try {
    const res = await getStats()
    stats.value = res.data
  } catch {
    stats.value = null
  }
})

const NAV = [
  { id: 'stats', label: 'Statistics' },
  { id: 'data-origin', label: 'Data Origin' },
  { id: 'how-to-use', label: 'How to Use' },
  { id: 'citations', label: 'Citations' },
]
</script>

<template>
  <div class="max-w-6xl mx-auto px-6 py-8">
    <div class="mb-6">
      <h1 class="text-2xl font-semibold text-gray-800">About MLOsMetaDB</h1>
      <p class="text-sm text-gray-600 mt-1">Statistics, data sources, usage guide, and citations.</p>
    </div>

    <nav class="sticky top-14 z-10 bg-white border-b border-gray-200 mb-8 flex gap-6 text-sm">
      <a
        v-for="item in NAV"
        :key="item.id"
        :href="`#${item.id}`"
        class="py-2 text-[#484E59] hover:text-[#185FA5] border-b-2 border-transparent hover:border-[#185FA5] transition-colors"
      >{{ item.label }}</a>
    </nav>

    <AboutStatsSection :stats="stats" />
    <DataOriginSection />
    <HowToUseCarousel />
    <CitationsSection />
  </div>
</template>
```

- [ ] **Step 2: Ask the user to verify in the browser**

This repo's convention is: **never run `npm run dev` yourself.** Ask the
user to run it and check:

1. Navigate to `/about`.
2. The Statistics section shows the 7-tile headline strip and 3 charts once
   `/stats` loads (may briefly show skeleton loaders first).
3. Clicking a bar in the "Top 10 organisms" chart or a segment in the
   "Driver vs. Component" donut navigates to `/results` with the expected
   filter applied.
4. The Data Origin section shows 5 LLPS source cards + 5 annotation source
   cards, each with a description and a clickable DOI link.
5. The How to Use carousel shows one slide at a time (dashed "Screenshot
   pending" placeholders are expected until real screenshots are added at
   `frontend/public/about/how-to-{1,2,3}.png`), and the page does not grow
   taller when switching slides.
6. In Citations, pasting a few real UniProt IDs (e.g. `P35637`) into the
   textarea and clicking "Check" returns a badge with a source database
   name and count.
7. Report back anything that looks wrong (console errors, broken layout,
   `/stats` or `/proteins/citations` request failures) instead of assuming
   it works.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/AboutPage.vue
git commit -m "feat: build full About page (stats, data origin, how-to-use, citations)"
```

---

## Post-plan note (not a task — for the user, not the implementer)

Once this plan is fully executed, drop three screenshots at
`frontend/public/about/how-to-1.png`, `how-to-2.png`, `how-to-3.png`
(matching the slide order in Task 9: Search & Results, Protein page & MLOs,
Download & API) — they'll appear automatically, no code change needed.
