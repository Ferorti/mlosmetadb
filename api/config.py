import os
import sys
from pathlib import Path

_REFACTOR_ROOT = Path(__file__).resolve().parent.parent
if str(_REFACTOR_ROOT) not in sys.path:
    sys.path.insert(0, str(_REFACTOR_ROOT))

_default_db = Path(__file__).parent.parent / "database" / "mlosmetadb.db"
DB_PATH = Path(os.environ["MLOSMETADB_PATH"]) if "MLOSMETADB_PATH" in os.environ else _default_db

CORS_ORIGINS = [
    "https://mlos.leloir.org.ar",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8080",
]

DEFAULT_PAGE = 1
DEFAULT_PER_PAGE = 50
MAX_PER_PAGE = 200
DEFAULT_PPI_PER_PAGE = 50
