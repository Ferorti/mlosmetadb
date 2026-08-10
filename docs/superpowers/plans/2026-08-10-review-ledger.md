# Review Ledger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar una sola lista consultable de qué sigue abierto en la auditoría biológica, con la verificación de cada afirmación registrada y la huella de datos autoidentificada.

**Architecture:** Un CSV (`docs/review/findings.csv`) que referencia los CSVs de la auditoría en vez de duplicarlos, un script que lo valida, un test que hace obligatoria la regla central, y un bloque `_meta` en la línea base que ya existe. Nada toca el pipeline, la DB, la API ni el frontend.

**Tech Stack:** Python 3.11+, `csv` y `argparse` de la stdlib, pytest. Sin dependencias nuevas.

**Spec:** `docs/superpowers/specs/2026-08-10-review-ledger-design.md`

## Global Constraints

- `docs/review/findings.csv` usa **LF**, no CRLF. Es archivo nuevo y no hereda la trampa documentada en `database/CLAUDE.md`.
- Escribir siempre con `csv.writer(..., lineterminator="\n")`; nunca concatenar strings a mano, porque varios campos contienen comas.
- Los estados válidos son exactamente ocho: `abierto`, `verificado`, `refutado`, `aplicado`, `rechazado`, `necesita_fuente`, `superado`, `cerrado`.
- Las clases de `id` válidas son exactamente seis: `ACT`, `INT`, `EQ`, `DEC`, `ADJ`, `OWN`.
- El razonamiento largo NO va al CSV. Va en `database/mappings/_archive/mlo_mapping_decisions.md` §11/§12, y la columna `decision` lleva una línea más el puntero.
- No modificar `_snapshot()` en `tests/test_dataset_invariants.py`. Ver Task 1.
- El repo tiene 164 tests que pasan hoy (`python3 -m pytest tests/ api/tests -q`). Ninguna task puede romperlos.

## Refinamientos sobre el spec

Dos, decididos al aterrizar el diseño, con su razón:

1. **`_meta` va en `_write_baseline()`, no en `_snapshot()`** (el spec §3.4 dice `_snapshot()`). Si estuviera en `_snapshot()`, la fixture `snapshot` del test lo calcularía en cada corrida y necesitaría invocar git. Poniéndolo donde se escribe el archivo, la intención del spec (línea base autoidentificada, test intacto) se cumple sin ese riesgo.
2. **Sexta clase de `id`: `OWN`** (el spec §3.2 cierra el conjunto en cinco). Dos de los tres ítems de spec §5.1 no salen de ningún documento de la auditoría, y forzarlos a `INT` mentiría sobre su origen.
3. **Octavo estado: `cerrado`** (el spec §3.3 cierra el conjunto en siete). Dos filas de la ronda 2 son casos donde la auditoría *aceptó* nuestra decisión: no hay acción pendiente ni cifra que remedir. En `abierto` entrarían al paquete de pendientes que `report()` imprime, listándole a Claude Science dos ítems que ellos mismos cerraron. `cerrado` exige `decision` apuntando a la fila que lo confirma, para que no se confunda con algo que nadie miró. **No** aplica a los cuatro casos `ADJ` cerrados como correctos: esos siguen `abierto` porque sus afirmaciones nunca se verificaron de nuestro lado.

## File Structure

| Archivo | Responsabilidad |
|---|---|
| `docs/review/findings.csv` | Crear. El libro. Datos, sin lógica |
| `scripts/review_ledger.py` | Crear. Validar el libro y reportar abiertos. Única lógica del sistema |
| `tests/test_review_ledger.py` | Crear. Invocar la validación y afirmar que pasa |
| `tests/fixtures/findings_invalid.csv` | Crear. Libro deliberadamente roto, para probar que la validación detecta |
| `tests/test_dataset_invariants.py` | Modificar `_write_baseline()` (línea 238-242). Solo agrega `_meta` |

---

### Task 1: `_meta` en la línea base

Hace que `tests/dataset_baseline.json` diga de qué commit salió, que es lo que faltaba para detectar que Claude Science midió sobre una copia vieja.

**Files:**
- Modify: `tests/test_dataset_invariants.py` — la función `_write_baseline()` y el decorador de `test_dataset_matches_the_committed_baseline`. Sin números de línea a propósito: el Step 1 agrega tests antes de esa función y los corre.
- Test: `tests/test_dataset_invariants.py` (test nuevo en el mismo archivo)

**Interfaces:**
- Consumes: `_snapshot(con) -> dict`, ya existe, no se toca.
- Produces: `tests/dataset_baseline.json` con clave `_meta` de dos campos: `generated_on_commit` (str, sha corto de HEAD) y `generated_at` (str, fecha ISO). Ninguna task posterior depende de esto en código; el consumidor es humano/agente al comparar contra un documento entrante.

- [ ] **Step 1: Escribir el test que falla**

En `tests/test_dataset_invariants.py`, agregar después de `test_dataset_matches_the_committed_baseline`:

```python
def test_baseline_declares_the_commit_it_was_generated_on(baseline):
    """Sin esto no hay forma de detectar que un análisis externo midió sobre
    una copia vieja: la ronda 1 de la auditoría corrió sobre 54.786 filas
    cuando la base viva tenía 35.971, y nada lo declaraba."""
    meta = baseline.get("_meta")
    assert meta, "dataset_baseline.json no tiene bloque _meta"
    assert meta.get("generated_on_commit"), "_meta sin generated_on_commit"
    assert meta.get("generated_at"), "_meta sin generated_at"


def test_meta_is_not_part_of_the_compared_sections():
    """_meta cambia en cada regeneración. Si entrara en la comparación, el test
    de la línea base fallaría en cada commit."""
    assert "_meta" not in COMPARED_SECTIONS
```

`COMPARED_SECTIONS` todavía no existe: se crea en el Step 3 extrayendo la lista que hoy está inline en el decorador `@pytest.mark.parametrize`. Se hace así en vez de inspeccionar `pytestmark` en runtime porque leer `.pytestmark[0].args[1]` funciona pero es frágil y opaco.

- [ ] **Step 2: Correr para verificar que falla**

Run: `python3 -m pytest tests/test_dataset_invariants.py -k "declares_the_commit or not_part_of_the_compared" -v`
Expected: `test_baseline_declares_the_commit_it_was_generated_on` FAIL con "dataset_baseline.json no tiene bloque _meta". El segundo PASA ya (no hay `_meta` en la lista).

- [ ] **Step 3: Implementar**

Primero extraer la lista de secciones comparadas a una constante de módulo, para
que el test del Step 1 pueda leerla. Reemplazar el decorador de
`test_dataset_matches_the_committed_baseline` por:

