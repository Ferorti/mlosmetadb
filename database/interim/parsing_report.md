# MLOsMetaDB — Informe de Parseo, Integración y Comparación

**Última actualización:** 2026-04-29  
**Dataset final:** `database/mlosmetadb.tsv`  
**Dataset referencia V1:** `database/databases_input_data/mlosmetadb_v1/mlosmetadb_dataset.tsv`

---

## 1. Resultados del parseo por fuente

### Reglas generales aplicadas
- Se descarta una fila **solo si falta el accession UniProt** — no se puede linkear a proteína.
- MLO vacío → `NotInformed` (fila conservada).
- Tokens genéricos del campo MLO se conservan tal como están en la fuente.
- DrLLPS `"Droplet"` → mapeado a `"in vitro droplet"`.
- PhaseDB: strings multi-MLO separados por `"; "` se exploden (una fila por MLO).
- PhasePro col[14]: separador `"; "` → explode a múltiples filas.
- LLPSDB: IDs compuestos (`p0001;p0226`) se exploden antes del join.

### Tabla resumen de parseo

| Parser | Archivos de entrada | Filas entrada | Descartadas | Filas salida |
|---|---|---|---|---|
| `parse_phasedb.py` | `phasedb_mlo_entries.tsv` | 11,135 | 273 (uniprot `_`) | 10,862 → **10,947** (post-explode) |
|  | `phasedb_detail.csv` | 3,528 | 0 | 3,528 → **3,661** (post-explode) |
|  | *(1,920 MLO vacíos → `NotInformed`)* | | | |
|  | **Total PhaseDB** | | | **14,608** |
| `parse_drllps.py` | `drllps_llps.tsv` | 9,281 | 27 (uniprot vacío) | **11,194** (post-explode MLOs) |
| `parse_llpsdb.py` | `llpsdb_entries.csv` + `llpsdb_proteins.csv` | 4,111 | 709 (sin uniprot post-join) | **380** (únicos por uniprot) |
| `parse_phasepro.py` | `phasepro.tsv` | 121 | 0 | **213** (post-explode MLOs) |
| `parse_cdcode.py` | `cdcode_protein2condensate.tsv` | 14,622 | 0 | **14,622** |
| **TOTAL** | | | | **41,017** |

### Nota: corrección de mapping MLO (2026-04-29)

El dataset fue generado inicialmente con `mlo_mapping.csv` (versión de sesión) en lugar del
archivo definitivo del usuario `mlo_unified_definitions_phasepro_phasepdb_cdcode_v3.csv`.
Se regeneró con v3 como fuente autoritativa. El impacto es exclusivamente sobre `unified_mlo`:
**1,200 filas** (~3% del total) cambiaron de canónico en 29 términos. Todos los demás números
del informe (proteínas, overlap con V1, roles, organismos, evidencia) son idénticos.

Cambios de criterio más relevantes:

| source_mlo | Antes | v3 (definitivo) | Filas |
|---|---|---|---|
| `Centrosome/Spindle pole body` | `centrosome` | `spindle_pole_body` | 910 |
| `Chromatoid body` | `nuage` | `chromatoid_body` | 222 |
| `Destruction complex condensate` | `wnt_signaling_condensate` | `wnt_destruction_complex` | 11 |
| `MARDO` | `balbiani_body` | `mardo` | 7 |
| `sex body` | `heterochromatin` | `sex_body` | 2 |
| `SIMR foci` | `mutator_foci` | `simr_foci` | 2 |

---

### Nota: PhaseDB — cambio respecto a la sesión de marzo

En la versión de marzo el parser producía 14,390 filas. Tras añadir el explode de strings
multi-MLO (`"Nucleolus; Stress granule"` → dos filas independientes), el total sube a **14,608** (+218 filas).
Los 66 tokens compuestos que antes quedaban sin mapear desaparecen; sus componentes individuales
ya estaban cubiertos en `mlo_mapping.csv`.

---

## 2. Dataset integrado final

**Archivo:** `database/mlosmetadb.tsv`  
**Script:** `integrate.py` — concatena interim, aplica `role_mapping.tsv` y `mlo_mapping.csv`

| Métrica | Valor |
|---|---|
| Filas totales | 41,017 |
| UniProt únicos | 15,967 |
| Cobertura `unified_mlo` | **100%** (0 unmapped) |
| Cobertura `unified_role` | 38% (15,578 mapeadas; ver §6) |
| Entradas DISCARD | 19 filas |

### Filas y proteínas por fuente

