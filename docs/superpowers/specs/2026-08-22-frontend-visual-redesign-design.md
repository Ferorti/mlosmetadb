# Design: sistema visual v3 (rediseño de layout/estilo, sin tocar datos)

**Date**: 2026-08-22 (implementado y mergeado a `frontend/visual-redesign` 2026-08-23; iterado con el usuario post-merge hasta 2026-08-24, ver §9)
**Status**: implementado — las 16 tareas del plan + revisión final +
correcciones post-merge de §9 están todas mergeadas en
`frontend/visual-redesign`. No queda en el worktree/branch de
implementación (`frontend/visual-redesign-impl`), que ya se borró tras
el merge.
**Scope**: `frontend/` completo (Tailwind config, fuentes, y las cuatro
pantallas cubiertas por los mockups: Home, Search Results/ResultsPage,
Protein Page, MLO detail). No toca `api/`, `database/`, `scripts/`,
`parsers/`, ni ningún dato, categoría, rol o identificador servido hoy.
Referencia de diseño: `frontend/cd/*.dc.html` (Claude Design), documento de
sistema visual pegado por el usuario en esta conversación.

---

## 0. Regla de prioridad (confirmada con el usuario, 2026-08-22)

El usuario la formuló así, textual:

> "Ante cualquier pregunta similar, siempre resolver a favor de lo
> actualmente existente que no sea dominio exclusivo de la interfaz.
> Categorías, roles, identificadores, todo eso tiene que mantenerse, solo
> modificar layouts, formas de presentar los datos, estilos, tipografías
> [...] si ahora hay ejes ortogonales, no importa lo que haya en el mock,
> quedan ejes ortogonales [...] todos los textos y definiciones van los
> actuales."

Aplicación concreta en este documento:

- Ningún campo, categoría, rol, axis o copy se **inventa** ni se
  **colapsa** porque el mock lo simplifique. Si el mock muestra un campo
  que el backend no devuelve, ese campo se **corta** de este alcance (no
  se implementa un backend nuevo para sostenerlo) o se adapta al campo
  real más cercano — nunca se rellena con datos de ejemplo del mock.
  Cada corte está listado explícitamente por pantalla, sección "Datos no
  disponibles".
- Toda copy (labels, tooltips, descripciones de rol, blurbs de fuente) se
  toma **verbatim** de donde ya existe en el código (`RoleCards.vue`,
  `RoleBadge.vue`, `SourcesSection.vue`, `mloAxes.js`, `BIOLOGY.md`), no
  del texto de ejemplo en los `.dc.html`.
- Lo que el mock SÍ tiene autoridad para decidir: paleta de color,
  tipografía, spacing, si algo va en card vs. tabla vs. lista plana, y
  decisiones de interacción que no cambian qué datos se pueden pedir (ej.
  chips → checkboxes reales, layout de tabs, tabla-única en vez de
  cards/tabla intercambiables).

---

## 1. Sistema global

### 1.1 Tipografía y fuentes

`frontend/index.html` — el `<link>` de Google Fonts pasa de
`IBM+Plex+Sans:wght@400;500` a:

```
IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&family=Archivo:wght@600;700
```

`IBM Plex Sans` deja de estar scoped a `FilterSidebar.vue` y pasa a ser la
fuente base de toda la app (hoy es el default del sistema vía Tailwind).
`Archivo` se usa solo para títulos grandes (H1 de pantalla, números de
stats). `IBM Plex Mono` para metadatos, accesiones, coordenadas,
encabezados de columna — reemplaza los usos sueltos de `font-mono` que ya
existen (Tailwind trae una mono por default; pasa a ser explícitamente
IBM Plex Mono vía `tailwind.config.js`).

### 1.2 `tailwind.config.js` — paleta

Los cuatro colores de marca actuales (`brand.blue/green/amber/teal`) se
usan en exactamente 2 archivos (`RoleBadge.vue`, `RoleCards.vue`, grep
confirmado). Pasan a la paleta del documento, con un color agregado que
el documento no define — ver 1.3.