```python
COMPARED_SECTIONS = [
    "table_rows",
    "annotations_by_source",
    "annotations_by_role",
    "annotations_by_dataset_active",
    "annotations_by_evidence_type",
    "source_db_count_histogram",
    "proteins_without_sequence",
    "annotations_with_literal_null_evidence",
    "distinct_unified_mlos_in_use",
    "fus_p35637",
]


@pytest.mark.parametrize("section", COMPARED_SECTIONS)
def test_dataset_matches_the_committed_baseline(snapshot, baseline, section):
    assert snapshot[section] == baseline[section], REFRESH_HINT
```

La constante tiene que ir **antes** de los dos tests nuevos del Step 1, porque
uno la referencia.

Después reemplazar la función `_write_baseline()` por:

```python
def _baseline_meta() -> dict:
    """Identifica sobre qué commit se generó esta línea base.

    El sha es el de HEAD al momento de regenerar, o sea el commit *anterior*
    al que va a incluir el archivo. Se lee como "generado sobre el commit X",
    que es lo que hace falta para detectar deriva contra un análisis externo.
    """
    sha = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True, cwd=Path(__file__).resolve().parent.parent,
    ).stdout.strip() or "unknown"
    return {"generated_on_commit": sha, "generated_at": date.today().isoformat()}


def _write_baseline() -> None:
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    # _meta va acá y no en _snapshot() a propósito: la fixture del test usa
    # _snapshot() en cada corrida y no debe depender de que git esté disponible.
    payload = {"_meta": _baseline_meta(), **_snapshot(con)}
    BASELINE_PATH.write_text(json.dumps(payload, indent=2) + "\n")
    con.close()
    print(f"baseline written: {BASELINE_PATH}")
```

Agregar a los imports del archivo:

```python
import subprocess
from datetime import date
```

- [ ] **Step 4: Regenerar la línea base y correr los tests**

Run: `python3 tests/test_dataset_invariants.py && python3 -m pytest tests/ api/tests -q`
Expected: `baseline written: ...`, después `166 passed` (164 previos + 2 nuevos).

- [ ] **Step 5: Confirmar que `_meta` quedó en el archivo**

Run: `python3 -c "import json; print(json.load(open('tests/dataset_baseline.json'))['_meta'])"`
Expected: un dict con `generated_on_commit` (sha corto) y `generated_at` (fecha de hoy).

- [ ] **Step 6: Commit**

```bash
git add tests/test_dataset_invariants.py tests/dataset_baseline.json
git commit -m "test: make the dataset baseline say which commit it came from

The baseline already carried every count an external analysis needs to
reconcile against, but not which commit produced them. Claude Science measured
round 1 on a copy predating the PhaSepDB deduplication — 54,786 rows against a
live 35,971 — and nothing in the package we handed over declared the vintage,
so half its absolute figures were born inflated.

_meta lives in _write_baseline(), not _snapshot(): the test fixture calls
_snapshot() on every run and must not depend on git being available. A test
asserts _meta stays out of the compared sections, so refreshing the baseline
does not start failing the suite."
```

---

### Task 2: El script de validación y su test

**Files:**
- Create: `scripts/review_ledger.py`
- Create: `tests/test_review_ledger.py`
- Create: `tests/fixtures/findings_invalid.csv`

**Interfaces:**
- Consumes: nada de tasks anteriores.
- Produces:
  - `validate(rows: list[dict], review_dir: Path) -> list[str]` — devuelve la lista de violaciones, vacía si está todo bien. Es lo que usa el test.
  - `load(path: Path) -> list[dict]` — lee el CSV y devuelve los dicts.
  - `LEDGER_PATH: Path` — `docs/review/findings.csv`.
  - `STATES: frozenset[str]` y `CLASSES: frozenset[str]` — los conjuntos cerrados.
  - CLI: `--check` valida y reporta; sin flags hace lo mismo que `--check`.

- [ ] **Step 1: Crear la fixture de libro roto**

Crear `tests/fixtures/findings_invalid.csv` con una violación de cada regla, para que el test compruebe que la validación las detecta y no solo que acepta lo bueno:

```csv
id,ronda,origen,afirmacion,estado,verificado_como,decision,aplicado_en,bloquea_publicacion
R1-ACT-01,1,-,estado invalido,inventado,-,-,-,no
R1-ACT-01,1,-,id duplicado,abierto,-,-,-,no
R1-XXX-02,1,-,clase invalida,abierto,-,-,-,no
R1-ACT-03,1,-,aplicado sin verificacion,aplicado,,algo,71cdcac,no
R1-ACT-04,1,-,aplicado sin commit,aplicado,una consulta,algo,-,no
R1-ACT-05,1,-,rechazado sin razon,rechazado,-,,-,no
R1-ACT-06,1,-,verificado sin verificacion,verificado,,-,-,no
R1-ACT-07,1,no/existe.csv:X,origen inexistente,abierto,-,-,-,no
R1-ACT-08,1,-,superado sin decision,superado,-,,-,no
R1-ACT-09,1,-,cerrado sin decision,cerrado,-,,-,no
```

- [ ] **Step 2: Escribir el test que falla**

Crear `tests/test_review_ledger.py`:

```python
"""El libro de hallazgos de la auditoría biológica se valida solo.

La regla que importa es que nada llegue a `aplicado` sin verificación
registrada. Las tres cifras erróneas que la auditoría mandó se detectaron
verificando a mano, y esa evidencia quedó únicamente en la conversación.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import review_ledger  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_the_real_ledger_is_valid():
    rows = review_ledger.load(review_ledger.LEDGER_PATH)
    violations = review_ledger.validate(rows, ROOT / "docs" / "review")
    assert violations == [], "\n".join(violations)


@pytest.mark.parametrize("fragment", [
    "estado 'inventado' no está en el conjunto cerrado",
    "id duplicado",
    "clase 'XXX' no está en el conjunto cerrado",
    "aplicado sin verificado_como",
    "aplicado sin aplicado_en",
    "rechazado sin decision",
    "verificado sin verificado_como",
    "origen apunta a un archivo que no existe",
    "superado sin decision",
    "cerrado sin decision",
])
def test_validation_catches_each_kind_of_break(fragment):
    rows = review_ledger.load(FIXTURES / "findings_invalid.csv")
    violations = "\n".join(review_ledger.validate(rows, ROOT / "docs" / "review"))
    assert fragment in violations
```

- [ ] **Step 3: Correr para verificar que falla**

Run: `python3 -m pytest tests/test_review_ledger.py -v`
Expected: FAIL en la colección, con `ModuleNotFoundError: No module named 'review_ledger'`.

