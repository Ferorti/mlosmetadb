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
```