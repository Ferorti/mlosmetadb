# MLOsMetaDB — Database Build Phase

## Objetivo de esta sesión

Construir la base de datos SQLite principal de MLOsMetaDB y los caches
locales de APIs externas (UniProt, InterPro, MobiDB).

Esta fase tiene dos etapas:

1. **Fetch + cache**: descargar y guardar JSON crudo de cada API externa
2. **Parse + load**: leer los caches y poblar las tablas de la base principal

En esta sesión se implementa **solo la etapa 1** (fetch + cache) y la
estructura de la base principal. Los parsers de features se diseñan en
la fase siguiente.

---

## Estructura de directorios

```
mlosmetadb/
├── database/
│   ├── final/                    # archivos de entrada — no modificar
│   │   ├── mlosmetadb.tsv        # dataset principal
│   │   ├── mlo_mapping.csv       # source_mlo → unified_mlo
│   │   └── mlo_definitions.csv   # definiciones por fuente
│   ├── cache/                    # caches locales de APIs — creado por scripts
│   │   ├── uniprot_cache.db
│   │   ├── interpro_cache.db
│   │   └── mobidb_cache.db
│   └── mlosmetadb.db             # base principal SQLite
├── scripts/
│   ├── build_db.py               # crea esquema y carga archivos de final/
│   ├── fetch_uniprot.py          # fetch batch UniProt → uniprot_cache.db
│   ├── fetch_interpro.py         # fetch InterPro → interpro_cache.db
│   ├── fetch_mobidb.py           # fetch MobiDB → mobidb_cache.db
│   └── build_summary.py          # popula proteins.disorder_* y protein_summary — corre después de los parsers de features
└── CLAUDE.md
```

---

## Reglas generales

- Nunca modificar archivos en `database/final/`
- Los caches son append-safe: si un script se interrumpe y se relanza,
  no debe duplicar entradas ni repetir requests ya cacheadas
- Todo fetch debe guardar `fetched_at` (timestamp ISO) y la versión de
  la API si está disponible en el response
- Los scripts deben reportar progreso: filas procesadas, requests hechos,
  entradas ya en cache (skipped), errores
- Delays entre requests: 0.2s para UniProt, 0.2s para InterPro, 0.2s
  para MobiDB — respetar rate limits
- Si un request falla (timeout, 429, 5xx): reintentar hasta 3 veces con
  backoff exponencial (1s, 2s, 4s), luego loguear el error y continuar

---

## Esquema de la base principal (mlosmetadb.db)

### Tabla: proteins
```sql
CREATE TABLE IF NOT EXISTS proteins (
    uniprot_id       TEXT PRIMARY KEY,
    gene_name        TEXT,
    protein_name     TEXT,
    organism         TEXT,
    taxon_id         INTEGER,
    sequence         TEXT,
    length           INTEGER,
    lineage          TEXT,    -- JSON array de strings (reino a especie)
    reviewed         INTEGER, -- 1 = Swiss-Prot, 0 = TrEMBL
    fetch_date       TEXT,    -- ISO timestamp de cuando se obtuvo de UniProt
    disorder_mobidb_lite_dc  REAL,   -- content_fraction from prediction-disorder-mobidb_lite (mobidb_cache.db)
    disorder_alphafold_dc    REAL    -- content_fraction from prediction-disorder-alphafold (mobidb_cache.db)
    -- NULL if protein has no cache entry or key is absent in JSON
);
```

### Tabla: mlo_annotations
```sql
CREATE TABLE IF NOT EXISTS mlo_annotations (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    uniprot_id       TEXT NOT NULL REFERENCES proteins(uniprot_id),
    source_db        TEXT NOT NULL,
    source_mlo       TEXT NOT NULL,
    unified_mlo      TEXT NOT NULL REFERENCES mlo_vocabulary(unified_mlo),
    source_role      TEXT,
    unified_role     TEXT,
    evidence         TEXT,    -- PMIDs semicolon-separated o NULL
    dataset_version  TEXT DEFAULT 'v2'
);
```

### Tabla: mlo_vocabulary
```sql
CREATE TABLE IF NOT EXISTS mlo_vocabulary (
    unified_mlo      TEXT PRIMARY KEY,
    category         TEXT,
    mapping_version  TEXT DEFAULT 'v3'
);
```

### Tabla: mlo_definitions
```sql
CREATE TABLE IF NOT EXISTS mlo_definitions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    unified_mlo      TEXT NOT NULL REFERENCES mlo_vocabulary(unified_mlo),
    source_db        TEXT NOT NULL,
    source_name      TEXT NOT NULL,
    definition       TEXT
);
```

### Tabla: sequence_features
Esquema preliminar — se completa con parsers en la fase siguiente.

```sql
CREATE TABLE IF NOT EXISTS sequence_features (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    uniprot_id       TEXT NOT NULL REFERENCES proteins(uniprot_id),
    feature_type     TEXT NOT NULL,
    -- valores posibles: 'domain', 'IDR', 'LCD', 'coiled_coil',
    -- 'signal_peptide', 'transmembrane', 'family', 'functional_site',
    -- 'binding_region', 'disorder_consensus'
    source           TEXT NOT NULL,
    -- valores posibles: 'Pfam', 'SMART', 'CDD', 'PANTHER', 'Gene3D',
    -- 'PROSITE', 'MobiDB-lite', 'MobiDB', 'Coils', 'SignalP', 'TMHMM'
    label            TEXT,     -- nombre del dominio, tipo de region, etc.
    accession        TEXT,     -- accession en la base de origen (IPR, PF, etc.)
    start            INTEGER,
    end              INTEGER,
    score            REAL,     -- e-value, disorder score, etc. segun fuente
    metadata         TEXT,     -- JSON con campos adicionales variables por fuente
    fetch_date       TEXT
);
```

### Tabla: protein_summary
```sql
CREATE TABLE IF NOT EXISTS protein_summary (
    uniprot_id      TEXT PRIMARY KEY REFERENCES proteins(uniprot_id),
    idr_regions     TEXT,   -- JSON: {"mobidb_lite": [[start,end],...], "alphafold": [[start,end],...]}
    lcr_regions     TEXT,   -- JSON: {"mobidb_lite": [{"start":N,"end":N,"label":"G-rich"},...]}
    domains         TEXT,   -- JSON: {"Pfam": [{"start":N,"end":N,"label":"...","accession":"PF..."}], "SMART": [...]}
    has_driver      INTEGER,  -- 1 if any mlo_annotations row has unified_role='driver'
    has_client      INTEGER,  -- 1 if any mlo_annotations row has unified_role='client'
    source_db_count INTEGER,  -- count of distinct source_db in mlo_annotations
    mlo_count       INTEGER,  -- count of distinct unified_mlo in mlo_annotations
    mlos            TEXT      -- JSON array: ["stress_granule","p_body"]
);
```

---

## Esquema de los caches (database/cache/)

Los tres archivos de cache tienen la misma estructura:

```sql
CREATE TABLE IF NOT EXISTS responses (
    uniprot_id   TEXT PRIMARY KEY,
    response     TEXT NOT NULL,  -- JSON crudo completo de la API
    fetched_at   TEXT NOT NULL,  -- ISO timestamp
    api_version  TEXT,           -- version de la API/base si disponible
    status_code  INTEGER         -- HTTP status code del response
);

CREATE TABLE IF NOT EXISTS fetch_errors (
    uniprot_id   TEXT NOT NULL,
    error_type   TEXT,           -- 'timeout', 'http_error', 'parse_error'
    error_detail TEXT,
    attempted_at TEXT NOT NULL,
    attempts     INTEGER DEFAULT 1
);
```

---

## Script: build_db.py

Crea el esquema completo y carga los archivos de `database/final/`.

**Pasos en orden:**

1. Crear `database/mlosmetadb.db` con todas las tablas (si no existe)
2. Crear `database/cache/` y los tres archivos de cache (si no existen)
3. Cargar `mlo_mapping.csv` → poblar `mlo_vocabulary`
   - Columnas: `Nombre Sugerido` → `unified_mlo`, `Categoria` → `category`
   - Ignorar entradas donde `Nombre Sugerido` sea: DISCARD, NULL,
     NotInformed, synthetic_condensate, o vacío
   - Deduplicar por `unified_mlo` (puede haber múltiples source names
     con el mismo canonical)
4. Cargar `mlo_definitions.csv` → poblar `mlo_definitions`
   - Columnas: `unified_mlo`, `source_db`, `source_name`, `definition`
   - Solo insertar filas donde `unified_mlo` existe en `mlo_vocabulary`
   - Ignorar filas con `definition` vacía
5. Cargar `mlosmetadb.tsv` → poblar `mlo_annotations` y `proteins`
   - Ignorar filas donde `unified_mlo` es 'unmapped', 'NULL', o vacío
   - Ignorar filas donde `uniprot_id` es vacío o 'NULL'
   - Insertar `uniprot_id` únicos en `proteins` como stubs
     (solo el campo `uniprot_id`, el resto NULL — se completa con fetch)
   - Insertar todas las filas válidas en `mlo_annotations`
