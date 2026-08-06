# MLOsMetaDB — Phase 4: REST API

## Project context

MLOsMetaDB v2 is a unified database of proteins associated with membraneless organelles (MLOs)
involved in liquid-liquid phase separation (LLPS). This phase builds a REST API over the
populated SQLite database (`database/mlosmetadb.db`).

The API replaces the backend of `mlos.leloir.org.ar`. It is public, no authentication required.

## Stack

- **Framework**: FastAPI
- **Database**: SQLite via `aiosqlite` (async). No ORM — raw SQL only.
- **Search**: SQLite FTS5 virtual tables (must be available — verify on startup).
- **Python**: 3.11+

## Directory structure

```
api/
├── main.py                    # FastAPI app, lifespan, router registration
├── database.py                # async connection pool, query helpers, FTS5 check
├── config.py                  # DB path, CORS origins, pagination defaults
├── routers/
│   ├── proteins.py            # GET /protein/{id}, GET /proteins
│   ├── mlos.py                # GET /mlo/{mlo}, GET /mlos
│   ├── search.py              # GET /search, GET /search/advanced
│   └── stats.py               # GET /stats
├── models/
│   └── schemas.py             # Pydantic v2 response models (all endpoints)
├── queries/
│   ├── protein_queries.py     # SQL for protein endpoints
│   ├── mlo_queries.py         # SQL for MLO endpoints
│   └── search_queries.py      # SQL for search endpoints
├── requirements.txt
└── CLAUDE_api.md
```

## Database reference

Database: `../database/mlosmetadb.db` (relative to `api/`)

### Relevant tables and key columns

```sql
proteins(
    uniprot_id TEXT PRIMARY KEY,
    gene_name TEXT,
    protein_name TEXT,
    organism TEXT,
    taxon_id INTEGER,
    sequence TEXT,
    length INTEGER,                -- mapped as `sequence_length` in API responses
    disorder_mobidb_lite_dc REAL,  -- content_fraction (0–1), NULL if absent
    disorder_alphafold_dc REAL     -- content_fraction (0–1), NULL if absent
)

mlo_annotations(
    id INTEGER PRIMARY KEY,
    uniprot_id TEXT,           -- FK → proteins
    unified_mlo TEXT,          -- FK → mlo_vocabulary
    source_db TEXT,            -- 'PhaseDB' | 'DrLLPS' | 'PhasePro' | 'LLPSDB' | 'CDCODE'
    source_mlo TEXT,
    source_role TEXT,
    unified_role TEXT,         -- 'driver' | 'client' | NULL
    evidence TEXT              -- semicolon-separated PMIDs (parsed into list in API)
)

mlo_vocabulary(
    unified_mlo TEXT PRIMARY KEY,
    category TEXT
)

mlo_definitions(
    unified_mlo TEXT,
    source_db TEXT,
    source_name TEXT,          -- original MLO name in that source
    definition TEXT,
    PRIMARY KEY (unified_mlo, source_db)
)

sequence_features(
    id INTEGER PRIMARY KEY,
    uniprot_id TEXT,           -- FK → proteins
    feature_type TEXT,         -- 'idr' | 'idr_curated' | 'lcd' | 'domain' |
                               -- 'family' | 'morf' | 'plddt_region'
    source TEXT,               -- 'MobiDB-lite' | 'AlphaFold' | 'Pfam' | 'SMART' | etc.
    label TEXT,                -- domain name, LCD type, etc.
    accession TEXT,            -- Pfam/SMART/IPR accession (NULL if not applicable)
    start INTEGER,
    end INTEGER,
    score REAL,                -- e-value, pLDDT score, disorder score (NULL if not applicable)
    metadata TEXT,             -- JSON with source-specific extra fields
    fetch_date TEXT
)

ppi(
    id INTEGER PRIMARY KEY,
    uniprot_id_a TEXT,         -- FK → proteins (always in our dataset)
    uniprot_id_b TEXT,         -- may or may not be in proteins table
    experimental_system TEXT,  -- e.g. 'Co-IP', 'Affinity Capture-MS'
    pubmed_id TEXT,            -- PubMed ID for the interaction record
    in_db INTEGER,             -- 1 if uniprot_id_b is in proteins table
    source_version TEXT        -- e.g. 'BioGRID'
)
```

