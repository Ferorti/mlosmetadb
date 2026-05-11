# MLOsMetaDB Frontend — Dev Log

---

## Registro de Cambios (Conciso)

| Fecha | Cambio | Autor |
|-------|--------|-------|
| 2026-05-08 | Añadida sección 'Diálogo entre IA' a CLAUDE.md y este registro de cambios. | GEMINI |
| 2026-05-08 | Verificación de estadísticas (DB vs API vs stats.json): coincidencia confirmada. | GEMINI |
| 2026-05-08 | Investigada discrepancia de roles: Stats contaba anotaciones, Resultados cuenta proteínas únicas. | GEMINI |
| 2026-05-08 | Corregidas estadísticas en backend (main.py) y stats.json para usar COUNT(DISTINCT uniprot_id). | GEMINI |
| 2026-05-11 | Result row redesign: accent bar por rol, layout 3 columnas (Identity/Annotations/Stats), D3 track full-width. | CLAUDE |
| 2026-05-11 | Result rows: quitada accent bar y sombreado D3, columna 1 a 140px, Sources arriba de MLOs, ★ en UniProt, organismo truncado a 2 palabras. | CLAUDE |
| 2026-05-11 | Fix parseDomains: deduplicación por label+start+end en lugar de solo label — preserva copias múltiples del mismo dominio (e.g. 4× RRM en O60506). | CLAUDE |
| 2026-05-11 | parseDomains solo usa Pfam (excluye SMART). Columnas reordenadas: Identity | Features+Size | Sources+MLOs(flex). Badge rol inline junto al gene name. | CLAUDE |
| 2026-05-11 | Layout 2 columnas: Identity 200px (gene→acc→organismo→badge) + flex-1 (Features/Sources/MLOs en filas key-value). UniProt acc sin pill. | CLAUDE |
| 2026-05-11 | Row tweaks: badge alineado a la derecha del gene name, col1 a 170px, etiquetas key sin uppercase a text-[9px], UniProt sin ★ ni pill. | CLAUDE |
| 2026-05-11 | D3 track movido a columna 2 (después de MLOs), modo compact (20px, sin labels). Leyenda eliminada. SequenceFeatureViewer: prop compact + COMPACT constants. | CLAUDE |
| 2026-05-11 | Sort funcional (10 opciones asc/desc) con sort_by+sort_order en URL; download TSV paginado (lotes 200, MAX_PER_PAGE backend); fixes: disorder_mobidb_lite_dc (nombre correcto), role:asc=drivers first (dirección correcta). | CLAUDE |
| 2026-05-11 | implement ProteinPage — tabbed layout (Structure/MLOs/Interactions/Ortologs), ProteinHeader con source DB links, ProteinMLOs grouped table, ProteinFeatureTrack D3 viewer, SourceDbBadge, PPI summary stub, useProtein composable, LoadingSpinner, MolStarViewer stub | CLAUDE |
| 2026-05-11 | fixed ProteinPage — feature track IDR/LCD/domain parsing (source filtering, case-insensitive pfam, new array format), header restructure (gene·protein title, source DB links as clickable badges, RoleBadge), MLO deduplication, Orthologs spelling, tab renamed to Overview, external resources section | CLAUDE |
| 2026-05-11 | fixed ProteinPage round 2 — LCD vertical centering (centerY formula), IDR/LCD source filtering (table shows MobiDB-lite + AlphaFold-disorder IDRs, MobiDB-lite-sub LCDs only), Pfam capitalization, pLDDT source → AlphaFold2, expanded type names, column order swap (feature left, AlphaFold right w-80), InterPro link added | CLAUDE |

---

## Sesión 2026-05-07 — Corrections round 6 (11 tasks)

### Qué se hizo

- **`src/api/client.js`**: añadidos interceptores Axios para logging en consola:
  - Request: `%c→ METHOD /api/path` en azul + params.
  - Response OK: `%c← STATUS /path` en verde + `{ total: N }`.
  - Response error: `%c✗ STATUS /path` en rojo + message.
- **`ResultsPanel.vue`** — layout y estilo:
  - Body rows (líneas 2–5: gene/organism, MLOs, Source, Features) envueltas en `<div class="pl-4">` — la línea 1 (título + accession + badge) no tiene indentación.
  - Sequence track: `style="max-width: 65%; margin-left: -8px;"` — ligeramente menos indentado que el texto.
  - Divider en rows de resultados cambiado de `border-gray-100` → `border-gray-200` (también en skeleton y tabla).
  - Comentario en MLO row: `mlo values are raw slugs — formatMlo() is display only`.
- **`ResultsPage.vue`** — bug fix de búsqueda + mejoras:
  - Import cambiado de `searchAdvanced` → `searchBasic`.
  - Reemplazados `buildAdvancedParams` + `fetchResults` con nueva lógica: `field=all` → `GET /api/search`, `field=uniprot_id` → `GET /api/proteins?uniprot_id=`, `field=gene_name` → `GET /api/proteins?gene_name=`, sin `q` → `GET /api/proteins` con filtros.
  - Response shape manejada para `/search` (total_hits) y `/proteins` (total).
  - Sort por `source_db_count` descendente (client-side, default "relevance") — TODO server-side.
  - `buildExtraFilters()` sin `source_db` (eliminado Task 8).
  - `onSearch({ q, field })` — eliminados mode y role (SearchBox compact solo emite q + field).
- **`FilterSidebar.vue`** — múltiples cambios:
  - **Task 7**: Molecular Features reemplazado con checkboxes multi-select. `featureTypeOptions` con 5 opciones (IDR, LCD, domain, coiled_coil, MoRF). `activeFeatureTypes` computed lee `feature_type` como comma-separated. `toggleFeatureType()` añade/quita valores. Sin chip activo — checkboxes siempre visibles.
  - **Task 8**: Sección "Source database" eliminada completamente. `SOURCE_DBS`, `sourceDbOptions`, `open.source` eliminados.
  - **Task 9**: Organismo: quitado `italic` del span; `text-xs` → `text-[13px]` (Task 11). Botones "+ N more / ↑ Show less" reemplazados por `<input disabled>` con placeholder "Search other organisms..." + texto explicativo `formatCount(totalOrganisms - 9)`. `orgShowAll` eliminado. `displayedOrgs` siempre slice(0, 9). Importado `formatCount`.