6. Reportar conteos finales por tabla

**Output esperado al finalizar:**
```
mlo_vocabulary:   N entradas
mlo_definitions:  N entradas
proteins (stub):  N entradas
mlo_annotations:  N entradas
cache dbs:        creados vacios
```

---

## Script: fetch_uniprot.py

Puebla `uniprot_cache.db` y actualiza `proteins` en `mlosmetadb.db`.

**Endpoint batch:**
```
https://rest.uniprot.org/uniprotkb/search
  ?query=accession:ID1+OR+accession:ID2+...
  &fields=accession,gene_names,protein_name,organism_name,
          organism_id,sequence,length,lineage,reviewed
  &format=json&size=500
```

**Lógica:**

1. Leer todos los `uniprot_id` de la tabla `proteins`
2. Filtrar los que ya están en `uniprot_cache.db` con `status_code=200` (skip)
3. Dividir restantes en batches de 500
4. Para cada batch:
   - GET con retry (3 intentos, backoff exponencial 1s/2s/4s)
   - Guardar cada proteína individualmente en `uniprot_cache.db`
   - Actualizar tabla `proteins` con los campos parseados
   - Delay 0.2s entre batches
5. Loguear accessions no encontrados o merged en `fetch_errors`

**Mapeo de campos JSON de UniProt a columnas de proteins:**

| Campo en JSON | Columna |
|---|---|
| `primaryAccession` | `uniprot_id` |
| `genes[0].geneName.value` | `gene_name` |
| `proteinDescription.recommendedName.fullName.value` | `protein_name` |
| `organism.scientificName` | `organism` |
| `organism.taxonId` | `taxon_id` |
| `sequence.value` | `sequence` |
| `sequence.length` | `length` |
| `lineages` array | `lineage` como JSON string |
| `entryType` == "UniProtKB reviewed" | `reviewed` = 1, sino 0 |

---

## Script: fetch_interpro.py

Puebla `interpro_cache.db`.

**Dos endpoints por proteína:**

Endpoint 1 — entradas (dominios, familias, sitios):
```
https://www.ebi.ac.uk/interpro/api/protein/uniprot/{id}
  /entry/all/?format=json&page_size=200
```

Endpoint 2 — features de secuencia (IDRs MobiDB-lite, coiled-coils, TM):
```
https://www.ebi.ac.uk/interpro/api/protein/uniprot/{id}
  /?format=json&extra_fields=sequence
```

**Lógica:**

1. Leer todos los `uniprot_id` de `proteins`
2. Filtrar los que ya están en `interpro_cache.db` (skip)
3. Para cada uniprot_id:
   - Llamar endpoint 1; si hay paginacion (`next`), seguir hasta agotar
   - Llamar endpoint 2
   - Guardar un JSON combinado: `{"entries": [...], "protein": {...}}`
   - Delay 0.2s entre proteínas

---

## Script: fetch_mobidb.py

Puebla `mobidb_cache.db`.

**Endpoint:**
```
https://mobidb.org/api/entry/{uniprot_id}
```

**Lógica:**

1. Leer todos los `uniprot_id` de `proteins`
2. Filtrar los que ya están en `mobidb_cache.db` (skip)
3. Para cada uniprot_id:
   - GET con retry
   - 404: guardar con `status_code=404` y `response='{}'`
     (no reintentar en el futuro)
   - Guardar JSON completo sin filtrar
   - Delay 0.2s entre requests

**El JSON de MobiDB incluye entre otros (guardar todo):**
- `mobidb_consensus.disorder` — IDRs consenso
- `low_complexity` — LCDs por composicion (polyQ, FG, RGG, etc.)
- `binding` — regiones de union en desorden
- `disprot` — anotaciones curadas cuando existen
- `ptm` — PTMs anotados
- `secondary_structure` — estructura secundaria predicha

---

## Script: build_summary.py

Popula `proteins.disorder_*` y la tabla `protein_summary`. Corre después
de que los parsers de features hayan poblado `sequence_features`.

**Pasos en orden:**

1. `ALTER TABLE proteins ADD COLUMN disorder_mobidb_lite_dc REAL` — ignorar
   si ya existe
2. `ALTER TABLE proteins ADD COLUMN disorder_alphafold_dc REAL` — ignorar
   si ya existe
3. Para cada `uniprot_id` en `proteins`: leer JSON de `mobidb_cache.db`,
   extraer `prediction-disorder-mobidb_lite.content_fraction` y
   `prediction-disorder-alphafold.content_fraction`. Si la key no existe en
   el JSON, dejar NULL. `UPDATE proteins`.
4. `CREATE TABLE IF NOT EXISTS protein_summary` con el esquema definido arriba.
5. Para cada `uniprot_id`: agregar desde `sequence_features` y
   `mlo_annotations`, serializar JSON, `INSERT OR REPLACE` en
   `protein_summary`.
6. `CREATE INDEX IF NOT EXISTS idx_sf_type_source ON sequence_features(feature_type, source)`
7. Reportar: proteínas actualizadas, proteínas con NULL en ambos campos de
   desorden, filas en `protein_summary`.

**Mapeo de fuentes para los JSON de protein_summary:**

| Campo JSON | Tabla fuente | Filtro |
|---|---|---|
| `idr_regions.mobidb_lite` | `sequence_features` | `feature_type='IDR' AND source='MobiDB-lite'` |
| `idr_regions.alphafold` | `sequence_features` | `feature_type='IDR' AND source='AlphaFold'` |
| `lcr_regions.mobidb_lite` | `sequence_features` | `feature_type='LCD' AND source='MobiDB-lite'` |
| `domains.Pfam` | `sequence_features` | `feature_type='domain' AND source='Pfam'` |
| `domains.SMART` | `sequence_features` | `feature_type='domain' AND source='SMART'` |

---

## Orden de ejecucion

```bash
python scripts/build_db.py
python scripts/fetch_uniprot.py
python scripts/fetch_interpro.py   # puede correr en paralelo con mobidb
python scripts/fetch_mobidb.py     # puede correr en paralelo con interpro
# después de que los parsers de features hayan poblado sequence_features:
python scripts/build_summary.py
```

`build_db.py` debe correr primero. Los tres fetch pueden relanzarse
en cualquier momento sin duplicar datos. `build_summary.py` requiere que
`sequence_features` esté poblada por los parsers de features.

---

## Verificacion al finalizar

```sql
-- Cobertura UniProt
SELECT COUNT(*) FROM proteins WHERE sequence IS NOT NULL;
SELECT COUNT(*) FROM proteins WHERE sequence IS NULL;

-- Errores
SELECT error_type, COUNT(*) FROM fetch_errors GROUP BY error_type;

-- Integridad
SELECT COUNT(*) FROM mlo_annotations
  WHERE uniprot_id NOT IN (SELECT uniprot_id FROM proteins);
-- debe ser 0

-- protein_summary coverage
SELECT COUNT(*) FROM protein_summary;
SELECT COUNT(*) FROM proteins WHERE disorder_alphafold_dc IS NULL;

-- sanity check FUS
SELECT uniprot_id, disorder_mobidb_lite_dc, disorder_alphafold_dc
FROM proteins WHERE uniprot_id = 'P35637';
-- disorder_alphafold_dc debe ser ≈ 0.785

SELECT idr_regions, domains, mlo_count FROM protein_summary
WHERE uniprot_id = 'P35637';
```# CLAUDE.md — MLOsMetaDB v2 Frontend

## Project overview

Frontend for MLOsMetaDB v2, a scientific meta-database of proteins associated with
membraneless organelles (MLOs) involved in liquid-liquid phase separation (LLPS).
Compiled SPA (Vite build) served as static files by the FastAPI backend.

---

## Stack

- **Framework**: Vue 3, Composition API, `<script setup>` only. Never use Options API.
- **CSS**: Tailwind CSS v3. Utility-first. Minimal scoped `<style>` blocks — only when
  Tailwind cannot express the rule (e.g. complex pseudo-selectors, third-party overrides).
- **Routing**: Vue Router v4. All routes defined in `src/router/index.js`.
- **State**: Pinia. One store per domain (`search.js`, `protein.js`, `mlo.js`).
- **HTTP**: Axios with a shared instance in `src/api/client.js`.
- **Table**: TanStack Table v8 (`@tanstack/vue-table`). Use for all paginated/sortable data.
- **Visualization**: D3.js v7 — used in `SequenceFeatureViewer.vue` only.
- **Language**: JavaScript (no TypeScript). No `.ts` files, no type annotations.
- **Build**: Vite. Output goes to `../api/static/` so FastAPI can serve it.
- **Fonts**: IBM Plex Sans (Google Fonts) — scoped to `FilterSidebar.vue` only.
  Global font: system default via Tailwind.