- [ ] **Step 4: Implementar el script**

Crear `scripts/review_ledger.py`:

```python
#!/usr/bin/env python3
"""review_ledger.py — valida docs/review/findings.csv y reporta qué sigue abierto.

El libro es la única lista de la verdad sobre el estado de cada hallazgo de la
auditoría biológica. Antes vivía en prosa repartida entre dos secciones de
database/mappings/_archive/mlo_mapping_decisions.md, así que para saber si algo
seguía pendiente había que leerlas y cruzarlas contra cuatro CSVs.

Diseño: el libro REFERENCIA los CSVs de la auditoría, no los duplica. Copiar sus
242 veredictos y 62 casos priorizados crearía una segunda verdad que se
desincroniza en la primera corrección.

Uso:
  python3 scripts/review_ledger.py --check
"""
import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REVIEW_DIR = ROOT / "docs" / "review"
LEDGER_PATH = REVIEW_DIR / "findings.csv"

COLUMNS = ["id", "ronda", "origen", "afirmacion", "estado",
           "verificado_como", "decision", "aplicado_en", "bloquea_publicacion"]

STATES = frozenset({"abierto", "verificado", "refutado", "aplicado",
                    "rechazado", "necesita_fuente", "superado", "cerrado"})

CLASSES = frozenset({"ACT", "INT", "EQ", "DEC", "ADJ", "OWN"})

# Estados que exigen que verificado_como diga algo. `refutado` está acá porque
# una refutación sin la medición que la sostiene no sirve de nada: las tres
# cifras que corregimos a la auditoría son entregables para ellos.
NEEDS_VERIFICATION = frozenset({"verificado", "refutado", "aplicado"})

# Estados en los que la columna decision no puede quedar vacía. `cerrado` está
# acá porque un ítem sin acción tiene que decir qué lo cierra: sin eso no se
# distingue de uno que nadie miró.
NEEDS_DECISION = frozenset({"rechazado", "superado", "cerrado"})

EMPTY = frozenset({"", "-"})


def load(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _blank(value: str | None) -> bool:
    return (value or "").strip() in EMPTY


def validate(rows: list[dict], review_dir: Path) -> list[str]:
    """Devuelve la lista de violaciones. Vacía significa libro válido."""
    violations: list[str] = []
    seen: set[str] = set()

    for row in rows:
        rid = (row.get("id") or "").strip()
        where = rid or "(fila sin id)"

        if not rid:
            violations.append("fila sin id")
        elif rid in seen:
            violations.append(f"{where}: id duplicado")
        seen.add(rid)

        parts = rid.split("-")
        if len(parts) < 3:
            violations.append(f"{where}: id no tiene forma R<ronda>-<clase>-<clave>")
        elif parts[1] not in CLASSES:
            violations.append(f"{where}: clase {parts[1]!r} no está en el conjunto cerrado")

        estado = (row.get("estado") or "").strip()
        if estado not in STATES:
            violations.append(f"{where}: estado {estado!r} no está en el conjunto cerrado")

        if estado in NEEDS_VERIFICATION and _blank(row.get("verificado_como")):
            violations.append(f"{where}: {estado} sin verificado_como")
        if estado == "aplicado" and _blank(row.get("aplicado_en")):
            violations.append(f"{where}: aplicado sin aplicado_en")
        if estado in NEEDS_DECISION and _blank(row.get("decision")):
            violations.append(f"{where}: {estado} sin decision")

        origen = (row.get("origen") or "").strip()
        if origen not in EMPTY:
            rel = origen.split(":")[0]
            if not (review_dir / rel).exists():
                violations.append(f"{where}: origen apunta a un archivo que no existe ({rel})")

    return violations


def report(rows: list[dict]) -> None:
    counts = Counter((r.get("estado") or "").strip() for r in rows)
    print(f"{len(rows)} hallazgos en el libro\n")
    for estado in sorted(STATES):
        print(f"  {estado:16} {counts.get(estado, 0)}")

    pendientes = [r for r in rows
                  if (r.get("estado") or "").strip() in ("abierto", "necesita_fuente")]
    print(f"\nPara el próximo paquete a Claude Science ({len(pendientes)}):\n")
    for row in pendientes:
        print(f"  [{row['estado']:15}] {row['id']:28} {row['afirmacion'][:70]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="validar y reportar (comportamiento por defecto)")
    parser.parse_args()

    if not LEDGER_PATH.exists():
        print(f"[FATAL] no existe {LEDGER_PATH}", file=sys.stderr)
        return 1

    rows = load(LEDGER_PATH)
    violations = validate(rows, REVIEW_DIR)
    if violations:
        print(f"[FATAL] {len(violations)} violaciones en {LEDGER_PATH.name}:", file=sys.stderr)
        for v in violations:
            print(f"    {v}", file=sys.stderr)
        return 1

    report(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Crear un libro mínimo válido para que el primer test pase**

`test_the_real_ledger_is_valid` necesita que el archivo exista. Crear `docs/review/findings.csv` con el encabezado y una sola fila real, la primera del arranque:

```csv
id,ronda,origen,afirmacion,estado,verificado_como,decision,aplicado_en,bloquea_publicacion
R1-ACT-02,1,devolucion/action_matrix.csv:2,"Colapsar los tags source_db PhaseDB y PhasePDB a un solo recurso PhaSepDB",refutado,"SELECT DISTINCT source_db: solo existe PhaSepDB; no se sostiene contra la base viva","Ya resuelto antes de recibir la devolución; ver mlo_mapping_decisions.md §11",2894fad,si
```

- [ ] **Step 6: Correr los tests**

Run: `python3 -m pytest tests/test_review_ledger.py -v`
Expected: `10 passed` (1 del libro real + 9 parametrizados).

- [ ] **Step 7: Correr el script a mano**

Run: `python3 scripts/review_ledger.py --check`
Expected: `1 hallazgos en el libro`, el conteo por estado con `refutado 1`, y la lista de pendientes vacía.

- [ ] **Step 8: Confirmar que la suite completa sigue verde**

Run: `python3 -m pytest tests/ api/tests -q`
Expected: `176 passed` (166 de la Task 1 + 10 nuevos).

- [ ] **Step 9: Commit**

```bash
git add scripts/review_ledger.py tests/test_review_ledger.py tests/fixtures/findings_invalid.csv docs/review/findings.csv
git commit -m "feat: add the findings ledger and make verification non-optional

The audit's state lived in prose across two sections of
mlo_mapping_decisions.md, so answering 'what is still open' meant reading both
and cross-referencing four CSVs. The ledger is that list, and it references the
audit's own CSVs rather than duplicating them — copying 242 verdicts and 62
prioritised cases would create a second truth that desynchronises on the first
correction.