- **`RoleCards.vue`** — Task 10: Tres cards rediseñadas:
  - Card 1: "LLPS Drivers", count de `by_role.driver`, descripción con evidencia experimental.
  - Card 2: "MLO Clients", count de `by_role.client`, descripción clientes.
  - Card 3: "MLO-associated proteins", count de `stats.proteins.total`, barra acento amber, navega a `/results` sin filtros.
  - `navigate('all')` → `/results`; drivers → `/results?role=driver`; clients → `/results?role=client`.
- **`HomePage.vue`** — Task 10: título de sección "Browse by LLPS role" → "Browse by component role".
- Build: `✓ 677 modules, 0 errores`.

### Decisiones técnicas

- **`searchBasic` para All Fields**: el endpoint `/search?q=&mode=` usa FTS5 — devuelve resultados relevantes para cualquier campo (gene_name, uniprot_id, protein_name, mlo_name). El workaround anterior (`searchAdvanced` con `gene_name=q`) solo buscaba por nombre de gen. Con FTS5 la búsqueda es genuinamente multi-field.
- **Response shape dual**: `/search` devuelve `{ items: [...], total_hits: N }` y `/proteins` devuelve `{ proteins: [...], total: N }`. El handler usa `?? res.data.items ?? res.data.results ?? []` y `?? res.data.total_hits ?? 0` para cubrir ambos.
- **Client-side sort por source_db_count**: sin soporte server-side aún. Siempre activo cuando sort='relevance' (default — `f.sort` no está en la URL). La ordenación es estable y no afecta la paginación server-side (solo reordena la página actual).
- **Checkboxes en lugar de click-to-apply para features**: UX más claro para multi-select. La feature_type se serializa como `IDR,LCD` en la URL. El API actualmente acepta un solo valor — TODO para array support.
- **`orgShowAll` eliminado**: el botón "+N more" no funcionaba bien (mostraba todos los ~950 organismos). El disabled input es más honesto — autocomplete real requiere API.
- **MLO raw slugs confirmados**: `protein.mlos` contiene slugs (e.g. `stress_granule`). `formatMlo()` solo para display. El comentario en template lo documenta explícitamente.



Registro acumulativo de decisiones, estado y pendientes.
Actualizar en cada sesión de trabajo.

---

## Sesión 2026-05-07 — D3 Sequence Feature Viewer

### Qué se hizo

- **`npm install d3`**: d3 v7.9.0 instalado. Bundle ResultsPage: 123 KB → 175 KB (esperado).
- **`src/utils/parseFeatures.js`** (nuevo): utilidades de parsing y stats:
  - `parseIdrRegions(idrJson)`: parsea `{ mobidb_lite: [[start,end],...] }` → `[{start,end}]`. Fallback a `alphafold`.
  - `parseLcdRegions(lcrJson)`: parsea `{ mobidb_lite: [{start,end,label},...] }` → array con `label ?? 'LCD'`.
  - `parseDomains(domainsJson)`: parsea `{Pfam:[{start,end,label,accession},...], SMART:[...]}`, aplana, deduplica por label.
  - `calcCoverage(regions, seqLen)`: máscara `Uint8Array` para porcentaje de cobertura sin solapamiento.
  - `buildFeatureStats({...})`: genera string "IDRs: 54% · LCD: 12% · 3 domains · 526 aa".
- **`src/components/results/SequenceFeatureViewer.vue`** (nuevo): visor SVG D3 compacto (34px height):
  - Props: `sequenceLength`, `idrRegions`, `lcdRegions`, `domains`, `llpsRegions`.
  - Capas en orden: baseline → IDR (rosa, h=24) → LCD (amber, h=18) → Domain (verde, h=18) → LLPS (azul, thin bar h=4).
  - Labels inline en regiones si el ancho renderizado es suficiente (minLabelWidth por tipo).
  - `ResizeObserver` para re-render responsive. `watch` para actualizar si cambian los datos.
  - Tooltip `position:fixed` con `clientX/clientY` (corrección: spec usaba `pageX/Y` que es incorrecto para `fixed`). Teleported a `body`.
- **`ResultsPanel.vue`** — cambios:
  - Imports: `SequenceFeatureViewer`, `parseIdrRegions`, `parseLcdRegions`, `parseDomains`, `buildFeatureStats`.
  - Computed `resultsWithFeatures`: pre-parsea feature data de todos los resultados, empareja con el objeto `protein`. La template itera `resultsWithFeatures` con destructuring `{ protein, idrRegions, lcdRegions, domains, featureStats, hasFeatures }`.
  - Eliminadas filas "Domains" (badges verdes) y "Features" (badges IDR/LCD + aa count).
  - Nueva fila "Features": label 80px + columna derecha con stats text + `<SequenceFeatureViewer>`.
  - Leyenda (Track: IDR / LCD / Domain) antes del primer resultado, solo en card view.
- Build: `✓ 677 modules, 0 errores`.

### Decisiones técnicas

- **`resultsWithFeatures` computed en lugar de computed por-proteína**: en la template, `v-for` itera el resultado computable directamente — el destructuring `{ protein, idrRegions, ... }` permite acceder a todo sin repetir `Map.get()` por cada prop. Más limpio que un `Map` separado.
- **`clientX/clientY` en tooltip**: el tooltip usa `position: fixed` (coordenadas de viewport). `pageX/pageY` son coordenadas de documento — incorrectas si la página está scrolleada. Corregido silenciosamente.
- **Capas D3 en orden**: IDR se dibuja primero (layer inferior) para que LCD y Domain queden encima. El rect transparente de hit-area se añade al final para cubrir todo el SVG sin interferir con la visual.
- **`minLabelWidth` por tipo**: IDR no recibe label (`null`). LCD y Domain solo muestran label si la región es suficientemente ancha para no colisionar.
- **Un tooltip por visor**: cada `SequenceFeatureViewer` teleporta su propio `div` tooltip al body. Con 20 resultados, hay 20 divs ocultos. Aceptable — todos son `display:none` hasta hover. Una alternativa sería un tooltip global singleton, pero eso requiere estado compartido.
- **Formato `idr_regions`**: `parseIdrRegions` espera `{ mobidb_lite: [[start,end],...] }` (arrays de 2 elementos). `parseLcdRegions` espera `{ mobidb_lite: [{start,end,label},...] }` (objetos). Estos formatos deben coincidir con lo que devuelve la API — verificar con datos reales.

