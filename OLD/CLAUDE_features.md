# MLOsMetaDB — Phase 3: Feature Parsing

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