| source_db | Filas | UniProt únicos | % filas |
|---|---|---|---|
| PhaseDB | 14,608 | 7,755 | 35.6% |
| CDCODE | 14,622 | 11,019 | 35.6% |
| DrLLPS | 11,194 | 9,253 | 27.3% |
| LLPSDB | 380 | 380 | 0.9% |
| PhasePro | 213 | 121 | 0.5% |

---

## 3. Comparación V1 vs dataset final

### 3.1 Cobertura global de proteínas

| | V1 | Nuevo | Δ |
|---|---|---|---|
| UniProt únicos | 12,036 | 15,967 | **+3,931** (+32.7%) |
| Bases de datos | 4 | 5 (+CDCODE) | |
| Filas (anotaciones) | ~20,281* | 41,017 | +20,736 (+102%) |

*V1 raw: 20,281 filas en `entrada_llps_proteins.csv`

### 3.2 Solapamiento de proteínas (V1 dataset vs nuevo)

| | N | % V1 |
|---|---|---|
| Compartidas (V1 ∩ nuevo) | 11,850 | **98.5%** |
| Solo en V1 (perdidas) | 186 | 1.5% |
| Solo en nuevo (ganadas) | 4,117 | — |
| — de las cuales exclusivas de CDCODE | 2,013 | — |
| — de las cuales en otras fuentes actualizadas | 2,104 | — |

### 3.3 Proteínas ganadas por fuente

| Fuente | Nuevas proteínas (no en V1) |
|---|---|
| PhaseDB | 2,090 |
| CDCODE | 11,019 (fuente nueva) |
| LLPSDB | 7 |
| DrLLPS | 8 |
| PhasePro | 0 |

El crecimiento real excluyendo CDCODE es **+2,105 proteínas** (+17.5% sobre V1),
principalmente por actualización de la fuente PhaseDB.

### 3.4 Proteínas perdidas (186)

| Fuente original (V1) | Perdidas |
|---|---|
| phasepdb | 181 |
| drllps | 6 |
| llpsdb | 2 |

**Causa principal (181 en PhaseDB):** Accessions retirados o remplazados en la versión
actualizada de PhaseDB. La mayoría corresponden a entradas sin MLO ni rol en V1
(campo `mlos` vacío), lo que indica que eran entradas incompletas en la fuente original.
Los 8 restantes (DrLLPS + LLPSDB) son accessions descontinuados en UniProt.

Ninguna pérdida es atribuible a errores de parseo.

---

## 4. MLOs: comparación y distribución

### 4.1 Vocabulario canónico V1 vs nuevo

| | V1 | Nuevo |
|---|---|---|
| Términos únicos en vocabulario | 144 | 159 |
| Compartidos entre ambas versiones | 65 | — |
| Solo en V1 (consolidados o renombrados) | 79 | — |
| Solo en nuevo (añadidos) | 94 | — |

**Términos importantes consolidados o renombrados de V1 a nuevo:**

| V1 | Nuevo | Razón |
|---|---|---|
| `centrosome/spindle_pole_body` | `centrosome` | Unificado (decisions.md §3.1) |
| `p-body` | `p_body` | Normalización snake_case |
| `chromatoid_body` | `nuage` | Equivalencia biológica (decisions.md §3.4) |
| `pericentriolar_material` | `centrosome` | PCM = componente condensado del centrosoma |
| `cytoplasmic_stress_granule` | `stress_granule` | Unificado al término canónico |
| `pyrenoid_matrix` | `pyrenoid` | Simplificación |
| `gw-body` | `p_body` | GW-bodies son P-bodies con marcador GW182 |
| `droplet` | `in_vitro_droplet` | Nombre más informativo |
| `pcg_body` / `pcg_chromatin_condensates` | `polycomb_body` | Unificación |
| `others` (DrLLPS) | `DISCARD` | Sin MLO real asignado |
| `spindle_matrix` | `spindle_apparatus` | Unificación terminológica |
| `imp1_ribonucleoprotein_granule` | `neuronal_granule` | Agrupamiento funcional |
| `mutator_focus` | `mutator_foci` | Normalización |

### 4.2 Top 20 MLOs canónicos en el nuevo dataset

