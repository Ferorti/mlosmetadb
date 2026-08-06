# MLO Mapping Audit — MLOsMetaDB v2

Última actualización: 2026-04-29

---

## Estado actual

| Métrica | Valor |
|---|---|
| Entradas en mlo_mapping.csv | ~838 |
| source_mlo únicos en dataset | 863 |
| **Sin mapear** | **0 — cobertura completa** |
| Filas totales en mlosmetadb.tsv | 41,017 |
| unified_mlo mapeadas | 41,017 (100%) |
| unified_role mapeadas | 15,578 (38%) |

---

## Cambios aplicados en esta sesión (2026-04-29)

### 1. Parser `parse_phasedb.py` — explode de multi-MLO
PhaseDB emitía cadenas como `"Nucleolus; Stress granule"` como token único.
Se añadió explode por `"; "` en ambas funciones (`parse_mlo_entries` y `parse_detail`).

Resultado: `phasedb.tsv` pasó de 14,390 → 14,608 filas (+218 por la explosión).
Los 66 tokens multi-MLO desaparecieron; todos sus componentes individuales ya estaban mapeados.

### 2. `mlo_mapping.csv` — reemplazado por v3 (2026-04-29)

Se detectó que la sesión de trabajo usó `mlo_mapping.csv` (versión anterior, ~177 entradas base)
en lugar del archivo definitivo del usuario: `mlo_unified_definitions_phasepro_phasepdb_cdcode_v3.csv` (830 entradas).

**Comparación v3 vs mapping de sesión:**
- 830 entradas en v3 — todas incluidas en mlo_mapping.csv de sesión ✓
- 2 entradas únicas de la sesión agregadas a v3: `Cytoplasmic protein granule`, `Galectin complex`
- **29 términos con Nombre Sugerido distinto** → v3 prevalece (decisiones del usuario)

Términos con cambio de criterio más impactantes (v3 vs sesión):

| source_mlo | Sesión | v3 (definitivo) | Filas |
|---|---|---|---|
| `Centrosome/Spindle pole body` | `centrosome` | `spindle_pole_body` | 910 |
| `Chromatoid body` | `nuage` | `chromatoid_body` | 222 |
| `axonal TIAR-2 granules` | `stress_granule` | `axonal_tiar2_granule` | 1 |
| `MARDO` | `balbiani_body` | `mardo` | 7 |
| `sex body` | `heterochromatin` | `sex_body` | 2 |
| `SIMR foci` | `mutator_foci` | `simr_foci` | 2 |
| `Destruction complex condensate` | `wnt_signaling_condensate` | `wnt_destruction_complex` | 11 |

Total filas afectadas por cambios de criterio: **1,200 / 41,017**

### 3. `integrate.py` — mejoras
- Corregido para leer `mlo_mapping.csv` (antes buscaba `.tsv`)
- CSV reader reemplazado por `csv.reader` de Python para manejar comas sin escapar en campo de justificación
- Separador detectado por extensión de archivo

### 4. Dataset final (v3)

| Métrica | Valor |
|---|---|
| Filas totales | 41,017 |
| unified_mlo cobertura | **100%** |
| unified_role cobertura | 38% (pendiente role_mapping) |

---

## Pendiente

- **unified_role**: 62% sin mapear (25,439 filas). Faltan `Client` y `Regulator` (capital) de DrLLPS en `role_mapping.tsv` — son las 10,817 filas más urgentes.
- Recalcular estadísticas de `parsing_report.md` con el dataset v3 final (comparación V1 vs V2 vs V3).
- Verificar/filtrar entradas DISCARD en análisis downstream.