---

## Directory structure

```
frontend/
├── src/
│   ├── api/
│   │   ├── client.js               # axios instance, baseURL, interceptors
│   │   ├── proteins.js             # /proteins, /protein/{id}
│   │   ├── mlos.js                 # /mlos, /mlo/{mlo}
│   │   ├── search.js               # /search, /search/advanced
│   │   └── stats.js                # /stats (currently reads from src/data/stats.json)
│   ├── components/
│   │   ├── layout/
│   │   │   ├── AppNavbar.vue       # gradient navy navbar, global
│   │   │   ├── AppFooter.vue       # dark navy footer, global
│   │   │   └── AnnouncementBanner.vue  # amber banner, controlled by src/config.js
│   │   ├── search/
│   │   │   ├── SearchBox.vue       # prop: showSearchOptions (home=true, results=false)
│   │   │   └── FilterSidebar.vue   # IBM Plex Sans font, click-to-apply filters
│   │   ├── browse/
│   │   │   ├── RoleCards.vue
│   │   │   ├── MloBadges.vue       # imports from src/data/mlos.js
│   │   │   └── OrganismGrid.vue
│   │   ├── results/
│   │   │   ├── ResultsPanel.vue
│   │   │   └── SequenceFeatureViewer.vue  # D3 compact track, uses Teleport for tooltip
│   │   ├── protein/
│   │   │   ├── ProteinHeader.vue
│   │   │   ├── ProteinFeatures.vue
│   │   │   ├── ProteinMLOs.vue
│   │   │   └── ProteinOrthologs.vue
│   │   ├── viewers/
│   │   │   ├── MolStarViewer.vue   # DO NOT MODIFY INTERNALS
│   │   │   ├── FeatureViewer.vue   # DO NOT MODIFY INTERNALS
│   │   │   └── ProSeqViewer.vue    # DO NOT MODIFY INTERNALS
│   │   └── ui/
│   │       ├── StatBar.vue
│   │       ├── MloBadge.vue
│   │       ├── RoleBadge.vue
│   │       └── LoadingSpinner.vue
│   ├── pages/
│   │   ├── HomePage.vue
│   │   ├── ResultsPage.vue
│   │   ├── ProteinPage.vue
│   │   ├── MlosPage.vue
│   │   ├── DownloadPage.vue
│   │   └── AboutPage.vue
│   ├── composables/
│   │   ├── useSearch.js            # search logic + URL query param sync
│   │   ├── useProtein.js           # protein data fetching + normalization
│   │   └── useMlos.js              # MLO data + compartment grouping
│   ├── stores/
│   │   ├── search.js
│   │   ├── protein.js
│   │   └── mlo.js
│   ├── router/
│   │   └── index.js
│   ├── data/
│   │   ├── stats.json              # static stats, mirrors GET /stats response
│   │   └── mlos.js                 # PLACEHOLDER_MLOS array, shared across components
│   ├── utils/
│   │   ├── format.js               # formatMlo(), formatCount(), formatPmids()
│   │   └── parseFeatures.js        # parseIdrRegions(), parseDomains(), buildFeatureStats()
│   ├── config.js                   # BANNER config
│   ├── assets/
│   │   └── main.css                # Tailwind directives only
│   └── main.js
├── public/
├── index.html                      # loads IBM Plex Sans + Tabler Icons from CDN
├── vite.config.js
└── tailwind.config.js
```

---

## API

Base URL: `/api`. The axios instance in `src/api/client.js` sets `baseURL: '/api'`.
Never hardcode full URLs in components — always call functions from `src/api/`.

### Endpoint → file mapping

```
GET /stats                   → src/api/stats.js       → getStats()
GET /search?q=...            → src/api/search.js      → searchBasic(q, mode)
GET /search/advanced?...     → src/api/search.js      → searchAdvanced(params)
GET /proteins?...            → src/api/proteins.js    → getProteins(params)
GET /protein/{uniprot_id}    → src/api/proteins.js    → getProtein(uniprotId, ppiPage)
GET /mlos?...                → src/api/mlos.js        → getMlos(category)
GET /mlo/{unified_mlo}       → src/api/mlos.js        → getMlo(mlo, params)
```

`getStats()` currently reads from `src/data/stats.json` — swap for `client.get('/stats')`
when the API is ready.

### Null handling

The API serializes SQLite NULL as JSON `null`. The frontend must handle:
- `disorder_mobidb_lite_dc: null` → display `—`, never `0%`
- `evidence_pmids: null` → display nothing, not an empty list
- `unified_role: null` → no role badge (CD-CODE entries have no role data)
- `ppi.interactions: null` → do not render interactions table
- `protein_name: null` → fall back to `gene_name`, then `uniprot_id`

---

## URL state

All search filters are serialized to URL query params so searches are shareable.

Supported query params:
`q`, `mode`, `field`, `organism`, `taxon_id`, `mlo`, `role`, `source_db`,
`feature_type`, `feature_label`, `feature_accession`, `page`, `per_page`

On filter change: `router.push({ path: '/results', query: filters })`
On ResultsPage mount: initialize filters from `route.query`

---

## Routes

```js
{ path: '/',               component: HomePage }
{ path: '/results',        component: ResultsPage }
{ path: '/protein/:id',    component: ProteinPage }
{ path: '/mlo/:mlo',       component: MlosPage }
{ path: '/mlos',           component: MlosPage }
{ path: '/download',       component: DownloadPage }
{ path: '/about',          component: AboutPage }
```

Vue Router must use `createWebHistory()`.

---

## Layout and visual design

### App.vue structure
```
AnnouncementBanner   ← amber, dismissable, controlled by config.js
AppNavbar            ← gradient navy, always visible
<RouterView />       ← page content
AppFooter            ← dark navy, always visible
```

### Navbar
- Background: `bg-gradient-to-r from-[#1B4F8A] to-[#2B7CD8]`
- Inner container: `max-w-6xl mx-auto px-6 flex items-center justify-between`
- Logo: three dots (light blue, green, lighter blue) + "MLOsMetaDB" white + "v2" muted

### ResultsPage layout
- Search bar: full width with `bg-[#EBF3FB]` background, inner `max-w-6xl mx-auto`
- Content: `max-w-6xl mx-auto px-6 flex gap-0 mt-6`
  - FilterSidebar: 220px fixed width, IBM Plex Sans font
  - ResultsPanel: flex-1

### Result rows
- Separated by `border-b border-[var(--color-border-tertiary)]` — NO card borders
- Row height: natural (no fixed height)
- Hover: `hover:bg-slate-50`
- Structure per row (top to bottom):
  1. Protein name (`text-[16px] font-medium text-[#185FA5]`) + Role badge(s) right-aligned
  2. UniProt acc (mono) · Gene name · Organism (italic) · ★ if reviewed
  3. `Organelles` key (80px fixed) + MLO names as plain text separated by ·
  4. `Features` key (80px fixed) + inline stats + D3 compact track

### Feature colors (badges and D3 track)
- IDR:    `bg-[#FCEBEB] text-[#791F1F] border-[#F7C1C1]` / D3: `#F5A0A0`
- LCD:    `bg-[#FAEEDA] text-[#633806] border-[#FAC775]` / D3: `#FAC775`
- Domain: `bg-[#EAF3DE] text-[#27500A] border-[#C0DD97]` / D3: `#86C865`

### SearchBox variants
- `showSearchOptions: true` (HomePage): shows "Drivers only" + "Exact match" chips
  - Desktop: chips inside input row
  - Mobile: chips on second line inside input container (`flex flex-wrap`)
- `showSearchOptions: false` (ResultsPage): no chips, clean input only

### FilterSidebar behavior
- Filter options: plain text links, click to apply immediately
- When a filter is active: ALL options in that section hidden, only active chip shown
- Removing chip (×): options reappear with `opacity` fade transition (0.15s)
- Font: IBM Plex Sans, options at `text-xs`, section headers at `text-xs font-medium`

---

## Color palette

```js
// tailwind.config.js
colors: {
  brand: {
    blue:  '#185FA5',   // driver, links, CTAs
    green: '#3B6D11',   // client
    amber: '#854F0B',   // accent
    teal:  '#0F6E56',   // hover
  }
}
```

Role display — always via `ui/RoleBadge.vue`, never inline:
- `driver` → brand-blue
- `client` → brand-green
- `null`   → no badge

### Text color rules

- **Never use Tailwind's `text-gray-400` or lighter for body/UI text** — it fails contrast and is nearly illegible.
- Secondary/muted text minimum: `#48 4E 59` (`rgb(72,78,89)`) — use `text-[#484E59]` or `text-gray-600` (which is `#4B5563`, close enough).
- Use lighter grays (`text-gray-400`) only for genuine placeholders inside inputs or purely decorative separators.
- Primary body text: `text-gray-800` (`#1f2937`) or darker.
- Links and interactive labels: `text-[#185FA5]` (brand blue).

