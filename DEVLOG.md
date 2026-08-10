# DEVLOG.md

## 2026-08-04 — refactor iniciado

Refactor iniciado desde la branch `audit/full-repo-review`, con
`refactor/` como futura raíz limpia del proyecto. Empezando por la capa de
datos (`database/` + `scripts/` + `parsers/`); `api/` y `frontend/` quedan
para una fase posterior.

Ver [REFACTOR_LOG.md](REFACTOR_LOG.md) para el detalle paso a paso de qué se
copió, qué se dejó afuera, y por qué.

## 2026-08-10 — libro de hallazgos para el intercambio con Claude Science

El intercambio con la auditoría biológica externa llevaba dos rondas
(`docs/review/devolucion/`, `docs/review/ultima/`) y el estado de cada
hallazgo vivía en prosa, repartido entre `mlo_mapping_decisions.md` §11.6 y
§12.5. Para saber qué seguía pendiente había que leer las dos secciones y
cruzarlas contra cuatro CSVs de la auditoría, y nada obligaba a que una
verificación quedara registrada: las tres cifras que la auditoría mandó mal
(el solapamiento sináptico, un PMID que ninguna fila de CD-CODE lleva, los
reguladores de `p_body`/`stress_granule`) se detectaron a mano y la evidencia
de esa verificación quedó solo en la conversación. Además, la auditoría mide
sobre una copia local: en la ronda 1 midió 54.786 filas cuando la base viva
tenía 35.971, porque nada en el paquete que le mandamos declaraba de qué
commit partía.

Cuatro piezas, sin tocar el pipeline, la DB, la API ni el frontend:

- **`docs/review/findings.csv`** — el libro: una fila por ítem que requiere o
  recibió una decisión nuestra, con `id` estable (`R<ronda>-<clase>-<clave>`),
  `estado` de un conjunto cerrado, y `verificado_como`/`decision`/
  `aplicado_en` obligatorios según el estado. Referencia los CSVs de la
  auditoría en vez de duplicarlos.
- **`_meta` en `tests/dataset_baseline.json`** — el commit y la fecha con que
  se generó la huella, para que la próxima devolución declare contra qué
  versión midió antes de que se le crea una sola cifra absoluta.
- **`scripts/review_ledger.py --check`** — valida el libro y reporta qué
  sigue abierto, que es lo que va en el próximo paquete a Claude Science.
- **`tests/test_review_ledger.py`** — hace no-opcional la regla central: nada
  llega a `aplicado` sin `verificado_como`.

La carga de las rondas 1 y 2 (57 filas) hizo su propia reconciliación contra
la prosa y encontró un problema en el propio diseño: §11.6 describe "esta
revisión" (v5), así que sus viñetas eran ciertas cuando se escribieron
incluso para los ítems que v6 fue y resolvió (`evidence_type`, los casos
"review"). Reescribirlas habría borrado esa historia, así que cada viñeta que
una ronda posterior tocó quedó con una nota que apunta hacia adelante en vez
de reescribirse, y las que siguen intactas recibieron su cita de `id` del
libro.

La revisión de rama completa que siguió encontró un problema más serio: la
carga había asumido que `action_matrix.csv` subsumía a las otras tres listas
de la auditoría, y no era cierto — `rationale_ref` solo cita 13 de los 24
hallazgos numerados entre `data_integrity_findings.csv`, `category_findings.csv`
y `role_model_findings.csv`. La mayoría del resto está cubierta de hecho por
una acción con fila propia, pero **cinco hallazgos no estaban en ninguna
lista**, incluido uno que la auditoría calificó `critical` (ROL-02, cobertura
de rol por MLO). Se agregaron como `R1-INT-02`, `R1-INT-04`, `R1-ROL-02`,
`R1-ROL-05` y `R1-ROL-07` — la clase `ROL` es nueva, para no mentir sobre que
vienen de `role_model_findings.csv` y no de `data_integrity_findings.csv`.

