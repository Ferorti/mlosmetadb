# Design: libro de hallazgos para el intercambio con Claude Science

**Date**: 2026-08-10
**Status**: approved, pending implementation plan
**Branch**: `fix/biology-audit-stage2` (o una nueva si se prefiere aislar)
**Scope**: agrega un libro de hallazgos (`docs/review/findings.csv`), un script
que lo valida, un test que hace obligatoria la regla central, y un bloque
`_meta` en `tests/dataset_baseline.json` que la vuelve autoidentificada. Carga
las rondas 1 y 2 hacia atrás. No toca el pipeline, la DB, la API ni el
frontend.

---

## 1. Problema

El intercambio con Claude Science lleva dos rondas completas
(`docs/review/devolucion/`, `docs/review/ultima/`) más nuestra respuesta
intermedia. Funcionó, pero dejó tres problemas que van a repetirse en la ronda 3
y que son los que este diseño ataca. Fueron elegidos explícitamente por el
usuario entre cuatro candidatos.

### 1.1 No hay una sola lista de lo que sigue abierto

El estado de cada hallazgo vive en prosa, repartido entre
`database/mappings/_archive/mlo_mapping_decisions.md` §11.6 y §12.5. Para
saber si algo sigue pendiente hay que leer dos secciones y cruzarlas contra
cuatro CSVs de la auditoría. No existe una vista consultable.

### 1.2 Las cifras que llegan no son confiables, y la verificación se pierde

Tres afirmaciones de la auditoría resultaron erróneas al chequearlas:

| Afirmación | Real |
|---|---|
| El solapamiento sináptico es intra-recurso (CD-CODE reexporta su entrada de PSD) | 1.353 de 1.360 vienen de DrLLPS; solo 3 de CD-CODE |
| Las filas de PSD de CD-CODE llevan PMID 23071613 | Ninguna fila de CD-CODE lleva PMID en esta base (0 de 13.844) |
| Reguladores: `p_body` 429, `stress_granule` 418 | 253 y 164; las cifras del informe suman más que su propio total de 607 |

Salió bien porque se verificó todo a mano, pero **la evidencia de esa
verificación quedó en la conversación y en mensajes de commit**, no en un lugar
consultable. Nada garantiza que la próxima ronda se verifique igual.

### 1.3 Claude Science mide sobre datos viejos

Comparte directorio de filesystem, pero se saca una copia local y sigue con
ella (lo declara en sus propias limitaciones). En la ronda 1 midió sobre 54.786
filas cuando la base viva tenía 35.971, porque nada en el paquete que le
mandamos declaraba de qué momento partía. La mitad de sus cifras absolutas
nacieron infladas por eso, incluidos los dos hallazgos que marcó como críticos
y que ya estaban resueltos.

### 1.4 Fuera de alcance, por decisión

- **Convención de nombres de directorio y numeración automática de rondas.** Es
  el cuarto candidato, y el usuario lo dejó explícitamente afuera. Los archivos
  aparecieron en `devolucion/` y después en `ultima/`, con tres nombres de
  documento sin numerar, y eso no molesta lo suficiente para construirle una
  solución.
- **Plantillas de documento** para el paquete que sale o el que vuelve.
- **Cualquier generalización a colaboraciones futuras.** El sistema es para
  cerrar *esta* auditoría. Si más adelante aparece otro intercambio, se evalúa
  entonces con el caso real a la vista.

---

## 2. Hallazgo que cambia el costo

**`tests/dataset_baseline.json` ya es una huella de datos y nadie la está usando
para esto.** Contiene conteos por tabla, por `source_db`, por `unified_role`,
por `dataset_active`, por `evidence_type`, el histograma de `source_db_count`,
los MLOs distintos en uso y el testigo de FUS (P35637). La genera `_snapshot()`
en `tests/test_dataset_invariants.py`, corriendo el módulo como script.

O sea que el problema §1.3 está a un `_meta` de distancia de estar resuelto: el
contenido ya existe, lo único que falta es que el archivo diga de qué commit
salió.

---

## 3. Componentes

Cuatro piezas.

| Pieza | Responsabilidad | Depende de |
|---|---|---|
| `docs/review/findings.csv` | El libro: una fila por ítem que requiere o recibió una decisión nuestra | nada |
| `_meta` en `tests/dataset_baseline.json` | Que la huella diga de qué commit y fecha salió | `_snapshot()` |
| `scripts/review_ledger.py` | Validar el libro y reportar qué sigue abierto | `findings.csv` |
| `tests/test_review_ledger.py` | Hacer no-opcional la regla central | el script |