---

## Shared data and utilities

### src/data/mlos.js
Single source of truth for placeholder MLO list.
Imported by `MloBadges.vue` and `FilterSidebar.vue`.
Each entry: `{ unified_mlo, category, protein_count, driver_count }`.

### src/utils/format.js
- `formatMlo(str)` — underscore → space, capitalize first word
- `formatCount(n)` — null → `—`, numbers → `toLocaleString()`
- `formatPmids(str)` — semicolon-separated PMIDs → `[{ id, url }]`

### src/utils/parseFeatures.js
- `parseIdrRegions(json)` — returns `[{ start, end }]`
- `parseLcdRegions(json)` — returns `[{ start, end, label }]`
- `parseDomains(json)`    — returns deduplicated `[{ start, end, label, accession }]`
- `buildFeatureStats({idrRegions, lcdRegions, domains, sequenceLength})`
  → `"IDRs: 54% · LCD: 12% · 3 domains · 526 aa"`

### src/config.js
```js
export const BANNER = {
  enabled: true,
  type: 'warning',
  message: 'MLOsMetaDB v2 is under active development...',
}
```

---

## FastAPI integration

Vite builds to `../api/static/`. SPA fallback in `api/main.py` must be registered
AFTER all `/api/*` routers:

```python
app.mount('/assets', StaticFiles(directory='static/assets'), name='assets')

@app.get('/{full_path:path}')
async def spa_fallback(full_path: str):
    return FileResponse('static/index.html')
```

---

## Component conventions

- PascalCase filenames. One component per file.
- Props via `defineProps` with defaults. Emits via `defineEmits`.
- No direct DOM manipulation except inside D3/viewer components.
- Data fetching only via `src/api/` functions, never directly in components.
- Logic shared by 2+ components → composable, not a component.
- No new npm dependencies without checking if Tailwind + native Vue solves it first.

---

## What NOT to do

- No Bootstrap, Vuetify, Quasar, or other CSS frameworks. Tailwind only.
- No inline `style="..."` except where Tailwind cannot express it.
- No `setTimeout` for reactivity — use `nextTick` or `watch`.
- No raw API responses stored in components — normalize first.
- Do not modify internals of `MolStarViewer.vue`, `FeatureViewer.vue`, `ProSeqViewer.vue`.
- Do not register the SPA fallback in FastAPI before the `/api` routers.
- `unified_role` has only two valid values: `'driver'` and `'client'`. Null is allowed.
  `'regulator'` does not exist in v2 schema.

---

## Git workflow

After every prompt that results in working, verified changes:
1. Run `npm run dev` and confirm no build errors in the terminal output
2. `git add -A`
3. `git commit -m "<short description of what was changed>"`

Do NOT commit if:
- `npm run dev` throws console errors
- A previously working feature is broken
- The task was only partially completed

One commit per prompt. Commit message should describe what changed, not what
was asked — e.g. "fix sidebar filter collapse behavior" not "applied corrections round 5".

---

## Current implementation status

### Done
- AppNavbar, AppFooter, AnnouncementBanner
- HomePage: hero, stats bar, search box, role cards, MLO badges, organism grid
- ResultsPage: search bar, FilterSidebar, ResultsPanel with result rows
- Result rows: key-value layout (Organelles / Features), D3 feature track
- FilterSidebar: click-to-apply, chip removal, IBM Plex Sans

### Pending / placeholder
- ProteinPage: stub only
- MlosPage: stub only
- DownloadPage, AboutPage: stubs
- `protein.reviewed` field: not in API yet — star hidden until populated
- Facet counts in sidebar: not in API yet — counts hidden until `/search/facets` exists
- `driver_count` per MLO and organism: placeholder data, real data pending API
- D3 feature track: uses placeholder data until `protein_summary` fields in API response

---

## Diálogo entre IA

Este proyecto es mantenido por múltiples IAs (Gemini, Claude).
- Se mantiene un archivo `DEVLOG.md` para registrar cada cambio implementado.
- Cada entrada en `DEVLOG.md` debe ser concisa, indicando qué se hizo y quién (GEMINI o CLAUDE).
- Antes de comenzar una tarea, consultar el estado actual en `DEVLOG.md`.# MLOsMetaDB — Phase 3: Feature Parsing

## Objetivo

Parsear los caches de InterPro y MobiDB para poblar la tabla
`sequence_features` en `mlosmetadb.db`.

Esta fase no hace requests a APIs externas — solo lee los caches
locales generados en la fase anterior.

---

## Archivos relevantes

```
database/
├── mlosmetadb.db              # base principal — se escribe aquí
└── cache/
    ├── interpro_cache.db      # JSON crudo de InterPro
    └── mobidb_cache.db        # JSON crudo de MobiDB
scripts/
├── parse_interpro.py          # lee interpro_cache → sequence_features
└── parse_mobidb.py            # lee mobidb_cache → sequence_features
```

---

## Esquema de sequence_features (ya existe en mlosmetadb.db)

```sql
CREATE TABLE IF NOT EXISTS sequence_features (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    uniprot_id   TEXT NOT NULL REFERENCES proteins(uniprot_id),
    feature_type TEXT NOT NULL,
    source       TEXT NOT NULL,
    label        TEXT,
    accession    TEXT,
    start        INTEGER,
    end          INTEGER,
    score        REAL,
    metadata     TEXT,   -- JSON string con campos adicionales
    fetch_date   TEXT
);
```

`feature_type` valores posibles en esta fase:
- `domain` — dominios Pfam y SMART
- `family` — familias Pfam
- `idr` — regiones intrínsecamente desordenadas
- `idr_curated` — IDRs curados de DisProt
- `lcd` — regiones de baja complejidad
- `morf` — regiones de unión desordenadas (MoRFs)
- `coiled_coil` — coiled-coils
- `signal_peptide` — péptido señal
- `transmembrane` — dominio transmembrana
- `plddt_region` — región con pLDDT bajo (AlphaFold disordered)

---

## Reglas generales de parseo

- Antes de insertar, verificar que el `uniprot_id` existe en `proteins`
- Un uniprot_id puede tener múltiples features del mismo tipo — no deduplicar
- Si `start` o `end` no están disponibles para un feature (ej. familia
  sin posición), insertar con `start=NULL, end=NULL`
- `fetch_date`: usar el `fetched_at` del cache correspondiente
- `metadata`: JSON string con campos adicionales variables por fuente.
  Siempre serializar como `json.dumps(dict)` — nunca dejar NULL si hay
  datos adicionales disponibles
- Usar `INSERT OR IGNORE` para idempotencia — si el script se relanza,
  no duplica filas
- Para idempotencia completa: antes de insertar un uniprot_id, verificar
  si ya tiene filas en `sequence_features` para esa fuente y saltear
- Reportar progreso cada 500 proteínas procesadas
- Loguear proteínas con cache vacío o status_code != 200

---

## Script: parse_interpro.py

### Estructura del JSON en interpro_cache

El JSON almacenado tiene estructura:
```json
{
  "entries": [...],   // matches de dominios/familias/sitios
  "protein": {...}    // features de secuencia (IDRs MobiDB-lite, TM, etc.)
}
```

### Features a extraer de `entries`

Cada elemento de `entries` tiene esta estructura relevante:
```json
{
  "metadata": {
    "accession": "IPR...",
    "name": "...",
    "type": "domain|family|homologous_superfamily|...",
    "source_database": "pfam|smart|..."
  },
  "proteins": [{
    "entry_protein_locations": [{
      "fragments": [{"start": N, "end": N, "score": F}]
    }]
  }]
}
```

**Filtros de fuente y tipo a incluir:**

| source_database | type | feature_type en DB |
|---|---|---|
| pfam | domain | domain |
| pfam | family | family |
| smart | domain | domain |

Descartar: gene3d, superfamily, prints, pirsf, tigrfam, cdd, hamap,
ncbifam, prosite_patterns, prosite_profiles (para esta fase).

**Lógica de extracción de entries:**

```python
for entry in data["entries"]:
    db = entry["metadata"]["source_database"].lower()
    entry_type = entry["metadata"]["type"].lower()
    
    if db not in ("pfam", "smart"):
        continue
    if entry_type not in ("domain", "family"):
        continue
    
    accession = entry["metadata"]["accession"]
    name = entry["metadata"]["name"]
    feature_type = entry_type  # "domain" o "family"
    
    # Extraer posiciones de fragments
    for protein_match in entry.get("proteins", []):
        for location in protein_match.get("entry_protein_locations", []):
            for fragment in location.get("fragments", []):
                start = fragment.get("start")
                end = fragment.get("end")
                score = fragment.get("score")  # puede ser None
                
                # insertar una fila por fragment
```

### Features a extraer de `protein`

El campo `protein` contiene features de secuencia anotadas directamente.
Estructura relevante:
```json
{
  "sequence_features": {
    "coils": [{"start": N, "end": N}],
    "signal_p": [{"start": N, "end": N}],
    "tmhmm": [{"start": N, "end": N}],
    "mobidb_lite": [{"start": N, "end": N}]
  }
}
```