---

## Sesión 2026-05-07 — Corrections round 5

### Qué se hizo

- **`FilterSidebar.vue`** — hide-on-active para 4 secciones (LLPS Role, Organelle, Organism, Source Database):
  - Chip activo: `v-if="filters.[key]"` → muestra solo el chip cuando el filtro está activo.
  - Opciones: envueltas en `<Transition name="fade"><div v-if="!filters.[key]">` → desaparecen completamente (no solo se atenúan) cuando el filtro está activo. Incluye search input y botón "+ N more".
  - Eliminado `:class="{ 'opacity-30 pointer-events-none': isFilterActive(...) }"` en esas 4 secciones.
  - Transición CSS `.fade-enter-active / .fade-leave-active` (0.15s) añadida al `<style scoped>`.
  - Chips actualizados: `gap-1.5`, `font-medium`, botón dismiss con `opacity-60 hover:opacity-100`.
  - Opciones cambiadas de `text-sm` a `text-xs` en las 4 secciones (Molecular features sin cambiar, no estaba en el spec).
- **`ResultsPanel.vue`** — nuevo layout de filas:
  - Proteína: `text-[15px]` → `text-[16px]`.
  - Líneas 3 y 4 (badges MLO + badges features) reemplazadas por 3 filas key-value:
    - **Organelles**: label "Organelles" en 80px, MLOs como texto plano separados por `·`, clicables, expandibles con "+N more".
    - **Domains**: label "Domains" en 80px, badges verdes (`bg-[#EAF3DE] text-[#27500A] border-[#C0DD97]`), deduplicados, máx 4.
    - **Features**: label "Features" en 80px, IDR rojo (`bg-[#FCEBEB] text-[#791F1F] border-[#F7C1C1]`), LCD amber (`bg-[#FAEEDA] text-[#633806] border-[#FAC775]`), longitud en aa. Usa `protein.has_idr` / `protein.has_lcd` (campos directos, pendiente de actualización en API).
  - Labels de 80px con `font-family: 'IBM Plex Sans'; font-weight: 500` via inline style.
- **`SearchBox.vue`** — nuevo prop `showSearchOptions` (boolean, default false):
  - `true` → muestra dos chips entre input y Search button: "Drivers only" y "Exact match".
  - Chips con estado toggle (dot blanco/gris, fondo azul/blanco).
  - "Drivers only" → agrega `role: 'driver'` al payload emitido.
  - "Exact match" → agrega `mode: 'exact'` al payload emitido.
  - Non-compact variant: `max-w-3xl mx-auto w-full` (antes `max-w-2xl mx-auto`).
- **`HomePage.vue`**: wrapper del search box cambiado a `max-w-3xl mx-auto w-full px-4`. SearchBox con `:show-search-options="true"`. `handleSearch` actualizado para manejar `{ q, field, role, mode }`.
- **`ResultsPage.vue`**: `onSearch` actualizado: `{ q, field, mode, role }` — pasa `mode` si no es fuzzy, pasa `role` si presente.
- Build: `✓ 109 modules, 0 errores`.

### Decisiones técnicas

- **`v-if` en lugar de `opacity-30`**: ocultar completamente es más claro UX. El usuario ve solo la selección activa; no hay opciones "fantasma" que confundan. La transición de 150ms suaviza el cambio.
- **`protein.has_idr` / `protein.has_lcd`**: los campos `idr_regions`/`lcr_regions` (JSON array) quedan en el script (`hasIdr()`, `hasLcd()`) pero no se usan en el template nuevo. Cuando la API exponga `has_idr`/`has_lcd` como booleanos en `ProteinSummary`, las Features row se mostrará. Por ahora no se muestra (field undefined → `v-if` false).
- **80px fixed-width labels**: los tres labels ("Organelles", "Domains", "Features") tienen width fijo para formar una columna izquierda consistente. `flex-shrink-0` evita que colapsen si el contenido de la derecha es amplio.
- **`showSearchOptions=false` en ResultsPage**: el search bar compacto del results page no muestra los chips — role y mode se aplican desde la sidebar. La SearchBox es stateless respecto a los chips de la results page.

---

## Sesión 2026-05-07 — Corrections round 4

### Qué se hizo

- **`ResultsPage.vue`**: contenido centrado con `max-w-6xl mx-auto`. Search bar mantiene fondo full-width (`bg-[#EBF3FB]`) pero el `<SearchBox>` está dentro de un inner div centrado. Sidebar + results también centrados en el mismo contenedor. Eliminado `style="height: calc(100vh - 56px)"`, reemplazado por `min-h-0` (sin altura fija — scroll natural del documento).
- **`src/config.js`**: `type` cambiado de `'info'` a `'warning'`.
- **`AnnouncementBanner.vue`**: eliminado el condicional de tipo — siempre amber (`bg-[#FAEEDA]`, `border-[#EF9F27]`, `text-[#633806]`). Icono `ti ti-alert-triangle`, botón dismiss `ti ti-x`. No hay branching por `BANNER.type` en el componente.
- **`SearchBox.vue`**: eliminado chip "Drivers only" por completo. Eliminados: prop `initialDriversOnly`, ref `driversOnly`, watch correspondiente, botón del chip, lógica `role=driver` en `handleSearch`. `emit('search')` ahora emite solo `{ q, field }`.
- **`ResultsPage.vue`** `onSearch`: eliminado `driversOnly` del destructuring y la línea `if (driversOnly) query.role = 'driver'`. Eliminado `:initial-drivers-only` del `<SearchBox>`.
- **`FilterSidebar.vue`**: clase `filter-sidebar` en el `<aside>` raíz. Scoped style aplica `font-family: 'IBM Plex Sans', sans-serif` al sidebar. Headers de sección con `font-weight: 500` via `:deep(.text-xs.font-semibold)`.
- **`index.html`**: añadidos preconnect + Google Fonts (IBM Plex Sans 400/500). Añadido Tabler Icons webfont CDN (`@tabler/icons-webfont@latest` via jsDelivr). Título cambiado de "Vite App" a "MLOsMetaDB".
- Build: `✓ 109 modules, 0 errores`.

