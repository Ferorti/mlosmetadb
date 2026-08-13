# Design: aplanar columnas JSON y blindar la generación del TSV de export

**Date**: 2026-08-13
**Status**: approved, pending implementation plan
**Scope**: `api/routers/proteins.py` — `_build_export_record`, `_records_to_tsv`,
y sus tests en `api/tests/test_proteins_router.py`. No toca `format=json`, no
toca `fields=basic`, no toca el frontend ni el pipeline/DB.

---

## 1. Problema

`GET /proteins/export?fields=full&format=tsv` pega tres columnas
(`idr_regions`, `lcr_regions`, `domains`) como texto JSON crudo dentro de una
celda TSV — comportamiento intencional y testeado
(`test_records_to_tsv_passes_through_raw_json_text_unmodified`,
`api/tests/test_proteins_router.py:73`), pero roto en la práctica: Excel
rechaza la celda por exceder el máximo de caracteres por celda (~32.767) en
proteínas con muchos dominios/regiones anotados.

Ese error de Excel es el síntoma, no la causa. La causa es de diseño: estos
tres campos son estructuras anidadas (listas de rangos con metadata) que
nunca debieron viajar sin transformar dentro de una celda de un formato
tabular plano. El propio spec original que introdujo el export
(`docs/superpowers/specs/2026-08-06-api-download-about-nav-design.md:142-143`)
ya advertía esto — *"nested JSON blobs, not flat scalars, and don't belong in
a bulk tabular export"* — pero terminaron incluidos igual.

Además, `_records_to_tsv` (`api/routers/proteins.py:128-140`) no escapa nada:
no usa `csv.writer`, no cita campos, no reemplaza tabs/newlines/comillas
internas. Cualquier valor futuro que contenga un tab o salto de línea literal
desalinearía la fila, no solo estas tres columnas.

---

## 2. Alcance

Afecta solo `format=tsv` con `fields=full` (las tres columnas problemáticas no
están en `fields=basic`). `format=json` no cambia: ya devuelve la estructura
anidada completa y correctamente parseada vía `_parse_json`, que es lo
correcto para quien necesita fidelidad total. El frontend no cambia: el mismo
botón pega al mismo endpoint: solo cambia el contenido de tres columnas y el
mecanismo interno de escritura del TSV.

Fuera de alcance: exponer selección de columnas o filtros en la UI de
`DataPage.vue` (ya señalado como simplificación deliberada, no es parte de
este arreglo), y cualquier cambio a `mlos`/`source_dbs` más allá de
beneficiarse del nuevo escapado.

---

## 3. Aplanado por campo

Los tres campos vienen de `protein_summary` como JSON (ver
`scripts/build_summary.py:209-219`, `SCHEMA.md:249-259`). Regla general:
**lista de nombres/tipos distintos, unidos con `"; "`, sin coordenadas.**

| Campo | JSON de origen | Aplanado | Ejemplo |
|---|---|---|---|
| `domains` | `{"pfam": [{"start","end","label","accession"}], "smart": [...]}` | `label` únicos de todas las fuentes, deduplicados, orden de aparición | `Zinc finger, C3HC4 RING-type; SH3 domain` |
| `lcr_regions` | `{"mobidb_lite": [{"start","end","label"}]}` | `label` únicos, deduplicados, orden de aparición | `Pos_rich; Polar` |
| `idr_regions` | `{"mobidb_lite": [[s,e],...], "alphafold": [...]}` | no tiene `label` por entrada (solo coordenadas por predictor); se listan los **nombres de predictor que tuvieron al menos una región**, deduplicados | `mobidb_lite; alphafold` |

Reglas comunes:

- Deduplicar preservando el primer orden de aparición (no alfabético), para
  no reordenar arbitrariamente respecto al JSON de origen.
- Objeto vacío (`{}`), clave ausente, o valor `NULL` en la columna de origen
  → celda vacía en el TSV (nunca `"{}"`, `"null"` ni `"[]"`).
- El separador `"; "` (punto y coma + espacio) es consistente con el que ya
  usan `mlos` y `source_dbs` (`"; "` reemplaza al `";"` sin espacio actual de
  esos dos campos — ver §5, es el único cambio visual fuera de las tres
  columnas nuevas).

---

## 4. Escapado del TSV (defensa en profundidad)

Se reemplaza el join manual de `_records_to_tsv` por `csv.writer` con
`delimiter="\t"` y `quoting=csv.QUOTE_MINIMAL`. Esto:

- cita automáticamente cualquier celda que contenga el tab, salto de línea o
  comilla (estándar del módulo `csv`, es lo que Excel/pandas esperan al abrir
  un TSV con `sep='\t'`),
- no cambia la representación visual de ninguna celda que no tenga
  caracteres especiales (o sea, el 99% de las celdas hoy),
- cierra la clase de bug de raíz (falta de escapado), no solo el caso puntual
  de estas tres columnas — protege también a `gene_name`, `protein_name`, o
  cualquier columna de texto libre futura.

Listas (`mlos`, `source_dbs`, y los tres campos nuevos) siguen siendo un
`str` ya armado (con `"; "` como separador interno) antes de llegar a
`csv.writer` — el separador de lista y el quoting de CSV son mecanismos
independientes y no interfieren entre sí.

---

## 5. Cambio de separador en `mlos` / `source_dbs`

Pasan de `";"` a `"; "` para que las cinco columnas de lista (`mlos`,
`source_dbs`, `domains`, `lcr_regions`, `idr_regions`) se vean consistentes.
Es un cambio cosmético menor sobre un formato que hoy no tiene consumidores
automatizados conocidos fuera de este mismo export.

---

## 6. Testing

- Reemplazar `test_records_to_tsv_passes_through_raw_json_text_unmodified`
  (fija el comportamiento viejo) por tests que verifiquen el aplanado nuevo:
  un caso por campo (`domains`, `lcr_regions`, `idr_regions`) con JSON de
  ejemplo → string aplanado esperado.
- Test de deduplicación: JSON con el mismo `label` repetido en dos fuentes
  (ej. mismo dominio anotado por pfam y smart) → aparece una sola vez.
- Test de vacío: `{}`, `None`, y clave ausente → celda vacía.
- Test de escapado: un valor con tab, coma y comilla interna sobrevive un
  roundtrip por `csv.reader(delimiter="\t")` con la cantidad correcta de
  columnas (no se puede dar este caso hoy con datos reales de UniProt, pero
  fija el comportamiento como red de seguridad).
- Correr la suite completa de `api/tests/` para confirmar que no se rompe
  nada fuera de `test_proteins_router.py`.

---

## 7. Lo que este diseño no resuelve

- No agrega selección de columnas ni filtros a la UI de descarga
  (`DataPage.vue` sigue siendo un botón de un click a `fields=full`).
- No cambia `format=json`, que ya es el camino correcto para quien necesita
  las coordenadas exactas de dominios/regiones.
- No valida que ningún `label` de UniProt/Pfam/SMART pueda contener `"; "`
  literal (colisionaría con el separador de lista) — riesgo preexistente,
  no introducido por este cambio, y no observado en los datos actuales.