Mapeo a `feature_type`:

| campo JSON | feature_type | source |
|---|---|---|
| `coils` | `coiled_coil` | `Coils` |
| `signal_p` | `signal_peptide` | `SignalP` |
| `tmhmm` | `transmembrane` | `TMHMM` |
| `mobidb_lite` | `idr` | `MobiDB-lite` |

**Nota:** la estructura exacta del campo `protein` puede variar según
la versión de InterPro. Si `sequence_features` no existe en el JSON,
loguear y continuar. Verificar la estructura real del JSON antes de
asumir los nombres de campos — imprimir las claves de `protein` para
las primeras 3 proteínas procesadas.

---

## Script: parse_mobidb.py

### Estructura del JSON en mobidb_cache

El JSON almacenado es una lista de un elemento: `data = json.loads(response)[0]`

Las claves varían por proteína. Siempre verificar con `if key in data`
antes de acceder.

### Features a extraer

#### 1. IDR consenso — `prediction-disorder-mobidb_lite`

```python
key = "prediction-disorder-mobidb_lite"
if key in data:
    for region in data[key].get("regions", []):
        start, end = region[0], region[1]
        content_fraction = data[key].get("content_fraction")
        # feature_type = "idr", source = "MobiDB-lite"
        # metadata = {"content_fraction": content_fraction}
```

#### 2. IDR consenso estricto — `prediction-disorder-th_50`

```python
key = "prediction-disorder-th_50"
if key in data:
    for region in data[key].get("regions", []):
        start, end = region[0], region[1]
        # feature_type = "idr", source = "MobiDB-th50"
        # metadata = {"content_fraction": data[key].get("content_fraction")}
```

#### 3. IDR curado DisProt — `curated-disorder-disprot`

```python
key = "curated-disorder-disprot"
if key in data:
    for region in data[key].get("regions", []):
        start, end = region[0], region[1]
        source_id = data[key].get("source_id", "")
        # feature_type = "idr_curated", source = "DisProt"
        # metadata = {"source_id": source_id,
        #             "content_fraction": data[key].get("content_fraction")}
```

#### 4. LCDs — `prediction-low_complexity-seg`

```python
key = "prediction-low_complexity-seg"
if key in data:
    for region in data[key].get("regions", []):
        start, end = region[0], region[1]
        # feature_type = "lcd", source = "SEG"
```

#### 5. LCDs MobiDB-lite — `prediction-low_complexity-mobidb_lite_sub`

```python
key = "prediction-low_complexity-mobidb_lite_sub"
if key in data:
    for region in data[key].get("regions", []):
        start, end = region[0], region[1]
        # feature_type = "lcd", source = "MobiDB-lite-sub"
```

#### 6. MoRFs — `derived-binding_mode_disorder_to_order-priority`

Regiones de unión desordenadas que se ordenan al unirse (MoRFs).
Usar la versión `-priority` que es más conservadora.

```python
key = "derived-binding_mode_disorder_to_order-priority"
if key in data:
    for region in data[key].get("regions", []):
        start, end = region[0], region[1]
        # feature_type = "morf", source = "MobiDB"
        # metadata = {"content_fraction": data[key].get("content_fraction")}
```

#### 7. IDR AlphaFold — `prediction-disorder-alphafold`

Regiones desordenadas predichas por AlphaFold. Tiene tanto `regions`
pre-calculadas como `scores` por residuo — usar `regions` directamente.

```python
key = "prediction-disorder-alphafold"
if key in data:
    for region in data[key].get("regions", []):
        start, end = region[0], region[1]
        content_fraction = data[key].get("content_fraction")
        # feature_type = "idr", source = "AlphaFold-disorder"
        # metadata = {"content_fraction": content_fraction}
```

#### 8. pLDDT regiones — `prediction-plddt-alphafold`

Regiones con pLDDT bajo (desorden estructural según AlphaFold).
Tiene `regions` pre-calculadas — usar directamente, no convertir scores.

```python
key = "prediction-plddt-alphafold"
if key in data:
    for region in data[key].get("regions", []):
        start, end = region[0], region[1]
        content_fraction = data[key].get("content_fraction")
        # feature_type = "plddt_region", source = "AlphaFold"
        # metadata = {"content_fraction": content_fraction}
```

**Nota sobre escala pLDDT en MobiDB:** los valores de `scores` están
normalizados entre 0 y 1 (divididos por 100). Las `regions` ya están
pre-calculadas por MobiDB usando el umbral estándar pLDDT < 50.
No es necesario recalcularlas desde los scores.

**Patrón general:** todos los campos de MobiDB que tienen `scores`
también tienen `regions` pre-calculadas. Siempre usar `regions` para
extraer posiciones — los `scores` son opcionales para metadata.

---

## Orden de ejecución

```bash
python scripts/parse_interpro.py
python scripts/parse_mobidb.py
```

Ambos pueden relanzarse sin duplicar datos (idempotentes).
Pueden correr secuencialmente o en paralelo (escriben a la misma tabla
pero con diferentes fuentes — no hay conflicto si SQLite está en modo
WAL).

Para activar WAL en mlosmetadb.db antes de correr en paralelo:
```python
conn.execute("PRAGMA journal_mode=WAL")
```

---

## Verificación al finalizar

```sql
-- Conteo por feature_type y fuente
SELECT feature_type, source, COUNT(*) as n
FROM sequence_features
GROUP BY feature_type, source
ORDER BY feature_type, source;

-- Cobertura: qué fracción de proteínas tiene al menos un IDR
SELECT
    COUNT(DISTINCT uniprot_id) as proteinas_con_idr,
    (SELECT COUNT(*) FROM proteins) as total_proteinas
FROM sequence_features
WHERE feature_type = 'idr' AND source = 'MobiDB-lite';

-- Cobertura de dominios Pfam
SELECT COUNT(DISTINCT uniprot_id) as proteinas_con_pfam
FROM sequence_features
WHERE source = 'pfam';

-- Proteínas con transmembrana (candidatas a revisar en anotaciones)
SELECT COUNT(DISTINCT uniprot_id)
FROM sequence_features
WHERE feature_type = 'transmembrane';
```

---
# MLOsMetaDB — Phase 4: PPI and Orthologs

## Objetivo

Poblar dos tablas nuevas en `mlosmetadb.db`:
- `ppi` — interacciones proteína-proteína físicas experimentales (BioGRID)
- `orthologs` — ortólogos en organismos representativos (OrthoDB)

---

## Regla crítica: probar antes de procesar

**Antes de procesar el archivo completo, SIEMPRE probar con un subset
de 5-10 proteínas conocidas.** Proteínas de prueba recomendadas:

```python
TEST_PROTEINS = [
    "P35637",  # FUS — bien anotada, muchas interacciones, IDRs
    "Q92520",  # FMR1 — stress granule driver
    "P09651",  # hnRNP A1 — stress granule
    "P38919",  # eIF4A3 — P-body
    "Q9NQC3",  # RBM14 — paraspeckle
]
```

El flujo obligatorio para cada script es:

1. Implementar el parser
2. Correrlo con `TEST_PROTEINS` únicamente
3. Imprimir los resultados e verificar que son correctos
4. Solo si el test pasa, correr el pipeline completo

No proceder al dataset completo sin confirmar que el test produce
resultados biológicamente razonables (ej. FUS debe tener interacciones
con TDP-43, EWSR1, etc.).

---

## Estructura de directorios

```
mlosmetadb/
├── database/
│   ├── mlosmetadb.db              # base principal — se escribe aquí
│   └── crossref/                  # archivos de fuentes externas
│       ├── BIOGRID-ALL-5.0.257.tab3.zip
│       ├── odb12v0_genes.tab.gz
│       ├── odb12v0_OGs.tab.gz
│       └── odb12v0_OG2genes.tab.gz
├── scripts/
│   ├── parse_biogrid.py
│   └── parse_orthologs.py
└── CLAUDE.md
```

---

## Nuevas tablas en mlosmetadb.db

### Tabla: ppi

```sql
CREATE TABLE IF NOT EXISTS ppi (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    uniprot_id_a        TEXT NOT NULL REFERENCES proteins(uniprot_id),
    uniprot_id_b        TEXT NOT NULL,
    in_db               INTEGER NOT NULL DEFAULT 0, -- 1 si uniprot_id_b está en proteins
    experimental_system TEXT NOT NULL,
    throughput          TEXT,   -- 'Low Throughput' / 'High Throughput'
    organism_id_a       INTEGER,
    organism_id_b       INTEGER,
    pubmed_id           TEXT,
    source_version      TEXT DEFAULT 'BIOGRID-5.0.257'
);

CREATE INDEX IF NOT EXISTS idx_ppi_a ON ppi(uniprot_id_a);
CREATE INDEX IF NOT EXISTS idx_ppi_b ON ppi(uniprot_id_b);
CREATE INDEX IF NOT EXISTS idx_ppi_indb ON ppi(in_db);
```