### 3.1 Principio: el libro referencia, no duplica

Claude Science ya mandó 12 archivos con 242 veredictos de equivalencia, 22
acciones priorizadas y 62 casos de revisión con su propia columna
`adjudication`. **Copiar ese contenido al libro crearía una segunda verdad que
se desincroniza en la primera corrección.**

Una fila del libro apunta a la fila de origen y agrega solo lo que la auditoría
no puede saber: qué verificamos, qué decidimos y dónde quedó aplicado.

Consecuencia práctica: de ~400 ítems totales en los CSVs, el libro tiene **~57
filas**, porque los 160 veredictos `correct` no necesitan seguimiento y los 53
casos sin adjudicar entran como una sola fila que apunta a su archivo.

### 3.2 `docs/review/findings.csv`

Columnas:

| Columna | Contenido |
|---|---|
| `id` | Estable y nuestro. Formato `R<ronda>-<clase>-<clave>`, con `<clase>` de un conjunto cerrado de siete: `ACT` (acción de su matriz), `INT` (hallazgo de integridad), `EQ` (error de equivalencia), `DEC` (decisión nuestra que ellos revisaron), `ADJ` (caso de revisión adjudicado), `OWN` (hallazgo propio, sin origen en ningún documento de ellos), `ROL` (hallazgo del modelo de rol, `role_model_findings.csv`). Ejemplos: `R1-ACT-03`, `R1-INT-10`, `R2-DEC-synaptic`, `R1-ROL-02` |
| `ronda` | 1, 2, ... |
| `origen` | `archivo:clave`, con el archivo **relativo a `docs/review/`**: `devolucion/data_integrity_findings.csv:INT-10`. Vale `-` para los ítems de §5.1, que no salen de ningún documento de ellos |
| `afirmacion` | Una línea: qué sostienen |
| `estado` | Uno de los ocho de §3.3 |
| `verificado_como` | La consulta y su resultado, o `criterio` más fundamento. **Nunca vacío si el estado es `verificado`, `refutado` o `aplicado`** (ver §3.3) |
| `decision` | Una línea más puntero al razonamiento largo. Obligatoria si el estado es `rechazado` o `superado` |
| `aplicado_en` | SHA del commit, o `-`. Obligatorio si el estado es `aplicado` |
| `bloquea_publicacion` | `si` / `no` / `-`. Tomado de su matriz de acciones para preservar la prioridad que ellos asignaron; `-` para los ítems que no vienen de esa matriz, que son la mayoría de los de la ronda 2 |

**Finales de línea: LF.** Es archivo nuevo, así que no hereda la trampa de
`mlo_mapping.csv` y `mlo_definitions.csv` (CRLF más saltos de línea embebidos en
campos citados), documentada en `database/CLAUDE.md`.

**Nota de implementación (fix wave del 2026-08-10, `fix/biology-audit-stage2`):**
la carga real terminó con dos clases más de las cinco previstas acá, y el
motivo de cada una quedó documentado en el propio script
(`scripts/review_ledger.py`, comentario sobre `CLASSES`):

- **`OWN`** — hallazgos propios sin origen en ningún documento de la
  auditoría (§5.1 ya los preveía como "sueltos", pero no como clase separada
  hasta que se cargaron: `R2-OWN-psd-orphans`,
  `R2-OWN-annotations-indexes`).
- **`ROL`** — los tres hallazgos de `role_model_findings.csv` que sobrevivieron
  a la reconciliación de la revisión de rama completa
  (`R1-ROL-02`, `R1-ROL-05`, `R1-ROL-07`). Forzarlos a `INT` habría descrito
  mal su procedencia: `role_model_findings.csv` es un archivo distinto de
  `data_integrity_findings.csv`, con su propio esquema de columnas.

### 3.3 Estados

Conjunto cerrado de siete cuando se diseñó; **ocho en la implementación
final** — ver la nota al pie de esta sección. El script rechaza cualquier
valor fuera del conjunto que efectivamente implementa.

| Estado | Significa | Exige |
|---|---|---|
| `abierto` | Todavía no se miró | — |
| `verificado` | Chequeado y es cierto, sin actuar aún | `verificado_como` |
| `refutado` | Chequeado y es falso | `verificado_como` con la corrección |
| `aplicado` | Actuado | `verificado_como` + `aplicado_en` |
| `rechazado` | Deliberadamente no se hace | `decision` con la razón |
| `necesita_fuente` | Bloqueado en leer una publicación | — |
| `superado` | Una ronda posterior lo reemplazó | `decision` apuntando a la fila que lo reemplaza |