**Note**: check CLAUDE_phase2_database.md and CLAUDE_phase3_features.md for full column
listings if a query needs a column not listed above.

## Runtime

- **API port**: `8765` — `uvicorn main:app --port 8765` desde `api/`
- **Frontend dev**: Vite en `5173` o `5174`; su proxy reescribe `/api/*` → `/*` antes de llegar a FastAPI (las rutas FastAPI no tienen prefijo `/api`)

## Performance: DB in-memory

La DB vive en BeeGFS (filesystem distribuido del cluster), que tiene alta latencia para
el I/O aleatorio pequeño que hace SQLite. Al arrancar, `database.open_db()` carga la DB
completa en RAM usando `sqlite3.backup()` hacia una named in-memory DB (`file:mlosmetadb_api?mode=memory&cache=shared`).

- Arranque: ~1-2s extra para copiar 229 MB desde BeeGFS.
- Después: todas las queries corren en RAM.
- `_mem_hold` (conexión sqlite3 sincrónica) mantiene la named in-memory DB viva mientras aiosqlite la usa.
- Al reconstruir la DB (scripts del pipeline), reiniciar uvicorn para recargarla.

## CORS configuration

```python
allow_origins = [
    "https://mlos.leloir.org.ar",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:8080",
]
```

## Startup checks (in lifespan)

1. Verify `mlosmetadb.db` is accessible and readable.
2. Verify FTS5 is available: `SELECT fts5(?1)` — if it fails, log a warning and disable
   fuzzy search (fall back to LIKE-based search only).
3. Create FTS5 virtual tables if they don't exist (see Search section below).

## Endpoints

### GET /protein/{uniprot_id}

Returns full protein record: metadata + MLO annotations + sequence features + PPI summary.

**PPI behavior**: by default, returns only the summary (`total_partners`,
`partners_in_mlosmetadb`). If `?ppi_page` is provided, also returns the paginated
`interactions` array. Default `ppi_per_page=50`, max 200.

**Response schema**:
```json
{
  "uniprot_id": "P35637",
  "gene_name": "FUS",
  "protein_name": "RNA-binding protein FUS",
  "organism": "Homo sapiens",
  "taxon_id": 9606,
  "sequence_length": 526,
  "mlo_annotations": [
    {
      "unified_mlo": "stress_granule",
      "category": "cytoplasmic_rnp",
      "source_db": "PhaseDB",
      "source_mlo": "Stress granules",
      "unified_role": "driver",
      "evidence_pmids": ["20639869", "28813787"]  -- parsed del campo `evidence` (semicolon-separated)
    }
  ],
  "sequence_features": {
    "idrs": [
      { "start": 1, "end": 165, "score": 0.91, "source": "MobiDB-lite" }
    ],
    "domains": [
      {
        "start": 285, "end": 371,
        "label": "RNA recognition motif",
        "accession": "PF00076",
        "database": "Pfam"
      }
    ],
    "lcds": [
      { "start": 1, "end": 165, "label": "G-rich", "source": "MobiDB-lite" }
    ],
    "morfs": [
      { "start": 60, "end": 95, "score": 0.78, "source": "MobiDB-lite" }
    ],
    "plddt_regions": [
      { "start": 1, "end": 165, "mean_score": 42.1, "category": "very_low" }
    ]
  },
  "ppi": {
    "total_partners": 312,
    "partners_in_mlosmetadb": 87,
    "interactions": null
  }
}
```

`interactions` is `null` when `ppi_page` is not provided. When provided:
```json
"interactions": {
  "page": 1,
  "per_page": 50,
  "total": 312,
  "items": [
    {
      "partner_uniprot_id": "P09651",
      "partner_gene": "HNRNPA1",
      "in_mlosmetadb": true,
      "evidence_types": ["Co-IP"],
      "pubmed_id": "12345678",
      "source": "BioGRID"
    }
  ]
}
```

**feature_type → campo en `sequence_features`**:
- `idr`, `idr_curated` → `idrs[]`
- `domain`, `family` → `domains[]`
- `lcd` → `lcds[]`
- `morf` → `morfs[]`
- `plddt_region` → `plddt_regions[]`

