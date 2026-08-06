# MLOsMetaDB Frontend — Dev Log (refactor/)

## Registro de Cambios (Conciso)

| Fecha | Commit | Cambio |
|-------|--------|--------|
| 2026-08-05 | `c27957e` | Port de `frontend/` → `refactor/frontend/` (copia sin modificar, 64 archivos; excluido el scaffold muerto de create-vue). |
| 2026-08-05 | `638b047` | `sortProteins.js` (nuevo): re-sort client-side de los resultados de `/search`, que no tiene `sort_by` y devuelve orden uniprot_id-ascendente — el dropdown de sort ahora se respeta también en búsqueda de texto libre. |
| 2026-08-05 | `3b3a549` | `ProteinPPI.vue`: quinta rama de render para `total_partners>0` con 0 partners en la DB (e.g. `O23702`), que antes no renderizaba nada. |
| 2026-08-05 | `058c121` | `ProteinPage.vue`: tab Orthologs oculto pendiente de rediseño (componentes intactos en disco). |
| 2026-08-05 | `da5a65c` | `MlosPage.vue`: control de sort (Most drivers / Alphabetical / Most proteins), con tie-break alfabético y `null`→0. |
| 2026-08-05 | `44bb9da` | `ProteinPPI.vue`: click en nodo del grafo selecciona la fila en la tabla (salta de página + scroll) en vez de navegar afuera. |
| 2026-08-05 | `da0406f` | `MlosPage.vue`: click en la card expande/colapsa definiciones; navegar a `/results?mlo=X` pasa al botón "Explore ... proteins" (siempre visible). |
| 2026-08-05 | `0eac4e6` | Docs: `CLAUDE.md` + `DEVLOG.md` de `refactor/frontend/`, Entry 14 del `REFACTOR_LOG.md`. |
| 2026-08-05 | (final review) | Fix crítico: `sort_by` sacado del trigger de escalación `/search` → `/search/advanced` en `ResultsPage.vue` — elegir cualquier sort en una búsqueda de texto reducía el corpus a un `LIKE` sobre `gene_name` solamente ("kinase": 50 → 0 resultados). Más limpiezas en `ProteinPPI.vue` (`rowRefs`/`selectedId`) y correcciones de documentación. Ver `REFACTOR_LOG.md` Entry 15. |

---

## 2026-08-05 — Port from frontend/ into refactor/frontend/

Ported per `docs/superpowers/plans/2026-08-05-refactor-frontend-phase.md`.
Full pre-port development history: `frontend/DEVLOG.md` (not copied forward
verbatim — that file's history belongs to the pre-refactor code; this file
starts fresh at the port).

See `refactor/REFACTOR_LOG.md` Entry 14 for the port narrative and
verification evidence, and Entry 15 for the final whole-branch review and
the single fix wave that followed it.
