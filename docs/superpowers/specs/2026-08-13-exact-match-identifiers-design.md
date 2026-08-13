# Design: exact match por identificador, y sacar protein_name del matching

**Date**: 2026-08-13
**Status**: approved, pending implementation plan
**Scope**: `api/routers/search.py`, `api/queries/search_queries.py`,
`api/database.py`, `api/main.py`, `frontend/src/components/search/SearchBox.vue`,
`api/tests/test_search_semantics.py`, `api/tests/test_search_corpus_parity.py`,
`api/tests/conftest_search.py`. No toca `/proteins`, `/proteins/export`,
`/mlo/{id}`, ni ningún otro router.

---

## 1. Problema

El toggle "Exact match" del buscador (`/search?mode=exact`) usa FTS5
`MATCH`, que es *token-exacto* (palabra completa), no igualdad de campo
completo, y matchea contra `uniprot_id`, `gene_name` **y** `protein_name` a
la vez, además de agregar hits de nombres de MLO a la misma respuesta. El
resultado: buscar "FUS" en modo exacto también puede traer una proteína
cuyo `protein_name` sea "FUS RNA-binding protein" — no es realmente "el
identificador que tipeaste", es "una palabra que aparece completa en algún
campo".

Decisión de fondo: el buscador pasa a ser sobre identificadores
(`gene_name`, `uniprot_id`) únicamente. `protein_name` deja de matchear en
absoluto, **en todos los modos** (fuzzy y exact), no solo en exact. Esto es
intencional y confirmado explícitamente pese a que reduce el recall del
buscador general: un término como "kinase", que hoy encuentra proteínas
solo por `protein_name`, va a pasar a devolver 0 resultados.

---

## 2. Alcance por pieza

### 2.1 `/search`, modo `exact`

Reescritura completa. Deja de usar FTS5. Pasa a ser una igualdad de campo
completo, case-insensitive, contra `gene_name` **o** `uniprot_id`. Puede
seguir devolviendo más de una fila (mismo gen en organismos distintos, sin
deduplicar). Deja de agregar hits de `unified_mlo` — el modo exact es solo
sobre proteínas.

`api/queries/search_queries.py`: `search_proteins_fts()` (líneas 6-30) y
`search_mlos_fts()` (líneas 63-76) se **eliminan** — no los usa nada más
que esta rama, confirmado por grep sobre todo `api/`. Se agrega una función
nueva:

```python
async def search_proteins_exact_identifier(q: str) -> list[dict]:
    return await fetchall(
        f"""
        SELECT p.uniprot_id, p.gene_name, p.protein_name, p.organism,
               p.length AS sequence_length,
               p.disorder_mobidb_lite_dc, p.disorder_alphafold_dc,
               p.reviewed,
               ps.idr_regions, ps.lcr_regions, ps.domains,
               ps.has_driver, ps.has_client, ps.source_db_count, ps.mlo_count, ps.mlos,
               ps.source_dbs,
               {_has_regulator_select("p")},
               CASE
                   WHEN LOWER(p.uniprot_id) = LOWER(?) THEN 'uniprot_id'
                   ELSE 'gene_name'
               END AS match_field
        FROM proteins p
        LEFT JOIN protein_summary ps ON ps.uniprot_id = p.uniprot_id
        WHERE LOWER(p.uniprot_id) = LOWER(?) OR LOWER(p.gene_name) = LOWER(?)
        LIMIT 50
        """,
        (q, q, q),
    )
```

`api/routers/search.py`, la rama `mode == "exact"` (líneas 73-80) pasa de:

```python
if mode == "exact" and not database.fts5_available:
    raise HTTPException(501, {"error": "fts5_unavailable", "message": "FTS5 not available; use mode=fuzzy"})
...
if mode == "exact":
    proteins = await search_proteins_fts(q)
    mlos = await search_mlos_fts(q)
```

a:

```python
if mode == "exact":
    proteins = await search_proteins_exact_identifier(q)
    mlos = []
```