**pLDDT region categories**:
- `very_low`: mean < 50
- `low`: 50–70
- `confident`: 70–90
- `very_high`: ≥ 90

**Errors**: 404 if `uniprot_id` not in `proteins`.

---

### GET /proteins

Paginated protein list with optional filters.

**Query parameters**:
| param | type | description |
|---|---|---|
| `organism` | str | exact match on `proteins.organism` |
| `taxon_id` | int | exact match on `proteins.taxon_id` |
| `mlo` | str | filter to proteins annotated in this `unified_mlo` |
| `role` | str | `driver` or `client` |
| `source_db` | str | one of the 5 source databases |
| `page` | int | default 1 |
| `per_page` | int | default 50, max 200 |

**Response schema**:
```json
{
  "total": 892,
  "page": 1,
  "per_page": 50,
  "filters_applied": { "mlo": "stress_granule", "organism": "Homo sapiens" },
  "proteins": [
    {
      "uniprot_id": "P35637",
      "gene_name": "FUS",
      "protein_name": "RNA-binding protein FUS",
      "organism": "Homo sapiens",
      "sequence_length": 526,
      "disorder_mobidb_lite_dc": 0.796,
      "disorder_alphafold_dc": null,
      "idr_regions": { "mobidb_lite": [[1, 286], [375, 526]] },
      "lcr_regions": { "mobidb_lite": [{"start": 1, "end": 165, "label": "G-rich"}] },
      "domains": { "Pfam": [{"start": 285, "end": 371, "label": "RNA recognition motif", "accession": "PF00076"}] },
      "mlo_count": 3,
      "mlos": ["stress_granule", "nuclear_speckle", "paraspeckle"]
    }
  ]
}
```

`idr_regions`, `lcr_regions` y `domains` provienen de `protein_summary` (ver Auxiliary tables).
Todos los campos de región son `null` si la proteína no tiene entrada en `protein_summary`.

---

### GET /mlo/{unified_mlo}

Returns MLO record with definitions, aggregate stats, and paginated protein list.

**Query parameters**: `page`, `per_page` (default 50, max 200), `organism`, `role`, `source_db`.

**Response schema**:
```json
{
  "unified_mlo": "stress_granule",
  "category": "cytoplasmic_rnp",
  "definitions": [
    { "source_db": "PhaseDB", "source_name": "Stress granule", "definition": "..." },
    { "source_db": "DrLLPS", "source_name": "SGs", "definition": "..." }
  ],
  "stats": {
    "total_proteins": 892,
    "by_source": { "PhaseDB": 450, "DrLLPS": 312, "PhasePro": 130 },
    "by_role": { "driver": 124, "client": 768, "unknown": 0 },
    "organisms": ["Homo sapiens", "Mus musculus", "Saccharomyces cerevisiae"]
  },
  "proteins": {
    "page": 1,
    "per_page": 50,
    "total": 892,
    "items": [
      {
        "uniprot_id": "P35637",
        "gene_name": "FUS",
        "organism": "Homo sapiens",
        "unified_role": "driver",
        "sources": ["PhaseDB", "DrLLPS"],
        "disorder_mobidb_lite_dc": 0.796,
        "disorder_alphafold_dc": null,
        "idr_regions": { "mobidb_lite": [[1, 286], [375, 526]] },
        "lcr_regions": { "mobidb_lite": [{"start": 1, "end": 165, "label": "G-rich"}] },
        "domains": { "Pfam": [{"start": 285, "end": 371, "label": "RNA recognition motif", "accession": "PF00076"}] }
      }
    ]
  }
}
```

**Errors**: 404 if `unified_mlo` not in `mlo_vocabulary`.

---

### GET /mlos

Full canonical MLO vocabulary. No pagination (164 entries — manageable).

**Query parameters**: `category` (optional filter).

**Response schema**:
```json
{
  "total": 164,
  "mlos": [
    {
      "unified_mlo": "stress_granule",
      "category": "cytoplasmic_rnp",
      "protein_count": 892
    }
  ]
}
```

---

### GET /search

Basic search over gene names, UniProt IDs, protein names, and MLO names.
Uses FTS5 if available; falls back to LIKE if not.