La misma revisión encontró seis filas medidas y dejadas en `abierto` en vez
de `verificado` — entre ellas `R1-ACT-14`, la que sostiene las cifras
correctas de reguladores que motivan todo este diseño — porque el validador
nunca exigió `verificado_como` para `abierto`. Se corrigieron las seis y se
agregó la regla que lo impide, se sumó `verificado` a la lista de pendientes
del reporte (antes solo miraba `abierto`/`necesita_fuente`, así que diez
filas medidas quedaban invisibles para el próximo paquete), y se cerraron
varios huecos más del validador: cuenta de campos exacta (la clase de bug de
`R1-ACT-19`, una coma sin comillas que desplaza columnas y valida bien si
nadie cuenta), `bloquea_publicacion` contra el enum, `ronda` como entero
positivo consistente con el prefijo del id, id con clave vacía, encabezado
con las nueve columnas exactas, y un chequeo de que `bloquea_publicacion` no
se desincronice de `blocks_publication` en `action_matrix.csv` — la única
columna que el libro copia literalmente de un archivo de ellos.

Libro final: 62 filas — `aplicado` 29, `abierto` 13, `verificado` 10,
`necesita_fuente` 3, `cerrado` 2, `refutado` 2, `rechazado` 2, `superado` 1.
Suite en 187 tests (10 nuevos, todos sobre `review_ledger.py`).

## 2026-08-10 — segunda ronda de la auditoría: evidence_type y una reversión

Llegó la segunda devolución (`docs/review/ultima/`), que verifica v5, responde
las seis consultas que le habíamos hecho y revisa las cuatro decisiones donde nos
habíamos apartado de su recomendación. De esas cuatro: dos aceptadas
(`xy_body`/`sex_body` y `Large dense-core vesicles`, en ambos casos diciendo que
nuestra lectura era mejor), una revertida y una corregida.

**La reversión.** `synaptic_compartment`, que en v5 habíamos creado para no
inventar un lado de la sinapsis, se retira: 1.353 de sus 1.366 proteínas ya están
anotadas como `postsynaptic_density` por DrLLPS y solo 3 como presinápticas. Al
verificar encontré que dos detalles de su argumento estaban mal —dicen que el
solapamiento es intra-recurso, cuando solo 3 vienen de CD-CODE, y citan un PMID
en filas de CD-CODE, que por diseño no tiene ninguno— pero la conclusión sale
reforzada: coincidencia entre recursos independientes es mejor evidencia que
duplicación interna.

**`plant_mtoc`.** Las 12 filas de Arabidopsis que v5 había dejado como
imprecisión documentada son γ-TuRC más maquinaria TON1/TRM: nucleación
acentrosómica. Es el primer canónico que no existe en `mlo_mapping.csv`, así que
`build_db.py` ahora arma el vocabulario leyendo también
`mlo_organism_scoped.csv`.

**`evidence_type`.** Cinco valores, no los tres que habían propuesto, porque
PhaSepDB emite dos afirmaciones distintas según el rol. Las ocho combinaciones
`(source_db, source_role)` se verificaron exhaustivas. El valor que cambia cómo
se lee la base es `membership_only`: hace explícito que las 13.844 filas sin rol
son el alcance declarado de CD-CODE y no un agujero de la ingesta. Dos tests
nuevos afirman que no hay NULL y que no aparece nada fuera de los cinco.

**Casos «review».** De los 62 vivos se cerraron nueve adjudicados desde listas de
genes. Dos requirieron cambio: `PCBP2 condensates` a `cytoplasmic_rnp_granule` y
`RISC complex` a descarte. Cuatro se cerraron como correctos, incluidos los dos
que el dossier había marcado como más expuestos (`Germ granule` → `p_granule` y
`Mitochondrial cloud` → `balbiani_body`). Tres siguen necesitando la publicación.
Y no toqué `RNA polymerase II, holoenzyme`: la devolución la da por marcada para
descarte, pero nunca recibió veredicto en ningún documento.