validate() enforces one rule that matters: nothing reaches 'aplicado' without a
recorded verification. Three of the audit's figures were wrong and were caught
by checking them by hand, but that evidence survived only in the conversation.
refutado demands a verification too — a refutation without the measurement
behind it is no use to the reviewer it goes back to.

A deliberately broken fixture proves the validation catches each kind of break,
not just that it accepts good input."
```

---

### Task 3: Cargar la ronda 1 (40 filas)

**Files:**
- Modify: `docs/review/findings.csv`

**Interfaces:**
- Consumes: el formato y las reglas de Task 2.
- Produces: 40 filas con `ronda=1`. Task 5 las reconcilia contra la prosa.

Reglas de derivación de estado usadas acá, para que sean auditables:

- `refutado` = la afirmación **no se sostiene contra la base viva**. No significa que se equivocaron: las acciones 1 y 2 eran ciertas para el snapshot que tenían.
- `superado` = una ronda posterior lo reemplazó (solo la acción 4).
- Las acciones 1 y 21 se parten en dos filas (`01a`/`01b`, `21a`/`21b`) porque cada mitad tiene estado distinto y un solo estado mentiría.
- Las acciones 3, 4 y 5 **absorben** sus errores de equivalencia correspondientes (`Centrosome/Spindle pole body`, `Presynaptic clusters and postsynaptic densities`, `XY body`). Por eso hay 15 filas `EQ` y no 18: crear ambas sería la duplicación que el diseño evita.

- [ ] **Step 1: Agregar las 24 filas de acciones**

Reemplazar el contenido de `docs/review/findings.csv` (manteniendo el encabezado) por el encabezado más estas filas. La fila `R1-ACT-02` ya estaba de Task 2; queda igual.

```csv
R1-ACT-01a,1,devolucion/action_matrix.csv:1,"Normalizar a una fila por (proteína, recurso, MLO, rol)",refutado,"35.970 filas totales = 35.970 claves distintas (uniprot_id, source_db, source_mlo, source_role); FUS/P35637 tiene 5 filas de stress_granule y no 119","Ya cierto antes de recibir la devolución; ver mlo_mapping_decisions.md §11",2894fad,si
R1-ACT-01b,1,devolucion/action_matrix.csv:1,"Mover los PMIDs a una tabla de evidencia con clave foránea",abierto,-,-,-,si
R1-ACT-02,1,devolucion/action_matrix.csv:2,"Colapsar los tags source_db PhaseDB y PhasePDB a un solo recurso PhaSepDB",refutado,"SELECT DISTINCT source_db: solo existe PhaSepDB; no se sostiene contra la base viva","Ya resuelto antes de recibir la devolución; ver mlo_mapping_decisions.md §11",2894fad,si
R1-ACT-03,1,devolucion/action_matrix.csv:3,"Separar la etiqueta compuesta 'Centrosome/Spindle pole body' por organismo",aplicado,"910 filas: 135 fúngicas (S. cerevisiae 87, S. pombe 48) contra 775 no fúngicas; spindle_pole_body 910 -> 135, centrosome 1.015 -> 1.790","Regla en mlo_organism_scoped.csv, source_mlo nunca se reescribe; §11.1. Refinado en R2-DEC-plantmtoc",71cdcac,si
R1-ACT-04,1,devolucion/action_matrix.csv:4,"Separar 'Presynaptic clusters and postsynaptic densities' en sus dos compartimientos",superado,"1.366 filas, 1.366 proteínas, todas humanas; presynaptic_active_zone 1.394 -> 28","Aplicado como synaptic_compartment y revertido en la ronda 2; ver R2-DEC-synaptic y §12.1",71cdcac,si
R1-ACT-05,1,devolucion/action_matrix.csv:5,"Crear xy_body para el cuerpo sexual meiótico y corregir la definición de sex_body",aplicado,"XY body: 10 proteínas de Mus musculus, cero solapamiento con las 42 de heterochromatin del mismo recurso; sex body contiene Rnf212 (recombinación meiótica)","Son sinónimos: ambos a xy_body y sex_body se disuelve. No se crea barr_body por la regla de cobertura; §11.2",71cdcac,si
R1-ACT-06,1,devolucion/action_matrix.csv:6,"Reemplazar la columna Categoria por los cinco ejes ortogonales",abierto,-,"Ver R2-DEC-axes: la ronda 2 lo reduce a cuatro ejes",-,si
R1-ACT-07,1,devolucion/action_matrix.csv:7,"Unificar las grafías de categoría Citoplasma y Citoplasmático",aplicado,"Resuelve 6 de los 23 conflictos sin decisión biológica; categorías 22 -> 21, cero filas con category='Citoplasma'","Los 17 restantes recibieron categoría curada con criterio documentado; §11.5",62af214,si
R1-ACT-08,1,devolucion/action_matrix.csv:8,"Agregar evidence_type a cada anotación",aplicado,"8 combinaciones (source_db, source_role) verificadas exhaustivas contra database/interim/*.tsv; cero NULL en 35.968 filas","Cinco valores y no tres, porque PhaSepDB emite dos afirmaciones según el rol; §12.4",45102ca,si
R1-ACT-09,1,devolucion/action_matrix.csv:9,"Reemplazar la cadena literal 'NULL' en evidence por NULL de SQL",aplicado,"13.847 filas con evidence='NULL' -> 0; evidence IS NULL pasa a 13.847","nullable() en build_db.py honra el centinela que el resto de las columnas ya honraba; §11",62af214,si
R1-ACT-10,1,devolucion/action_matrix.csv:10,"Eliminar NotInformed como canónico y representar la localización ausente como NULL",abierto,"930 anotaciones y 930 proteínas, de las cuales 457 no tienen ninguna otra anotación (el informe reporta 1.217 y 505, infladas por la doble ingesta)",-,-,si
R1-ACT-11,1,devolucion/action_matrix.csv:11,"Eliminar in_vitro_droplet como canónico y representarlo como evidence_type",abierto,"551 anotaciones, 442 proteínas, 146 sin ningún MLO in vivo (el informe reporta 426 y 142)",-,-,no
R1-ACT-12,1,devolucion/action_matrix.csv:12,"Indicar por MLO si algún recurso aporta proteoma masivo de clientes",abierto,-,-,-,si
R1-ACT-13,1,devolucion/action_matrix.csv:13,"Documentar que el rol de DrLLPS es de alcance proteína y se propaga a todos sus MLOs",aplicado,"criterio: la devolución lo verificó (1.055 proteínas multi-MLO con rol idéntico, cero excepciones) y no se remidió","Documentado en SCHEMA.md y BIOLOGY.md via curator_assignment; §12.4",5cd39aa,si
R1-ACT-14,1,devolucion/action_matrix.csv:14,"Reinstaurar Regulator como tercer valor de rol o exponer las filas excluidas",abierto,"1.389 filas, 977 proteínas, 502 invisibles; esas 502 aportan 607 anotaciones en 19 MLOs: p_body 253, stress_granule 164, p_granule 107 (el informe reporta 429 y 418, que suman más que su propio total)",-,-,no
R1-ACT-15,1,devolucion/action_matrix.csv:15,"Corregir los errores de equivalencia restantes",aplicado,"Los 18 verificados uno por uno; ver las filas R1-EQ-*","Uno se apartó de la recomendación (Large dense-core vesicles) y la ronda 2 lo aceptó; §11.4",71cdcac,no
R1-ACT-16,1,devolucion/action_matrix.csv:16,"Adjudicar las 64 equivalencias marcadas 'review' con un curador",abierto,-,"9 adjudicadas en la ronda 2 (ver R2-ADJ-*); 53 siguen abiertas en R2-ADJ-batch",-,no
R1-ACT-17,1,devolucion/action_matrix.csv:17,"Derivar taxonomic_scope de los organismos anotados; corregir refractile_body y rho_body",abierto,"Confirmado: refractile_body está en Procariota y su única proteína es de Eimeria tenella (apicomplejo); rho_body está en Procariota sin ningún organismo resoluble",-,-,no
R1-ACT-18,1,devolucion/action_matrix.csv:18,"Definir el vocabulario de sufijos estructurales y aplicarlo consistentemente",abierto,-,-,-,no
R1-ACT-19,1,devolucion/action_matrix.csv:19,"Arreglar la fila CSV mal escapada de axonal TIAR-2 granules",aplicado,"Una sola fila con 5 campos en vez de 4; tras el arreglo, cero filas con != 4 campos en 842","La justificación con PMID:31378567 se recuperó; §11",62af214,no
R1-ACT-20,1,devolucion/action_matrix.csv:20,"Documentar las tres vías de exclusión (DISCARD, synthetic_condensate, NULL) como un mecanismo con motivo",abierto,-,-,-,no
R1-ACT-21a,1,devolucion/action_matrix.csv:21,"Resolver el split por capitalización entre cytoplasmic_protein_granule y cytoplasmic_rnp_granule",aplicado,"'Cytoplasmic protein granule' y 'cytoplasmic protein granule' iban a canónicos distintos; cytoplasmic_protein_granule 17 -> 22, cytoplasmic_rnp_granule 71 -> 66","Fallo de normalización, no de criterio; §11.4",71cdcac,no
R1-ACT-21b,1,devolucion/action_matrix.csv:21,"Redefinir el límite biológico entre cytoplasmic_protein_granule y cytoplasmic_rnp_granule",abierto,-,-,-,no
R1-ACT-22,1,devolucion/action_matrix.csv:22,"Actualizar mapping_version en mlo_vocabulary para que refleje los términos presentes",aplicado,"Las 170 filas llevaban el DEFAULT 'v3' con un mapeo que ya era v4; ahora se sella explícito y el loader falla si alguna queda fuera","MAPPING_VERSION como constante, se bumpea junto con el archivo de mapeo; §11",62af214,no
```

- [ ] **Step 2: Agregar las 15 filas de errores de equivalencia**

Al final del mismo archivo:

```csv
R1-EQ-abc-transporter,1,devolucion/equivalence_verdicts.csv:ABC transporter condensate,"'ABC transporter condensate' -> bacterial_rnp_body es un ensamblaje de transporte de membrana en un canónico de gránulos de RNP",aplicado,"2 proteínas, ambas de Mycobacterium; sin relación compositiva con BR-bodies nucleados por RNasa E","Canónico propio abc_transporter_condensate, categoría Procariota; §11.4",71cdcac,-
R1-EQ-ldcv,1,devolucion/equivalence_verdicts.csv:Large dense-core vesicles,"'Large dense-core vesicles' -> chromogranin_condensate equipara una vesícula con membrana al condensado",aplicado,"1 proteína (SEMG2/Q02383) y es su única anotación: descartarla la borraba del dataset y rompía el invariante de que toda proteína tiene una anotación","Nos apartamos de la recomendación: se conserva la asignación (el condensado ES el núcleo denso intravesicular) y se corrige la justificación. La ronda 2 lo aceptó; §11.4 y §12",71cdcac,-
R1-EQ-cyto-protein-granule,1,devolucion/equivalence_verdicts.csv:Cytoplasmic protein granule,"'Cytoplasmic protein granule' -> cytoplasmic_rnp_granule mientras la variante en minúscula va a cytoplasmic_protein_granule",aplicado,"La misma etiqueta fuente se repartía entre dos canónicos según su capitalización; 5 filas movidas","Ver R1-ACT-21a; el límite entre ambos canónicos sigue abierto en R1-ACT-21b",71cdcac,-
R1-EQ-golgi-ribbon,1,devolucion/equivalence_verdicts.csv:Golgi ribbon,"'Golgi ribbon' -> golgin_condensate importa una disposición de organela con membrana",aplicado,"1 proteína, con otras anotaciones, así que el descarte no la pierde; golgin_condensate 15 -> 14","DISCARD, mismo criterio con el que ya se descartaron sinaptosoma y matriz extracelular; §11.4",71cdcac,-
R1-EQ-ddr1,1,devolucion/equivalence_verdicts.csv:DDR1 condensate,"'DDR1 condensate' -> hippo_condensate clasifica un receptor de colágeno como vía Hippo",aplicado,"2 proteínas; hippo_condensate 20 -> 18, signaling_cluster 52 -> 54","A signaling_cluster, el catch-all documentado para condensados de membrana sin identidad específica; §11.4",71cdcac,-
R1-EQ-ibag,1,devolucion/equivalence_verdicts.csv:inclusion body-associated granule (IBAG),"'IBAG' -> inclusion_body trata una factoría viral como agregado patológico",aplicado,"9 proteínas; junto con P6, inclusion_body 95 -> 80 y viral_factory 35 -> 50","A viral_factory: subcompartimiento de inclusiones de replicación del VRS; §11.4",71cdcac,-
R1-EQ-p6,1,devolucion/equivalence_verdicts.csv:P6 inclusion body,"'P6 inclusion body' -> inclusion_body trata una factoría del virus del mosaico de la coliflor como agregado patológico",aplicado,"6 proteínas; ver R1-EQ-ibag para el efecto conjunto","A viral_factory; §11.4",71cdcac,-
R1-EQ-tifa,1,devolucion/equivalence_verdicts.csv:TIFA-TRAF6 Condensate,"'TIFA-TRAF6 Condensate' -> inflammasome, pero los TIFAsomas activan NF-kB sin sensor NLR ni caspasa-1",aplicado,"7 proteínas; inflammasome 9 -> 2, tifasome 7","Canónico propio tifasome; §11.4",71cdcac,-
R1-EQ-fatz1,1,devolucion/equivalence_verdicts.csv:FATZ-1 condensate,"'FATZ-1 condensate' -> postsynaptic_density, pero MYOZ1 es del disco Z sarcomérico",aplicado,"1 proteína; postsynaptic_density 4.479 -> 4.478, z_disc_condensate 1","Canónico propio z_disc_condensate; probable match por similitud de nombre; §11.4",71cdcac,-
R1-EQ-psg,1,devolucion/equivalence_verdicts.csv:Proteasome Storage Granule,"'Proteasome Storage Granule' -> proteasome_foci, que es Nuclear, siendo una estructura citoplasmática de quiescencia en levadura",aplicado,"5 proteínas; proteasome_foci 26 -> 21, proteasome_storage_granule 5","Canónico propio proteasome_storage_granule; §11.4",71cdcac,-
R1-EQ-hsp,1,devolucion/equivalence_verdicts.csv:HSP condensate,"'HSP condensate' -> signaling_condensate clasifica chaperonas como señalización",aplicado,"1 proteína, de Dictyostelium discoideum","Canónico propio chaperone_condensate; §11.4",71cdcac,-
R1-EQ-plectin,1,devolucion/equivalence_verdicts.csv:Plectin condensates,"'Plectin condensates' -> signaling_condensate clasifica un entrecruzador de filamentos intermedios como señalización",aplicado,"2 proteínas","Canónico propio plectin_condensate, categoría Citoesqueleto; §11.4",71cdcac,-
R1-EQ-ssb,1,devolucion/equivalence_verdicts.csv:SSB condensate,"'SSB condensate' -> signaling_condensate, siendo replicación y reparación de ADN",aplicado,"3 proteínas; signaling_condensate 21 -> 15, dna_damage_foci 85 -> 88","Vuelve a dna_damage_foci, revirtiendo la reclasificación de v3; §11.4",71cdcac,-
R1-EQ-asyn,1,devolucion/equivalence_verdicts.csv:α-synuclein condensates,"'α-synuclein condensates' -> synapsin_condensate fusiona dos ensamblajes distintos que coexisten en el presináptico",aplicado,"8 filas junto con la variante mal escrita; synapsin_condensate 15 -> 7, alpha_synuclein_condensate 8","Canónico propio: no obliga a elegir entre el rol fisiológico y la ruta a cuerpos de Lewy; §11.4",71cdcac,-
R1-EQ-asyn-typo,1,devolucion/equivalence_verdicts.csv:α-synnuclein condensates,"'α-synnuclein condensates' es la misma etiqueta mal escrita y va al mismo canónico",aplicado,"1 proteína; ver R1-EQ-asyn","Normalizada al mismo destino; §11.4",71cdcac,-
```

- [ ] **Step 3: Agregar la fila del hallazgo que quedó sin veredicto**

```csv
R1-INT-09,1,devolucion/data_integrity_findings.csv:INT-09,"'RNA polymerase II, holoenzyme' sobrevive como token compuesto sin explotar y es candidato a descarte",abierto,"2 filas en transcriptional_condensate (POLR2A humano, RPO21 de S. cerevisiae), que tiene 220 en total, así que descartarlo no disuelve el canónico","INT-09 solo pedía mandarlo a la revisión de descarte y eso nunca pasó: no aparece en discard_review.csv ni en equivalence_verdicts.csv. La ronda 2 lo da por marcado para descarte, pero nunca recibió veredicto; §12.3",-,no
```

- [ ] **Step 4: Validar**

Run: `python3 scripts/review_ledger.py --check`
Expected: `40 hallazgos en el libro`, sin violaciones, con este conteo: `aplicado 25`, `abierto 12`, `refutado 2`, `superado 1`, y `cerrado 0`, `necesita_fuente 0`, `rechazado 0`, `verificado 0`.

- [ ] **Step 5: Confirmar los finales de línea**

Run: `file docs/review/findings.csv && python3 -c "print('CRLF' if b'\r\n' in open('docs/review/findings.csv','rb').read() else 'LF ok')"`
Expected: `LF ok`.

- [ ] **Step 6: Correr los tests**

Run: `python3 -m pytest tests/ api/tests -q`
Expected: `176 passed`.

- [ ] **Step 7: Commit**

```bash
git add docs/review/findings.csv
git commit -m "docs: backfill round 1 into the findings ledger