### Decisiones técnicas

- **Tabler Icons CDN en index.html**: el componente `AnnouncementBanner` usa `<i class="ti ti-...">` que requiere el webfont. Se añade junto con IBM Plex Sans como link en `<head>`. Alternativa sería importar el paquete npm, pero la versión Node 16 del entorno hace que el CDN sea más directo.
- **`min-h-0` vs altura fija en ResultsPage**: el `height: calc(100vh - 56px)` anterior causaba un layout de "panel fijo" donde la página no hacía scroll. Con `min-h-0` el contenido crece naturalmente y el scroll es el del documento. Más consistente con la página de inicio.
- **`:deep(.text-xs.font-semibold)` para headers**: los section headers de la sidebar ya tienen `text-xs font-semibold` de Tailwind. Con `:deep()` no hace falta modificar cada elemento — la regla CSS apunta a todos los headers ya marcados. Si cambia la estructura, la regla deja de aplicar (no rompe nada).
- **Rol vía sidebar exclusivamente**: el chip "Drivers only" era redundante con el filtro LLPS Role de la sidebar (que ya tiene Driver, Client, Unknown). Eliminarlo simplifica el componente y la experiencia de usuario.

---

## Estado actual

| Ítem | Estado |
|------|--------|
| Scaffold Vue 3 + dependencias | ✅ |
| Configuración Tailwind / Vite | ✅ |
| Capa API (`src/api/`) | ✅ stub stats, ✅ resto listo |
| `src/utils/format.js` | ✅ |
| Router (`src/router/index.js`) | ✅ |
| `AppNavbar` | ✅ |
| `AppFooter` | ✅ |
| `StatBar` | ✅ |
| `RoleCards` | ✅ |
| `MloBadges` | ✅ datos desde `src/data/mlos.js` |
| `OrganismGrid` | ✅ datos placeholder |
| `HomePage.vue` | ✅ completo, usa `SearchBox` |
| `ResultsPage.vue` | ✅ completo — search + filters + results |
| `ProteinPage.vue` | ⬜ placeholder |
| `MlosPage.vue` | ⬜ placeholder |
| `DownloadPage.vue` | ⬜ placeholder |
| `AboutPage.vue` | ⬜ placeholder |
| `SearchBox.vue` | ✅ componente reutilizable |
| `FilterSidebar.vue` | ✅ click-to-apply, chips activos, facets-ready |
| `ResultsPanel.vue` | ✅ cards + tabla TanStack (rows refinados AlphaFold-style) |
| `RoleBadge.vue` | ✅ |
| `AnnouncementBanner.vue` | ✅ info/warning, dismissable |
| `src/config.js` | ✅ `BANNER` config |
| `src/data/mlos.js` | ✅ constante compartida |
| Stores Pinia | ⬜ |
| Composables | ⬜ |

---

## Sesión 2026-05-07 — ResultsPage: AlphaFold-style row refinement + sidebar click-to-apply

### Qué se hizo

- **`src/config.js`** (nuevo): exporta `BANNER = { enabled, type, message }`. Controla el banner global; `enabled: false` lo oculta sin tocar componentes.
- **`AnnouncementBanner.vue`** (`src/components/layout/`): banner informativo/warning en la parte superior de la app. Lee `BANNER` de `config.js`. Dismissable con ×. Inserido en `App.vue` encima de `AppNavbar`.
- **`FilterSidebar.vue`** — reescritura completa del modelo de interacción:
  - Eliminado estado local pendiente (`local`) y botones Apply/Clear.
  - Cada opción es un texto clicable que aplica el filtro inmediatamente (`applyFilter` emite `update:filters`).
  - Cuando un filtro de sección está activo, aparece un chip con × dentro de esa sección; las otras opciones se deshabilitan (`opacity-30 pointer-events-none`).
  - `removeFilter(key)` limpia ese key del objeto filters y hace page=1.
  - "Reset filters" en el header del sidebar, visible solo cuando `hasActiveFilters`.
  - **Facets-ready**: `mloOptions`, `organismOptions`, `sourceDbOptions` son computeds que usan `props.facets` si está disponible; si no, usan los datos estáticos (placeholder). Incluye TODO comment explicando qué endpoint falta.
  - Sección Molecular features: `feature_type` usa click-to-apply; `feature_accession` (Pfam) usa input local con botón "Go" + Enter. Ambos muestran chip activo con ×.
  - Emite `reset-filters` (nuevo evento) manejado en `ResultsPage`.
- **`ResultsPanel.vue`** — rows rediseñados al estilo AlphaFold DB:
  - `py-4` (antes `py-3`), sin `-mx-2 px-2 rounded` (sin card borders), `border-b border-gray-100` siempre (con `last:border-b-0`).
  - **Línea 1**: nombre de proteína `text-[15px] font-medium text-[#185FA5]` + badges de rol a la derecha.
  - **Línea 2**: UniProt acc en `font-mono text-xs text-gray-500` · gene name · organism en italic · ★ amber solo si `protein.reviewed === true` (strict equality, no se muestra si es null/undefined).
  - **Línea 3**: badges MLO, máximo 5 visibles + botón "+N more" que expande inline. Clic en badge aplica filtro `?mlo=` via router. Expansión tracked en `reactive(new Set())` — las mutaciones de Set son reactivas en Vue 3.
  - **Línea 4**: badge IDR (azul) si `idr_regions` no vacío, badge LCD (verde) si `lcr_regions` no vacío, badges de dominio (gris, deduplicados, máx 4 + "+N more"), longitud en `text-gray-400`.
  - Funciones nuevas: `visibleMlos`, `hasIdr`, `hasLcd`, `uniqueDomains`, `domainExtra`, `applyFilter`.
  - Importa `useRoute` para construir el query push en `applyFilter`.