### Tabla: orthologs

```sql
CREATE TABLE IF NOT EXISTS orthologs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    uniprot_id      TEXT NOT NULL REFERENCES proteins(uniprot_id),
    ortholog_id     TEXT NOT NULL,  -- UniProt ID del ortólogo
    organism        TEXT NOT NULL,
    taxon_id        INTEGER NOT NULL,
    og_id           TEXT,           -- OrthoDB group ID
    in_db           INTEGER NOT NULL DEFAULT 0, -- 1 si ortholog_id está en proteins
    source          TEXT DEFAULT 'OrthoDB',
    source_version  TEXT DEFAULT 'odb12v0'
);

CREATE INDEX IF NOT EXISTS idx_orth_uniprot ON orthologs(uniprot_id);
CREATE INDEX IF NOT EXISTS idx_orth_indb ON orthologs(in_db);
CREATE INDEX IF NOT EXISTS idx_orth_taxon ON orthologs(taxon_id);
```

Crear estas tablas al inicio de cada script si no existen.

---

## Script: parse_biogrid.py

### Archivo de entrada

```
database/crossref/BIOGRID-ALL-5.0.257.tab3.zip
```

Leer directamente desde el ZIP sin descomprimir:
```python
import zipfile, csv

with zipfile.ZipFile("database/crossref/BIOGRID-ALL-5.0.257.tab3.zip") as z:
    filename = [f for f in z.namelist() if f.endswith(".tab3")][0]
    with z.open(filename) as f:
        reader = csv.DictReader(
            (line.decode("utf-8") for line in f),
            delimiter="\t"
        )
```

### Columnas relevantes del tab3

| Columna | Uso |
|---|---|
| `Experimental System` | filtro de inclusión |
| `Experimental System Type` | filtro adicional == "physical" |
| `SWISS-PROT Accessions Interactor A` | UniProt ID A (preferido) |
| `TREMBL Accessions Interactor A` | UniProt ID A (fallback) |
| `SWISS-PROT Accessions Interactor B` | UniProt ID B (preferido) |
| `TREMBL Accessions Interactor B` | UniProt ID B (fallback) |
| `Organism ID Interactor A` | taxon ID de A |
| `Organism ID Interactor B` | taxon ID de B |
| `Throughput` | Low / High Throughput |
| `Publication Source` | PMID (formato "PUBMED:XXXXXXX") |

### Sistemas experimentales válidos

```python
VALID_SYSTEMS = {
    "Co-immunoprecipitation",
    "Affinity Capture-MS",
    "Affinity Capture-Western",
    "Affinity Capture-RNA",
    "FRET",
    "Proximity Label-MS",
    "Biochemical Activity",
    "Reconstituted Complex",
    "Co-crystal Structure",
    "Co-purification",
    "Protein-RNA EMSA",
    "PCA",
}
```

### Lógica del parser

**Paso 1 — Cargar UniProt IDs del dataset en memoria:**
```python
db_proteins = set()  # todos los uniprot_id de la tabla proteins
```

**Paso 2 — Para cada fila del TSV:**

```python
# Filtro 1: tipo físico
if row["Experimental System Type"].strip() != "physical":
    continue

# Filtro 2: sistema válido
if row["Experimental System"].strip() not in VALID_SYSTEMS:
    continue

# Resolver UniProt IDs — Swiss-Prot tiene prioridad sobre TrEMBL
# Los campos pueden tener múltiples valores separados por "|"
def resolve_uniprot(swiss, trembl):
    for acc in swiss.split("|"):
        acc = acc.strip()
        if acc and acc != "-":
            return acc
    for acc in trembl.split("|"):
        acc = acc.strip()
        if acc and acc != "-":
            return acc
    return None

uid_a = resolve_uniprot(
    row["SWISS-PROT Accessions Interactor A"],
    row["TREMBL Accessions Interactor A"]
)
uid_b = resolve_uniprot(
    row["SWISS-PROT Accessions Interactor B"],
    row["TREMBL Accessions Interactor B"]
)

if not uid_a or not uid_b:
    continue

# Filtro 3: al menos uno de los dos debe estar en el dataset
if uid_a not in db_proteins and uid_b not in db_proteins:
    continue

# Normalizar: siempre poner el del dataset en uniprot_id_a
if uid_a not in db_proteins:
    uid_a, uid_b = uid_b, uid_a
    # también intercambiar organism_ids

# Extraer PMID
pubmed_raw = row["Publication Source"].strip()
pubmed_id = pubmed_raw.replace("PUBMED:", "").strip() if "PUBMED" in pubmed_raw else None

# in_db flag
in_db = 1 if uid_b in db_proteins else 0
```

**Paso 3 — Deduplicación:**
Antes de insertar, verificar que no exista ya la misma combinación
`(uniprot_id_a, uniprot_id_b, experimental_system)`. Usar
`INSERT OR IGNORE` con un UNIQUE constraint o verificar en memoria
con un set de tuplas vistas.

### Test obligatorio antes del pipeline completo

```python
# Correr primero con solo estas proteínas
TEST_PROTEINS = {"P35637", "Q92520", "P09651", "P38919", "Q9NQC3"}

# Verificar resultados esperados:
# P35637 (FUS) debe tener interacciones con TDP-43 (Q13148),
# EWSR1 (Q01844), hnRNP A1 (P09651), etc.
```

Imprimir para cada proteína de test: número de interacciones encontradas
y los primeros 5 `uniprot_id_b` con su `experimental_system`.

### Reporte al finalizar

```
Filas procesadas:          N
Filtradas (no physical):   N
Filtradas (sistema inv.):  N
Sin UniProt ID:            N
Ninguno en dataset:        N
Insertadas:                N
  - con in_db = 1:         N  (ambas proteínas en el dataset)
  - con in_db = 0:         N  (solo una en el dataset)
```

---

## Script: parse_orthologs.py

### Archivos de entrada

```
database/crossref/odb12v0_genes.tab.gz
database/crossref/odb12v0_OGs.tab.gz
database/crossref/odb12v0_OG2genes.tab.gz
```

### Organismos de interés

```python
TARGET_TAXONS = {
    9606:  "Homo sapiens",
    10090: "Mus musculus",
    7955:  "Danio rerio",
    7227:  "Drosophila melanogaster",
    6239:  "Caenorhabditis elegans",
    4932:  "Saccharomyces cerevisiae",
    3702:  "Arabidopsis thaliana",
    44689: "Dictyostelium discoideum",
    83333: "Escherichia coli K-12",
}
```

### Estructura de los archivos OrthoDB

**odb12v0_genes.tab** (sin header):
```
gene_id | organism_taxid | protein_id | UniProt_accession | ...
```
Columnas relevantes (0-indexed): verificar con las primeras 3 filas
antes de asumir posiciones — imprimir header o primeras filas al inicio.

**odb12v0_OG2genes.tab** (sin header):
```
og_id | gene_id
```

**odb12v0_OGs.tab** (sin header):
```
og_id | level_taxid | og_name | ...
```

### Lógica del parser

**Paso 1 — Verificar estructura de archivos:**
```python
import gzip

# Imprimir primeras 3 líneas de cada archivo para confirmar columnas
for filepath in [genes_file, ogs_file, og2genes_file]:
    with gzip.open(filepath, "rt") as f:
        for i, line in enumerate(f):
            print(line.strip())
            if i >= 2:
                break
```
**No continuar hasta confirmar las posiciones de columnas correctas.**

**Paso 2 — Cargar genes.tab → diccionario uniprot → (gene_id, taxon_id):**
```python
# Solo cargar genes de los taxons de interés para reducir memoria
uniprot_to_gene = {}   # uniprot_id → gene_id
gene_to_taxon = {}     # gene_id → taxon_id
gene_to_uniprot = {}   # gene_id → uniprot_id

with gzip.open(genes_file, "rt") as f:
    for line in f:
        cols = line.strip().split("\t")
        # verificar índices correctos tras el paso 1
        gene_id = cols[IDX_GENE_ID]
        taxon_id = int(cols[IDX_TAXON])
        uniprot = cols[IDX_UNIPROT].strip()
        
        if not uniprot or uniprot == "":
            continue
            
        gene_to_taxon[gene_id] = taxon_id
        gene_to_uniprot[gene_id] = uniprot
        
        if taxon_id in TARGET_TAXONS or uniprot in db_proteins:
            uniprot_to_gene[uniprot] = gene_id
```

**Paso 3 — Cargar OG2genes.tab → diccionario gene_id → og_id:**
```python
gene_to_og = {}
with gzip.open(og2genes_file, "rt") as f:
    for line in f:
        cols = line.strip().split("\t")
        og_id, gene_id = cols[0], cols[1]
        gene_to_og[gene_id] = og_id
```

