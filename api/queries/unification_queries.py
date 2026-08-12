"""Reads Phase 1's precomputed build artifacts (database/exports/) -- no SQL.

unification_stats.json is produced by scripts/build_unification_stats.py and
already covered by tests/test_unification_stats.py's invariants at the repo
root; this module does not re-validate or re-shape its contents, it only
reads the file and hands back the parsed dict (or None if the artifact
hasn't been built yet -- a normal state for a fresh checkout, not an error).
"""

import json
import logging
from pathlib import Path

from config import EXPORTS_DIR

logger = logging.getLogger(__name__)


def load_unification_stats() -> dict | None:
    path = EXPORTS_DIR / "unification_stats.json"
    if not path.exists():
        logger.warning("unification_stats.json not found at %s -- run scripts/build_unification_stats.py", path)
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to parse %s: %s", path, exc)
        return None


def discrepant_pairs_csv_path() -> Path:
    return EXPORTS_DIR / "discrepant_pairs.csv"


def mlo_term_mapping_csv_path() -> Path:
    return EXPORTS_DIR / "mlo_term_mapping.csv"
