# DEVLOG.md

## 2026-08-04 — refactor iniciado

Refactor iniciado desde la branch `audit/full-repo-review`, con
`refactor/` como futura raíz limpia del proyecto. Empezando por la capa de
datos (`database/` + `scripts/` + `parsers/`); `api/` y `frontend/` quedan
para una fase posterior.

Ver [REFACTOR_LOG.md](REFACTOR_LOG.md) para el detalle paso a paso de qué se
copió, qué se dejó afuera, y por qué.

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