- **`ResultsPage.vue`**: añadida función `onResetFilters` (preserva `q` y `field`, borra todo lo demás); conectado `@reset-filters` en `<FilterSidebar>`.
- Build: `✓ 108 modules, 0 errores`.

### Decisiones técnicas

- **`reactive(new Set())` para expandedRows**: `ref(new Set())` no trackea mutaciones (`.add()` no dispara reactividad porque la referencia del Set no cambia). `reactive()` sobre un Set sí intercepta mutaciones nativas en Vue 3. No hace falta crear un Set nuevo en cada expansión.
- **Strict `=== true` para `reviewed`**: el campo puede ser `true`, `null` o ausente. `v-if="protein.reviewed"` mostraría la estrella si fuera `1` o cualquier truthy; `=== true` garantiza solo Swiss-Prot entries confirmadas. Igual patrón para `has_driver`/`has_client`.
- **`applyFilter` en ResultsPanel vía router, no emit**: el panel está tres niveles abajo de la lógica de URL. Pasar callbacks hacia arriba requeriría props adicionales. Usar el router directamente (`router.push({ query: { ...route.query, [key]: value } })`) es más simple y consistente con cómo ResultsPage maneja todos los cambios de filtro.
- **Sidebar sin estado local**: el patrón click-to-apply elimina la desincronización entre lo que el usuario ve y lo que está activo en la URL. La URL sigue siendo la única fuente de verdad — cada click hace un `router.push` a través del emit chain.
- **Facets-ready pero sin API todavía**: los computeds ya tienen la lógica de switcheo `facets ?? fallback`. Cuando el endpoint `/search/facets` exista, solo hay que pasar `facets` como prop desde `ResultsPage` (ya lo recibe como `null`).

---

## Sesión 2026-05-07 — ResultsPage: search + filters + results

### Qué se hizo

- **`src/data/mlos.js`**: extraída la constante `PLACEHOLDER_MLOS` de `HomePage.vue` a un módulo compartido. Importado en `MloBadges.vue`, `FilterSidebar.vue` y `HomePage.vue`.
- **`SearchBox.vue`** (`src/components/search/`): componente reutilizable que encapsula el search bar. Props: `initialQuery`, `initialField`, `initialDriversOnly`, `compact`. Emite `search` con `{ q, field, driversOnly }`. `compact=true` → sin padding extra (usado en `ResultsPage`), `compact=false` → centrado con `max-w-2xl` (usado en `HomePage`). `HomePage` migrado para usarlo.
- **`FilterSidebar.vue`** (`src/components/search/`): sidebar de 220px con 5 secciones colapsables (LLPS role, Organelle, Organism, Source database, Molecular features). Estado local pendiente, se aplica con botón "Apply". "Clear all" mantiene el `q` y limpia el resto. Molecular features colapsado por defecto. Slider de disorder content marcado como "Coming soon" (deshabilitado). Secciones de organelas y organismos tienen search input + "show more".
- **`RoleBadge.vue`** (`src/components/ui/`): pill badge para driver/client/unknown con colores semánticos.
- **`ResultsPanel.vue`** (`src/components/results/`): panel principal. Toggle Cards/Table. Skeleton de 5 filas durante carga. Empty state para "sin filtros" y "sin resultados". Rows con `border-b` divisor (estilo AlphaFold DB, sin card borders). Cada fila muestra: nombre + UniProt ID, gene + organismo, badges MLO (máx 4 + "+N more"), features (IDR%, dominios, length). Tabla con TanStack Table v8, columnas sortables client-side. Paginación con ellipsis. Active filter chips con botón × por chip.
- **`ResultsPage.vue`**: lógica de routing por tipo de búsqueda: `q`+`field=all` → `/search/advanced?gene_name=q`, `q`+`field=gene_name|uniprot_id` → `/search/advanced?gene_name/uniprot_id=q`, sin `q` → `/proteins?...`. URL es la única fuente de verdad para todos los filtros.
- **Corrección proxy Vite**: añadido `rewrite: path => path.replace(/^\/api/, '')` al proxy config — sin esto, Vite reenviaba `/api/search/advanced` como `/api/search/advanced` a FastAPI (que tiene rutas sin prefijo `/api`), resultando en 404.
- **Extensión API `ProteinSummary`**: añadido campo `sequence_length: int | None = None`. Todos los campos nullable ahora tienen `= None` como default (compatibilidad Pydantic v2). `get_proteins_page` incluye `p.length AS sequence_length`. `advanced_search` reescrito para usar CTE + `LEFT JOIN protein_summary` (igual que `get_proteins_page`) — ahora devuelve mlos, domains, idr_regions, disorder_dc y sequence_length en lugar del GROUP_CONCAT anterior. Router `search.py` construye `ProteinSummary` completo con `_parse_json`/`_parse_mlos`.
- Build: `✓ 106 modules, 0 errores`.

### Decisiones técnicas

- **URL como única fuente de verdad**: todos los filtros viven en `route.query`. `watch(() => route.query, fetchResults)` dispara el fetch en cada cambio. No se usa Pinia para esto — el router es suficiente y permite compartir/bookmarkear URLs directamente.
- **`/search/advanced` en lugar de `/search` para texto libre**: `/search?q=` devuelve `SearchProteinHit` (sin `mlos`, sin `domains`) — insuficiente para mostrar las filas completas. Se redirige todo texto a `/search/advanced?gene_name=q` para obtener `ProteinSummary` completo. Limitación: solo busca por gene_name (no multi-field). Pendiente: endpoint de búsqueda full-text que retorne `ProteinSummary`.
- **`has_driver`/`has_client` ausentes en `ProteinSummary`**: los badges de rol usan `=== true` (strict equality) — `undefined` no activa el badge. Pendiente: añadir campos de rol a `ProteinSummary` o a `protein_summary` table.
- **`idrPercent` y `topDomains` como funciones en `ResultsPanel`**: el API devuelve `disorder_mobidb_lite_dc` (0–1 float) y `domains: {Pfam: [{label, accession, ...}]}`. Las funciones convierten a `%` y extraen etiquetas únicas. No se almacenan como campos derivados para evitar computación innecesaria.
- **TanStack Table: sort client-side únicamente**: la tabla ordena los datos de la página actual (ya cargados). Sort server-side requeriría pasar `sort` como query param a la API — marcado como TODO.
- **`FilterSidebar` con estado local + botón Apply**: filtros no se aplican inmediatamente al hacer click — se acumulan en `local` y se emiten al hacer "Apply". Evita N fetches por cada checkbox clicado. El padre (`ResultsPage`) hace el `router.push` al recibir `update:filters`.

