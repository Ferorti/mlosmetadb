# MLOsMetaDB API — Guía de consultas

Base URL: `http://localhost:8765` (desarrollo) · `https://mlos.leloir.org.ar/api` (producción)

---

## Índice

1. [Consultas simples](#1-consultas-simples)
   - [Obtener una proteína](#11-obtener-una-proteína)
   - [Listar proteínas](#12-listar-proteínas)
   - [Obtener un MLO](#13-obtener-un-mlo)
   - [Listar todos los MLOs](#14-listar-todos-los-mlos)
   - [Búsqueda básica](#15-búsqueda-básica)
   - [Estadísticas globales](#16-estadísticas-globales)
2. [Consultas con filtros](#2-consultas-con-filtros)
   - [Proteínas por organismo](#21-proteínas-por-organismo)
   - [Proteínas por MLO y rol](#22-proteínas-por-mlo-y-rol)
   - [Proteínas por fuente de datos](#23-proteínas-por-fuente-de-datos)
   - [MLO filtrado por organismo](#24-mlo-filtrado-por-organismo)
3. [Paginación](#3-paginación)
   - [Proteínas paginadas](#31-proteínas-paginadas)
   - [Interacciones PPI de una proteína](#32-interacciones-ppi-de-una-proteína)
4. [Búsqueda avanzada](#4-búsqueda-avanzada)
   - [Por tipo de feature estructural](#41-por-tipo-de-feature-estructural)
   - [Por accession de dominio](#42-por-accession-de-dominio)
   - [Combinación compleja](#43-combinación-compleja)
5. [Referencia de campos](#5-referencia-de-campos)

---

## 1. Consultas simples

### 1.1 Obtener una proteína

Retorna el registro completo: metadatos, anotaciones MLO, features estructurales y resumen PPI.

```bash
curl "http://localhost:8765/protein/P35637"
```

**Respuesta parcial** (FUS, proteína de referencia con IDRs, dominios y múltiples MLOs):

```json
{
  "uniprot_id": "P35637",
  "gene_name": "FUS",
  "protein_name": "RNA-binding protein FUS",
  "organism": "Homo sapiens",
  "taxon_id": 9606,
  "sequence_length": 526,
  "disorder_mobidb_lite_dc": 0.797,
  "disorder_alphafold_dc": 0.785,
  "mlo_annotations": [
    {
      "unified_mlo": "stress_granule",
      "category": "cytoplasmic_rnp",
      "source_db": "PhaseDB",
      "source_mlo": "Stress granules",
      "unified_role": "driver",
      "evidence_pmids": ["20639869", "28813787"]
    }
  ],
  "sequence_features": {
    "idrs": [
      { "start": 1, "end": 286, "score": null, "source": "MobiDB-lite" },
      { "start": 1, "end": 278, "score": null, "source": "AlphaFold-disorder" }
    ],
    "domains": [
      { "start": 287, "end": 365, "label": "RNA recognition motif", "accession": "PF00076", "database": "pfam" }
    ],
    "lcds": [
      { "start": 17, "end": 75, "label": "low_complexity", "source": "MobiDB-lite-sub" }
    ],
    "morfs": [
      { "start": 1, "end": 33, "score": null, "source": "MobiDB" }
    ],
    "plddt_regions": [
      { "start": 1, "end": 165, "mean_score": 42.1, "category": "very_low" }
    ]
  },
  "ppi": {
    "total_partners": 506,
    "partners_in_mlosmetadb": 370,
    "interactions": null
  }
}
```

**Campos clave:**

| Campo | Descripción |
|---|---|
| `disorder_mobidb_lite_dc` | Fracción de residuos predichos como desordenados por MobiDB-lite (0–1). `null` si no hay datos. |
| `disorder_alphafold_dc` | Ídem para AlphaFold (pLDDT < umbral). |
| `ppi.interactions` | Siempre `null` a menos que se pida con `?ppi_page`. |

---

### 1.2 Listar proteínas

Listado paginado de todas las proteínas, con resumen de features y MLOs precalculado.

```bash
curl "http://localhost:8765/proteins?per_page=3"
```

**Respuesta:**

```json
{
  "total": 15409,
  "page": 1,
  "per_page": 3,
  "filters_applied": {},
  "proteins": [
    {
      "uniprot_id": "A0A023J6F3",
      "gene_name": null,
      "protein_name": "Putative uncharacterized protein",
      "organism": "Saccharomyces cerevisiae",
      "disorder_mobidb_lite_dc": null,
      "disorder_alphafold_dc": null,
      "idr_regions": null,
      "lcr_regions": null,
      "domains": null,
      "mlo_count": 1,
      "mlos": ["mast_cell_granule"]
    }
  ]
}
```

---

### 1.3 Obtener un MLO

Devuelve definiciones, estadísticas agregadas y lista paginada de proteínas.

```bash
curl "http://localhost:8765/mlo/stress_granule"
```

**Respuesta parcial:**

```json
{
  "unified_mlo": "stress_granule",
  "category": "Citoplasmático",
  "definitions": [
    { "source_db": "PhaseDB", "definition": "...", "source_name": "Stress granules" }
  ],
  "stats": {
    "total_proteins": 2834,
    "by_source": { "PhaseDB": 1734, "DrLLPS": 1485, "CDCODE": 1694 },
    "by_role": { "driver": 202, "client": 1633, "unmapped": 1967 },
    "organisms": ["Homo sapiens", "Mus musculus", "Saccharomyces cerevisiae"]
  },
  "proteins": {
    "page": 1, "per_page": 50, "total": 2834,
    "items": [
      {
        "uniprot_id": "A0A023PZG4",
        "gene_name": null,
        "organism": "Saccharomyces cerevisiae",
        "unified_role": "unmapped",
        "sources": ["DrLLPS"],
        "disorder_alphafold_dc": 0.262,
        "disorder_mobidb_lite_dc": null,
        "idr_regions": { "alphafold": [[1, 120]] },
        "lcr_regions": null,
        "domains": null
      }
    ]
  }
}
```

---

### 1.4 Listar todos los MLOs

164 entradas del vocabulario canónico con conteo de proteínas. No tiene paginación.

```bash
curl "http://localhost:8765/mlos"
```

Filtrar por categoría:

```bash
curl "http://localhost:8765/mlos?category=nuclear"
```

---

### 1.5 Búsqueda básica

**Modo `fuzzy` (por defecto):** substring en `uniprot_id` y `gene_name`; palabra completa en `protein_name`.

```bash
curl "http://localhost:8765/search?q=FUS"
```

Retorna proteínas donde gene_name contiene "FUS" (FUS, FUS3, fus1…) + MLOs cuyo nombre coincide.

**Modo `exact`:** token completo via FTS5. Más restrictivo, ordenado por relevancia.

```bash
curl "http://localhost:8765/search?q=FUS&mode=exact"
```

| Modo | `q=FUS` retorna | Semántica |
|---|---|---|
| `fuzzy` | FUS, FUS3, Fus, fus1, fus.S | substring en gene_name / palabra completa en protein_name |
| `exact` | FUS, Fus, fus.S | token exacto vía FTS5, ordenado por relevancia |

---

### 1.6 Estadísticas globales

Precalculadas al inicio del servidor. Sin costo por request.

```bash
curl "http://localhost:8765/stats"
```

```json
{
  "database_version": "2.0",
  "last_updated": "2026-05-04",
  "proteins": {
    "total": 15409,
    "by_organism": { "Homo sapiens": 6536, "Mus musculus": 2134 },
    "top_organisms": 10
  },
  "mlo_annotations": {
    "total": 37990,
    "unique_mlos": 164,
    "by_source": { "PhaseDB": 11234, "DrLLPS": 9821, "CDCODE": 7102, "LLPSDB": 5890, "PhasePro": 3943 },
    "by_role": { "client": 15200, "driver": 7100, "unmapped": 15690 }
  },
  "sequence_features": {
    "total": 303681,
    "by_type": { "idr": 180158, "idr_curated": 1390, "lcd": 53004, "domain": 256, "family": 10, "morf": 3256, "plddt_region": 65607 },
    "proteins_with_features": 14823
  },
  "ppi": {
    "total_interactions": 905393,
    "proteins_with_ppi": 8431
  }
}
```

---

## 2. Consultas con filtros

### 2.1 Proteínas por organismo

```bash
curl "http://localhost:8765/proteins?organism=Homo%20sapiens&per_page=5"
```

El match es case-insensitive pero debe ser el nombre completo del organismo (no parcial).
Alternativa con `taxon_id` (más eficiente):

```bash
curl "http://localhost:8765/proteins?taxon_id=9606&per_page=5"
```

---

### 2.2 Proteínas por MLO y rol

Proteínas **drivers** en stress granule de humano:

```bash
curl "http://localhost:8765/proteins?mlo=stress_granule&role=driver&organism=Homo%20sapiens"
```

```json
{
  "total": 97,
  "filters_applied": { "mlo": "stress_granule", "role": "driver", "organism": "Homo sapiens" },
  "proteins": [ ... ]
}
```

Roles válidos: `driver`, `client`. Las proteínas sin rol asignado (`unmapped`) no aparecen al filtrar por rol.

---

### 2.3 Proteínas por fuente de datos

Proteínas anotadas exclusivamente en PhaseDB:

```bash
curl "http://localhost:8765/proteins?source_db=PhaseDB&per_page=10"
```

Fuentes válidas: `PhaseDB`, `DrLLPS`, `PhasePro`, `LLPSDB`, `CDCODE`.

Combinando fuente y MLO:

```bash
curl "http://localhost:8765/proteins?source_db=DrLLPS&mlo=p_body"
```

---

### 2.4 MLO filtrado por organismo

Lista solo las proteínas de Mus musculus en p_body:

```bash
curl "http://localhost:8765/mlo/p_body?organism=Mus%20musculus&per_page=10"
```

El filtro aplica a la lista de proteínas, no a las estadísticas (que siempre son globales para ese MLO).

---

## 3. Paginación

### 3.1 Proteínas paginadas

Página 3 de 20 proteínas por página, filtradas por organismo:

```bash
curl "http://localhost:8765/proteins?organism=Homo%20sapiens&page=3&per_page=20"
```

Límite máximo: `per_page=200`. Si se envía un valor mayor, el servidor lo recorta a 200.

Para iterar todas las páginas:

```python
import requests

page = 1
while True:
    r = requests.get("http://localhost:8765/proteins",
                     params={"organism": "Homo sapiens", "page": page, "per_page": 200})
    data = r.json()
    proteins = data["proteins"]
    if not proteins:
        break
    # procesar proteins...
    total_pages = -(-data["total"] // 200)  # ceil division
    if page >= total_pages:
        break
    page += 1
```

---

### 3.2 Interacciones PPI de una proteína

Por defecto, el endpoint `/protein/{id}` solo devuelve el resumen PPI (`total_partners`, `partners_in_mlosmetadb`).
Para obtener la lista paginada de interacciones, usar `ppi_page`:

```bash
# Primera página de interacciones (50 por defecto)
curl "http://localhost:8765/protein/P35637?ppi_page=1"
```

```json
{
  "ppi": {
    "total_partners": 506,
    "partners_in_mlosmetadb": 370,
    "interactions": {
      "page": 1,
      "per_page": 50,
      "total": 506,
      "items": [
        {
          "partner_uniprot_id": "A2RU48",
          "partner_gene": null,
          "in_mlosmetadb": false,
          "evidence_types": ["Affinity Capture-MS"],
          "pubmed_id": "28514442",
          "source": "BIOGRID-5.0.257"
        }
      ]
    }
  }
}
```

Página 2 con 20 interacciones:

```bash
curl "http://localhost:8765/protein/P35637?ppi_page=2&ppi_per_page=20"
```

`in_mlosmetadb: true` indica que el partner también está en la base de datos MLOsMetaDB.

---

## 4. Búsqueda avanzada

Requiere al menos un parámetro. Retorna el mismo schema que `/proteins`.

### 4.1 Por tipo de feature estructural

Proteínas humanas con regiones IDR predichas:

```bash
curl "http://localhost:8765/search/advanced?feature_type=idr&organism=Homo%20sapiens"
```

Tipos de features disponibles: `idr`, `idr_curated`, `lcd`, `domain`, `family`, `morf`, `plddt_region`.

Proteínas con LCDs (regiones de baja complejidad):

```bash
curl "http://localhost:8765/search/advanced?feature_type=lcd&organism=Homo%20sapiens&per_page=10"
```

---

### 4.2 Por accession de dominio

Proteínas con el dominio RNA recognition motif (Pfam PF00076):

```bash
curl "http://localhost:8765/search/advanced?feature_accession=PF00076"
```

Proteínas con algún dominio de zinc finger (búsqueda parcial en label):

```bash
curl "http://localhost:8765/search/advanced?feature_label=zinc%20finger"
```

---

### 4.3 Combinación compleja

Proteínas de ratón que son **drivers** en cualquier MLO, tienen el dominio RRM y están en DrLLPS:

```bash
curl "http://localhost:8765/search/advanced?\
organism=Mus%20musculus&\
role=driver&\
source_db=DrLLPS&\
feature_accession=PF00076"
```

Drivers humanos de stress granule con IDRs, página 2:

```bash
curl "http://localhost:8765/search/advanced?\
organism=Homo%20sapiens&\
mlo=stress_granule&\
role=driver&\
feature_type=idr&\
page=2&per_page=25"
```

Sin filtros → error 422:

```bash
curl "http://localhost:8765/search/advanced"
# {"error": "no_filters_provided", "message": "At least one filter parameter is required"}
```

---

## 5. Referencia de campos

### Campos de desorden (`disorder_*_dc`)

Fracción de residuos predichos como desordenados, calculada a partir de MobiDB.

| Campo | Predictor | Método |
|---|---|---|
| `disorder_mobidb_lite_dc` | MobiDB-lite (consensus) | `prediction-disorder-mobidb_lite.content_fraction` |
| `disorder_alphafold_dc` | AlphaFold (pLDDT) | `prediction-disorder-alphafold.content_fraction` |

- Rango: 0.0–1.0. FUS: mobidb=0.797, alphafold=0.785 (proteína muy desordenada).
- `null` si la proteína no tiene datos en mobidb_cache (especialmente no-humanas o poco estudiadas).

### Estructura de `idr_regions`

JSON con predictor como clave, lista de intervalos `[start, end]` (1-indexed, inclusivos):

```json
{
  "mobidb_lite": [[1, 286], [375, 424], [444, 526]],
  "alphafold":   [[1, 278], [368, 426], [451, 526]]
}
```

Claves posibles: `mobidb_lite` (MobiDB-lite), `alphafold` (AlphaFold-disorder).
`null` si la proteína no tiene ningún IDR anotado.

### Estructura de `lcr_regions`

Regiones de baja complejidad con etiqueta composicional:

```json
{
  "mobidb_lite": [
    {"start": 17, "end": 75,  "label": "low_complexity"},
    {"start": 83, "end": 164, "label": "low_complexity"}
  ]
}
```

### Estructura de `domains`

Base de datos como clave (solo Pfam y SMART disponibles actualmente):

```json
{
  "Pfam": [
    {"start": 287, "end": 365, "label": "RNA recognition motif", "accession": "PF00076"},
    {"start": 422, "end": 453, "label": "Zn-finger in Ran binding protein", "accession": "PF00641"}
  ],
  "SMART": [
    {"start": 286, "end": 367, "label": "RNA recognition motif", "accession": "SM00360"}
  ]
}
```

### Categorías de pLDDT (`plddt_regions`)

| Categoría | `mean_score` | Interpretación |
|---|---|---|
| `very_low` | < 50 | Región muy desordenada / flexible |
| `low` | 50–70 | Baja confianza estructural |
| `confident` | 70–90 | Estructura predicha con confianza |
| `very_high` | ≥ 90 | Estructura bien definida |

### Errores comunes

| Código | `error` | Causa |
|---|---|---|
| 404 | `protein_not_found` | UniProt ID no existe en la DB |
| 404 | `mlo_not_found` | MLO no está en el vocabulario |
| 422 | `invalid_parameter` | Parámetro inválido (`q` < 2 chars, `per_page` > 200, etc.) |
| 422 | `no_filters_provided` | `/search/advanced` sin ningún filtro |
| 501 | `fts5_unavailable` | `mode=exact` pero FTS5 no disponible en SQLite |
| 500 | `database_error` | Error interno (ver logs del servidor) |