Se elimina el chequeo de `fts5_available` — este modo ya no depende de
FTS5, así que el 501 `fts5_unavailable` deja de poder ocurrir nunca.

### 2.2 `/search`, modo `fuzzy`

`search_proteins_like()` (`api/queries/search_queries.py:33-60`) saca la
condición `OR LOWER(' ' || p.protein_name || ' ') LIKE LOWER(?) ESCAPE
'\\'` y el `ELSE 'protein_name'` de su `CASE` de `match_field`. Pasa a
matchear solo `uniprot_id`/`gene_name`. `search_mlos_like()` no se toca
(el modo fuzzy sigue devolviendo hits de MLO, a diferencia de exact).

### 2.3 `/search/advanced`

`_build_advanced_clauses()` (`api/queries/search_queries.py:100-129`): el
filtro de texto libre `q` (líneas 122-129) saca la misma condición sobre
`protein_name`, quedando simétrico con 2.2 — el comentario existente en el
código (líneas 117-121) documenta que este filtro se armó igual a
`search_proteins_like` a propósito, para no repetir una regresión pasada
("kinase" daba 50 hits por un lado y 0 por el otro); sacar `protein_name`
de los dos lugares a la vez mantiene esa simetría, no la rompe. El filtro
dedicado `gene_name` (parámetro propio, no el `q` libre) no se toca.

### 2.4 Frontend — sugerencias (`SearchBox.vue:165-179`)

El título de cada sugerencia del dropdown pasa de:
```
{{ protein.protein_name || protein.gene_name || protein.uniprot_id }}
```
a:
```
{{ protein.gene_name || protein.uniprot_id }}
```
`uniprot_id` (mono) y `organism` (cursiva) siguen mostrándose igual que
hoy, sin cambios — con esto la sugerencia queda "Gene Name · UniProt ·
Organism" (con fallback a UniProt si no hay gene name).

### 2.5 Frontend — el chip

**Label**: queda **"Exact match"**, sin renombrar (decisión explícita: con
el buscador ya limitado a identificadores, agregar "Identifier" al label no
aporta nada — solo tendría sentido para alguien que conoce la charla de
diseño que llevó hasta acá, no para un usuario nuevo).

**Tooltip** (`SearchBox.vue:137`, hoy *"Search for exact term only (e.g.
FUS but not FUSED)"*): pasa a **"Match the gene name or UniProt accession
exactly (e.g. FUS, not FUSED)"** — afirmación positiva y autocontenida del
comportamiento actual, sin contrastar contra un comportamiento anterior
(`protein_name`/FTS5) que el usuario nunca supo que existía. Ver nota de
estilo en §5.

### 2.6 Sacar FTS5 por completo

Sin ningún llamador después de 2.1, queda como código muerto real (no
hipotético) si se deja. Se elimina:

- `api/database.py`: `fts5_available` (línea 15), `check_fts5()` (líneas
  90-95), `setup_fts5()` (líneas 125-146) — las tres, completas.
- `api/main.py`: la llamada `await database.setup_fts5()` en `lifespan()`
  (línea 139), y el log de arranque (línea 144) deja de referenciar FTS5
  (`"Startup complete"` en vez de `"Startup complete — FTS5=%s"`).
- `api/routers/search.py`: el chequeo de `fts5_available` (ya cubierto en
  2.1).

Confirmado por grep: ningún fixture de test (`conftest.py`,
`conftest_search.py`) llama `setup_fts5()`/`check_fts5()` directamente, así
que esta eliminación no rompe la suite por ese lado — solo el test que
asertaba sobre el 501 (ver §4) necesita actualizarse.

---

## 3. Documentación a actualizar

- `api/CLAUDE.md`, fila de `/search` en la tabla de endpoints: pasa de
  *"Basic search over gene names/UniProt IDs/protein names/MLO names — FTS5
  if available, else LIKE fallback"* a reflejar que matchea
  `gene_name`/`uniprot_id` (proteínas) y nombres de MLO (modo fuzzy
  únicamente), sin FTS5.