`superado` no es un lujo: `synaptic_compartment` se **aplicó** en la ronda 1
(commit `71cdcac`) y se **revirtió** en la ronda 2 (commit `45102ca`). Sin ese
estado, una de las dos filas tendría que mentir.

`refutado` no se borra del libro. Las tres correcciones de §1.2 son entregables
para Claude Science, no ruido interno nuestro.

**Octavo estado agregado en la carga: `cerrado`.** Cubre un caso que este
diseño no había previsto — una decisión nuestra que la ronda siguiente
confirma sin remedir ninguna cifra (`R2-DEC-xybody`, `R2-DEC-ldcv`). No es
`aplicado` (no hay commit propio, la acción ya estaba aplicada de antes) ni
`superado` (no lo reemplaza nada). Exige `decision` diciendo qué lo cierra,
por la misma razón que el resto de `NEEDS_DECISION`: sin eso no se distingue
de un ítem que nadie miró. Ver `scripts/review_ledger.py`.

### 3.4 `_meta` en `tests/dataset_baseline.json`

`_snapshot()` agrega:

```json
"_meta": {
  "generated_on_commit": "<sha de HEAD al momento de generar>",
  "generated_at": "<ISO date>"
}
```

**El test no lo compara.** `test_dataset_matches_the_committed_baseline` está
parametrizado sobre una lista explícita de secciones, así que una clave nueva
simplemente no entra en la comparación y el test no empieza a fallar en cada
commit.

Nota honesta sobre el valor guardado: el SHA es el de `HEAD` cuando se regenera
la línea base, o sea el commit *anterior* al que va a incluir el archivo. Se lee
como "generado sobre el commit X", que es exactamente lo que se necesita para
detectar deriva.

Contrapartida aceptada: refrescar la línea base ahora produce diff en `_meta`
además de los conteos. Es ruido informativo, no accidental.

### 3.5 `scripts/review_ledger.py`

Un solo modo, `--check`, que hace dos cosas:

1. **Valida** `findings.csv` contra las reglas de §3.3 y además: sin `id`
   duplicado, `id` con `<clase>` del conjunto cerrado de §3.2, y `origen`
   apuntando a un archivo que existe bajo `docs/review/` (salvo `-`). Sale con
   código distinto de cero si algo falla, listando cada violación con su `id`.
2. **Reporta** el conteo por estado y la lista de `abierto` + `necesita_fuente`,
   que es lo que va en el próximo paquete para Claude Science.

Deliberadamente **no** hace verificación de deriva de la huella. La huella
cambia legítimamente cada vez que se regenera la DB; convertir eso en una
comprobación automática produciría falsos positivos. La comparación contra lo
que declara el documento entrante es una lectura de dos valores, y con `_meta`
presente es trivial.

### 3.6 `tests/test_review_ledger.py`

Invoca la validación y afirma que pasa. Nada más. Lee un CSV de ~57 filas, así
que no agrega tiempo perceptible a la suite (hoy 164 tests en ~25s).

Es la única pieza del enfoque C que se adopta, y ataca directo el dolor de
§1.2: la regla "nada llega a `aplicado` sin verificación" deja de depender de
que alguien se acuerde.

---

## 4. Flujo

### 4.1 Lo que sale

Cada paquete para Claude Science lleva:

- `tests/dataset_baseline.json`, con `_meta`.
- Las filas del libro en `abierto` o `necesita_fuente`, del reporte de
  `--check`.

Lo segundo es lo que faltó las dos veces: nunca se les dijo explícitamente qué
seguía pendiente de nuestro lado. La segunda devolución acertó la prioridad por
su cuenta, sin que se lo pidiéramos en esos términos.

### 4.2 Lo que vuelve

El documento declara contra qué commit midió. **Primer paso antes de tocar
nada**: comparar contra `_meta`. Si no coincide, toda cifra absoluta del
documento queda sospechada y se remide antes de aplicar.

### 4.3 El ciclo por hallazgo

```
abierto → (verificar) → verificado | refutado → aplicado | rechazado | necesita_fuente
                                                     ↓
                                              (ronda posterior)
                                                     ↓
                                                 superado
```

La regla dura, y la única que se testea: **nada llega a `aplicado` con
`verificado_como` vacío.**

### 4.4 Dónde vive el razonamiento largo

