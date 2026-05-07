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
```