- `api/CLAUDE.md`, tabla de errores: se saca la fila `mode=exact` sin FTS5
  → 501 `fts5_unavailable` — ya no puede pasar.

Fuera de alcance (no pedido, no se hace en este cambio): documentar el
dropdown de sugerencias en `frontend/CLAUDE.md` — hoy no está documentado
ahí (gap preexistente, no introducido por este cambio).

---

## 4. Testing

### 4.1 `api/tests/conftest_search.py` — el fixture `SEARCH_FIXTURE`

Tres filas existen únicamente para probar semántica de `protein_name` que
este cambio elimina (confirmado por grep: ninguna aparece fuera de
`test_search_semantics.py` / `test_search_corpus_parity.py` / este mismo
fixture):

- **`P00002`** (`STK33`, protein_name `"Serine/threonine-protein kinase
  33"`) — se **mantiene**, pero se repropósita: en vez de probar que
  "kinase" la encuentra (matchea solo por protein_name), pasa a ser la
  prueba negativa de que ya no la encuentra. Comentario actualizado: *"kinase" ya no debe encontrar esto — su única conexión léxica es protein_name*.
- **`P00009`** (`ZZZ9`, protein_name `"Phosphokinaselike domain protein"`)
  — se **elimina** (proteins + protein_summary). Probaba la regla de
  "palabra completa" que era específica de `protein_name`; esa regla deja
  de existir junto con el campo.
- **`P00010`** (`ZZZ10`, protein_name `"Casein kinase II subunit alpha"`,
  driver de `stress_granule`) — se **elimina** (proteins + protein_summary
  + su fila en `mlo_annotations`). Los dos tests que lo usaban (§4.3) se
  reescriben usando **`P00001`** en su lugar, que ya existe en el fixture,
  ya es driver (`has_driver=1`) y ya tiene una fila `mlo_annotations` para
  `stress_granule` — y matchea "kinase" por `gene_name` (`KINASE1`), no por
  `protein_name`, así que sirve exactamente para el mismo propósito.
