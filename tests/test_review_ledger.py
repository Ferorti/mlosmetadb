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
    "fila sin id",
    "id no tiene forma R<ronda>-<clase>-<clave>",
    "id con clave vacía",
    "abierto con verificado_como — corresponde 'verificado'",
    "fila con 10 campos y no 9",
    "bloquea_publicacion 'quizas' no es 'si'/'no'/'-'",
    "ronda 'abc' no es un entero positivo",
    "ronda '1' no coincide con el prefijo R<ronda> del id",
    "no coincide con blocks_publication",
])
def test_validation_catches_each_kind_of_break(fragment):
    rows = review_ledger.load(FIXTURES / "findings_invalid.csv")
    violations = "\n".join(review_ledger.validate(rows, ROOT / "docs" / "review"))
    assert fragment in violations


def test_bad_header_raises():
    with pytest.raises(ValueError, match="encabezado inválido"):
        review_ledger.load(FIXTURES / "findings_bad_header.csv")