Verificado: anotaciones 35.970 → 35.968, vocabulario 177, `postsynaptic_density`
4.478 → 5.844, `centrosome` 1.790 → 1.778, `plant_mtoc` 12. 164 tests en verde.

Queda para la etapa siguiente, en `mlo_mapping_decisions.md` §12.5: reinstaurar
los reguladores (cambia lo que sirve el sitio) y la migración de categorías, que
ahora son **cuatro** ejes y no cinco —omitir `functional_process` deja solo tres
términos sin clasificar—, así que sale más barata de lo previsto.

## 2026-08-09 — correcciones de la auditoría biológica, etapa 1

Llegó la devolución de la revisión externa (`docs/review/devolucion/`): informe
más 12 CSVs y 5 figuras. De 242 equivalencias revisadas, 160 correctas, 64
pendientes de curador y 18 errores.

Lo primero fue verificar contra la base actual, porque la auditoría corrió
sobre una copia previa al fix de doble ingesta de PhaSepDB. Sus dos acciones
bloqueantes de ingesta (colapsar los tags duplicados y normalizar las filas por
PMID) ya estaban resueltas: la base tiene 35.971 filas con clave
`(uniprot_id, source_db, source_mlo, source_role)` única, y FUS aparece con 5
filas de `stress_granule`, no con las 119 que reportaba el informe.

Se hizo la etapa 1 en dos commits sobre `fix/biology-audit-stage1`.

**Defectos que no dependen de criterio biológico.** La `Categoria` almacenada
era arbitraria para 23 de los 170 canónicos: el loader deduplicaba por canónico
e insertaba con `INSERT OR IGNORE`, así que ganaba la fila que leyera primero.
Seis de esos conflictos ni siquiera eran biología (`Citoplasma` y
`Citoplasmático` eran la misma categoría con dos grafías). Ahora hay una
categoría curada por canónico y el loader falla si el archivo se contradice.
Además: `evidence` tenía el string literal `'NULL'` en 13.847 filas,
`mapping_version` estaba en `v3` para un mapeo que ya era v4, y tres términos
del vocabulario no tenían ninguna anotación detrás.

**Los 18 errores de equivalencia.** Los dos grandes eran etiquetas compuestas
que la regla de explosión no cubría, porque solo contemplaba `;` y no `X/Y` ni
`X and Y`. `Centrosome/Spindle pole body` mandaba 775 proteínas de metazoos al
término fúngico; se resolvió con un archivo nuevo,
`database/mappings/mlo_organism_scoped.csv`, que redirige por organismo sin
reescribir nunca `source_mlo`. `Presynaptic clusters and postsynaptic densities`
asignaba 1.366 proteínas al lado presináptico y perdía el postsináptico; ahora
tiene canónico propio a la resolución que la fuente realmente anota.

`XY body` y `sex body` resultaron ser dos nombres de la misma estructura
meiótica, con la justificación de `sex_body` describiendo el cuerpo de Barr:
ambos van a `xy_body` y no se crea `barr_body` porque nada lo anota.
`polarity_condensate` se abrió en tres, que era lo que el dossier ya venía
preguntando.

Verificado: anotaciones 35.971 → 35.970, proteínas 15.879 sin cambio,
vocabulario 167 → 177, `spindle_pole_body` 910 → 135, `centrosome`
1.015 → 1.790. 67 tests del pipeline y 94 de la API en verde.

Queda abierto y documentado en `mlo_mapping_decisions.md` §11.6: el esquema de
cinco ejes, `evidence_type`, sacar `NotInformed` e `in_vitro_droplet` del
vocabulario de organelas, reinstaurar los reguladores de DrLLPS y los 64 casos
"a revisar".

## 2026-08-08 — dossier de biología para revisión externa + bug de doble ingesta

