# Design: filtro de robustez de evidencia en PPI (método/estudio/throughput)

**Date**: 2026-08-27
**Status**: propuesto, pendiente de plan de implementación
**Origen**: análisis externo ("Claude Science", ver `docs/review/ppi_evidence_filter/`)
**Baseline commit medido**: `5bcd4f6c8628732f09d4d9c83b5b743a2ec39a8e` (`main`,
2026-08-25) — `database/mlosmetadb.db`, 254.509.056 bytes. Las cifras de este
documento son válidas para ese commit; si `ppi` cambió desde entonces (nueva
build de BioGRID), re-verificar antes de implementar.
**Scope**: `frontend/src/components/protein/ProteinPPI.vue` únicamente. No
toca `api/`, ni el schema de `PpiPartner`, ni ninguna query SQL — los tres
campos que hacen falta (`experimental_systems`, `evidence_count`,
`pubmed_ids`) ya viajan en la respuesta de `GET /protein/{id}/ppi`.

---

## 1. Problema, medido contra la base viva

Se pidió evaluar si la sección de interacciones proteína-proteína (PPI)
necesita un filtro por cantidad de métodos, porque el panel de partners de
muchas proteínas "parece tener demasiadas interacciones". La medición confirma
que la percepción tiene una causa cuantificable, no es solo volumen:

Sobre 913.858 filas de evidencia BioGRID (no-self), agregadas en 821.519 pares
`(uniprot_id_a, uniprot_id_b)` no dirigidos:

| Métodos distintos por par | N° de pares | % |
|---|---|---|
| 1 | 765.829 | 93,22% |
| 2 | 45.290 | 5,51% |
| 3 | 7.752 | 0,94% |
| 4 | 2.042 | 0,25% |
| 5 | 474 | 0,06% |
| 6+ | 132 | 0,02% |

Clasificando cada par por tres ejes de evidencia independientes —
`n_methods`, `n_pubmed` (PubMed IDs distintos) y si tiene alguna fila
low-throughput—:

| Categoría | N° de pares | % |
|---|---|---|
| 1 método, 1 solo PubMed ID, solo high-throughput (nivel más débil) | 652.480 | 79,42% |
| ≥2 métodos, o ≥2 estudios independientes, o alguna evidencia low-throughput | 169.039 | 20,58% |

Es decir: **4 de cada 5 pares partner-partner en la tabla de un protein page
provienen de un único screen de alto rendimiento, sostenido por un único
paper.** El 87% de esa evidencia de un solo método es Affinity Capture-MS
(68%) o Proximity Label-MS (18%) — dos técnicas AP-MS/BioID de alto
rendimiento conocidas por generar co-purificaciones inespecíficas más que
interacción física directa confirmada. 15 PubMed IDs (redes proteómicas a
escala del interactoma, p. ej. PMID 33961781/BioPlex) explican el 37,7% de
toda esa evidencia débil.

Los grados de conectividad confirman el efecto "hairball": mediana de 5
partners por proteína, pero 6.842 de 43.793 proteínas (15,6%) superan 50
partners, y 1.040 superan 300. El máximo es P0DTD1 (poliproteína replicasa de
SARS-CoV-2, 5.257 partners). El frontend ya reconoce este problema para el
grafo — `INTER_EDGE_DEFAULT_THRESHOLD = 50` en `ProteinPPI.vue` oculta aristas
partner-partner por defecto cuando hay más de 50 partners visibles — pero no
existe ningún filtro equivalente para la tabla ni para el contenido de la
lista de partners en sí.

Detalle completo, tablas y figura de tres paneles:
`docs/review/ppi_evidence_filter/` (ver §6 de este documento).

## 2. Decisión de diseño: qué filtrar y con qué regla