---

## Sesión 2026-05-05 — UI corrections round 2

### Qué se hizo

- **"Drivers only" chip**: movido desde debajo del search box a dentro del input row, entre el `<input>` y el `<button>` de Search. El chip usa `self-center mx-2` para alinearse verticalmente en el flex row. El `border-l border-r border-gray-200` solo se aplica cuando el chip está en su estado base (se reemplaza por `border border-[#185FA5]` al activarse). El tooltip `title="Restrict search..."` reemplaza el label textual externo. El `<div class="flex items-center gap-2 mt-3 justify-center">` del toggle externo fue eliminado completamente.
- **MloBadges.vue**: reemplazado `flex flex-wrap` por CSS grid con `grid-template-columns: repeat(auto-fill, minmax(148px, 1fr))`. Cada card usa `flex flex-col justify-between min-h-[90px]` — el contenido superior (category + nombre) y el inferior (counts) siempre se distribuyen verticalmente. Condición `driver_count != null` (antes era truthy) para mostrar 0 drivers si corresponde. El skeleton también usa el mismo grid.
- **OrganismGrid.vue**: reemplazados todos los emojis con `<img>` apuntando a `/src/assets/organisms/${org.key}.svg`. CSS filter aplicado inline: `invert(20%) sepia(80%) saturate(600%) hue-rotate(195deg) brightness(80%)`. Datos pasados de `props.stats` (API) a `PLACEHOLDER_ORGANISMS` hardcodeado (igual que MloBadges) — incluyendo `driver_count`. Cada item ahora muestra protein count y driver count debajo del nombre.
- **SVG silhouettes**: creados 9 archivos en `src/assets/organisms/`. `homo_sapiens.svg` copiado desde `src/assets/` (potrace silhouette real). Los otros 8 son silhouettes SVG construidas con paths geométricos — reconocibles pero placeholder; ver TODO en el componente.
- Build: `✓ 45 modules, 0 errores`, 14.14s.

### Decisiones técnicas

- **Chip dentro del flex row**: el chip está entre `<input>` y `<button>`. El `border-l border-r border-gray-200` en el estado inactivo crea una separación visual suave desde el input y el botón, sin agregar elementos `<div>` divisores extra. El `self-center` es necesario porque el flex row tiene `items-stretch`.
- **`driver_count != null` en lugar de `v-if="mlo.driver_count"`**: el operador truthy fallaría si `driver_count = 0`, que es un valor válido. Se cambió a comparación estricta.
- **OrganismGrid ahora usa datos placeholder**: desacoplado de `props.stats` porque el endpoint real no existe aún. Cuando `GET /organisms` esté disponible, reemplazar `PLACEHOLDER_ORGANISMS` con llamada a API y reconectar `props.stats`.
- **CSS filter para colorear SVGs**: las SVGs son negras (`fill="#000"`), el filter las convierte a azul navy (~`#1B3D6F`). Aplicado como `style` inline (no clase Tailwind) por ser un valor complejo que Tailwind arbitrary no maneja bien.
- **`/src/assets/...` paths en dev**: Vite sirve el directorio `src/` como assets en modo dev. En build, los assets se copian a `/assets/`. Para producción correcta habría que importar los SVGs como módulos o usar `new URL(...)`. Agregar como pendiente.

---

## Sesión 2026-05-05 — Architecture fix + corrections pass

### Qué se hizo

- **App.vue**: ahora incluye `AppNavbar` + `AppFooter` + `<main class="flex-1"><RouterView/></main>`. El navbar y footer son globales — se ven en todas las páginas.
- **HomePage.vue**: eliminados `AppNavbar` y `AppFooter` (ya están en App.vue). Eliminado el wrapper `min-h-screen flex flex-col` (ahora está en App.vue). Renombrado `search()` → `handleSearch()`. Agregado `driversOnly = ref(false)` y lógica para añadir `role=driver` al query si está activo.
- **AppNavbar.vue**: rediseñado con gradiente `bg-gradient-to-r from-[#1B4F8A] to-[#2B7CD8]`, alto `h-14`, contenedor centrado `max-w-5xl`, dots con nuevos tamaños (w-3/w-4/w-2.5) y colores (`#7EC8F0`, `#5BBF8E`, `#A8D4F5`). Nav links como RouterLink (incluido API → `/about` como placeholder). `active-class="text-white font-medium"` (sin `!` — ya no hay conflicto con la clase base).
- **Hero**: ahora incluye el search box y el toggle "Drivers only" dentro del mismo bloque `bg-gradient-to-b from-slate-100 to-white`. Logo dots más grandes (16/22/14px). StatBar queda justo debajo del hero, sin gap.
- **MloBadges.vue**: rediseñado como tarjetas `inline-flex flex-col` con dot de categoría + label, nombre del MLO, protein count y driver count. Sin secciones por compartimento — todo en un único `flex-wrap`. Eliminado el `grouped` computed, agregados `categoryColor()` y `compartmentLabel()`. Renombrado `navigate()` → `browseMlo()`.
- **PLACEHOLDER_MLOS**: actualizado con `driver_count` en cada entrada (`null` para in_vitro_droplet).
- **Placeholder pages**: todas las páginas excepto HomePage muestran su nombre centrado con `py-32 text-2xl text-gray-400`.
- Build: `✓ 45 modules, 0 errores`, 14.2s.

### Decisiones técnicas