Forty rows: the 22 actions (two split, because each half has a different state
and one state would lie), the 15 equivalence errors, and INT-09.

Fifteen and not eighteen equivalence rows: actions 3, 4 and 5 already carry
their corresponding errors (Centrosome/Spindle pole body, Presynaptic clusters
and postsynaptic densities, XY body), and creating both would be the
duplication the design exists to avoid.

'refutado' means the claim does not hold against the live DB, not that the
reviewer was wrong — actions 1 and 2 were true of the snapshot they had.

Two rows carry corrections to figures the audit published: NotInformed is 930
proteins and not 1,217, and the regulator breakdown is 253/164 rather than
429/418, which summed past its own total."
```

---

### Task 4: Cargar la ronda 2 y los ítems propios (17 filas)

**Files:**
- Modify: `docs/review/findings.csv`

**Interfaces:**
- Consumes: el formato de Task 2, las filas de Task 3 (varias `decision` apuntan a ids `R1-*`).
- Produces: 57 filas en total. Task 5 las reconcilia.

- [ ] **Step 1: Agregar las 5 filas de decisiones nuestras que la ronda 2 revisó**

```csv
R2-DEC-synaptic,2,ultima/SEGUNDA_DEVOLUCION.md:2.1,"Retirar synaptic_compartment y tratar la etiqueta como sinónimo de postsynaptic_density",aplicado,"1.360 de 1.366 proteínas ya están en postsynaptic_density, pero 1.353 vienen de DrLLPS y solo 3 de CD-CODE: el solapamiento es ENTRE recursos y no intra-recurso como afirma el informe. Su segunda señal tampoco se sostiene: ninguna fila de CD-CODE lleva PMID en esta base (0 de 13.844). postsynaptic_density 4.478 -> 5.844","Se revierte R1-ACT-04. La conclusión sale reforzada: coincidencia entre recursos independientes es mejor evidencia que duplicación interna; §12.1",45102ca,-
R2-DEC-xybody,2,ultima/SEGUNDA_DEVOLUCION.md:2.2,"La devolución acepta que xy_body y sex_body son la misma estructura y que no corresponde crear barr_body",cerrado,-,"Sin acción: confirma lo aplicado en R1-ACT-05. No se remidió porque no hay cifra que remedir; §12.1",-,-
R2-DEC-ldcv,2,ultima/SEGUNDA_DEVOLUCION.md:2.3,"La devolución acepta conservar Large dense-core vesicles en chromogranin_condensate para no perder SEMG2",cerrado,-,"Sin acción: confirma lo aplicado en R1-EQ-ldcv; §12.1",-,-
R2-DEC-plantmtoc,2,ultima/SEGUNDA_DEVOLUCION.md:2.4,"Crear plant_mtoc y mover las 12 filas de Arabidopsis que el split fúngico dejó en centrosome",aplicado,"Las 12 son TUBG1, GCP3, GCP4, NEDD1, GIP1 (γ-TuRC), TON1A, TPX2, EB1A, EB1C, KIN14D, AAA1 (TON1/TRM) y TUBA1, que el informe omite; nucleación acentrosómica. centrosome 1.790 -> 1.778, plant_mtoc 12","Primer canónico que no existe en mlo_mapping.csv: build_db.py ahora arma el vocabulario leyendo también mlo_organism_scoped.csv; §12.2",45102ca,-
R2-DEC-axes,2,ultima/SEGUNDA_DEVOLUCION.md:3.5,"Cuatro ejes de categoría alcanzan: omitir functional_process deja sin clasificar solo liquid_dyrk3_speckle, midbody_granule y fip200_puncta",abierto,-,"Responde nuestra consulta §6.5 y abarata R1-ACT-06. La afirmación de los tres términos NO se verificó de nuestro lado",-,-
```

- [ ] **Step 2: Agregar las 10 filas de casos de revisión**

```csv
R2-ADJ-mitochondrial-cloud,2,ultima/review_cases_adjudicated.csv:Mitochondrial cloud,"'Mitochondrial cloud' -> balbiani_body es correcto: en ovocito de Xenopus la nube mitocondrial ES el cuerpo de Balbiani",abierto,-,"Cerrado como correcto por ellos, sin verificar de nuestro lado. Es el caso de mayor volumen: 598 de las 790 proteínas en revisión; §12.3",-,-
R2-ADJ-germ-granule,2,ultima/review_cases_adjudicated.csv:Germ granule,"'Germ granule' -> p_granule es correcto: osk, vas, tej, spn-E, me31B, tdrd6 son plasma germinal canónico",abierto,-,"Cerrado como correcto por ellos, sin verificar de nuestro lado. Cierra el merge que el dossier marcó como el que más quería que cuestionaran; §12.3",-,-
R2-ADJ-tip-body,2,ultima/review_cases_adjudicated.csv:+TIP body,"'+TIP body' -> spindle_apparatus es defendible aunque grueso: KAR9/BIM1/BIK1 y mal3/tea2/tip1 son complejos de rastreo de extremo más",abierto,-,"Cerrado como correcto por ellos, sin verificar de nuestro lado; §12.3",-,-
R2-ADJ-leucocyte,2,ultima/review_cases_adjudicated.csv:Leucocyte nuclear body,"'Leucocyte nuclear body' -> nuclear_body es correcto pero pierde el calificador de tipo celular",abierto,-,"Cerrado como correcto por ellos, sin verificar de nuestro lado. 'Leucocito' se recuperaría con el eje cell_type_context; §12.3",-,-
R2-ADJ-pcbp2,2,ultima/review_cases_adjudicated.csv:PCBP2 condensates,"'PCBP2 condensates' -> signaling_condensate es un error: DCP1A y DDX6 son cuerpo P y TIA1 es gránulo de estrés",aplicado,"5 filas: PCBP2, DCP1A, DDX6, TIA1 humanas más Pcbp2 de ratón; signaling_condensate 15 -> 10, cytoplasmic_rnp_granule 66 -> 71","A cytoplasmic_rnp_granule y no p_body: el conjunto mezcla ambas cosas y afirmar cuerpo P con TIA1 adentro sería más preciso de lo que el dato sostiene; §12.3",45102ca,-
R2-ADJ-risc,2,ultima/review_cases_adjudicated.csv:RISC complex,"'RISC complex' -> mirisc es nombre de complejo macromolecular y corresponde descartarlo",aplicado,"2 filas (AGO2, TNRC6B de PhasePro); verificado sin pérdida: mirisc conserva 8 filas y las mismas 2 proteínas por la etiqueta 'miRISC'","DISCARD. La afirmación de que domina el 100% del canónico es cierta en proteínas pero no en filas; §12.3",45102ca,-
R2-ADJ-perinucleolar,2,ultima/review_cases_adjudicated.csv:Peri-nucleolar condensate,"'Peri-nucleolar condensate' -> perinucleolar_compartment probablemente mal: HSP104 y SIS1 marcan el compartimiento yuxtanuclear de control de calidad en levadura",necesita_fuente,-,"6 proteínas, 75% del canónico destino. Requiere leer la publicación; §12.3",-,-
R2-ADJ-orc1,2,ultima/review_cases_adjudicated.csv:ORC1 bodies,"'ORC1 bodies' -> replication_compartment probablemente mal: SUV39H1, EZH2, CBX5 y DNMT1 son silenciamiento y heterocromatina",necesita_fuente,-,"Solo ORC1 encaja en replicación. Requiere leer la publicación; §12.3",-,-
R2-ADJ-receptor-cluster,2,ultima/review_cases_adjudicated.csv:Receptor cluster,"'Receptor cluster' -> signaling_cluster necesita split o descarte: mezcla sinapsis inmune, SNAREs de exocitosis y señalización antiviral",necesita_fuente,-,"24 proteínas, 63% del canónico destino; el caso de mayor volumen entre los que requieren la fuente. Requiere leer la publicación; §12.3",-,-
R2-ADJ-batch,2,ultima/review_cases_prioritized.csv,"Los 53 casos de revisión que siguen sin adjudicar, priorizados por volumen y por dominancia sobre el término destino",abierto,-,"Una sola fila y no 53: su archivo ya tiene columna adjudication propia, y duplicarlos sería la segunda verdad que el diseño evita. 109 proteínas en total; §12.3",-,-
```

- [ ] **Step 3: Agregar las 2 filas de ítems propios**

```csv
R2-OWN-psd-orphans,2,-,"Las 6 proteínas que quedaron sin cobertura al retirar synaptic_compartment: O43236, P17152, Q14DG7, Q5VSY0, Q6P995, Q9NQR7",abierto,"Las 6 no están en postsynaptic_density por ningún recurso; la devolución señala que una (TMEM11) es mitocondrial","Detectado al aplicar R2-DEC-synaptic. Merecen revisión aparte; §12.1",-,-
R2-OWN-annotations-indexes,2,-,"mlo_annotations no tiene índice ni en uniprot_id ni en unified_mlo",rechazado,"Una consulta con NOT EXISTS sobre la tabla tarda minutos; verificado contra el backup previo que los índices nunca existieron, así que es preexistente y no lo introdujo este trabajo","Fuera del alcance de la auditoría biológica. Se registra para que no se pierda ni se confunda con un pendiente de la auditoría; candidato si se mira performance de la API",-,-
```

- [ ] **Step 4: Validar**

Run: `python3 scripts/review_ledger.py --check`
Expected: `57 hallazgos en el libro`, sin violaciones, con: `aplicado 29`, `abierto 19`, `necesita_fuente 3`, `cerrado 2`, `refutado 2`, `superado 1`, `rechazado 1`, `verificado 0`.

- [ ] **Step 5: Correr los tests**

Run: `python3 -m pytest tests/ api/tests -q`
Expected: `176 passed`.

- [ ] **Step 6: Commit**

```bash
git add docs/review/findings.csv
git commit -m "docs: backfill round 2 and our own items into the ledger

