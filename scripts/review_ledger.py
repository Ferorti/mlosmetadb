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
import re
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

# Siete clases. `ROL` se agregó junto con las filas R1-ROL-*: son hallazgos de
# role_model_findings.csv, un origen distinto del resto de INT (que viene de
# data_integrity_findings.csv). Forzarlas a INT mentiría sobre su procedencia.
CLASSES = frozenset({"ACT", "INT", "EQ", "DEC", "ADJ", "OWN", "ROL"})

# Estados que exigen que verificado_como diga algo. `refutado` está acá porque
# una refutación sin la medición que la sostiene no sirve de nada: las tres
# cifras que corregimos a la auditoría son entregables para ellos.
NEEDS_VERIFICATION = frozenset({"verificado", "refutado", "aplicado"})

# Estados en los que la columna decision no puede quedar vacía. `cerrado` está
# acá porque un ítem sin acción tiene que decir qué lo cierra: sin eso no se
# distingue de uno que nadie miró.
NEEDS_DECISION = frozenset({"rechazado", "superado", "cerrado"})

EMPTY = frozenset({"", "-"})

# Valores válidos de bloquea_publicacion.
BLOQUEA_VALUES = frozenset({"si", "no", "-"})

# blocks_publication (inglés, en el CSV de la auditoría) -> bloquea_publicacion
# (español, en el libro). Es la única columna copiada literalmente del CSV de
# ellos, así que es la que más fácil se desincroniza en silencio.
BLOCKS_MAP = {"yes": "si", "no": "no"}


def load(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != COLUMNS:
            raise ValueError(
                f"{path}: encabezado inválido — se esperaban {COLUMNS!r} "
                f"y se leyó {reader.fieldnames!r}"
            )
        return list(reader)


def _blank(value: str | None) -> bool:
    return (value or "").strip() in EMPTY


def _field_count(row: dict) -> int:
    """Cuenta los campos crudos que produjo csv.DictReader para esta fila.

    Una fila con más campos que encabezados (p. ej. una coma sin comillas en
    `decision`) desplaza `aplicado_en` y valida bien igual si solo se mira el
    diccionario final — es exactamente el bug de R1-ACT-19. DictReader guarda
    los campos de más bajo la clave `None` (restkey) y rellena con `None` los
    campos que faltan (restval), así que ninguno de los dos casos se puede ver
    revisando solo `COLUMNS`.
    """
    count = sum(1 for c in COLUMNS if row.get(c) is not None)
    extra = row.get(None)
    if isinstance(extra, list):
        count += len(extra)
    elif extra is not None:
        count += 1
    return count


def _load_action_matrix_blocks(review_dir: Path) -> dict[int, str] | None:
    """priority -> blocks_publication desde devolucion/action_matrix.csv.

    Devuelve None (en vez de lanzar) si el archivo no se puede leer: es el CSV
    de la auditoría, no un archivo nuestro, y su ausencia no debería tumbar
    --check.
    """
    path = review_dir / "devolucion" / "action_matrix.csv"
    try:
        with open(path, newline="", encoding="utf-8") as f:
            return {
                int(row["priority"]): (row["blocks_publication"] or "").strip()
                for row in csv.DictReader(f)
            }
    except (OSError, KeyError, ValueError):
        return None


def validate(rows: list[dict], review_dir: Path) -> list[str]:
    """Devuelve la lista de violaciones. Vacía significa libro válido."""
    violations: list[str] = []
    seen: set[str] = set()
    action_blocks = _load_action_matrix_blocks(review_dir)

    for row in rows:
        rid = (row.get("id") or "").strip()
        where = rid or "(fila sin id)"

        if not rid:
            violations.append("fila sin id")
        elif rid in seen:
            violations.append(f"{where}: id duplicado")
        seen.add(rid)

        n = _field_count(row)
        if n != len(COLUMNS):
            violations.append(f"{where}: fila con {n} campos y no {len(COLUMNS)}")

        parts = rid.split("-")
        if len(parts) < 3:
            violations.append(f"{where}: id no tiene forma R<ronda>-<clase>-<clave>")
        elif parts[1] not in CLASSES:
            violations.append(f"{where}: clase {parts[1]!r} no está en el conjunto cerrado")
        elif not "-".join(parts[2:]):
            violations.append(f"{where}: id con clave vacía")

        estado = (row.get("estado") or "").strip()
        if estado not in STATES:
            violations.append(f"{where}: estado {estado!r} no está en el conjunto cerrado")

        if estado in NEEDS_VERIFICATION and _blank(row.get("verificado_como")):
            violations.append(f"{where}: {estado} sin verificado_como")
        # Sin esto, una fila medida (verificado_como con contenido) puede
        # quedar en `abierto` y perder esa medición sin que nada lo note: es
        # justo lo que dejaba pasar a R1-ACT-14 con las cifras de reguladores
        # que motivan todo este diseño.
        if estado == "abierto" and not _blank(row.get("verificado_como")):
            violations.append(f"{where}: abierto con verificado_como — corresponde 'verificado'")
        if estado == "aplicado" and _blank(row.get("aplicado_en")):
            violations.append(f"{where}: aplicado sin aplicado_en")
        if estado in NEEDS_DECISION and _blank(row.get("decision")):
            violations.append(f"{where}: {estado} sin decision")

        origen = (row.get("origen") or "").strip()
        if origen not in EMPTY:
            rel = origen.split(":")[0]
            if not (review_dir / rel).exists():
                violations.append(f"{where}: origen apunta a un archivo que no existe ({rel})")

        bp = (row.get("bloquea_publicacion") or "").strip()
        if bp not in BLOQUEA_VALUES:
            violations.append(f"{where}: bloquea_publicacion {bp!r} no es 'si'/'no'/'-'")

        ronda_raw = (row.get("ronda") or "").strip()
        if not ronda_raw.isdigit() or int(ronda_raw) <= 0:
            violations.append(f"{where}: ronda {ronda_raw!r} no es un entero positivo")
        elif rid and not rid.startswith(f"R{ronda_raw}-"):
            violations.append(f"{where}: ronda {ronda_raw!r} no coincide con el prefijo R<ronda> del id")

        # bloquea_publicacion es la única columna copiada literalmente del CSV
        # de la auditoría; esto detecta que se desincronice de su fuente sin
        # que nadie se dé cuenta (el principio de §3.1: el libro referencia,
        # no duplica, y una copia que no se re-chequea es peor que no copiar).
        if action_blocks is not None and rid.startswith("R1-ACT-"):
            m = re.match(r"R1-ACT-(\d+)", rid)
            if m:
                prio = int(m.group(1))
                expected_raw = action_blocks.get(prio)
                expected = BLOCKS_MAP.get(expected_raw) if expected_raw is not None else None
                if expected is not None and bp != expected:
                    violations.append(
                        f"{where}: bloquea_publicacion={bp!r} no coincide con "
                        f"blocks_publication={expected_raw!r} de action_matrix.csv "
                        f"(prioridad {prio})"
                    )

    return violations


def report(rows: list[dict]) -> None:
    counts = Counter((r.get("estado") or "").strip() for r in rows)
    print(f"{len(rows)} hallazgos en el libro\n")
    for estado in sorted(STATES):
        print(f"  {estado:16} {counts.get(estado, 0)}")

    pending_states = ("abierto", "verificado", "necesita_fuente")
    pendientes = [r for r in rows if (r.get("estado") or "").strip() in pending_states]
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

    try:
        rows = load(LEDGER_PATH)
    except ValueError as e:
        print(f"[FATAL] {e}", file=sys.stderr)
        return 1

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
