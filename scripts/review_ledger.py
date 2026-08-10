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