Seventeen rows: the four decisions the review revisited plus the four-axis
answer, the nine adjudicated review cases, the 53 unadjudicated ones as a
single row pointing at their file, and two items that exist in no list at all.

The backfill surfaces something worth knowing: several round-2 claims were
never verified on our side — that four axes suffice, and the gene-list
reasoning behind the four cases closed as correct. Those sit at 'abierto',
which is the honest state, rather than being quietly treated as settled.

R2-OWN-annotations-indexes is recorded as 'rechazado' with its reason so a
preexisting performance gap discovered during this work does not get lost or
mistaken for an audit item."
```

---

### Task 5: Reconciliar contra la prosa

Es el criterio de aceptación del spec §5.2, y la task más probable de encontrar algo: si el libro y la prosa no coinciden, una de las dos está mal.

**Files:**
- Modify: `database/mappings/_archive/mlo_mapping_decisions.md` (solo si la reconciliación encuentra discrepancias)
- Modify: `docs/review/findings.csv` (idem)

**Interfaces:**
- Consumes: las 57 filas de Tasks 3 y 4.
- Produces: nada de código. Un libro y una prosa que dicen lo mismo.

- [ ] **Step 1: Sacar la lista de abiertos del libro**

Run: `python3 scripts/review_ledger.py --check`

Anotar la lista de `abierto` + `necesita_fuente` (22 filas esperadas).

- [ ] **Step 2: Sacar la lista de pendientes de la prosa**

Run: `sed -n '/### 11.6/,/^---$/p;/### 12.5/,$p' database/mappings/_archive/mlo_mapping_decisions.md`

- [ ] **Step 3: Comparar ítem por ítem y anotar cada discrepancia**

Para cada pendiente de la prosa, encontrar su fila en el libro. Para cada `abierto`/`necesita_fuente` del libro, encontrarlo en la prosa.

Discrepancias esperadas, porque el libro es más granular que la prosa:

- La prosa de §11.6 no menciona las acciones 12, 18, 20 ni 21b, que sí están abiertas.
- La prosa de §12.5 no menciona la mitad de la acción 1 que falta (`R1-ACT-01b`, la tabla de evidencia).
- Ningún párrafo menciona los ítems de `R2-OWN-*`.

**Cada discrepancia se resuelve en una sola dirección: el libro es la lista de la verdad, y la prosa se completa para coincidir.** La prosa nunca gana, porque su propósito es explicar el razonamiento y no llevar el inventario.

- [ ] **Step 4: Completar la prosa**

Agregar a §12.5 los pendientes que el libro tiene y la prosa no, con una línea cada uno y su `id` del libro entre paréntesis. Agregar al principio de §11.6 y §12.5 la misma línea:

```markdown
> El inventario completo y su estado vive en `docs/review/findings.csv`
> (`python3 scripts/review_ledger.py --check`). Esta sección explica el
> razonamiento; el libro lleva la cuenta.
```

- [ ] **Step 5: Verificar que coinciden**

Run: `python3 scripts/review_ledger.py --check`

Recorrer la lista de abiertos y confirmar que cada uno aparece ahora en §11.6 o §12.5.

- [ ] **Step 6: Correr los tests**

Run: `python3 -m pytest tests/ api/tests -q`
Expected: `176 passed`.

- [ ] **Step 7: Commit**

```bash
git add database/mappings/_archive/mlo_mapping_decisions.md docs/review/findings.csv
git commit -m "docs: reconcile the ledger against the prose that preceded it