Se armó `docs/review/` (dossier de curación biológica en inglés,
autocontenido, + 3 CSV) para mandar a revisión externa: modelo
driver/component, criterios de unificación de nombres de MLO, historial de
decisiones v1→v4 con las reversiones y las correcciones rechazadas, esquema
de categorías e inventario completo de los 170 `unified_mlo`.

Armándolo aparecieron dos defectos verificados contra la DB:

- **`PhaseDB` y `PhasePDB` son el mismo recurso (PhaSepDB) ingestado dos
  veces**, sin deduplicar. Inflaba todos los conteos y el filtro por fuente
  del frontend dejaba 14 875 anotaciones inalcanzables. `parsers/CLAUDE.md`
  afirmaba lo contrario ("two separate source databases"), que es por qué
  nunca se detectó — corregido. **Resuelto el mismo día**, ver la entrada de
  abajo.
- **23 canonicals tienen categoría arbitraria**: cuando varios `source_mlo`
  colapsan en un canonical con `Categoria` distinta, `build_db.py` usa
  `INSERT OR IGNORE` y gana la primera fila leída. Documentado en el dossier
  §7, sin issue propio todavía.

## 2026-08-08 — arreglada la doble ingesta de PhaSepDB

Resuelto el primero de los dos defectos de arriba. Al mirar los archivos de
origen apareció que el diagnóstico inicial se quedaba corto: no eran "dos
exports distintos del mismo recurso" sino **los mismos dos archivos,
duplicados con otro nombre** (MD5 idéntico). Toda la diferencia entre
`phasedb.tsv` (14 608 filas) y `phasepdb.tsv` (14 875) la producían los
parsers, no los datos.

Qué se hizo:

- Un solo parser, `parsers/parse_phasesepdb.py`, con `source_db = "PhaSepDB"`,
  leyendo únicamente de `database/raw/`. Se quedó con lo mejor de cada uno: el
  fallback a `MLO Types` del summary (recupera 813 nombres reales de MLO que el
  otro llenaba con `NotInformed`) y sin la exclusión ad-hoc que descartaba las
  filas de componente de toda proteína ya listada como driver. De paso, el
  pipeline dejó de depender de `OLD/`.
- Deduplicación genérica en `integrate.py`: una fila por
  `(uniprot_id, source_db, source_mlo, source_role)`, uniendo los PMIDs en
  `evidence`. Sin ramas por base de datos. El rol va en la clave a propósito:
  PhaSepDB publica un dataset de drivers y otro de componentes de MLOs, y una
  proteína puede estar en ambos — son dos observaciones experimentales
  distintas, así que se conservan las dos filas (decisión del usuario,
  registrada en `BIOLOGY.md`).
- `build_db.py` pasó a ser re-ejecutable (borra `mlo_annotations` y
  `mlo_definitions` antes de cargar). Hasta ahora la regeneración documentada
  en tres comandos duplicaba en silencio todas las filas en la segunda corrida.

Resultado: 54 786 → 35 971 anotaciones, seis `source_db` → cinco,
`source_db_count` máximo 6 → 5, 15 879 proteínas sin cambios. Las tablas
enriquecidas (`sequence_features`, `ppi`, `orthologs`) quedaron intactas.
Detalle completo y verificación en
[docs/issues/001-phasedb-phasepdb-duplicate-ingestion.md](docs/issues/001-phasedb-phasepdb-duplicate-ingestion.md).

**Pendiente**: el frontend está buildeado con las listas viejas —
`api/static/` necesita un `npm run build` para que los badges y el filtro por
fuente de `/mlos` tomen `PhaSepDB`.

## 2026-08-06 — repo-root swap: `refactor/` pasa a ser la raíz real

`refactor/` deja de ser área de staging: el árbol pre-refactor se retiró a
`OLD/` y `refactor/*` se promovió a la raíz del repo. Ver Entry 16 de
[REFACTOR_LOG.md](REFACTOR_LOG.md) para el detalle (dos pases de `git mv`,
fixes de `.gitignore`, verificación de paths y corrección de docs).