```js
colors: {
  ink:      '#16181C',  // texto principal
  ink2:     '#4A4E55',  // texto secundario
  ink3:     '#4E5762',  // texto terciario / mono metadatos
  muted:    '#5F6874',  // gris más claro permitido
  navy:     '#0E2136',  // header, footer, botón primario
  brand:    '#1560A8',  // azul del sitio: links, acento, rol Driver
  surface:  '#FFFFFF',
  page:     '#F7F9FC',
  border:   { strong: '#D2D9E3', DEFAULT: '#DFE4EC', soft: '#E9EDF4' },
  track:    '#E8ECF3',  // riel de barra vacío
  feature: {
    idr:    '#B8362B',
    domain: '#2C7A6B',
    lcd:    '#98A2B3',
    morf:   '#6B4E8F',
  },
}
```

`FEATURE_COLORS` en `useProteinFeatures.js` y las constantes `TRACK`/
`COMPACT` en `SequenceFeatureViewer.vue` (hoy con dos paletas
divergentes, ver `frontend/CLAUDE.md`) se unifican a esta única paleta —
el documento es explícito en que el color de clase de feature "no es
decorativo" y solo puede significar una cosa en todo el sitio.

### 1.3 Decisión de diseño no cubierta por el documento: color de rol Regulator