**No usar solo el conteo de métodos.** Un par con un único método pero
múltiples publicaciones independientes, o con evidencia low-throughput
(típicamente ensayos dirigidos, más confiables que un screen), no debería
quedar en el mismo bucket "débil" que un par visto una sola vez en un solo
screen masivo. Dos hubs del propio dataset lo muestran: SUCLG2 (Q96I99) y
Q9UGI0 tienen 2.878 y 2.844 partners respectivamente, casi todos sostenidos
por Affinity Capture-MS **de un único estudio muy profundo** cada uno
(2.811 y 2.672 filas del mismo PMID) — un solo método, pero un dato de
robustez completamente distinto a "un partner que aparece una vez en un
screen genérico de 70.000 interacciones".

Regla propuesta, calculable enteramente a partir de lo que `PpiPartner` ya
expone:

```
is_robust(partner) =
    len(set(partner.experimental_systems)) >= 2
    OR len(set(partner.pubmed_ids)) >= 2
    // (opcional, requiere el campo `throughput` — ver §3)
    OR partner.has_low_throughput_evidence
```

Sin el campo throughput (ver §3), la regla queda en dos de los tres ejes:
`n_methods >= 2 OR n_pubmed >= 2`. Sobre el baseline medido esto ya separa el
79,4% débil del 20,6% robusto — el eje throughput mueve el bucket robusto pero
no cambia el orden de magnitud del problema.

## 3. Qué necesita tocar la API (mínimo) y qué puede evitarse

**Nada es estrictamente necesario en el backend** para lo mínimo (métodos +
estudios): `PpiPartner.experimental_systems` y `PpiPartner.pubmed_ids` ya son
`list[str]`, así que `filteredPartners` en `ProteinPPI.vue` puede calcular
`n_methods = new Set(p.experimental_systems).size` y
`n_pubmed = new Set(p.pubmed_ids).size` en un `computed` de frontend puro, sin
tocar `api/queries/protein_queries.py` ni el schema.

Si se quiere incluir el eje throughput (BioGRID trae `Low Throughput` /
`High Throughput` / `High Throughput|Low Throughput` por fila, ver
`ppi.throughput` en el schema de la tabla), eso sí requiere un cambio de API:
hoy `throughput` no se selecciona en ninguna de las CTEs de `get_ppi_all`
(`api/queries/protein_queries.py:558-570`) ni aparece en `PpiPartner`
(`api/models/schemas.py:196-205`). Agregar
`MAX(CASE WHEN p.throughput LIKE '%Low%' THEN 1 ELSE 0 END) AS has_low_throughput`
a la CTE `partners` y un campo `has_low_throughput: bool` a `PpiPartner` sería
el cambio mínimo — mismo patrón que `evidence_count`/`experimental_systems`
que ya están ahí. Se sugiere hacerlo en una segunda pasada, no bloqueante para
el filtro de métodos/estudios.

## 4. Cambios de frontend concretos (`ProteinPPI.vue`)

1. **Filtro nuevo, junto a los de rol y MLO** (líneas ~20-22 declaran
   `filterRole`/`filterMlo` como `ref`s; el nuevo filtro sigue el mismo
   patrón): un toggle de tres estados — "todos" / "múltiple evidencia"
   (≥2 métodos o ≥2 estudios) / "evidencia única" (el complemento) — no un
   slider numérico, porque la regla es categórica (método+estudio+throughput
   combinados), no un umbral simple sobre una sola columna.
2. **`filteredPartners` (computed, línea 64)** gana una tercera condición,
   igual de estructurada que las dos existentes (`filterRole`, `filterMlo`):
   ```js
   if (filterEvidence.value === 'robust') {
     list = list.filter(p => new Set(p.experimental_systems).size >= 2
                            || new Set(p.pubmed_ids).size >= 2)
   } else if (filterEvidence.value === 'weak') {
     list = list.filter(p => new Set(p.experimental_systems).size < 2
                            && new Set(p.pubmed_ids).size < 2)
   }
   ```
