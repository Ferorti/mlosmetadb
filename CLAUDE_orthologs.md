# MLOsMetaDB — Ortholog Groups (OrthoDB v2)

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