**Paso 4 — Construir índice inverso og_id → [gene_ids]:**
```python
from collections import defaultdict
og_to_genes = defaultdict(list)
for gene_id, og_id in gene_to_og.items():
    og_to_genes[og_id].append(gene_id)
```

**Paso 5 — Para cada proteína del dataset:**
```python
db_proteins = set()  # cargar desde tabla proteins

for uniprot_id in db_proteins:
    gene_id = uniprot_to_gene.get(uniprot_id)
    if not gene_id:
        continue
    
    og_id = gene_to_og.get(gene_id)
    if not og_id:
        continue
    
    # Obtener todos los miembros del grupo ortólogo
    for member_gene_id in og_to_genes[og_id]:
        member_taxon = gene_to_taxon.get(member_gene_id)
        member_uniprot = gene_to_uniprot.get(member_gene_id)
        
        # Filtrar por organismos de interés
        if member_taxon not in TARGET_TAXONS:
            continue
        
        # No insertar la proteína consigo misma
        if member_uniprot == uniprot_id:
            continue
        
        if not member_uniprot:
            continue
        
        in_db = 1 if member_uniprot in db_proteins else 0
        
        # insertar en orthologs
```

### Test obligatorio antes del pipeline completo

```python
TEST_PROTEINS = {"P35637", "Q92520", "P09651", "P38919", "Q9NQC3"}
```

Verificar para cada proteína de test:
- ¿Tiene ortólogo en humano? (debe ser ella misma o un parálogo — no insertar)
- ¿Tiene ortólogo en ratón? FUS (P35637) debe tener Q60900
- ¿El flag `in_db` es correcto?

Imprimir para cada proteína de test: lista de ortólogos encontrados
por organismo con su `ortholog_id` e `in_db`.

### Reporte al finalizar

```
Proteínas en dataset:          N
Con gene_id en OrthoDB:        N
Con og_id asignado:            N
Sin ortólogo en ningún taxon:  N
Filas insertadas:              N
  - con in_db = 1:             N
Por organismo:
  Homo sapiens:                N
  Mus musculus:                N
  Danio rerio:                 N
  Drosophila melanogaster:     N
  Caenorhabditis elegans:      N
  Saccharomyces cerevisiae:    N
  Arabidopsis thaliana:        N
  Dictyostelium discoideum:    N
  Escherichia coli K-12:       N
```

---

## Orden de ejecución

```bash
python scripts/parse_biogrid.py
python scripts/parse_orthologs.py
```

Cada script crea sus tablas si no existen y puede relanzarse
sin duplicar datos.

---

## Verificación al finalizar

```sql
-- PPI: distribución por sistema experimental
SELECT experimental_system, COUNT(*) as n
FROM ppi
GROUP BY experimental_system
ORDER BY n DESC;

-- PPI: fracción de interacciones internas (ambas proteínas en el dataset)
SELECT in_db, COUNT(*) FROM ppi GROUP BY in_db;

-- Ortólogos: distribución por organismo
SELECT organism, COUNT(*) as n
FROM orthologs
GROUP BY organism
ORDER BY n DESC;

-- Ortólogos: proteínas sin ningún ortólogo en OrthoDB
SELECT COUNT(*) FROM proteins
WHERE uniprot_id NOT IN (SELECT DISTINCT uniprot_id FROM orthologs);

-- Ortólogos con in_db = 1 (los más valiosos)
SELECT COUNT(*) FROM orthologs WHERE in_db = 1;
```

---

## Prompt de lanzamiento para Claude Code (BioGRID + OrthoDB)

```
Lee CLAUDE_phase4_ppi_orthologs.md. Implementa parse_biogrid.py
primero. Antes de procesar el archivo completo, corre el test
con TEST_PROTEINS e imprimí los resultados para verificar que
son correctos. Solo si el test pasa, procesá el archivo completo.
Luego implementa parse_orthologs.py con el mismo criterio:
primero verificar estructura de archivos imprimiendo las primeras
3 líneas de cada uno, luego test con TEST_PROTEINS, luego
pipeline completo. Mostrar los reportes finales de ambos scripts
antes de terminar.
```

---

## Alternativa para ortólogos: OMA Browser API

**Usar esta sección en lugar de parse_orthologs.py si OrthoDB
tiene cobertura insuficiente.** OMA mapea por UniProt accession
con match exacto de secuencia, lo que da mejor cobertura que
OrthoDB para proteínas TrEMBL.

### Script: fetch_oma.py + parse_oma.py

Mismo patrón que InterPro/MobiDB: fetch → cache → parse.

**Cache:** `database/cache/oma_cache.db` — misma estructura que
los otros caches:
```sql
CREATE TABLE IF NOT EXISTS responses (
    uniprot_id   TEXT PRIMARY KEY,
    response     TEXT NOT NULL,
    fetched_at   TEXT NOT NULL,
    status_code  INTEGER
);
CREATE TABLE IF NOT EXISTS fetch_errors (
    uniprot_id   TEXT,
    error_type   TEXT,
    error_detail TEXT,
    attempted_at TEXT,
    attempts     INTEGER DEFAULT 1
);
```

### Endpoints OMA API

**Ortólogos por UniProt ID:**
```
GET https://omabrowser.org/api/protein/{uniprot_id}/orthologs/?format=json
```

Devuelve lista de ortólogos. Cada elemento tiene:
```json
{
  "entry_nr": 12345,
  "omaid": "HUMAN12345",
  "canonicalid": "P35637",
  "taxon": {
    "id": 9606,
    "name": "Homo sapiens",
    "species": "Homo sapiens"
  },
  "rel_type": "1:1",
  ...
}
```

**Paginación:** la API devuelve 100 resultados por página.
Manejar con el header `Link` o el parámetro `?page=N&per_page=100`.
Para proteínas con muchos ortólogos seguir hasta agotar páginas.

**Rate limit:** OMA no documenta un rate limit explícito.
Usar delay de 0.3s entre requests como práctica conservadora.

### Lógica de fetch_oma.py

```python
import requests, time, json, sqlite3
from datetime import datetime, timezone

BASE_URL = "https://omabrowser.org/api/protein/{uid}/orthologs/?format=json"

def fetch_orthologs(uniprot_id):
    """Fetch all ortholog pages for a given UniProt ID."""
    all_results = []
    url = BASE_URL.format(uid=uniprot_id)
    page = 1

    while url:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 404:
            return None, 404
        resp.raise_for_status()
        data = resp.json()

        # OMA puede devolver lista directa o dict con results
        if isinstance(data, list):
            all_results.extend(data)
            url = None  # sin paginación
        else:
            all_results.extend(data.get("results", []))
            # Seguir paginación si hay next en headers Link
            url = None
            if "Link" in resp.headers:
                links = parse_link_header(resp.headers["Link"])
                url = links.get("next")

        time.sleep(0.3)

    return all_results, 200
```

### Lógica de parse_oma.py

**Organismos de interés** (mismos que OrthoDB):
```python
TARGET_TAXONS = {
    9606, 10090, 7955, 7227, 6239, 4932, 3702, 44689, 83333
}

TAXON_NAMES = {
    9606:  "Homo sapiens",
    10090: "Mus musculus",
    7955:  "Danio rerio",
    7227:  "Drosophila melanogaster",
    6239:  "Caenorhabditis elegans",
    4932:  "Saccharomyces cerevisiae",
    3702:  "Arabidopsis thaliana",
    44689: "Dictyostelium discoideum",
    83333: "Escherichia coli K-12",
}
```

**Extracción por entrada del JSON:**
```python
for entry in ortholog_list:
    taxon_id = entry.get("taxon", {}).get("id")
    if taxon_id not in TARGET_TAXONS:
        continue

    ortholog_uniprot = entry.get("canonicalid", "").strip()
    if not ortholog_uniprot or ortholog_uniprot == uniprot_id:
        continue

    in_db = 1 if ortholog_uniprot in db_proteins else 0
    og_id = entry.get("oma_group")  # OMA group ID si disponible

    # insertar en tabla orthologs
    # source = "OMA", source_version = "OMA-2024"
```

### Test obligatorio

Mismas proteínas de prueba que el resto de scripts:
```python
TEST_PROTEINS = ["P35637", "Q92520", "P09651", "P38919", "Q9NQC3"]
```

Verificar:
- P35637 (FUS) debe tener ortólogo en ratón (P56959)
- Imprimir por proteína de test: lista de ortólogos por organismo
  con `ortholog_id` e `in_db`
- Solo si el test pasa, correr pipeline completo

### Reporte al finalizar

Mismo formato que parse_orthologs.py — comparar cobertura:
```
Proteínas en dataset:          15,409
Fetcheadas de OMA:             N
404 (no en OMA):               N
Filas insertadas en orthologs: N
  - con in_db = 1:             N
Por organismo:
  Homo sapiens:                N
  Mus musculus:                N
  ...
```

---