- **Navbar en App.vue**: arquitectura correcta para un SPA — el navbar global no debe estar acoplado a ninguna página individual.
- **`active-class` sin `!`**: en la versión anterior usaba `!text-white` para forzar override. Ahora que la clase base del link es `text-blue-100` (no `text-white`), `active-class="text-white font-medium"` funciona sin forzar. Tailwind no usa specificity de CSS — si hay clases en conflicto, la última en el CSS gana. En la práctica, `active-class` añade clases extras que tienen la misma o mayor especificidad.
- **Drivers only toggle fuera del card del search box**: está en el hero block pero fuera del `bg-white` card, con `mt-3`. Esto hace que el chip sea visualmente más aéreo y no apriete el search input.
- **`driver_count: null` para in_vitro**: la plantilla usa `v-if="mlo.driver_count"` por lo que `null` simplemente no renderiza el span de drivers.

---

## Sesión 2026-05-04 — Visual refinement pass (styling only)

### Qué se hizo

- **AppNavbar**: fondo `#1B3D6F` (navy oscuro, como v1), texto blanco, links `text-blue-100 hover:text-white`, dots con colores específicos (`#4A9EDB`, `#5BBF8E`, `#3B7DD8`), sin borde inferior.
- **AppFooter**: fondo `#1B3D6F` (mismo que navbar — encuadra la página), texto `text-blue-100`, links `text-blue-300 hover:text-white`, grid de 3 columnas con `gap-8`.
- **StatBar**: fondo `#EBF3FB` (azul muy claro), borde `#C8DFF2`, números `text-[#1B3D6F]` bold, labels uppercase tracking-wide en `#4A7BA7`, skeletons usan `bg-[#C8DFF2]`.
- **RoleCards**: cards con barra de acento de 3px en el tope (driver=brand-blue, client=brand-green, unknown=gray-300), fondo blanco, borde gris uniforme, `overflow-hidden` para clip del acento, unknown tiene `opacity-80`. Sin colores en el borde del card. Skeleton también tiene barra de acento en gris.
- **MloBadges**: badges más pequeños (`text-xs`), borde gris claro con hover azul (`#2B7CD8`), conteo en `text-[10px]`, compartimento label con `tracking-widest`, grupos con `py-2` separación.
- **OrganismGrid**: sin borde en cada item (solo hover bg `slate-50`), count en `text-[10px]`, links en `#2B6CB0`.
- **HomePage**:
  - Hero: `bg-slate-50` full-width, logo dots encima del título (14/18/12px), título en `text-[#1B3D6F]` (no black), subtítulo en `text-sm text-gray-500`.
  - Search box: card con `border border-gray-200 rounded-lg shadow-sm overflow-hidden`, select con `border-r`, button `bg-[#1B3D6F]`, sin gap entre elementos (flush).
  - Section headings: `text-[#1B3D6F]` con `border-l-[3px] border-[#2B7CD8] pl-3`.
  - Dividers: `<div class="border-t border-gray-100 mx-6 my-8">` (reemplaza `<hr>`).
  - Advanced search link: `text-[#2B6CB0] font-medium`.
- Build: `✓ 45 modules, 0 errores`, 14.6s.

### Decisiones técnicas

- **Accent bar en RoleCards**: implementado como `<div class="h-[3px] -mx-5 -mt-5 mb-4 ...">` con `overflow-hidden` en el card. Los márgenes negativos compensan el `p-5` del card. El color se resuelve en template con ternario sobre `card.role` — sin modificar la lógica del `computed`.
- **Colores hex directos vs tokens**: se usan tokens Tailwind (`brand-blue`, `brand-green`) donde corresponde; arbitrarios (`bg-[#1B3D6F]`, etc.) para los colores nuevos del refinamiento que no están en el config. Considerar agregar `navy: '#1B3D6F'` al config si se usan en muchos componentes.
- **`active-class` en RouterLink**: agregado `active-class="!text-white font-medium"` a los links del navbar. El `!` fuerza override sobre `text-blue-100`.
- **Search box sin gap**: estructura `flex items-stretch` con `overflow-hidden` en el wrapper — el select, input y button son hijos directos, el overflow-hidden del wrapper recorta las esquinas.

---

## Sesión 2025-08-01 — Scaffold + landing page

### Qué se hizo

- Scaffoldeado con `create-vue@3.6.4` (no la última — Node 16 no tiene `styleText` en `node:util`; la versión 3.6.4 es la última compatible con Node 16).
- Instaladas dependencias: `axios`, `@tanstack/vue-table`, `tailwindcss@3`, `postcss`, `autoprefixer`.
- `vite.config.js`: build output → `../api/static/`, proxy `/api` → `localhost:8000`.
- `tailwind.config.js`: colores brand configurados.
- `src/assets/main.css`: solo directivas Tailwind (reemplazado el CSS del scaffold).
- `src/data/stats.json`: copiado desde la raíz del repo.
- `src/api/stats.js`: stub que devuelve el JSON local; pendiente reemplazar con `client.get('/stats')` cuando la API esté lista.
- `src/router/index.js`: 7 rutas, `createWebHistory()`.
- `HomePage.vue` ensamblada con todos los componentes; stats se cargan en `onMounted`.
- `MloBadges`: usa datos placeholder hardcodeados (ver constante `PLACEHOLDER_MLOS` en el componente). Cuando `GET /mlos` esté disponible, reemplazar con llamada a `getMlos()`.
- `OrganismGrid`: datos vienen de `stats.proteins.by_organism`. Iconos son emoji temporales.
- Build: `✓ 45 modules, 0 errores`, output en `api/static/`.

### Decisiones técnicas

- **Node 16**: el entorno tiene Node 16.20.2. `create-vue@latest` requiere Node ≥ 18. Solución: pin a `create-vue@3.6.4`.
- **`postcss.config.js` CommonJS**: generado por `npx tailwindcss init -p` con `module.exports`. No hay `"type": "module"` en `package.json`, así que es correcto.
- **`RouterLink` sin import en componentes**: en Vue 3, `RouterLink` y `RouterView` se registran globalmente con `app.use(router)`. No hace falta importarlos en cada componente.
- **`stats.js` stub**: en lugar de mockear axios, el stub importa directamente el JSON local. Al migrar a la API real, solo hay que cambiar `stats.js` — los componentes no cambian.
- **Datos placeholder en `MloBadges`**: `GET /mlos` aún no existe. Constante `PLACEHOLDER_MLOS` vive en el componente, no en un store, porque es temporal.