Sigue en `mlo_mapping_decisions.md` §11 y §12. La columna `decision` es una
línea más un puntero. Si el libro se llena de prosa deja de ser consultable y
reintroduce el problema de §1.1.

---

## 5. Arranque: cargar las rondas 1 y 2

Es trabajo real y es de donde sale el valor inmediato.

| Origen | Filas | Nota |
|---|---:|---|
| `devolucion/action_matrix.csv` | 22 | Ya es la vista accionable; la mayoría de los findings de integridad, categoría y rol se subsumen en estas acciones |
| Los 18 errores de equivalencia | 18 | Uno por fila: cada uno recibió su propia decisión y varios se desviaron de la recomendación |
| Ronda 2: las 4 decisiones revisadas | 4 | Dos aceptadas, una revertida (`synaptic_compartment`), una corregida (MTOCs vegetales) |
| Ronda 2: los 9 casos adjudicados | 9 | 4 cerrados como correctos, 2 aplicados, 3 `necesita_fuente` |
| Los 53 casos sin adjudicar | 1 | Una fila apuntando a `ultima/review_cases_prioritized.csv` |
| Sueltos | 3 | Ver §5.1 |

**Total ~57 filas.**

### 5.1 Ítems que hoy no figuran en ninguna lista

El arranque los saca a la luz, y es una razón independiente para hacerlo:

1. **`RNA polymerase II, holoenzyme`** (2 filas en `transcriptional_condensate`).
   La segunda devolución la describe como "ya marcada para descarte" al
   justificar el descarte de `RISC complex`, pero **nunca recibió veredicto**:
   INT-09 de la ronda 1 solo pedía mandarla a la revisión de descarte, y no
   aparece ni en `discard_review.csv` ni en `equivalence_verdicts.csv`. Estado:
   `abierto`.
2. **Las 6 proteínas que quedaron huérfanas** al retirar `synaptic_compartment`
   (O43236, P17152, Q14DG7, Q5VSY0, Q6P995, Q9NQR7). La devolución señala que
   una es mitocondrial. Estado: `abierto`.
3. **Los índices ausentes en `mlo_annotations`.** No tiene índice ni en
   `uniprot_id` ni en `unified_mlo`, lo que hace que una consulta con `NOT
   EXISTS` sobre esa tabla tarde minutos. Es preexistente (se verificó contra el
   backup previo al trabajo) y está fuera del alcance biológico, pero se
   descubrió acá y hoy no está anotado en ningún lado. Estado: `rechazado`, con
   la razón en `decision`, para que no se pierda ni se confunda con un pendiente
   de la auditoría.

### 5.2 Criterio de aceptación

**El reporte de abiertos del script tiene que reproducir exactamente lo que
§11.6 y §12.5 dicen en prosa.** Si no coinciden, una de las dos está mal, y
enterarse ahora es el punto.

Además: `--check` pasa, el test nuevo pasa, y los 164 tests existentes siguen
pasando.

---

## 6. Casos borde

**Afirmaciones que no son numéricas.** "El esquema de categorías mezcla cinco
ejes semánticos" es criterio, no una cifra remedible. `verificado_como` acepta
el valor `criterio` seguido de una línea de fundamento. Lo que no acepta es
quedar vacío: si nadie puede decir por qué se aceptó, no corresponde `aplicado`.

**Que reenvíen un CSV revisado.** `origen` apunta a `archivo:clave`. Si el
archivo no existe, `--check` falla. Si la clave desapareció dentro de un archivo
que sí existe, no se detecta automáticamente: es una limitación aceptada, porque
validar claves contra formatos heterogéneos (`finding_id`, `source_name`,
`priority`) costaría más de lo que ahorra a esta escala.

**Una ronda nueva antes de cerrar la anterior.** Los `id` llevan prefijo de
ronda, así que no colisionan. Un ítem que la ronda nueva reemplaza pasa a
`superado`.

**Edición manual que rompe el archivo.** Para eso están `--check` y el test.

---

## 7. Lo que este diseño no resuelve

- **No obliga a Claude Science a nada.** Es un sistema de nuestro lado. Si su
  próximo documento no declara commit, lo único que cambia es que hay que
  remedir todo en vez de solo lo que corresponda.
- **No detecta una afirmación falsa por sí solo.** Obliga a registrar la
  verificación, no a hacerla bien. El valor es que la ausencia de verificación
  se vuelve visible.
- **No cubre las rondas futuras automáticamente.** Cada ronda agrega filas a
  mano, que a ~15 filas por ronda es más barato que cualquier automatización.