The acceptance criterion for the backfill was that the ledger's open list
reproduce what §11.6 and §12.5 say in prose, on the grounds that a disagreement
means one of them is wrong. It did disagree, and the prose was the one missing
items: four open actions it never listed, half of action 1, and both items we
raised ourselves.

Resolved in one direction on purpose. The ledger is the inventory; the prose
explains reasoning. Both sections now point at the ledger for state."
```

---

## Self-Review

**Cobertura del spec:**

| Sección del spec | Task |
|---|---|
| §3.2 `findings.csv` y sus columnas | Task 2 Step 5, Tasks 3-4 |
| §3.3 los siete estados | Task 2 Step 4 (`STATES`, `NEEDS_VERIFICATION`, `NEEDS_DECISION`) |
| §3.4 `_meta` | Task 1 |
| §3.5 el script | Task 2 |
| §3.6 el test | Task 2 |
| §4 flujo | Task 2 Step 4 (`report()` imprime lo que va en el paquete) |
| §5 arranque | Tasks 3 y 4 |
| §5.1 los tres ítems sueltos | Task 3 Step 3 (Pol II), Task 4 Step 3 (los otros dos) |
| §5.2 criterio de aceptación | Task 5 |
| §6 casos borde | Task 2: `criterio` como valor de `verificado_como` (usado en `R1-ACT-13`), `origen` inexistente validado, prefijo de ronda en los `id` |

Sin huecos.

**Escaneo de placeholders:** las 57 filas están escritas, los cuatro archivos tienen su contenido completo, y cada step de código lleva su bloque. No hay "similar a la Task N".

**Consistencia de tipos:** `validate(rows, review_dir)` y `load(path)` se usan con esa firma en `tests/test_review_ledger.py`. `LEDGER_PATH` se importa del módulo. Los mensajes de violación del script coinciden literalmente con los fragmentos que el test parametrizado busca.