---

## Pendientes y próximos pasos

### Alta prioridad
- [ ] `ProteinPage.vue`: header, anotaciones MLO, features (IDR viewer, dominios), PPIs.
- [ ] API: añadir `has_driver`/`has_client` a `ProteinSummary` — actualmente los role badges no se muestran en la lista de resultados.
- [ ] API: endpoint de búsqueda full-text (`/search`) que retorne `ProteinSummary` completo (con mlos, domains) para poder usar búsqueda multi-field real en lugar del workaround `gene_name LIKE`.

### Media prioridad
- [ ] `MlosPage.vue`: lista/grid de todos los MLOs agrupados por compartimento.
- [ ] API: `GET /search/facets` — mismos params que `/search/advanced`, devuelve `{ by_role, by_mlo, by_organism, by_source_db }` con conteos. Sidebar ya está preparado para recibirlos via prop `facets`.
- [ ] `ResultsPanel`: sort server-side (pasar `sort` como query param a la API).
- [ ] `ResultsPanel`: botón Download funcional.
- [ ] Reemplazar `MloBadges` placeholder con llamada real a `getMlos()`.
- [ ] `DownloadPage.vue`, `AboutPage.vue`.

### Baja prioridad / futuro
- [ ] Stores Pinia: `search.js`, `protein.js`, `mlo.js`.
- [ ] Composables: `useSearch.js`, `useProtein.js`, `useMlos.js`.
- [ ] Viewers: `MolStarViewer.vue`, `FeatureViewer.vue`, `ProSeqViewer.vue`.
- [ ] SVG organism icons: producción requiere importar como módulos o usar `import.meta.glob`. Los `/src/assets/...` paths solo funcionan en dev.
- [ ] Reemplazar SVG placeholders de organismos con silhouettes reales de Phylopic.
- [ ] `ui/MloBadge.vue`, `ui/LoadingSpinner.vue`.
- [ ] Integrar SPA fallback en `api/main.py` (ver `CLAUDE.md` sección FastAPI integration).

---

## Estructura de archivos (generada)

```
frontend/
├── src/
│   ├── api/
│   │   ├── client.js               ✅ axios, baseURL: /api
│   │   ├── stats.js                ✅ stub → JSON local
│   │   ├── mlos.js                 ✅
│   │   ├── search.js               ✅ searchBasic, searchAdvanced
│   │   └── proteins.js             ✅ getProteins, getProtein
│   ├── config.js                   ✅ BANNER config
│   ├── components/
│   │   ├── layout/
│   │   │   ├── AppNavbar.vue       ✅
│   │   │   ├── AppFooter.vue       ✅
│   │   │   └── AnnouncementBanner.vue ✅ info/warning, dismissable
│   │   ├── browse/
│   │   │   ├── RoleCards.vue       ✅
│   │   │   ├── MloBadges.vue       ✅ usa PLACEHOLDER_MLOS de data/mlos.js
│   │   │   └── OrganismGrid.vue    ✅
│   │   ├── search/
│   │   │   ├── SearchBox.vue       ✅ reutilizable, prop compact
│   │   │   └── FilterSidebar.vue   ✅ click-to-apply, chips, facets-ready
│   │   ├── results/
│   │   │   └── ResultsPanel.vue    ✅ cards/tabla, AlphaFold-style rows
│   │   └── ui/
│   │       ├── StatBar.vue         ✅
│   │       └── RoleBadge.vue       ✅
│   ├── data/
│   │   ├── stats.json              ✅
│   │   └── mlos.js                 ✅ PLACEHOLDER_MLOS compartido
│   ├── pages/
│   │   ├── HomePage.vue            ✅ usa SearchBox
│   │   ├── ResultsPage.vue         ✅ search + filters + results
│   │   ├── ProteinPage.vue         ⬜ placeholder
│   │   ├── MlosPage.vue            ⬜ placeholder
│   │   ├── DownloadPage.vue        ⬜ placeholder
│   │   └── AboutPage.vue           ⬜ placeholder
│   ├── router/
│   │   └── index.js                ✅
│   ├── utils/
│   │   └── format.js               ✅ formatMlo, formatCount, formatPmids
│   ├── assets/
│   │   └── main.css                ✅ solo Tailwind directives
│   ├── App.vue                     ✅
│   └── main.js                     ✅
├── index.html
├── vite.config.js                  ✅ proxy con rewrite /api → ''
├── tailwind.config.js              ✅
├── postcss.config.js               ✅
└── CLAUDE.md                       (referencia de diseño — no modificar)
```

---

## Notas de entorno

- **Node**: 16.20.2 — no actualizar sin verificar compatibilidad con el resto del proyecto.
- **npm**: 8.19.4
- **Vite**: 4.5.x (latest compatible con Node 16 + Vue 3.3)
- **Tailwind**: 3.x (v4 requiere cambios de configuración y aún no es estable para Vue)
- `npm run dev` → puerto 5173
- `npm run build` → `../api/static/` (usado por FastAPI para servir el SPA)
- El proxy de dev redirige `/api/*` a `localhost:8765` con `rewrite` que elimina el prefijo `/api` antes de llegar a FastAPI (las rutas FastAPI no tienen prefijo `/api`). El backend FastAPI debe estar corriendo en el puerto 8765.

---

## Convenciones recordatorio

- Siempre `<script setup>` — nunca Options API.
- Colores de rol: driver → `brand-blue`, client → `brand-green`, unknown → gray.
- `formatMlo()` para mostrar nombres de MLOs, `formatCount()` para números, `null` → `—`.
- UniProt IDs en `font-mono`, nombres de organismos en `italic`.
- No inline styles. No Bootstrap/Vuetify. Solo Tailwind.
- Datos: nunca fetchear en componentes directamente — siempre via `src/api/`.