| Rank | unified_mlo | Filas | Proteínas únicas |
|---|---|---|---|
| 1 | `nucleolus` | 9,990 | — |
| 2 | `stress_granule` | 5,564 | — |
| 3 | `postsynaptic_density` | 4,477 | — |
| 4 | `p_body` | 2,560 | — |
| 5 | `centrosome` | 1,921 | — |
| 6 | `NotInformed` | 1,920 | — |
| 7 | `p62_body` | 1,530 | — |
| 8 | `presynaptic_active_zone` | 1,395 | — |
| 9 | `pml_nuclear_body` | 1,390 | — |
| 10 | `nuclear_speckle` | 1,177 | — |
| 11 | `balbiani_body` | 1,013 | — |
| 12 | `p_granule` | 871 | — |
| 13 | `synthetic_condensate` | 770 | — |
| 14 | `nuclear_stress_body` | 596 | — |
| 15 | `in_vitro_droplet` | 552 | — |
| 16 | `mast_cell_granule` | 533 | — |
| 17 | `paraspeckle` | 477 | — |
| 18 | `cajal_body` | 393 | — |
| 19 | `NULL` | 316 | — |
| 20 | `transcriptional_condensate` | 279 | — |

### 4.3 MLOs únicos por fuente

| source_db | MLOs únicos | Top 3 |
|---|---|---|
| CDCODE | 124 | `nucleolus`, `stress_granule`, `postsynaptic_density` |
| PhaseDB | 91 | `nucleolus`, `stress_granule`, `NotInformed` |
| PhasePro | 55 | `stress_granule`, `nuclear_body`, `DISCARD` |
| DrLLPS | 38 | `nucleolus`, `postsynaptic_density`, `stress_granule` |
| LLPSDB | 1 | `in_vitro_droplet` |

---

## 5. Roles: distribución y cambios

### 5.1 Distribución de source_role

| source_role | Filas | Fuente |
|---|---|---|
| NotInformed | 14,622 | CDCODE (sin información de rol) |
| client | 10,947 | PhaseDB |
| Client | 9,378 | DrLLPS |
| driver | 4,254 | PhaseDB + LLPSDB + PhasePro |
| Regulator | 1,439 | DrLLPS |
| Scaffold | 377 | DrLLPS |

### 5.2 Cobertura de unified_role

| unified_role | Filas | % |
|---|---|---|
| unmapped | 25,439 | 62.0% |
| Client | 10,947 | 26.7% |
| Driver | 4,631 | 11.3% |

**La causa del 62% unmapped:** el `role_mapping.tsv` solo tiene 4 entradas activas.
Faltan `Client` (capital C, DrLLPS — 9,378 filas) y `Regulator` (DrLLPS — 1,439 filas).
**Acción requerida:** añadir estas dos entradas al `role_mapping.tsv`.

### 5.3 Cambios de rol para proteínas compartidas V1 → nuevo

Para las 11,850 proteínas presentes en ambas versiones (excluyendo CDCODE):

| Transición (V1 rol → nuevo unified_role) | N proteínas |
|---|---|
| `client` → `unmapped`* | 5,767 |
| `NotInformed` → `Client` | 2,120 |
| `client` → `Client` | 1,858 |
| `driver` → `Driver` | 637 |
| `regulator` → `unmapped`* | 544 |
| `client` → `Driver` | 352 |
| `regulator` → `Client` | 285 |
| `NotInformed` → `Driver` | 146 |
| `regulator` → `Driver` | 86 |

*`unmapped` = DrLLPS `Client`/`Regulator` que faltan en `role_mapping.tsv` (ver §5.2)

Los cambios `NotInformed → Client/Driver` (2,266 proteínas) son **enriquecimiento real**:
PhaseDB actualizó su anotación de rol en entradas que antes eran HT sin rol asignado.

---

## 6. Anotación multi-fuente y multi-MLO

### 6.1 Proteínas anotadas en más de una fuente

| N fuentes | Proteínas |
|---|---|
| 1 | 6,410 |
| 2 | 6,785 |
| 3 | 2,598 |
| 4 | 116 |
| 5 | 58 |

Las 58 proteínas con las 5 fuentes son las mejor caracterizadas en el campo LLPS.

### 6.2 Diversidad de MLOs por proteína

| MLOs únicos asignados | Proteínas |
|---|---|
| 1 | 11,347 |
| 2–3 | 3,555 |
| 4 o más | 1,065 |
| Máximo: 21 MLOs | P35637 (FUS/TLS) |

---

## 7. Cobertura de evidencia y organismos

### 7.1 Evidencia (PMIDs)

| source_db | Filas con PMID | Cobertura |
|---|---|---|
| PhaseDB | 14,608 / 14,608 | 100% |
| DrLLPS | 11,194 / 11,194 | 100% |
| PhasePro | 213 / 213 | 100% |
| LLPSDB | 378 / 380 | 99.5% |
| CDCODE | 0 / 14,622 | **0%** — fuente sin PMID |
| **Total** | **26,393 / 41,017** | **64.3%** |