**Query parameters**:
| param | type | description |
|---|---|---|
| `q` | str | search term (required, min 2 chars) |
| `mode` | str | `exact` or `fuzzy` (default `fuzzy`) |

**FTS5 setup** (create on startup if not exists):
```sql
CREATE VIRTUAL TABLE IF NOT EXISTS fts_proteins USING fts5(
    uniprot_id, gene_name, protein_name,
    content='proteins', content_rowid='rowid'
);

CREATE VIRTUAL TABLE IF NOT EXISTS fts_mlos USING fts5(
    unified_mlo,
    content='mlo_vocabulary', content_rowid='rowid'
);
```

**Response schema**:
```json
{
  "query": "FUS",
  "mode": "fuzzy",
  "total_hits": 5,
  "proteins": [
    {
      "uniprot_id": "P35637",
      "gene_name": "FUS",
      "protein_name": "RNA-binding protein FUS",
      "organism": "Homo sapiens",
      "match_field": "gene_name"
    }
  ],
  "mlos": [
    {
      "unified_mlo": "stress_granule",
      "category": "cytoplasmic_rnp",
      "match_field": "unified_mlo"
    }
  ]
}
```

**Errors**: 422 if `q` is shorter than 2 characters.

**Limitación frontend**: `SearchProteinHit` solo incluye metadatos básicos (sin `mlos`, `domains`, `idr_regions`). El frontend usa `/search/advanced?gene_name=q` en su lugar para obtener `ProteinSummary` completo. Pendiente: endpoint full-text que retorne `ProteinSummary`.

---

### GET /search/advanced

Structured search with field-level filters. All parameters are optional but at least
one must be provided.

**Query parameters**:
| param | type | description |
|---|---|---|
| `gene_name` | str | exact or partial match on gene name |
| `uniprot_id` | str | exact match |
| `organism` | str | exact match on organism name |
| `taxon_id` | int | exact match |
| `mlo` | str | annotated in this unified_mlo |
| `role` | str | `driver` or `client` |
| `source_db` | str | one of the 5 sources |
| `feature_type` | str | `idr`, `idr_curated`, `lcd`, `domain`, `family`, `morf`, `plddt_region` |
| `feature_label` | str | partial match on `sequence_features.label` (domain name, LCD class, etc.) |
| `feature_accession` | str | exact match on Pfam/SMART accession |
| `page` | int | default 1 |
| `per_page` | int | default 50, max 200 |

**Response schema**: same as `GET /proteins` with additional `filters_applied` object
showing all active filters.

**Errors**: 422 if no filter parameters are provided.

---

### GET /stats

Aggregate statistics for the whole dataset. Results should be cached in memory
at startup (computed once, never stale during a server session).

**Response schema**:
```json
{
  "database_version": "2.0",
  "last_updated": "2025-08-01",
  "proteins": {
    "total": 15409,
    "by_organism": { "Homo sapiens": 8432, "Mus musculus": 2341 },
    "top_organisms": 10
  },
  "mlo_annotations": {
    "total": 37990,
    "unique_mlos": 164,
    "by_source": {
      "PhaseDB": 12000, "DrLLPS": 9500, "PhasePro": 7200,
      "LLPSDB": 5100, "CDCODE": 4190
    },
    "by_role": { "driver": 8200, "client": 22100, "unknown": 7690 }
  },
  "sequence_features": {
    "total": 303415,
    "by_type": { "IDR": 14200, "domain": 98000, "LCD": 11000 },
    "proteins_with_features": 15409
  },
  "ppi": {
    "total_interactions": 284000,
    "proteins_with_ppi": 12300
  }
}
```

---

## Error response format

All errors return this structure:

```json
{ "error": "protein_not_found", "message": "No protein with UniProt ID 'XXXXX'" }
```

| Situation | HTTP | `error` |
|---|---|---|
| Protein not in DB | 404 | `protein_not_found` |
| MLO not in vocabulary | 404 | `mlo_not_found` |
| Invalid query parameter | 422 | `invalid_parameter` |
| `q` shorter than 2 chars | 422 | `invalid_parameter` |
| No filters in advanced search | 422 | `no_filters_provided` |
| `per_page` > 200 | 422 | `invalid_parameter` |
| FTS5 not available (fuzzy search requested) | 501 | `fts5_unavailable` |
| SQLite error | 500 | `database_error` |