- El comentario de cabecera del fixture (línea 19-20, *"Each row isolates
  exactly one matching path for the query 'kinase'"*) se actualiza para no
  listar `protein_name` como uno de los tres caminos de matching.

### 4.2 `api/tests/test_search_semantics.py`

- `test_matches_through_protein_name` (línea 31) → se **invierte** y
  renombra a `test_protein_name_no_longer_matches`: `assert "P00002" not in
  ids(hits(c, q="kinase"))`.
- `test_protein_name_matches_whole_words_only` (línea 64) → se **elimina**
  (usaba `P00009`, que sale del fixture; la regla que probaba ya no existe).
- `test_all_three_fields_answer_one_query` (línea 43) → se actualiza a
  `{"P00001", "KINASE9"} <= found` (saca `P00002`), y se renombra a
  `test_both_fields_answer_one_query`.
- `test_exact_mode_without_fts5_is_a_clean_501` (línea 137) → se reemplaza
  por un test que confirma que `mode=exact` responde 200 siempre (ya no
  puede dar 501, FTS5 no existe más).
- Tests nuevos:
  - `mode=exact` matchea `gene_name` completo, case-insensitive.
  - `mode=exact` matchea `uniprot_id` completo, case-insensitive.
  - `mode=exact` NO matchea un término que sea substring de
    `gene_name`/`uniprot_id` (ej. buscar "KINASE" con `mode=exact` no debe
    encontrar `P00001`/`KINASE1`, porque el gene_name completo es
    `"KINASE1"`, no `"KINASE"`).
  - `mode=exact` nunca devuelve `mlos` (lista vacía).
  - `mode=exact` puede devolver más de una fila (mismo gen, organismos
    distintos) — no existe hoy ningún par de filas con el mismo
    `gene_name` en `SEARCH_FIXTURE`, así que se agregan dos nuevas:
    `('P00011', 'DUPGENE', 'Duplicate gene protein one', 'Homo sapiens', 9606, 100, 1)`
    y `('P00012', 'DUPGENE', 'Duplicate gene protein two', 'Mus musculus', 10090, 100, 1)`
    (más sus filas mínimas en `protein_summary`, mismo patrón que las
    demás), y el test verifica `{"P00011", "P00012"} <= ids(hits(c,
    q="DUPGENE", mode="exact"))`.
- El resto (matching de MLO, wildcards literales, case-insensitivity de
  `gene_name`, `NULL` que no rompe la query, anotaciones inactivas, DB
  faltante) no se toca.

### 4.3 `api/tests/test_search_corpus_parity.py`

- `test_free_text_matches_the_same_proteins_on_both_paths` — **no se
  toca**: la paridad entre `/search` y `/search/advanced` se preserva
  precisamente porque `protein_name` se saca de los dos lados de forma
  simétrica (§2.2 y §2.3); el invariante que este test protege no depende
  de qué columnas se comparan, solo de que ambos paths comparen las
  mismas.
- `test_advanced_free_text_reaches_protein_name` (línea 40, usa `P00002`)
  → se **elimina** (duplicaría la cobertura negativa que ya da §4.2, y su
  premisa — que el free text *debe* alcanzar protein_name — es
  exactamente lo que este cambio revierte).
- `test_advanced_keeps_the_whole_word_rule_for_protein_name` (línea 51,
  usa `P00009`) → se **elimina** (mismo motivo que en §4.2: `P00009` sale
  del fixture, la regla que probaba ya no existe).
- `test_advanced_free_text_reaches_uniprot_id`,
  `test_advanced_free_text_escapes_like_metacharacters` → no se tocan.
- `test_a_filter_narrows_the_result_set_without_changing_the_corpus`
  (línea 64, usa `P00010`) → se **reescribe** con `P00001`: docstring pasa
  a *"P00001 is a driver whose only 'kinase' match is its gene_name"*,
  mismas aserciones (`unfiltered`/`drivers` con `role="driver"`) apuntando
  a `P00001` en vez de `P00010`.
- `test_filtering_by_organelle_keeps_protein_name_matches` (línea 74, usa
  `P00010`) → se **reescribe** con `P00001` y se renombra a
  `test_filtering_by_organelle_keeps_gene_name_matches`: `assert "P00001"
  in advanced(c, q="kinase", mlo="stress_granule")`.
- Los tests de paginación/orden/"sin filtros" (líneas 81-117) usan
  `q="kinase"` de forma genérica y solo necesitan `total >= 3`: con
  `P00002`/`P00009`/`P00010` fuera, "kinase" sigue matcheando exactamente 3
  filas por `gene_name`/`uniprot_id` (`P00001` `KINASE1`, `P00004`
  `KiNaSe4`, `KINASE9`) — **no se tocan**, la aserción `total >= 3` sigue
  siendo cierta con el fixture actualizado.

---

## 5. Nota de estilo aplicada (no específica de este cambio)

Ningún texto de UI de este cambio debe leerse como un diff contra una
decisión de diseño que el usuario final nunca vio — cada label/tooltip se
redactó como afirmación positiva del comportamiento actual, no como
contraste ("ya no busca X", "solo Y") contra un comportamiento anterior
que el usuario no tiene por qué conocer.

---

## 6. Lo que este diseño no resuelve

- No agrega el dropdown de sugerencias a la documentación de
  `frontend/CLAUDE.md` (gap preexistente, no introducido acá).
- No cambia qué se muestra en la tabla de resultados ni en la página de
  proteína — `protein_name` sigue siendo un dato visible ahí, esto es solo
  sobre qué campos *matchean* una búsqueda.
- No optimiza con un índice sobre `gene_name`/`uniprot_id` para la
  igualdad exacta — `uniprot_id` ya es `PRIMARY KEY` (índice implícito);
  si `gene_name` no tiene índice hoy y el volumen de datos lo justifica en
  el futuro, es una mejora de performance separada, no parte de este
  cambio de comportamiento.