## Prompts de lanzamiento para Claude Code

### Solo BioGRID (PPI):
```
Lee CLAUDE_phase4_ppi_orthologs.md. Implementa solo parse_biogrid.py.
Antes de procesar el archivo completo, corre el test con TEST_PROTEINS
e imprimí los resultados. Solo si el test pasa, procesá el archivo
completo. Mostrá el reporte final antes de terminar.
```

### Solo OMA (ortólogos — recomendado sobre OrthoDB):
```
Lee CLAUDE_ppi_orthologs.md. Implementa fetch_oma.py y
parse_oma.py usando la sección "Alternativa para ortólogos: OMA
Browser API". No implementes parse_orthologs.py (OrthoDB).
Primero corre el test con TEST_PROTEINS en fetch_oma.py e imprimí
los ortólogos encontrados por organismo. Solo si el test pasa,
fetcheá el dataset completo y luego corré parse_oma.py. Mostrá
el reporte final antes de terminar.
```

### BioGRID + OMA (completo):
```
Lee CLAUDE_ppi_orthologs.md. Implementa parse_biogrid.py
y luego fetch_oma.py + parse_oma.py (sección OMA, no OrthoDB).
En cada script: primero test con TEST_PROTEINS, luego pipeline
completo solo si el test pasa. Mostrá los reportes finales de
ambos scripts antes de terminar.
```# MLOsMetaDB — Ortholog Groups (OrthoDB v2)

## Objetivo

Poblar dos tablas nuevas en `mlosmetadb.db` con grupos ortólogos y sus
miembros, usando los archivos locales de OrthoDB v2. Reemplaza la tabla
`orthologs` generada por OMA.

---

## Archivos de entrada

```
database/crossref/
├── odb12v2_genes.tab.gz       # gene_id → organism, uniprot (col 4)
├── odb12v2_gene_xrefs.tab.gz  # gene_id → xref, source
├── odb12v2_OGs.tab.gz         # og_id, taxon_id, name
├── odb12v2_OG2genes.tab.gz    # og_id → gene_id
└── odb12v2_levels.tab.gz      # taxon_id, level_name, ...
```

---

## Esquema

### Tabla: ortholog_groups

```sql
CREATE TABLE IF NOT EXISTS ortholog_groups (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    uniprot_id     TEXT NOT NULL REFERENCES proteins(uniprot_id),
    og_id          TEXT NOT NULL,
    og_name        TEXT,
    level_taxon_id INTEGER NOT NULL,
    level_name     TEXT,
    gene_count     INTEGER,
    is_default     INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_og_uniprot ON ortholog_groups(uniprot_id);
CREATE INDEX IF NOT EXISTS idx_og_ogid ON ortholog_groups(og_id);
```

### Tabla: ortholog_members

```sql
CREATE TABLE IF NOT EXISTS ortholog_members (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    og_id       TEXT NOT NULL,
    uniprot_id  TEXT NOT NULL,
    organism    TEXT,
    taxon_id    INTEGER,
    in_db       INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_om_ogid ON ortholog_members(og_id);
CREATE INDEX IF NOT EXISTS idx_om_indb ON ortholog_members(in_db);
```

---

## Script: parse_orthologs.py

### Pasos en orden

**Paso 0 — Backup tabla existente:**

```python
conn.execute("ALTER TABLE orthologs RENAME TO orthologs_oma_backup")
```

**Paso 1 — Cargar levels:**

```python
# odb12v2_levels.tab.gz: taxon_id(col0), level_name(col1)
levels = {}  # taxon_id (int) → level_name (str)
```

**Paso 2 — Cargar OGs:**

```python
# odb12v2_OGs.tab.gz: og_id(col0), taxon_id(col1), name(col2)
ogs = {}  # og_id → {"taxon_id": int, "name": str}
```

**Paso 3 — Cargar genes:**

```python
# odb12v2_genes.tab.gz: gene_id(col0), organism_id(col1), ..., uniprot(col4)
# Solo cargar filas donde col4 no está vacía
gene_to_uniprot = {}   # gene_id → uniprot_id
gene_to_taxon = {}     # gene_id → taxon_id
```

Nota sobre taxon_id en genes.tab: el `organism_id` en col1 es el
prefijo del `gene_id` (ej. `9606_0` para humano). El taxon_id numérico
real se extrae del prefijo: `organism_id.split('_')[0]`.

**Paso 4 — Cargar xrefs (UniProt solamente):**

```python
# odb12v2_gene_xrefs.tab.gz: gene_id(col0), xref(col1), source(col2)
# Filtrar source == "UniProt"
# Construir también el índice inverso
uniprot_to_gene = {}   # uniprot_id → gene_id
```

**Paso 5 — Cargar OG2genes:**

```python
# odb12v2_OG2genes.tab.gz: og_id(col0), gene_id(col1)
from collections import defaultdict
og_to_genes = defaultdict(list)   # og_id → [gene_ids]
gene_to_ogs = defaultdict(list)   # gene_id → [og_ids]
```

**Paso 6 — Cargar proteins del dataset:**

```python
db_proteins = set()  # todos los uniprot_id de la tabla proteins
```

**Paso 7 — Para cada proteína del dataset:**

```python
for uniprot_id in db_proteins:
    gene_id = uniprot_to_gene.get(uniprot_id)
    if not gene_id:
        continue

    og_ids = gene_to_ogs.get(gene_id, [])
    for og_id in og_ids:
        og_meta = ogs.get(og_id, {})
        taxon_id = og_meta.get("taxon_id")
        level_name = levels.get(taxon_id, "Unknown")
        gene_count = len(og_to_genes.get(og_id, []))

        # INSERT INTO ortholog_groups
        # is_default = 0 por ahora — se calcula en paso 9
```

**Paso 8 — Para cada OG encontrado, insertar miembros:**

```python
# Deduplicar OGs primero (muchas proteínas pueden compartir el mismo OG)
# Solo insertar miembros de OGs no procesados aún

for og_id in ogs_to_process:
    for member_gene_id in og_to_genes[og_id]:
        member_uniprot = gene_to_uniprot.get(member_gene_id)
        if not member_uniprot:
            continue
        taxon_id = int(gene_to_taxon.get(member_gene_id, 0))
        organism = levels.get(taxon_id, "Unknown")
        in_db = 1 if member_uniprot in db_proteins else 0
        # INSERT INTO ortholog_members
```

**Paso 9 — Marcar is_default:**

Para cada proteína, el OG default es el de nivel más específico
(mayor profundidad en la jerarquía) que tenga al menos 2 miembros
con `in_db = 1` distintos de la proteína misma. Si ninguno cumple,
el default es el OG más específico disponible.

```python
# UPDATE ortholog_groups SET is_default = 1
# WHERE id = (og más específico con >= 2 in_db para ese uniprot_id)
```

---

## Reglas generales

- Verificar estructura de archivos imprimiendo las primeras 3 líneas
  antes de asumir posiciones de columnas
- Reportar progreso cada 1000 proteínas procesadas
- Usar `INSERT OR IGNORE` para idempotencia en `ortholog_members`
  (mismo og_id + uniprot_id no se duplica)
- Los archivos son grandes (4-5 GB) — cargar en memoria como
  diccionarios, no iterar múltiples veces
- Loguear proteínas del dataset sin `gene_id` en OrthoDB

---

## Test obligatorio antes del pipeline completo

```python
TEST_PROTEINS = ["P35637", "Q92520", "P09651", "P38919", "Q9NQC3"]
```

Para cada proteína de test imprimir:
- `gene_id` encontrado en OrthoDB
- Lista de OGs con su `level_name` y `gene_count`
- OG marcado como `is_default`
- Primeros 5 miembros con `in_db = 1`

Solo proceder al dataset completo si el test produce resultados
biológicamente razonables (P35637 debe tener ortólogo en ratón
con `in_db = 1`).

---

## Verificación al finalizar

```sql
-- Cobertura: proteínas con al menos un OG
SELECT COUNT(DISTINCT uniprot_id) FROM ortholog_groups;

-- Distribución de niveles
SELECT level_name, COUNT(DISTINCT uniprot_id) as proteinas
FROM ortholog_groups
GROUP BY level_name
ORDER BY proteinas DESC
LIMIT 20;

-- Miembros in_db por OG de FUS
SELECT og.og_id, og.level_name, COUNT(*) as total_members,
       SUM(om.in_db) as in_db_members
FROM ortholog_groups og
JOIN ortholog_members om ON og.og_id = om.og_id
WHERE og.uniprot_id = 'P35637'
GROUP BY og.og_id, og.level_name;

-- Sanity check: FUS debe tener ortólogo en ratón
SELECT om.uniprot_id, om.organism, om.in_db
FROM ortholog_groups og
JOIN ortholog_members om ON og.og_id = om.og_id
WHERE og.uniprot_id = 'P35637'
AND og.is_default = 1
AND om.taxon_id = 10090;
```