El documento solo asigna color a **Driver** (`#1560A8`, "el color del
sitio"). No define qué color usa el texto/badge cuando el rol es
`regulator` (aparece en `RoleBadge.vue` hoy como ámbar `#854F0B`, y en
`/mlo/{id}`'s `by_role` de a tres — driver/regulator/component — ver
§4.3 más abajo).

**Decisión**: mantengo un tercer color de rol, ámbar, recalculado dentro
de la paleta más desaturada del sistema nuevo: `#8A5A1E` sobre fondo
`#F6EFE4` (mismo par que ya usa `RoleBadge.vue`, verificado AA). No es
parte de los 4 colores de feature (eje distinto: rol de proteína, no
clase de secuencia), así que no viola la regla de "un eje, un color". Lo
marco acá para que puedas vetarlo — es la única decisión de color que no
sale directamente del documento.

### 1.4 Layout, tablas, tracks, formularios

Se aplican 1:1 como están en el documento (§3–§6): `max-width: 1080px`
(1180px con sidebar), sin cards para listas/tablas, sin sombras/
gradientes/radios > 2px, tabla con header mono 10.5px, filas separadas
por `#E9EDF4`, checkboxes reales en vez de chips dentro del buscador,
tracks de secuencia un carril por clase de feature con escala compartida
en listados. Ninguna de estas reglas toca un dato — son puramente
visuales/interacción, dentro del dominio del documento.

---

## 2. Home

### 2.1 Se aplica del mock

Layout completo: hero con búsqueda + checkboxes (reemplaza los chips
actuales), stats en `Archivo` 30px, tabla "Source databases", ranking de
organismos con barra proporcional, matriz de coverage (organela ×
5 fuentes, punto/guión), cards "Get the data".

### 2.2 Contenido real a usar (no el texto de ejemplo del mock)

- **Blurbs de fuente**: el mock inventa texto ("Community-curated
  condensates", etc.). Ya existe copy real en
  `components/unification/SourcesSection.vue:26-30` — se reusa verbatim:
  - CD-CODE: "Community-editable database of biomolecular condensates."
  - DrLLPS: "Scaffold, regulator, and client proteins involved in LLPS."
  - LLPSDB: "Proteins with LLPS behavior observed in vitro, with
    experimental conditions."
  - PhaSepDB: "Manually curated database of proteins linked to LLPS."
  - PhasePro: "Proteins and regions experimentally validated as LLPS
    drivers."
- **Conteos por fuente**: `StatsResponse.mlo_annotations.
  unique_proteins_by_source` (`api/models/schemas.py:313`), no el número
  fijo del mock.
- **Organismos**: `StatsResponse.proteins.by_organism` (real, ya
  consumido hoy en `statsData.proteins.by_organism` vía
  `FilterSidebar.vue:37`).
- **Matriz de coverage**: se arma con `/mlos` (`MloListItem.protein_count`,
  `.sources`, `.definitions[].source_name` para el tooltip "término tal
  como lo escribe esa fuente" — dato real, mismo campo que ya usa
  `MlosPage.vue` para las definiciones expandibles).
- **Stats de cabecera** (proteins/organelles/drivers/species/sources):
  de `/stats` + `len(mlos)`, no hardcodeados.

### 2.3 Datos no disponibles → se cortan

Ninguno en esta pantalla — todo el contenido del mock de Home tiene un
campo real detrás.

---

## 3. Search Results (`ResultsPage.vue` + `ResultsPanel.vue`)

### 3.1 Se aplica del mock

Tabla única con columnas PROTEIN / ARCHITECTURE (bandas IDR+dominio a
escala compartida) / LENGTH / MLOS / SOURCES (matriz de puntos) / ROLE.
**Esto reemplaza el toggle cards/tabla actual** — decisión de UX dentro
del dominio del documento (no cambia qué se puede filtrar ni qué dato se
muestra, solo cómo). La vista "cards" de `ResultsPanel.vue` se elimina;
TanStack Table se mantiene como mecanismo de tabla pero re-skinneada a
estas reglas (o se reemplaza por markup plano si TanStack no puede
expresar las bandas D3 sin fricción — a decidir en el plan de
implementación, es un detalle técnico, no de diseño).

### 3.2 Contenido real a usar

- Columnas y datos: `protein_summary`/`/proteins`'s campos ya
  consumidos hoy (`idr_regions`, `domains`, `sequence_length`, `mlos`,
  `unified_role`, `source_dbs`) — nada nuevo.
- Rol en la columna ROLE: dos colores reales, `driver` → `brand`
  (`#1560A8`), cualquier otro (`client`/`null`) → `ink3` (`#4E5762`),
  igual que hace el mock (`roleColor: role === "Driver" ? blue : gray`).
  El mock no tiene una tercera opción visible para `regulator` en esta
  tabla — no hace falta inventar una: **una fila de resultados no lleva
  un rol per-annotation de regulator hoy** (`unified_role` es driver/
  client/null a nivel proteína en este endpoint), así que dos colores
  alcanza y no hay conflicto.

### 3.3 Datos no disponibles → se cortan / se adaptan

- **El sidebar de facets del mock** (ORGANISM/ROLE/SOURCE/COMPARTMENT,
  cada opción con un conteo) implica un endpoint de facets con conteos
  por valor que **no existe funcionando hoy** —
  `FilterSidebar.vue:16-18` tiene el TODO explícito: *"facets require
  API extension — GET /search/facets [...] Until then, facets prop is
  null and counts are not shown."* Completar ese endpoint es trabajo de
  backend fuera del alcance de un rediseño visual.
  **Decisión**: mantengo los filtros reales de hoy (organism vía
  autocomplete de `/organisms/search`, role driver/component, mlo desde
  `/mlos`, source_db, feature_type/feature_accession) restyleados con la
  tipografía mono + checkbox del documento, mostrando conteo solo cuando
  `props.facets` lo trae (ya es así hoy) y sin conteo cuando no — nunca
  un número inventado. No agrego un facet "COMPARTMENT" nuevo: no hay
  filtro por `spatial_location` en `/search/advanced` hoy
  (`_build_advanced_clauses` no lo acepta); agregarlo sería una feature
  nueva de backend, no visual.
- El mock muestra `role="Regulator"` como una opción de facet
  (`facetDef`, `["Regulator", 58]`) — `roleOptions` real
  (`FilterSidebar.vue:42-45`) solo ofrece driver/component porque
  `role=` como query param no acepta `regulator` (`policy.
  component_role_clause()` — ver `api/CLAUDE.md`). No se agrega la
  opción.

---

## 4. Protein Page

Es la pantalla más fiel al mock — casi todo el contenido ya existe hoy
con la misma forma.

### 4.1 Se aplica del mock

Header con nombre + badge de rol + "IN N SOURCES", tabs Overview/MLO
annotations/Interactions, track de secuencia por carril (DISORDER/
COMPOSITION/DOMAINS/MOTIFS) con regla de coordenadas, bloque de secuencia
monoespaciada con highlight de IDR, viewer de AlphaFold, tabla de
features agrupada por clase, matriz de fuentes en la tab de MLOs, tabla
de partners de PPI + grafo.

### 4.2 Contenido real a usar

- Colores de feature: paleta unificada de §1.2 (ya coincide con lo que
  hoy vive en `useProteinFeatures.js`, solo se recalculan los hex).
- Badge de rol y su tooltip: **verbatim de `RoleBadge.vue`** — labels
  "LLPS Driver"/"MLO Component"/"Regulator", tooltip de regulator sin
  cambios: *"Annotated as a regulator of this organelle, not as a
  resident of it — a curator assignment that applies to the whole
  protein, not to this compartment specifically"*.
- Matriz de fuentes en la tab MLO annotations: ya es real hoy
  (`ProteinMLOs.vue`'s `dedupedAnnotations`), con el caveat de
  `NotInformed` (§ "NotInformed display rule" de `frontend/CLAUDE.md`)
  preservado — el mock no lo contempla porque su dataset de ejemplo no
  tiene ningún caso `NotInformed`, no porque lo excluya a propósito.
- **Corrección de un hallazgo previo de esta spec**: en la versión
  anterior de este documento yo había marcado la mención a STRING del
  mock como un dato inventado, basado solo en que `api/CLAUDE.md` y
  `BIOLOGY.md` no la mencionan. Al leer el componente real
  (`ProteinPPI.vue:378-381`) encontré que la app **ya** enlaza a BioGRID
  y a STRING como recursos externos para "the full network" — el mismo
  patrón que los links a UniProt/AlphaFold/MobiDB/InterPro en
  `ProteinPage.vue`. STRING no es una fuente de datos integrada (los
  partners que se listan salen de BioGRID), pero el link externo a
  STRING como "dónde mirar la red completa" es contenido real ya
  existente, no algo que este cambio deba sacar. Lo único falso del mock
  es el **número inventado** ("503 further interactions") atribuido a
  esa combinación — se mantiene la fórmula actual (conteo real de
  `total_partners` + los dos links externos, sin asignarle el conteo a
  una fuente en particular), restyleada, no reescrita.

### 4.3 Datos no disponibles → ninguno

No encontré contenido inventado en este mock más allá del punto STRING
ya corregido arriba.

---

## 5. MLO detail — el caso grande

### 5.1 Estado real hoy (antes de este cambio)

**Esta pantalla no existe como vista separada.** Las rutas `/mlo/:mlo` y
`/mlos` renderizan el mismo `MlosPage.vue` (la lista completa con
filtros), que **ignora** el parámetro `:mlo`. `getMlo(mlo, params)`
existe en `api/mlos.js` pero no lo llama nadie — código muerto
documentado como tal en `frontend/CLAUDE.md`. El backend sí tiene todo lo
necesario: `GET /mlo/{unified_mlo}` devuelve `MloDetail` (4 ejes +
provenance, `definitions[]` por fuente, `stats` con
`total_proteins`/`by_source`/`by_role`(driver/regulator/component)/
`organisms` (lista de nombres, sin conteo), y `proteins` paginado).

**Decisión de alcance**: construyo la vista de detalle real, conectando
`getMlo()` (ya escrito, nunca usado) — esto no es "solo estilo" en
sentido estricto, es construir una pantalla que hoy no renderiza nada
distinto de la lista, pero usa exclusivamente datos que el backend ya
sirve. Lo marco para que lo confirmes junto con el resto: es más trabajo
que un restyle puro, aunque cero riesgo de dato inventado porque todo
sale de un endpoint que ya existe y ya se prueba
(`api/tests/test_proteins_router.py` y afines cubren `/mlo/{id}`
indirectamente — a confirmar cobertura exacta en el plan de
implementación).

### 5.2 Se aplica del mock

Breadcrumb, header con nombre + stats a la derecha, sección "Source
terms mapped here" (tabla fuente/término/conteo), tabla de proteínas con
disorder/sources/role, pills de filtro Drivers/Components/All.

### 5.3 Datos no disponibles → se cortan o se adaptan

- **`GO:0010494` y el tag `"reversible"`** en el header: no existen en
  `MloDetail` ni en ninguna tabla de `SCHEMA.md` — no hay columna de GO
  term ni de reversibilidad en `mlo_vocabulary`. **Se cortan.** Si en
  algún momento se quiere anotación GO, es un mapeo de datos nuevo, no
  parte de este rediseño.
- **El párrafo de descripción del header** ("Cytoplasmic condensate
  of..."): `MloDetail` no tiene un campo de descripción unificada, solo
  `definitions[]` por fuente (una por `source_db`, con su propio texto).
  Mostrar una de esas como si fuera "la" descripción canónica sería
  elegir una fuente por sobre las demás sin base — **exactamente lo que
  el punto 2 de tu propia regla de prioridad prohíbe** (esconder que la
  info viene de varias fuentes con términos propios). Se corta el
  párrafo suelto del header; la sección "Source terms mapped here" ya
  cumple ese rol mostrando las `N` definiciones con su fuente explícita,
  sin elegir una como "la" oficial.
- **Conteo de proteínas por término de fuente** en la tabla "Source terms
  mapped here" (mock: columna PROTEINS con "1,204", "88", etc. por fila
  de término): `MloDetail.definitions[]` trae `source_db`/`source_name`/
  `definition`, sin conteo por término individual — el conteo que sí
  existe es agregado por `source_db` completo
  (`stats.by_source`), no por término exacto dentro de esa fuente. Se
  corta la columna PROTEINS de esa tabla específica (queda
  fuente/término); el conteo por fuente completa se muestra en la
  sección de stats de cabecera, que sí es real.
- **"Species" con barra proporcional y conteo por especie**:
  `MloStats.organisms` es `list[str]` — nombres, sin conteo por
  organismo. Se corta la barra proporcional y el número; queda una lista
  simple de organismos (o se agrupa "N species" como cifra agregada, que
  sí es `len(organisms)`, real).
- **"Related organelles" por proteínas compartidas**: no hay ningún
  cálculo de organelas relacionadas por overlap de proteínas en el
  backend — ni en `mlo_queries.py` ni en `SCHEMA.md`. **Se corta la
  sección completa** de este alcance. Es una feature de backend nueva
  (requiere una query de intersección de `mlo_annotations` por
  `uniprot_id`), no un rediseño de algo que ya se calcula.
- **"Roles" con 4 buckets** (Driver/Component/Regulator/Unclassified):
  `by_role` real de `/mlo/{id}` tiene **3** buckets
  (`mlo_queries.py::get_mlo_stats()`, `api/CLAUDE.md` tabla de
  vocabularios de `by_role`) — el `else` de ese `CASE` ya mete todo rol
  `NULL`/no-driver-no-regulator dentro de `component`, no hay un cuarto
  balde. Se implementan los 3 buckets reales, no 4.
- **Textos de rol**: verbatim de `RoleCards.vue:23-40` (no del mock):
  - Driver: "Proteins with direct experimental evidence of driving
    liquid-liquid phase separation and/or MLO formation. Annotated as
    driver or scaffold in at least one source database."
  - Component: "Proteins associated with membraneless organelles without
    direct evidence of driving phase separation. Includes clients and
    proteins whose role no source determined."
  - Regulator: "Proteins a curator annotated as regulating an organelle
    rather than driving or residing in it. Curator-assigned in at least
    one source database."

  Esto responde directamente tu segunda respuesta ("todos los textos y
  definiciones van los actuales") — descarto la copy del mock
  ("Modulates assembly or dissolution, often post-translationally", que
  además afirma un mecanismo post-traduccional que `BIOLOGY.md` no
  documenta en ningún lado).
- **Los 4 ejes de clasificación**: el mock solo usa `spatial_location`
  ("cytoplasm" en el breadcrumb y el header). Se agregan
  `taxonomic_scope`, `physiological_state`, `cell_type_context` — con
  sus caveats (`spatial_location_evidence === 'hand_assigned'` →
  "provisional", `taxonomic_support_n` bajo → nota de soporte débil,
  ambos ya implementados en `mloAxes.js`) — en el header de esta
  pantalla, con la tipografía mono del sistema en vez de los bordes
  punteados que usa hoy `MlosPage.vue`. Es la aplicación directa de tu
  primera respuesta.
- **Pills Drivers/Components/All** para filtrar la tabla de proteínas: sí
  tienen backing real (`role` query param de `get_mlo_proteins_page`,
  ya usado). Se implementan tal cual.

---

## 6. Fuera de alcance (todas las pantallas)

- No se completa el TODO de `/search/facets` (conteos por facet en
  Search Results).
- No se agrega backend para GO terms, reversibilidad, related-organelles
  por overlap, o conteo por especie en `/mlo/{id}`.
- No se cambia ningún valor de `unified_role`, ningún axis, ninguna
  categoría de fuente, ningún identificador.
- No se toca `MlosPage.vue`'s comportamiento de lista/filtro — se
  restylea con las mismas reglas visuales que el resto, pero sigue
  siendo la vista de "todas las MLOs"; la nueva vista de detalle es
  aparte (activada cuando la ruta trae `:mlo`).
- No se cambia el mecanismo de paginación, sort, ni ningún contrato de
  URL state documentado en `frontend/CLAUDE.md`.

---

## 7. Plan de commits (orden propuesto, uno por punto de verificación)

1. Tokens globales: `tailwind.config.js`, fuentes en `index.html`,
   unificación de `FEATURE_COLORS`/`TRACK`/`COMPACT`. Sin cambio visible
   en ninguna página todavía si se hace bien (nuevos tokens sin uso).
2. `AppNavbar.vue`/`AppFooter.vue`/`AnnouncementBanner.vue` — layout de
   header/footer del sistema nuevo.
3. Home — página completa.
4. Search Results — filtros restyleados + tabla única (retiro de cards
   view).
5. Protein Page — track/secuencia/features/PPI restyleados.
6. MLO detail — página nueva, conectando `getMlo()`; `MlosPage.vue`
   (lista) restyleada por separado.
7. Barrido final: cualquier página no cubierta por los mocks (Download,
   About, Data/Unification) queda en el estilo actual — fuera de este
   alcance salvo que se pida explícitamente.

Cada punto es un commit separado (o varios, si conviene dividir por
componente) para poder volver a un estado intermedio.

---

## 8. Lo que este diseño no resuelve

- No decide si TanStack Table puede expresar las bandas D3 de
  ARCHITECTURE sin fricción, o si esa columna se implementa con markup
  plano dentro de la misma tabla — detalle técnico para el plan de
  implementación.
- No decide la cobertura de tests automatizados para la nueva vista de
  MLO detail (es una página nueva; probablemente necesita al menos un
  test de router/integración si no existe ya cobertura indirecta de
  `/mlo/{id}`) — a confirmar en el plan.
- No define el comportamiento mobile/responsive de las tablas anchas
  (ARCHITECTURE, matrices de fuente) más allá de lo que ya dicta
  `overflow-x` estándar — el documento no lo cubre y no hay mockup
  mobile.

---

## 9. Correcciones post-merge (revisión directa del usuario sobre la app corriendo, 2026-08-23/24)

Las 16 tareas del plan se ejecutaron vía subagent-driven-development en
un worktree aislado (`frontend/visual-redesign-impl`), pasaron su
revisión final, y se mergearon a `frontend/visual-redesign` (fast-forward,
commit `c988f22`). El worktree y la branch de implementación ya no
existen — todo lo de esta sección son commits directos sobre
`frontend/visual-redesign`, hechos por el usuario mirando la app real con
`npm run dev` y pidiendo ajustes puntuales. Ninguna de estas correcciones
pasó por el proceso de subagentes/revisión del plan original; son
ediciones directas, cada una en su propio commit.

### 9.1 Tres reversiones de copy (commit `2b86fe7`)

El usuario detectó que, pese a la regla de prioridad de §0, tres textos
reales habían sido reemplazados por copy inventado del mock durante la
Task 5 del plan:

- Home H1: **"Proteins in membraneless organelles"** (tagline del mock) →
  vuelve a **"MLOsMetaDB"** (nombre real del producto).
- Home hero, línea de ejemplos: **"TRY"** → vuelve a **"Examples:"**.
- `ProteinHeader.vue`, pill de rol: **"LLPS driver"** (minúscula, casing
  del mock) → vuelve a **"LLPS Driver"** (label verbatim de
  `RoleBadge.vue`).

**Lección para cualquier trabajo futuro sobre este código**: la regla de
§0 ("todo el texto existente se mantiene, solo layout/estilo/tipografía
cambia") aplica a **cualquier** copy visible, no solo a categorías/roles/
identificadores en el sentido de datos de la base. Un H1 con el nombre
del producto, una etiqueta de UI, el casing exacto de un label — todo
eso es "texto existente" y no se reemplaza por la redacción del mock sin
preguntar primero, aunque parezca una mejora de UX defendible en el
momento. Ya pasó tres veces en esta misma sesión (ver también §9.5 con
el click-to-filter de MLOs, mismo patrón pero de comportamiento en vez
de texto).

### 9.2 Home hero (commits `f60266c`, `741c4ef`)

- Vuelve a estar centrado (`text-center`), con el logo
  (`loguito_horizontal.svg`) arriba del título, título más chico (30px
  en vez de 52px), y todo el bloque (logo, título, párrafo, buscador,
  ejemplos) dentro de un único contenedor `max-w-3xl mx-auto` en vez de
  cada hijo con su propio ancho — así quedan alineados al mismo borde.
- Padding vertical reducido (`pt-14/pb-9` → `pt-8/pb-7`) — había
  demasiado espacio en blanco arriba y entre los ejemplos y la línea
  divisoria de abajo.
- Fondo celeste restaurado: `#EAF2FA` / borde `#D2E3F1` — un tinte del
  `brand` nuevo (`#1560A8`) mezclado con blanco a la misma claridad que
  el `#EBF3FB` pre-rediseño, no el hex viejo reciclado. Valores inline,
  no promovidos a token todavía.

### 9.3 Home — "Browse by MLO" reconstruido (commits `5ace99e`, `1d746d7`, `ebb617b`, `e6c2d3a`)

La sección "Organelle coverage" que salió de la Task 6 del plan (top-14
por protein_count, solo informativa, sin filtro, sin link a explorar)
**reemplazaba** — sin que el usuario lo hubiera pedido — a la sección
original "Browse by MLO" (`MloBadges.vue`, ya no usado): un grid de
cards con filtro de texto, ordenado por driver_count, con conteo de
proteínas y de drivers, y click a `/results?mlo=X`. El usuario pidió
mantener el formato tabla (más informativo, matriz de 5 fuentes) pero
recuperando el comportamiento completo del original:

- Filtro de texto (`filterMlosByQuery`, mismo util que ya usaba
  `MlosPage.vue`), ordenado por `driver_count` desc, tope de 20
  filas sin filtrar / 30 filtrando, con "N more match — view all".
- Columnas: ORGANELLE (link) | COMPARTMENT | 5 puntos de fuente |
  PROTEINS | DRIVERS.
- El nombre de la organela linkea a **`/results?mlo=X`** (browsear
  proteínas), no a `/mlo/:mlo` — error real detectado por el usuario:
  clickear "Stress granule" llevaba a la página nueva de detalle de MLO
  en vez de a resultados, que es lo que hacía el original. La columna
  "Explore →" que existía como link redundante a lo mismo se sacó; el
  nombre (coloreado `text-brand`, con `hover:underline`) cumple esa
  función solo.
- Sección movida: ahora va **antes** de "Model organisms"/"Source
  databases" (antes iba después, como "Organelle coverage").
- El párrafo introductorio ya no tiene `max-w-[64ch]` — antes quedaba a
  la mitad del ancho de la sección.

**Importante para quien retome esto**: `/mlo/:mlo` (la página nueva de
detalle de MLO, Tasks 13-14 del plan) sigue existiendo y sigue
funcionando — solo se sacó como destino de este link puntual del Home.
`ProteinMLOs.vue` (pestaña MLO Annotations de la página de proteína)
sigue linkeando a `/mlo/:mlo}` tal como lo hacía desde antes del
rediseño (confirmado contra el commit pre-rediseño, no es algo que este
trabajo haya introducido). El usuario decidió explícitamente **no**
revertir la página de detalle en sí — solo corregir este link.

### 9.4 Home — Model organisms / Source databases (commits `ebb617b`, `e6c2d3a`)

- Orden de columnas swapeado: **Model organisms a la izquierda**, Source
  databases a la derecha (antes era al revés).
- Organisms: top 10 (antes top 8). Fila compacta de una sola línea
  (nombre, barra, conteo) en vez de dos líneas — el usuario adjuntó una
  captura de referencia mostrando el formato compacto deseado.
- La barra usa `grid-cols-[170px_1fr_140px]` (columna fija para el
  conteo) en vez de `flex-1` compartiendo espacio con el texto del
  conteo — con flex, el ancho renderizado de la barra variaba según la
  cantidad de dígitos del número de esa fila (bug real detectado por el
  usuario, no cosmético: la barra vacía no terminaba en el mismo punto
  en todas las filas).
- Cada fila es ahora un `RouterLink` a `/results?organism=X`, usando el
  nombre **crudo** del organismo (`rawName`, antes de `formatOrganism()`)
  como valor del query param — mismo patrón que ya usa
  `FilterSidebar.vue` para este filtro (`value: name` sin formatear,
  `label: formatOrganism(name)` solo para mostrar).
- El subtítulo "top N of M species" se dejó tal cual a pedido explícito
  del usuario (se le preguntó si sacar "top" o cambiar "species" por
  "model organisms"; respondió dejarlo como está).
- "Browse by component role": ancho unificado a `max-w-[1080px] px-8`
  (antes `max-w-4xl px-6`, más angosto que el resto de las secciones).

### 9.5 Search Results — `ResultsPanel.vue` (commits `858a382`, `77c87a8`, `53e544f`)

- **Orden de columnas**: PROTEIN, ROLE, SOURCES, ARCHITECTURE, LENGTH,
  MLOS (antes PROTEIN, ARCHITECTURE, LENGTH, MLOS, SOURCES, ROLE) — rol
  y fuente se leen primero, antes del detalle de arquitectura/longitud.
- **Lista de MLOs**: sale de la columna PROTEIN (donde quedaba apretada
  y visualmente se mezclaba con ARCHITECTURE) y pasa a ser una
  sub-sección de ancho completo (`colspan` sobre las 6 columnas) debajo
  de cada fila. El texto es el mismo formato de siempre — nombres
  unidos con " · " — solo que ahora vive en esa sub-fila ancha en vez
  de adentro de PROTEIN; hubo un paso intermedio donde se probó un
  layout en grid (`grid-cols-[repeat(auto-fill,minmax(150px,1fr))]`,
  una MLO por celda) para alinear columnas, pero el usuario pidió
  volver al texto corrido con "·" — el grid no quedó.
- **Truncado**: se mantiene el comportamiento original — hasta 10 MLOs
  visibles, con un "+N more" clickeable que expande el resto
  (`expandedRows`/`visibleMlos`, mismo mecanismo que ya existía
  pre-rediseño). *Nota: hubo idas y vueltas acá — en un primer paso se
  sacó el truncado completamente (mostrar siempre todas las MLOs) a
  pedido del usuario, junto con la sub-fila; en un pedido posterior el
  usuario pidió revertir específicamente el truncado (volver a +N more)
  manteniendo el resto de los cambios de esa misma sub-fila (formato
  fila completa). Cada MLO individual **no** es clickeable para
  filtrar — se agregó esa interacción sin que se pidiera y se revirtió
  en el mismo ciclo (ver lección de §9.1: no agregar comportamiento no
  pedido, ni siquiera "restaurando" algo que existía en una versión
  anterior, sin confirmarlo primero).*
- **SOURCES**: nombres de fuente apilados uno por línea (solo las que
  anotan a esa proteína, orden canónico) en vez del patrón de 5 puntos
  encendido/apagado.
- **Hover unificado**: cada proteína (fila principal + sub-fila de MLOs)
  vive en su propio `<tbody class="group">`, con `group-hover:bg-page`
  en ambos `<tr>` en vez de `hover:bg-page` independiente por fila — al
  pasar el mouse por cualquiera de las dos partes se resaltan ambas como
  una sola sección clickeable (la división en dos `<tr>` es solo un
  recurso de layout, no dos filas reales del dato).

### 9.6 Patrón general de esta iteración

Todas las correcciones de esta sección salieron de que el usuario miró
la app real (`npm run dev`) y comparó contra lo que esperaba — no de
releer el spec. Dos categorías de error se repitieron y vale la pena
que quien siga desde acá las tenga presentes:

1. **Copy/comportamiento inventado sin preguntar** (§9.1, la mitad de
   §9.5): pasa cuando una decisión de la Task N del plan se redactó
   como "esto no es dato, es UX, lo cambio directamente" sin marcarlo
   como pregunta. La regla real es más estricta que como se aplicó: ante
   la duda, preguntar — no decidir y seguir.
2. **Reemplazar una sección funcional por una versión "más linda pero
   menos capaz"** (§9.3): la Task 6 original cambió "Browse by MLO"
   (con filtro y navegación) por "Organelle coverage" (solo lectura) sin
   que estuviera explícitamente aprobado que se perdiera esa
   funcionalidad — el plan lo documentó como una decisión de diseño
   propia, no como algo que el usuario hubiera pedido perder.