---

## Auxiliary tables

### `proteins` — additional columns (ALTER TABLE, populated by `build_summary.py`)

```sql
ALTER TABLE proteins ADD COLUMN disorder_mobidb_lite_dc REAL;
-- content_fraction from prediction-disorder-mobidb_lite in mobidb_cache.db
-- NULL if protein has no entry in cache or key is absent

ALTER TABLE proteins ADD COLUMN disorder_alphafold_dc REAL;
-- content_fraction from prediction-disorder-alphafold in mobidb_cache.db
-- NULL if protein has no entry in cache or key is absent
```

The API serializes NULL as `null` (not 0.0) — the frontend handles the distinction.

### `protein_summary` — precomputed aggregates for list endpoints

Avoids per-request JOINs over `sequence_features` (303K rows) and `mlo_annotations`
(38K rows) when rendering paginated protein lists.

```sql
CREATE TABLE IF NOT EXISTS protein_summary (
    uniprot_id      TEXT PRIMARY KEY,  -- FK → proteins
    idr_regions     TEXT,              -- JSON, see schema below
    lcr_regions     TEXT,              -- JSON, see schema below
    domains         TEXT,              -- JSON, see schema below
    has_driver      INTEGER,           -- 1 if any annotation has unified_role='driver'
    has_client      INTEGER,           -- 1 if any annotation has unified_role='client'
    source_db_count INTEGER,           -- count of distinct source_db in mlo_annotations
    mlo_count       INTEGER,           -- count of distinct unified_mlo in mlo_annotations
    mlos            TEXT               -- JSON array of unified_mlo strings
);
```

**Nota**: `has_driver`, `has_client` y `source_db_count` existen en la tabla pero actualmente **no se exponen** en `ProteinSummary` (pendiente añadir). Los role badges de la UI usan `=== true` (strict) por lo que no activan con `undefined`.

**JSON schemas**:

`idr_regions` — source as top-level key, array of [start, end] pairs (no score needed;
presence in list implies the residues are predicted disordered by that predictor):
```json
{
  "mobidb_lite": [[1, 286], [375, 424], [444, 526]],
  "alphafold":   [[1, 278], [368, 426], [451, 526]]
}
```

`lcr_regions` — source as top-level key, objects include compositional label:
```json
{
  "mobidb_lite": [
    {"start": 1,   "end": 165, "label": "G-rich"},
    {"start": 600, "end": 641, "label": "Q-rich"}
  ]
}
```

`domains` — database as top-level key:
```json
{
  "Pfam": [
    {"start": 287, "end": 365, "label": "RNA recognition motif", "accession": "PF00076"},
    {"start": 422, "end": 453, "label": "Zinc finger, RanBP2-type", "accession": "PF00641"}
  ],
  "SMART": [
    {"start": 290, "end": 360, "label": "RRM", "accession": "SM00360"}
  ]
}
```

`mlos` — plain JSON array:
```json
["stress_granule", "p_body", "nuclear_speckle"]
```

**Source mapping** (how `build_summary.py` populates each field):

| JSON key | Source table | Filter |
|---|---|---|
| `idr_regions.mobidb_lite` | `sequence_features` | `feature_type='idr' AND source='MobiDB-lite'` |
| `idr_regions.alphafold` | `sequence_features` | `feature_type='idr' AND source='AlphaFold'` |
| `lcr_regions.mobidb_lite` | `sequence_features` | `feature_type='lcd' AND source='MobiDB-lite'` |
| `domains.Pfam` | `sequence_features` | `feature_type='domain' AND source='Pfam'` |
| `domains.SMART` | `sequence_features` | `feature_type='domain' AND source='SMART'` |

**Query pattern for list endpoints** — filtering uses original indexed tables;
`protein_summary` is joined only for the paginated result set:

```sql
WITH filtered AS (
    SELECT DISTINCT p.uniprot_id
    FROM proteins p
    JOIN mlo_annotations a ON p.uniprot_id = a.uniprot_id
    WHERE a.unified_mlo = ? AND LOWER(p.organism) = LOWER(?)
    LIMIT ? OFFSET ?
)
SELECT p.uniprot_id, p.gene_name, p.protein_name, p.organism,
       p.length AS sequence_length,
       p.disorder_mobidb_lite_dc, p.disorder_alphafold_dc,
       ps.idr_regions, ps.lcr_regions, ps.domains,
       ps.mlo_count, ps.mlos
FROM filtered f
JOIN proteins p          ON p.uniprot_id  = f.uniprot_id
JOIN protein_summary ps  ON ps.uniprot_id = f.uniprot_id
ORDER BY f.uniprot_id;
```

### `build_summary.py` — population script

Run once after all pipeline stages are complete, before starting the API.
Located at project root alongside other pipeline scripts.

Steps:
1. `ALTER TABLE proteins ADD COLUMN disorder_mobidb_lite_dc REAL` (ignore if exists)
2. `ALTER TABLE proteins ADD COLUMN disorder_alphafold_dc REAL` (ignore if exists)
3. For each protein in `proteins`: read JSON from `mobidb_cache.db`, extract
   `prediction-disorder-mobidb_lite.content_fraction` and
   `prediction-disorder-alphafold.content_fraction`, UPDATE `proteins`.
4. `CREATE TABLE IF NOT EXISTS protein_summary ...`
5. For each protein: aggregate from `sequence_features` and `mlo_annotations`,
   serialize JSON fields, INSERT into `protein_summary`.
6. `CREATE INDEX IF NOT EXISTS idx_sf_type_db ON sequence_features(feature_type, database)`
7. Report counts: proteins updated, proteins with NULL disorder fields.

## Schema validation (mandatory before any implementation)

Before writing any code, run the following against the real database and verify that
the column names, types, and representative values match what is documented in this file
and in CLAUDE_phase2_database.md:

```sql
PRAGMA table_info(proteins);
PRAGMA table_info(mlo_annotations);
PRAGMA table_info(mlo_vocabulary);
PRAGMA table_info(mlo_definitions);
PRAGMA table_info(sequence_features);
PRAGMA table_info(ppi);
SELECT * FROM proteins LIMIT 3;
SELECT * FROM mlo_annotations LIMIT 3;
SELECT * FROM sequence_features LIMIT 5;
SELECT * FROM ppi LIMIT 3;
SELECT DISTINCT feature_type FROM sequence_features;
SELECT DISTINCT source_db FROM mlo_annotations;
```

If any column name, type, or value differs from what is documented here, update
`models/schemas.py` and the relevant queries accordingly before proceeding.
Do not assume the documentation is correct — the database is the source of truth.

## Sample-first testing rule

For every router, before running against the full dataset:
1. Test with a small, fixed set of known inputs (see below).
2. Inspect the raw response — check for missing fields, null handling, type mismatches.
3. Only proceed to the next router after the sample response looks correct.

**Fixed test cases**:
- Protein: `P35637` (FUS — has IDRs, domains, LCDs, PPIs, multiple MLO annotations)
- Protein: `P0DMV8` (HSPA1A — as a second check)
- MLO: `stress_granule`
- Search query: `"FUS"`
- Advanced search: `feature_type=idr&organism=Homo sapiens`

If any of these returns an unexpected result (missing field, wrong type, empty array
where data is expected), fix before moving on. Do not assume the issue is isolated.

## Implementation rules

- All database access is async via `aiosqlite`. Never use synchronous `sqlite3` in
  async route handlers.
- SQL strings live in `queries/`. Routers import query functions, not raw SQL.
- Use parameterized queries everywhere — never f-string interpolation into SQL.
- `GET /stats` stats are computed once at startup in the lifespan context and stored
  in app state (`app.state.stats`). Do not recompute per request.
- FTS5 tables are created in lifespan if they don't exist. Population of FTS5 tables
  uses `INSERT INTO fts_proteins SELECT ...` — run only if the FTS table is empty.
- `per_page` is capped at 200 server-side regardless of what the client sends.
- All string filters (`organism`, `gene_name`, `feature_label`) are case-insensitive
  (`LOWER()` on both sides, or `COLLATE NOCASE`).
- Log all 500 errors with the full SQL query and exception traceback.
- Do not expose raw SQLite error messages to the client — return generic `database_error`.

---

## Launch prompt for Claude Code

See separate file: `LAUNCH_PROMPT_phase4.md`