3. **Columna "Evidence" de la tabla** (`shortSystems`, línea 397, usado en
   línea ~547): hoy trunca a 2 sistemas experimentales sin decir cuántos
   PubMed IDs distintos hay detrás. Agregar el conteo de estudios junto al de
   métodos (p. ej. "Affinity Capture-MS, Proximity Label-MS +1 · 3 studies")
   para que la robustez sea visible sin abrir el tooltip.
4. **`resetFilters` (línea ~393)** debe incluir el nuevo filtro en su reset.
5. No tocar el umbral de hairball del grafo (`INTER_EDGE_DEFAULT_THRESHOLD`,
   línea 27) en este cambio — es un problema de renderizado de grafo,
   ortogonal al de confianza de evidencia; si se decide bajarlo, que sea un
   cambio separado justificado por su propio análisis (ver §5 de
   `docs/review/ppi_evidence_filter/ppi_evaluation_report.md` para el
   argumento, si hiciera falta).

## 5. Consideraciones y riesgos a tener en cuenta

- **No es un problema de calidad de dato de MLOsMetaDB.** BioGRID cura
  genuinamente estos registros; el filtro es una ayuda de lectura para el
  usuario final del sitio, no una corrección de la base. No archivar esto
  bajo `docs/issues/` como si fuera un bug — es una mejora de UX/
  interpretación, entra en `docs/superpowers/`.
- **No confundir con el scope contract del ciclo de revisión biológica**
  (`docs/review/`, ver `BIOLOGY.md`): ese ciclo es sobre mapeo de términos
  MLO/rol entre las seis fuentes, no sobre PPI. Este cambio es
  independiente y no necesita pasar por `findings.csv`/`review_ledger.py`.
- **Default del filtro.** Se sugiere default = "todos" (no filtrar), igual
  que `filterMlo`, y dejar "evidencia única"/"múltiple" como elección
  explícita del usuario — cambiar el default de `filterRole` (hoy 'driver')
  no está en el alcance de este cambio.
- **No hay test runner de frontend en este repo** (confirmado en
  `frontend/CLAUDE.md`): verificar leyendo el resultado renderizado o
  pidiéndole al usuario que confirme en el dev server, no escribiendo un
  test automatizado que no existe infraestructura para correr.
- **Los números de este documento son de un análisis puntual, no de un
  script versionado.** Si se quiere que la cifra "79,4% débil" sea
  reproducible contra futuras builds de la DB (por ejemplo para mostrarla en
  el About page o en texto de ayuda de la UI), conviene versionar el cálculo
  como un script pequeño en `scripts/` en vez de citar el número fijo de este
  documento indefinidamente — recompute-don't-quote, mismo criterio que ya
  rige el ciclo de `docs/review/`.

## 6. Material de respaldo

`docs/review/ppi_evidence_filter/`:

- `ppi_evaluation_report.md` — informe completo en prosa (español), con las
  mismas cifras de este documento más el detalle de hubs individuales
  (NUDT21, PRKN, MYC, CUL3, RPA1/2/3, VIRMA, CCNF, DHH1, CCR4 — y las dos
  excepciones SUCLG2/Q9UGI0 citadas en §2).
- `figures/ppi_evidence_overview.png` — panel A (distribución de métodos por
  par), panel B (robustez combinada), panel C (curva de grado rank-ordenada
  con el umbral de hairball existente marcado).
- `data/ppi_method_tier_summary.csv`, `ppi_robustness_summary.csv`,
  `ppi_top_hub_proteins.csv` (top 50 hubs con % de evidencia débil),
  `method_type_evidence_rows.csv`, `weak_tier_method_breakdown.csv`,
  `weak_tier_top_pmids.csv`.

## 7. Próximo paso sugerido

Un plan de implementación (`docs/superpowers/plans/`) con una sola tarea:
agregar el filtro de robustez a `ProteinPPI.vue` según §4.1-§4.4, sin tocar
la API. El eje throughput (§3) queda como tarea opcional de segunda pasada,
solo si se decide que vale la pena el cambio de schema para ese tercer eje.
