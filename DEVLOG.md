# DEVLOG.md

## 2026-08-04 — refactor iniciado

Refactor iniciado desde la branch `audit/full-repo-review`, con
`refactor/` como futura raíz limpia del proyecto. Empezando por la capa de
datos (`database/` + `scripts/` + `parsers/`); `api/` y `frontend/` quedan
para una fase posterior.

Ver [REFACTOR_LOG.md](REFACTOR_LOG.md) para el detalle paso a paso de qué se
copió, qué se dejó afuera, y por qué.

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