### 7.2 Top 10 organismos (proteínas únicas)

| Organismo | Proteínas únicas |
|---|---|
| *Homo sapiens* | 6,683 |
| *Mus musculus* | 2,067 |
| *Arabidopsis thaliana* | 2,019 |
| *Caenorhabditis elegans* | 950 |
| *Saccharomyces cerevisiae* | 778 |
| *Danio rerio* | 267 |
| *Bos taurus* | 259 |
| *Drosophila melanogaster* | 221 |
| *S. cerevisiae* S288c | 201 |
| *Xenopus laevis* | 194 |

---

## 8. Entradas DISCARD

19 filas tienen `unified_mlo = "DISCARD"` — términos GO estructurales o complejos moleculares
que no son MLOs. Están presentes en el dataset pero deben filtrarse para análisis.

| source_db | source_mlo | Filas |
|---|---|---|
| DrLLPS | `Microtubule` | 5 |
| PhasePro | `intracellular non-membrane-bounded organelle` | 4 |
| PhasePro | `Arp2/3 protein complex` | 3 |
| PhasePro | `ribonucleoprotein complex` | 2 |
| PhasePro | varios (1 c/u) | 5 |

---

## 9. Acciones pendientes

| Acción | Impacto | Prioridad |
|---|---|---|
| Añadir `Client` y `Regulator` a `role_mapping.tsv` | +10,817 filas mapeadas (DrLLPS) | Alta |
| Filtrar/marcar entradas DISCARD en output final | 19 filas | Media |
| CDCODE no tiene evidencia (PMID) | 14,622 filas sin PMID | Informativo |
| Decidir tratamiento de `NotInformed` (1,920 filas PhaseDB) | Análisis downstream | Baja |

---

## 10. Registro de scripts y ejecuciones

### Scripts del pipeline

| Script | Función | Output |
|---|---|---|
| `parsers/parse_phasedb.py` | Parsea PhaseDB (mlo_entries + detail); explode multi-MLO | `database/interim/phasedb.tsv` |
| `parsers/parse_drllps.py` | Parsea DrLLPS; explode MLO por `, ` | `database/interim/drllps.tsv` |
| `parsers/parse_llpsdb.py` | Parsea LLPSDB; join entries+proteins, deduplica por UniProt | `database/interim/llpsdb.tsv` |
| `parsers/parse_phasepro.py` | Parsea PhasePro (sin header); explode MLO por `; ` | `database/interim/phasepro.tsv` |
| `parsers/parse_cdcode.py` | Parsea CDCODE protein2condensate | `database/interim/cdcode.tsv` |
| `integrate.py` | Concatena interim + aplica mappings | `database/mlosmetadb.tsv` |
| `parsers/compare_v1_v2.py` | Comparación V1 vs V2 (interim) — versión marzo | (stdout) |

### Archivos de mapping

| Archivo | Entradas | Estado |
|---|---|---|
| `database/mappings/mlo_mapping.csv` | ~838 | Cobertura 100% de source_mlo |
| `database/mappings/role_mapping.tsv` | 4 | Incompleto — faltan `Client` y `Regulator` de DrLLPS |
| `database/mappings/mlo_mapping_decisions.md` | — | Justificaciones biológicas de todos los mapeos |
| `database/mappings/mlo_mapping_audit.md` | — | Historial de cobertura y pendientes |

### Historial de ejecuciones

| Fecha | Acción | Resultado |
|---|---|---|
| 2026-03-31 | Primera ejecución de los 5 parsers | 40,999 filas interim |
| 2026-03-31 | Primera comparación V1 vs interim (compare_v1_v2.py) | 99.3% proteínas V1 recuperadas |
| 2026-04-28 | Usuario añade entradas CDCODE a mlo_mapping.csv | 766 entradas (177 → 766) |
| 2026-04-29 | Auditoría de cobertura: 133 source_mlo sin mapear | Detectados 3 grupos de problemas |
| 2026-04-29 | Fix parse_phasedb.py: explode de strings multi-MLO (`; `) | phasedb.tsv: 14,390 → 14,608 filas |
| 2026-04-29 | Añadidas 71 entradas a mlo_mapping.csv | 766 → ~838 entradas |
| 2026-04-29 | Fix integrate.py: soporte para mlo_mapping.csv (era .tsv) | — |
| 2026-04-29 | Ejecución final de integrate.py | **41,017 filas, unified_mlo 100%** |
| 2026-04-29 | Auditoría residual: 9 filas unmapped → 5 términos añadidos | Cobertura completa |
