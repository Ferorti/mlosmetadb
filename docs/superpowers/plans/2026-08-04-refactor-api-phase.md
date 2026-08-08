# Refactor `api/` Phase Implementation Plan

> **Correction (2026-08-08).** This document treats `PhaseDB` and `PhasePDB`
> as two source databases (or counts six sources where there are five). They
> were two ingestion tags for one resource, **PhaSepDB**, whose two parsers
> read byte-identical copies of the same export files — so every PhaSepDB
> annotation was loaded twice. The document is left as written because it
> records a past design decision; the tags no longer exist in the data. See
> `docs/issues/001-phasedb-phasepdb-duplicate-ingestion.md`.


> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the existing, working `api/` FastAPI backend into `refactor/api/`, fixing the schema-drift bugs it has against the corrected `refactor/database/mlosmetadb.db` (missing `dataset_active` filtering, a role-normalization bug, and a matching aggregation gap in `build_summary.py`) via one new shared policy module, then update docs to match the corrected end state.

**Architecture:** Straight directory port (`api/` → `refactor/api/`, same `main.py`/`config.py`/`database.py`/`models/`/`queries/`/`routers/` layout, no restructuring). A new `refactor/policy.py` module becomes the single place that encodes "what counts as visible in the served dataset," imported by both `refactor/api/queries/*.py` (live request-time filtering) and `refactor/scripts/build_summary.py` (materialized `protein_summary` aggregation), replacing several independent, duplicated, and in one case actively-wrong pieces of filtering logic.

**Tech Stack:** Python 3.11+, FastAPI 0.111+, `aiosqlite`, Pydantic v2, raw SQL (no ORM), `sqlite3` (build_summary.py), `pytest` (no `pytest-asyncio` — async query functions are exercised via `asyncio.run()` inside plain sync test functions).

## Global Constraints

- **Hard rule of the whole `refactor/` effort**: nothing outside `refactor/` is ever modified. The original `api/` at the repo root is read-only source; it is copied from, never edited.
- **`dataset_active` domain rule** (from `docs/superpowers/specs/2026-08-04-refactor-api-phase-design.md`): `dataset_active=0` is reserved only for deliberate scope exclusions (today: DrLLPS Regulator rows). A `NULL` `unified_role` or indeterminate MLO is an annotation gap, never a reason to exclude — those rows stay `dataset_active=1` and fully visible (no role badge, per `frontend/CLAUDE.md`), never dropped.
- **No role-string remapping**: `unified_role` is passed through the API exactly as stored (`'driver'` / `'client'` / `None`). Never rewritten to `'component'`, `'unmapped'`, or any other placeholder in a *response field*. (The `role=component` *query parameter* convention, meaning "filter to not-driver," is a pre-existing, separate, and still-valid mechanism — it is not touched by this plan.)
- **Test-before-batch / verification-before-completion**: every fix in this plan is proven with a failing-then-passing test before being declared done, and the final phase is proven end-to-end against the real DB with the project's standard `TEST_PROTEINS` set before any doc claims "done."
- **`refactor/policy.py` is the only place that encodes serving policy.** No query file may hardcode `dataset_active` filtering or MLO-category exclusion independently of it.

---

## File Structure

```
refactor/
├── policy.py                         # NEW — shared serving-policy module
├── tests/
│   └── test_policy.py                # NEW
├── api/                               # NEW — ported from repo-root api/
│   ├── main.py                        # ported + fixed (_compute_stats, import policy)
│   ├── config.py                      # ported unchanged (path math already resolves correctly)
│   ├── database.py                    # ported unchanged
│   ├── requirements.txt                # ported unchanged
│   ├── CLAUDE.md                       # NEW (not copied from api/CLAUDE_api.md)
│   ├── API_EXAMPLES.md                 # NEW (not copied from api/API_EXAMPLES.md)
│   ├── models/
│   │   └── schemas.py                  # ported unchanged (no model shape changes needed)
│   ├── queries/
│   │   ├── mlo_queries.py              # ported + fixed
│   │   ├── protein_queries.py          # ported + fixed
│   │   └── search_queries.py           # ported + fixed
│   ├── routers/
│   │   ├── mlos.py                     # ported + fixed (_normalize_role removed)
│   │   ├── proteins.py                 # ported + fixed (_normalize_role removed)
│   │   ├── search.py                   # ported unchanged
│   │   ├── stats.py                    # ported unchanged
│   │   └── organisms.py                # ported unchanged
│   └── tests/
│       ├── conftest.py                 # NEW — sys.path + in-memory test_db fixture
│       ├── test_mlo_queries.py         # NEW
│       ├── test_protein_queries.py     # NEW
│       ├── test_search_queries.py      # NEW
│       └── test_stats.py               # NEW
├── scripts/
│   └── build_summary.py                # already ported (Entry 2) — fixed here
└── REFACTOR_LOG.md                     # Entry 11 appended
```

---

### Task 1: Port `api/` → `refactor/api/`

**Files:**
- Create: `refactor/api/` (entire tree copied from `api/`)
- Test: manual verification steps below (no automated test framework needed for a pure copy)

**Interfaces:**
- Produces: a working `refactor/api/` tree, importable exactly like the original (`main.py` as ASGI entrypoint, `config.DB_PATH` resolving to `refactor/database/mlosmetadb.db` with zero code changes).

- [ ] **Step 1: Copy the tree, excluding dead/stale files**

```bash
mkdir -p refactor/api
rsync -a \
  --exclude='__pycache__' \
  --exclude='mlosmetadb.db' \
  --exclude='CLAUDE_api.md' \
  --exclude='API_EXAMPLES.md' \
  api/ refactor/api/
```

`mlosmetadb.db` here is the dead 0-byte file at `api/mlosmetadb.db` (not the real DB, which lives under `database/`). `CLAUDE_api.md`/`API_EXAMPLES.md` are excluded because they document the old, uncorrected behavior (stale `"unified_role": "unmapped"` examples, stale casing claims) — Task 10 writes fresh replacements from scratch rather than editing these forward.

- [ ] **Step 2: Verify the copy is complete and nothing extra came along**

```bash
diff -rq api/ refactor/api/ \
  --exclude=__pycache__ --exclude=mlosmetadb.db \
  --exclude=CLAUDE_api.md --exclude=API_EXAMPLES.md --exclude=static
```

Expected: no output (identical trees modulo the four excluded paths and `api/static/` which doesn't need porting yet — no frontend build exists under `refactor/` this phase).

- [ ] **Step 3: Confirm `config.py`'s path math resolves to the new DB with no edits**

```bash
cd refactor/api && python3 -c "from config import DB_PATH; print(DB_PATH)"
```

Expected output: an absolute path ending in `refactor/database/mlosmetadb.db`. This works unmodified because `config.py` computes `Path(__file__).parent.parent / "database" / "mlosmetadb.db"` — moving the whole `api/` directory one level deeper (into `refactor/`) automatically re-resolves this to the sibling `refactor/database/`. **Do not add a code change here if this already prints the right path** — that would be an unnecessary edit to code that already does the right thing by construction.

- [ ] **Step 4: Boot-smoke-test against a tiny throwaway DB (not the full 240MB+ one)**

```bash
cd refactor/api
python3 - <<'EOF'
import sqlite3, tempfile, os

path = os.path.join(tempfile.mkdtemp(), "smoke.db")
conn = sqlite3.connect(path)
conn.executescript("""
    CREATE TABLE proteins (uniprot_id TEXT PRIMARY KEY, gene_name TEXT, protein_name TEXT,
        organism TEXT, taxon_id INTEGER, length INTEGER, reviewed INTEGER,
        disorder_mobidb_lite_dc REAL, disorder_alphafold_dc REAL);
    CREATE TABLE mlo_vocabulary (unified_mlo TEXT PRIMARY KEY, category TEXT);
    CREATE TABLE mlo_annotations (id INTEGER PRIMARY KEY AUTOINCREMENT, uniprot_id TEXT,
        source_db TEXT, source_mlo TEXT, unified_mlo TEXT, source_role TEXT,
        unified_role TEXT, dataset_active INTEGER NOT NULL DEFAULT 1, evidence TEXT);
    CREATE TABLE mlo_definitions (id INTEGER PRIMARY KEY AUTOINCREMENT, unified_mlo TEXT,
        source_db TEXT, source_name TEXT, definition TEXT);
    CREATE TABLE sequence_features (id INTEGER PRIMARY KEY AUTOINCREMENT, uniprot_id TEXT,
        feature_type TEXT, source TEXT, label TEXT, accession TEXT, start INTEGER,
        end INTEGER, score REAL, metadata TEXT);
    CREATE TABLE protein_summary (uniprot_id TEXT PRIMARY KEY, idr_regions TEXT,
        lcr_regions TEXT, domains TEXT, has_driver INTEGER, has_client INTEGER,
        source_db_count INTEGER, mlo_count INTEGER, mlos TEXT, source_dbs TEXT);
    CREATE TABLE ppi (id INTEGER PRIMARY KEY AUTOINCREMENT, uniprot_id_a TEXT,
        uniprot_id_b TEXT, in_db INTEGER DEFAULT 0, experimental_system TEXT,
        throughput TEXT, organism_id_a INTEGER, organism_id_b INTEGER, pubmed_id TEXT,
        source_version TEXT);
    CREATE TABLE orthologs (id INTEGER PRIMARY KEY AUTOINCREMENT, uniprot_id TEXT,
        ortholog_id TEXT, organism TEXT, taxon_id INTEGER, og_id TEXT,
        in_db INTEGER DEFAULT 0, source TEXT, source_version TEXT);
    CREATE TABLE ortholog_meta (ortholog_id TEXT PRIMARY KEY, gene_name TEXT,
        protein_name TEXT, organism TEXT, taxon_id INTEGER, length INTEGER,
        disorder_mobidb_lite_dc REAL, disorder_alphafold_dc REAL, sequence TEXT);
    CREATE TABLE ortholog_features (id INTEGER PRIMARY KEY AUTOINCREMENT, ortholog_id TEXT,
        feature_type TEXT, source TEXT, label TEXT, accession TEXT, start INTEGER,
        end INTEGER, score REAL, metadata TEXT);
""")
conn.commit()
conn.close()
print(path)
EOF
```

Copy the printed path, then:

```bash
cd refactor/api
MLOSMETADB_PATH=<paste the printed path here> python3 -c "
from fastapi.testclient import TestClient
from main import app

with TestClient(app) as client:
    r = client.get('/stats')
    assert r.status_code == 200, r.text
    print('boot OK, /stats ->', r.json())
"
```

Expected: `boot OK, /stats -> {...}` with all-zero counts (empty DB) and no traceback. `TestClient(app)` as a context manager triggers the FastAPI `lifespan` (so `database.open_db()`/`setup_fts5()` actually run against the throwaway DB) — this is a real boot test, not just an import check.

- [ ] **Step 5: Commit**

```bash
git add refactor/api
git commit -m "$(cat <<'EOF'
refactor: port api/ into refactor/api/ (unmodified copy)

Straight copy of the working FastAPI backend, excluding the dead
api/mlosmetadb.db and the stale api/CLAUDE_api.md / API_EXAMPLES.md
(replaced with fresh docs once the schema-drift fixes land). No code
changes yet — config.py's DB_PATH already resolves correctly to
refactor/database/mlosmetadb.db by construction.
EOF
)"
```

---

### Task 2: `refactor/policy.py` — shared serving-policy module

**Files:**
- Create: `refactor/policy.py`
- Test: `refactor/tests/test_policy.py`

**Interfaces:**
- Produces: `active_annotation_clause(alias: str = "ma") -> str`,
  `excluded_mlo_category_clause(alias: str = "mv") -> tuple[str | None, list[str]]`,
  `EXCLUDED_MLO_CATEGORIES: list[str]` — consumed by every task from here on.

- [ ] **Step 1: Write the failing tests**

`refactor/tests/test_policy.py`:
```python
import sys
from pathlib import Path

REFACTOR_ROOT = Path(__file__).resolve().parent.parent
if str(REFACTOR_ROOT) not in sys.path:
    sys.path.insert(0, str(REFACTOR_ROOT))

from policy import (
    EXCLUDED_MLO_CATEGORIES,
    active_annotation_clause,
    excluded_mlo_category_clause,
)


def test_active_annotation_clause_default_alias():
    assert active_annotation_clause() == "ma.dataset_active = 1"


def test_active_annotation_clause_custom_alias():
    assert active_annotation_clause("x") == "x.dataset_active = 1"
    assert active_annotation_clause("ma2") == "ma2.dataset_active = 1"


def test_excluded_mlo_categories_empty_by_default():
    assert EXCLUDED_MLO_CATEGORIES == []


def test_excluded_mlo_category_clause_is_noop_by_default():
    clause, params = excluded_mlo_category_clause("mv")
    assert clause is None
    assert params == []


def test_excluded_mlo_category_clause_when_configured(monkeypatch):
    monkeypatch.setattr("policy.EXCLUDED_MLO_CATEGORIES", ["Unspecified"])
    clause, params = excluded_mlo_category_clause("mv")
    assert clause == "mv.category NOT IN (?)"
    assert params == ["Unspecified"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /biodata/forti/proyectos/mlos/mlosmetadb
python3 -m pytest refactor/tests/test_policy.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'policy'` (the file doesn't exist yet).

- [ ] **Step 3: Write `refactor/policy.py`**

```python
"""Shared serving policy for MLOsMetaDB.

Single source of truth for what counts as "active"/visible in the served
dataset, as distinct from the raw provenance data in mlosmetadb.db.
Imported by both refactor/api/ (live request-time queries) and
refactor/scripts/build_summary.py (materialized protein_summary
aggregation) so that a policy change only has to happen in one file.

Domain rule (see docs/superpowers/specs/2026-08-04-refactor-api-phase-design.md
and REFACTOR_LOG.md Entry 4/11): dataset_active=0 is reserved for
deliberate scope exclusions where inclusion is biologically debatable
(today: DrLLPS Regulator rows). A NULL unified_role or indeterminate MLO
name is an annotation gap, never a reason to exclude -- those rows always
stay dataset_active=1 and fully visible.
"""


def active_annotation_clause(alias: str = "ma") -> str:
    """SQL boolean expression, true iff an mlo_annotations row counts
    toward the served/default dataset. Use as a JOIN ON condition or a
    WHERE conjunct wherever mlo_annotations is queried."""
    return f"{alias}.dataset_active = 1"


EXCLUDED_MLO_CATEGORIES: list[str] = []
"""mlo_vocabulary.category values excluded from /mlos listings by default.

Empty today: the 'Unspecified' (NotInformed) bucket is intentionally left
unfiltered per explicit user decision (2026-08-04, see the design spec).
Change this list -- and refactor/api/CLAUDE.md's policy section -- if that
decision changes; no query file should hardcode category-based filtering
independently of this."""


def excluded_mlo_category_clause(alias: str = "mv") -> tuple[str | None, list[str]]:
    """Returns (sql_clause, params) for excluding EXCLUDED_MLO_CATEGORIES,
    or (None, []) when there's nothing to exclude (today's default) --
    callers must skip adding the clause entirely when it's None, rather
    than appending a dead 'AND 1=1'-style no-op to every query."""
    if not EXCLUDED_MLO_CATEGORIES:
        return None, []
    placeholders = ",".join("?" * len(EXCLUDED_MLO_CATEGORIES))
    return f"{alias}.category NOT IN ({placeholders})", list(EXCLUDED_MLO_CATEGORIES)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest refactor/tests/test_policy.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add refactor/policy.py refactor/tests/test_policy.py
git commit -m "$(cat <<'EOF'
feat: add refactor/policy.py shared serving-policy module

Single source of truth for dataset_active filtering and MLO-category
exclusion, to be imported by both refactor/api/ and
refactor/scripts/build_summary.py in the following tasks.
EOF
)"
```

---

### Task 3: Fix `refactor/api/queries/mlo_queries.py`

**Files:**
- Modify: `refactor/api/queries/mlo_queries.py`
- Test: `refactor/api/tests/conftest.py` (new — shared fixture for this and all remaining query-file tasks), `refactor/api/tests/test_mlo_queries.py` (new)

**Interfaces:**
- Consumes: `policy.active_annotation_clause`, `policy.excluded_mlo_category_clause` (Task 2).
- Produces: no change to the public signatures of `get_mlo_meta`, `get_mlo_definitions`, `get_mlo_stats`, `get_mlo_proteins_page`, `get_all_mlos`, `get_definitions_for_mlos` — only their SQL bodies change. Later tasks and routers keep calling them exactly as before.

- [ ] **Step 1: Write `refactor/api/tests/conftest.py`**

```python
import asyncio
import sqlite3
import sys
from pathlib import Path

import aiosqlite
import pytest

API_ROOT = Path(__file__).resolve().parent.parent      # refactor/api/
REFACTOR_ROOT = API_ROOT.parent                          # refactor/
for p in (str(API_ROOT), str(REFACTOR_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import database as db_module

SCHEMA = """
CREATE TABLE proteins (
    uniprot_id TEXT PRIMARY KEY, gene_name TEXT, protein_name TEXT,
    organism TEXT, taxon_id INTEGER, length INTEGER, reviewed INTEGER,
    disorder_mobidb_lite_dc REAL, disorder_alphafold_dc REAL
);
CREATE TABLE mlo_vocabulary (unified_mlo TEXT PRIMARY KEY, category TEXT);
CREATE TABLE mlo_annotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT, uniprot_id TEXT NOT NULL,
    source_db TEXT NOT NULL, source_mlo TEXT, unified_mlo TEXT NOT NULL,
    source_role TEXT, unified_role TEXT,
    dataset_active INTEGER NOT NULL DEFAULT 1, evidence TEXT
);
CREATE TABLE mlo_definitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, unified_mlo TEXT NOT NULL,
    source_db TEXT NOT NULL, source_name TEXT, definition TEXT
);
CREATE TABLE protein_summary (
    uniprot_id TEXT PRIMARY KEY, idr_regions TEXT, lcr_regions TEXT, domains TEXT,
    has_driver INTEGER, has_client INTEGER, source_db_count INTEGER,
    mlo_count INTEGER, mlos TEXT, source_dbs TEXT
);
CREATE TABLE ppi (
    id INTEGER PRIMARY KEY AUTOINCREMENT, uniprot_id_a TEXT, uniprot_id_b TEXT,
    in_db INTEGER DEFAULT 0, experimental_system TEXT, pubmed_id TEXT,
    source_version TEXT
);
CREATE TABLE sequence_features (
    id INTEGER PRIMARY KEY AUTOINCREMENT, uniprot_id TEXT, feature_type TEXT,
    source TEXT, label TEXT, accession TEXT, start INTEGER, end INTEGER,
    score REAL, metadata TEXT
);
"""

# Fixture data, mirroring the project's standard test-protein convention:
# - P35637 (FUS): one ACTIVE driver annotation in stress_granule via PhaseDB.
# - QREG01 (synthetic): ONLY an INACTIVE DrLLPS-Regulator annotation in
#   nucleolus -- the case that must be invisible everywhere after the fix.
FIXTURE = """
INSERT INTO proteins (uniprot_id, gene_name, organism, length) VALUES
    ('P35637', 'FUS', 'Homo sapiens', 526),
    ('QREG01', 'REGTEST', 'Homo sapiens', 100);

INSERT INTO mlo_vocabulary (unified_mlo, category) VALUES
    ('stress_granule', 'Cytoplasmic'),
    ('nucleolus', 'Nuclear');

INSERT INTO mlo_annotations (uniprot_id, source_db, unified_mlo, unified_role, dataset_active) VALUES
    ('P35637', 'PhaseDB', 'stress_granule', 'driver', 1);

INSERT INTO mlo_annotations (uniprot_id, source_db, unified_mlo, unified_role, dataset_active) VALUES
    ('QREG01', 'DrLLPS', 'nucleolus', NULL, 0);

INSERT INTO protein_summary (uniprot_id, has_driver, has_client, source_db_count, mlo_count, mlos, source_dbs) VALUES
    ('P35637', 1, 0, 1, 1, '["stress_granule"]', 'PhaseDB'),
    ('QREG01', 0, 0, 0, 0, NULL, NULL);
"""


@pytest.fixture
def test_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    conn.executescript(FIXTURE)
    conn.commit()
    conn.close()

    async def _open():
        db_module._db = await aiosqlite.connect(db_path)
        db_module._db.row_factory = aiosqlite.Row

    async def _close():
        await db_module._db.close()

    asyncio.run(_open())
    yield db_path
    asyncio.run(_close())
    db_module._db = None
```

- [ ] **Step 2: Write the failing tests**

`refactor/api/tests/test_mlo_queries.py`:
```python
import asyncio

import policy
from queries.mlo_queries import get_all_mlos, get_mlo_proteins_page, get_mlo_stats


def test_get_mlo_stats_excludes_inactive_only_protein(test_db):
    stats = asyncio.run(get_mlo_stats("nucleolus"))
    assert stats["total_proteins"] == 0
    assert stats["by_source"] == {}


def test_get_mlo_stats_counts_active_protein(test_db):
    stats = asyncio.run(get_mlo_stats("stress_granule"))
    assert stats["total_proteins"] == 1
    assert stats["by_source"] == {"PhaseDB": 1}
    assert stats["by_role"] == {"driver": 1}


def test_get_mlo_proteins_page_excludes_inactive_only_protein(test_db):
    total, rows = asyncio.run(get_mlo_proteins_page("nucleolus", None, None, None, 1, 50))
    assert total == 0
    assert rows == []


def test_get_all_mlos_shows_zero_count_for_inactive_only_mlo(test_db):
    rows = asyncio.run(get_all_mlos(category=None))
    by_mlo = {r["unified_mlo"]: r for r in rows}
    assert by_mlo["stress_granule"]["protein_count"] == 1
    # nucleolus's only annotation is inactive -- it must still be listed
    # (mlo_vocabulary entry exists) but with a zero protein_count, not
    # disappear and not count the inactive row.
    assert by_mlo["nucleolus"]["protein_count"] == 0


def test_excluded_mlo_category_clause_wired_into_get_all_mlos(test_db, monkeypatch):
    monkeypatch.setattr(policy, "EXCLUDED_MLO_CATEGORIES", ["Nuclear"])
    rows = asyncio.run(get_all_mlos(category=None))
    names = {r["unified_mlo"] for r in rows}
    assert "nucleolus" not in names       # category='Nuclear', now excluded
    assert "stress_granule" in names      # category='Cytoplasmic', unaffected
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd refactor/api
python3 -m pytest tests/test_mlo_queries.py -v
```

Expected: FAILs — `get_mlo_stats("nucleolus")` currently returns `total_proteins == 1` (counts the inactive row), and `test_excluded_mlo_category_clause_wired_into_get_all_mlos` fails because `get_all_mlos` never calls `excluded_mlo_category_clause`.

- [ ] **Step 4: Fix `refactor/api/queries/mlo_queries.py`**

Add at the top of the file:
```python
import policy
from database import fetchone, fetchall, fetchval
```

Replace `get_mlo_stats`:
```python
async def get_mlo_stats(unified_mlo: str) -> dict:
    active = policy.active_annotation_clause("ma")

    total = await fetchval(
        f"SELECT COUNT(DISTINCT ma.uniprot_id) FROM mlo_annotations ma WHERE ma.unified_mlo = ? AND {active}",
        (unified_mlo,),
    ) or 0

    source_rows = await fetchall(
        f"""
        SELECT ma.source_db, COUNT(DISTINCT ma.uniprot_id) AS cnt
        FROM mlo_annotations ma
        WHERE ma.unified_mlo = ? AND {active}
        GROUP BY ma.source_db
        """,
        (unified_mlo,),
    )
    by_source = {r["source_db"]: r["cnt"] for r in source_rows}

    role_rows = await fetchall(
        f"""
        SELECT
            CASE WHEN LOWER(ma.unified_role) = 'driver' THEN 'driver' ELSE 'component' END AS role,
            COUNT(DISTINCT ma.uniprot_id) AS cnt
        FROM mlo_annotations ma
        WHERE ma.unified_mlo = ? AND {active}
        GROUP BY role
        """,
        (unified_mlo,),
    )
    by_role = {r["role"]: r["cnt"] for r in role_rows}

    org_rows = await fetchall(
        f"""
        SELECT DISTINCT p.organism
        FROM mlo_annotations ma
        JOIN proteins p ON ma.uniprot_id = p.uniprot_id
        WHERE ma.unified_mlo = ? AND {active}
        ORDER BY p.organism
        """,
        (unified_mlo,),
    )
    organisms = [r["organism"] for r in org_rows if r["organism"]]

    return {
        "total_proteins": total,
        "by_source": by_source,
        "by_role": by_role,
        "organisms": organisms,
    }
```

Replace `get_mlo_proteins_page`:
```python
async def get_mlo_proteins_page(
    unified_mlo: str,
    organism: str | None,
    role: str | None,
    source_db: str | None,
    page: int,
    per_page: int,
) -> tuple[int, list[dict]]:
    active = policy.active_annotation_clause("ma")
    conditions = ["ma.unified_mlo = ?", active]
    params: list = [unified_mlo]

    if organism:
        conditions.append("LOWER(p.organism) = LOWER(?)")
        params.append(organism)
    if role:
        if role.lower() == "component":
            conditions.append("LOWER(ma.unified_role) != 'driver'")
        else:
            conditions.append("LOWER(ma.unified_role) = LOWER(?)")
            params.append(role)
    if source_db:
        conditions.append("ma.source_db = ?")
        params.append(source_db)

    where = "WHERE " + " AND ".join(conditions)

    total = await fetchval(
        f"SELECT COUNT(DISTINCT ma.uniprot_id) FROM mlo_annotations ma JOIN proteins p ON ma.uniprot_id = p.uniprot_id {where}",
        tuple(params),
    ) or 0

    offset = (page - 1) * per_page
    rows = await fetchall(
        f"""
        WITH filtered AS (
            SELECT DISTINCT ma.uniprot_id
            FROM mlo_annotations ma
            JOIN proteins p ON ma.uniprot_id = p.uniprot_id
            {where}
            ORDER BY ma.uniprot_id
            LIMIT ? OFFSET ?
        )
        SELECT p.uniprot_id, p.gene_name, p.organism,
               p.disorder_mobidb_lite_dc, p.disorder_alphafold_dc,
               ps.idr_regions, ps.lcr_regions, ps.domains,
               MAX(ma.unified_role) AS unified_role,
               GROUP_CONCAT(DISTINCT ma.source_db) AS sources_concat
        FROM filtered f
        JOIN proteins p          ON p.uniprot_id  = f.uniprot_id
        JOIN protein_summary ps  ON ps.uniprot_id = f.uniprot_id
        JOIN mlo_annotations ma  ON ma.uniprot_id = f.uniprot_id AND ma.unified_mlo = ? AND {active}
        GROUP BY f.uniprot_id
        ORDER BY f.uniprot_id
        """,
        tuple(params) + (per_page, offset, unified_mlo),
    )
    return total, rows
```

Replace `get_all_mlos`:
```python
async def get_all_mlos(
    category: str | None,
    source_db: str | None = None,
    organism: str | None = None,
    q: str | None = None,
) -> list[dict]:
    active_ma = policy.active_annotation_clause("ma")
    active_x = policy.active_annotation_clause("x")
    excluded_clause, excluded_params = policy.excluded_mlo_category_clause("mv")

    conditions: list[str] = []
    params: list = []

    if excluded_clause:
        conditions.append(excluded_clause)
        params.extend(excluded_params)
    if category:
        conditions.append("mv.category = ?")
        params.append(category)
    if q:
        conditions.append("LOWER(mv.unified_mlo) LIKE LOWER(?)")
        params.append(f"%{q}%")
    if source_db:
        conditions.append(
            f"EXISTS (SELECT 1 FROM mlo_annotations x WHERE x.unified_mlo = mv.unified_mlo AND x.source_db = ? AND {active_x})"
        )
        params.append(source_db)
    if organism:
        conditions.append(
            "EXISTS ("
            "SELECT 1 FROM mlo_annotations x "
            "JOIN proteins p ON x.uniprot_id = p.uniprot_id "
            f"WHERE x.unified_mlo = mv.unified_mlo AND LOWER(p.organism) = LOWER(?) AND {active_x}"
            ")"
        )
        params.append(organism)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    return await fetchall(
        f"""
        SELECT mv.unified_mlo, mv.category,
               COUNT(DISTINCT ma.uniprot_id) AS protein_count,
               COUNT(DISTINCT CASE WHEN LOWER(ma.unified_role) = 'driver' THEN ma.uniprot_id END) AS driver_count,
               GROUP_CONCAT(DISTINCT ma.source_db) AS sources_concat
        FROM mlo_vocabulary mv
        LEFT JOIN mlo_annotations ma ON mv.unified_mlo = ma.unified_mlo AND {active_ma}
        {where}
        GROUP BY mv.unified_mlo, mv.category
        ORDER BY mv.unified_mlo
        """,
        tuple(params),
    )
```

`get_mlo_meta`, `get_mlo_definitions`, `get_definitions_for_mlos` are unchanged (they never touch `mlo_annotations`).

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd refactor/api
python3 -m pytest tests/test_mlo_queries.py -v
```

Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add refactor/api/queries/mlo_queries.py refactor/api/tests/
git commit -m "$(cat <<'EOF'
fix: apply dataset_active + MLO-category policy to mlo_queries.py

get_mlo_stats, get_mlo_proteins_page, and get_all_mlos now exclude
mlo_annotations rows with dataset_active=0 (e.g. DrLLPS Regulator) via
the shared refactor/policy.py module, instead of silently counting them.
get_all_mlos also wires in policy.excluded_mlo_category_clause as a
no-op extension point for future MLO-category filtering.
EOF
)"
```

---

### Task 4: Fix `refactor/api/queries/protein_queries.py`

**Files:**
- Modify: `refactor/api/queries/protein_queries.py`
- Test: `refactor/api/tests/test_protein_queries.py` (new)

**Interfaces:**
- Consumes: `policy.active_annotation_clause` (Task 2), `test_db` fixture (Task 3's `conftest.py`).
- Produces: no signature changes to `get_proteins_page`, `get_proteins_facets`, `get_protein_mlo_annotations`.

- [ ] **Step 1: Write the failing tests**

`refactor/api/tests/test_protein_queries.py`:
```python
import asyncio

from queries.protein_queries import (
    get_protein_mlo_annotations,
    get_proteins_facets,
    get_proteins_page,
)


def test_get_protein_mlo_annotations_excludes_inactive_row(test_db):
    rows = asyncio.run(get_protein_mlo_annotations("QREG01"))
    assert rows == []


def test_get_protein_mlo_annotations_includes_active_row(test_db):
    rows = asyncio.run(get_protein_mlo_annotations("P35637"))
    assert len(rows) == 1
    assert rows[0]["unified_mlo"] == "stress_granule"
    assert rows[0]["unified_role"] == "driver"


def test_get_proteins_page_role_filter_excludes_inactive_only_protein(test_db):
    total, rows = asyncio.run(
        get_proteins_page(None, None, "nucleolus", None, None, None, None, "asc", 1, 50)
    )
    assert total == 0
    assert rows == []


def test_get_proteins_facets_mlo_facet_excludes_inactive_annotation(test_db):
    facets = asyncio.run(get_proteins_facets(None, None, None, None, None, None))
    assert facets["by_mlo"].get("nucleolus") is None
    assert facets["by_mlo"].get("stress_granule") == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd refactor/api
python3 -m pytest tests/test_protein_queries.py -v
```

Expected: FAILs — `get_protein_mlo_annotations("QREG01")` currently returns the inactive row, and the `mlo`-filtered `get_proteins_page`/facets queries currently match on it too.

- [ ] **Step 3: Fix `refactor/api/queries/protein_queries.py`**

Add at the top:
```python
import policy
from database import fetchone, fetchall, fetchval
```

In `get_proteins_page`, change:
```python
    from_clause = "FROM proteins p"
    if needs_mlo:
        from_clause += " JOIN mlo_annotations ma ON p.uniprot_id = ma.uniprot_id"
```
to:
```python
    from_clause = "FROM proteins p"
    if needs_mlo:
        active = policy.active_annotation_clause("ma")
        from_clause += f" JOIN mlo_annotations ma ON p.uniprot_id = ma.uniprot_id AND {active}"
```

In `get_proteins_facets`, apply the identical change to its own `from_clause` block:
```python
    from_clause = "FROM proteins p"
    if needs_mlo:
        active = policy.active_annotation_clause("ma")
        from_clause += f" JOIN mlo_annotations ma ON p.uniprot_id = ma.uniprot_id AND {active}"
```
and change its `mlo_rows` query:
```python
    mlo_rows = await fetchall(
        f"""
        SELECT ma2.unified_mlo, COUNT(DISTINCT ma2.uniprot_id) AS cnt
        FROM ({base_cte}) f
        JOIN mlo_annotations ma2 ON ma2.uniprot_id = f.uniprot_id AND {policy.active_annotation_clause("ma2")}
        GROUP BY ma2.unified_mlo
        ORDER BY cnt DESC
        """,
        p,
    )
```

Replace `get_protein_mlo_annotations`:
```python
async def get_protein_mlo_annotations(uniprot_id: str) -> list[dict]:
    active = policy.active_annotation_clause("ma")
    return await fetchall(
        f"""
        SELECT
            ma.unified_mlo,
            mv.category,
            ma.source_db,
            ma.source_mlo,
            ma.unified_role,
            ma.evidence
        FROM mlo_annotations ma
        LEFT JOIN mlo_vocabulary mv ON ma.unified_mlo = mv.unified_mlo
        WHERE ma.uniprot_id = ? AND {active}
        ORDER BY ma.unified_mlo, ma.source_db
        """,
        (uniprot_id,),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd refactor/api
python3 -m pytest tests/test_protein_queries.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add refactor/api/queries/protein_queries.py refactor/api/tests/test_protein_queries.py
git commit -m "$(cat <<'EOF'
fix: apply dataset_active policy to protein_queries.py

get_proteins_page, get_proteins_facets, and get_protein_mlo_annotations
now exclude inactive mlo_annotations rows via refactor/policy.py --
previously an inactive-only annotation (e.g. DrLLPS Regulator) would
still match role/mlo filters and appear in a protein's annotation list.
EOF
)"
```

---

### Task 5: Fix `refactor/api/queries/search_queries.py`

**Files:**
- Modify: `refactor/api/queries/search_queries.py`
- Test: `refactor/api/tests/test_search_queries.py` (new)

**Interfaces:**
- Consumes: `policy.active_annotation_clause` (Task 2).
- Produces: no signature changes.

- [ ] **Step 1: Write the failing tests**

`refactor/api/tests/test_search_queries.py`:
```python
import asyncio

from queries.search_queries import advanced_search, get_advanced_search_facets


def test_advanced_search_mlo_filter_excludes_inactive_only_protein(test_db):
    total, rows = asyncio.run(
        advanced_search(
            gene_name=None, uniprot_id=None, organism=None, taxon_id=None,
            mlo="nucleolus", role=None, source_db=None,
            feature_type=None, feature_label=None, feature_accession=None,
            page=1, per_page=50,
        )
    )
    assert total == 0
    assert rows == []


def test_advanced_search_facets_mlo_bucket_excludes_inactive_annotation(test_db):
    facets = asyncio.run(
        get_advanced_search_facets(
            gene_name=None, uniprot_id=None, organism=None, taxon_id=None,
            mlo=None, role=None, source_db=None,
            feature_type=None, feature_label=None, feature_accession=None,
        )
    )
    assert facets["by_mlo"].get("nucleolus") is None
    assert facets["by_mlo"].get("stress_granule") == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd refactor/api
python3 -m pytest tests/test_search_queries.py -v
```

Expected: FAILs — both currently match/count the inactive `QREG01`/`nucleolus` row.

- [ ] **Step 3: Fix `refactor/api/queries/search_queries.py`**

Add at the top:
```python
import policy
from database import fetchall, fts5_available
```

In `_build_advanced_clauses`, change:
```python
    if need_mlo:
        joins.append("JOIN mlo_annotations ma ON p.uniprot_id = ma.uniprot_id")
```
to:
```python
    if need_mlo:
        joins.append(
            f"JOIN mlo_annotations ma ON p.uniprot_id = ma.uniprot_id AND {policy.active_annotation_clause('ma')}"
        )
```

In `get_advanced_search_facets`, change its `mlo_rows` query:
```python
    mlo_rows = await fetchall(
        f"""
        SELECT ma2.unified_mlo, COUNT(DISTINCT ma2.uniprot_id) AS cnt
        FROM ({base_cte}) f
        JOIN mlo_annotations ma2 ON ma2.uniprot_id = f.uniprot_id AND {policy.active_annotation_clause("ma2")}
        GROUP BY ma2.unified_mlo
        ORDER BY cnt DESC
        """,
        p,
    )
```

`search_proteins_fts`, `search_proteins_like`, `search_mlos_fts`, `search_mlos_like` are unchanged — none of them touch `mlo_annotations` directly (they read `protein_summary`/`mlo_vocabulary`, which is fixed at the source in Task 8).

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd refactor/api
python3 -m pytest tests/test_search_queries.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add refactor/api/queries/search_queries.py refactor/api/tests/test_search_queries.py
git commit -m "$(cat <<'EOF'
fix: apply dataset_active policy to search_queries.py

_build_advanced_clauses' mlo join and get_advanced_search_facets' MLO
facet now exclude inactive mlo_annotations rows via refactor/policy.py.
EOF
)"
```

---

### Task 6: Fix `refactor/api/main.py`'s `_compute_stats()`

**Files:**
- Modify: `refactor/api/main.py`
- Test: `refactor/api/tests/test_stats.py` (new)

**Interfaces:**
- Consumes: `policy.active_annotation_clause` (Task 2), `test_db` fixture.
- Produces: no signature change to `_compute_stats()`.

- [ ] **Step 1: Write the failing test**

`refactor/api/tests/test_stats.py`:
```python
import asyncio

from main import _compute_stats


def test_compute_stats_mlo_annotations_excludes_inactive_row(test_db):
    stats = asyncio.run(_compute_stats())
    assert stats["mlo_annotations"]["total"] == 1
    assert stats["mlo_annotations"]["by_source"] == {"PhaseDB": 1}
    assert stats["mlo_annotations"]["unique_mlos"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd refactor/api
python3 -m pytest tests/test_stats.py -v
```

Expected: FAIL — currently `total == 2` and `unique_mlos == 2` (counts the inactive `QREG01`/`nucleolus` row).

- [ ] **Step 3: Fix `refactor/api/main.py`**

Change the import block:
```python
import database
from config import CORS_ORIGINS
import policy
from routers import mlos, organisms, proteins, search, stats
```

Replace the `mlo_annotations`-touching lines inside `_compute_stats()`:
```python
    active = policy.active_annotation_clause("mlo_annotations")

    ann_total = await database.fetchval(f"SELECT COUNT(*) FROM mlo_annotations WHERE {active}") or 0
    unique_mlos = await database.fetchval(
        f"SELECT COUNT(DISTINCT unified_mlo) FROM mlo_annotations WHERE {active}"
    ) or 0
    src_rows = await database.fetchall(
        f"SELECT source_db, COUNT(*) AS cnt FROM mlo_annotations WHERE {active} GROUP BY source_db"
    )
    role_rows = await database.fetchall(
        f"SELECT COALESCE(LOWER(unified_role), 'unknown') AS role, COUNT(DISTINCT uniprot_id) AS cnt "
        f"FROM mlo_annotations WHERE {active} GROUP BY role"
    )
```

(These replace the existing un-prefixed `mlo_annotations` queries in place — `proteins`/`sequence_features`/`ppi` queries in the same function are untouched, since `dataset_active` only exists on `mlo_annotations`.)

- [ ] **Step 4: Run test to verify it passes**

```bash
cd refactor/api
python3 -m pytest tests/test_stats.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add refactor/api/main.py refactor/api/tests/test_stats.py
git commit -m "$(cat <<'EOF'
fix: apply dataset_active policy to main.py's _compute_stats()

/stats' mlo_annotations aggregate (total, unique_mlos, by_source,
by_role) now excludes dataset_active=0 rows via refactor/policy.py.
EOF
)"
```

---

### Task 7: Delete `_normalize_role()` from `routers/mlos.py` and `routers/proteins.py`

**Files:**
- Modify: `refactor/api/routers/mlos.py`
- Modify: `refactor/api/routers/proteins.py`
- Test: `refactor/api/tests/test_mlos_router.py` (new), `refactor/api/tests/test_proteins_router.py` (new)

**Interfaces:**
- Consumes: `test_db` fixture (Task 3's `conftest.py`), `fastapi.testclient.TestClient`.
- Produces: no signature change to `get_mlo`/`get_protein` endpoints; only the `unified_role` value in their JSON response changes.

- [ ] **Step 1: Write the failing tests**

`refactor/api/tests/test_proteins_router.py`:
```python
from fastapi.testclient import TestClient

from main import app


def test_protein_detail_shows_raw_driver_role(test_db):
    with TestClient(app) as client:
        r = client.get("/protein/P35637")
    assert r.status_code == 200
    anns = r.json()["mlo_annotations"]
    assert len(anns) == 1
    assert anns[0]["unified_role"] == "driver"
    assert anns[0]["unified_role"] != "component"
```

`refactor/api/tests/test_mlos_router.py`:
```python
from fastapi.testclient import TestClient

from main import app


def test_mlo_detail_proteins_show_raw_role_not_component(test_db):
    with TestClient(app) as client:
        r = client.get("/mlo/stress_granule")
    assert r.status_code == 200
    items = r.json()["proteins"]["items"]
    assert len(items) == 1
    assert items[0]["unified_role"] == "driver"
    assert items[0]["unified_role"] != "component"
```

Note: the fixture DB has no `'client'`-role row yet, but these tests already prove the fix on the `'driver'` path (which passed through unchanged even with the bug, since `_normalize_role` only rewrites the *component-set* roles) is not enough on its own — add one more assertion-only test that directly targets the bug (a `'client'` row must not become `'component'`):

Add to `refactor/api/tests/conftest.py`'s `FIXTURE` string (append, don't replace):
```python
INSERT INTO proteins (uniprot_id, gene_name, organism, length) VALUES
    ('PCLIENT', 'CLIENTTEST', 'Homo sapiens', 200);
INSERT INTO mlo_annotations (uniprot_id, source_db, unified_mlo, unified_role, dataset_active) VALUES
    ('PCLIENT', 'PhaseDB', 'stress_granule', 'client', 1);
INSERT INTO protein_summary (uniprot_id, has_driver, has_client, source_db_count, mlo_count, mlos, source_dbs) VALUES
    ('PCLIENT', 0, 1, 1, 1, '["stress_granule"]', 'PhaseDB');
```

Add to `refactor/api/tests/test_proteins_router.py`:
```python
def test_protein_detail_shows_raw_client_role_not_component(test_db):
    with TestClient(app) as client:
        r = client.get("/protein/PCLIENT")
    assert r.status_code == 200
    anns = r.json()["mlo_annotations"]
    assert anns[0]["unified_role"] == "client"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd refactor/api
python3 -m pytest tests/test_proteins_router.py tests/test_mlos_router.py -v
```

Expected: `test_protein_detail_shows_raw_client_role_not_component` FAILs — `_normalize_role` currently rewrites `'client'` to `'component'`. The other two pass already (the bug doesn't affect `'driver'`), which is expected and fine — they guard against regression once the function is deleted.

- [ ] **Step 3: Delete `_normalize_role` from both routers**

In `refactor/api/routers/mlos.py`, remove:
```python
_COMPONENT_ROLES = {"client", "unknown", "unmapped"}


def _normalize_role(role: str | None) -> str | None:
    if role and role.lower() in _COMPONENT_ROLES:
        return "component"
    return role
```
and change:
```python
            unified_role=_normalize_role(r.get("unified_role")),
```
to:
```python
            unified_role=r.get("unified_role"),
```

In `refactor/api/routers/proteins.py`, remove:
```python
_COMPONENT_ROLES = {"client", "unknown", "unmapped"}


def _normalize_role(role: str | None) -> str | None:
    if role and role.lower() in _COMPONENT_ROLES:
        return "component"
    return role
```
and change:
```python
        unified_role=_normalize_role(row.get("unified_role")),
```
to:
```python
        unified_role=row.get("unified_role"),
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd refactor/api
python3 -m pytest tests/test_proteins_router.py tests/test_mlos_router.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add refactor/api/routers/mlos.py refactor/api/routers/proteins.py refactor/api/tests/
git commit -m "$(cat <<'EOF'
fix: delete _normalize_role(), pass unified_role through unchanged

_normalize_role() collapsed 'client' into 'component' in API responses,
contradicting frontend/CLAUDE.md's contract (driver -> blue badge,
client -> green badge, null -> no badge). Raw passthrough is correct
now that unified_role is clean ('driver'/'client'/None) in the
corrected DB -- the frontend already derives its own "component" UI
concept client-side from has_driver, never from this API field.
EOF
)"
```

---

### Task 8: Fix `refactor/scripts/build_summary.py`'s `_build_mlo_aggregates()`

**Files:**
- Modify: `refactor/scripts/build_summary.py`
- Test: `refactor/tests/test_build_summary.py` (new)

**Interfaces:**
- Consumes: `policy.active_annotation_clause` (Task 2).
- Produces: no signature change to `_build_mlo_aggregates(conn) -> dict[str, dict]`.

- [ ] **Step 1: Write the failing test**

`refactor/tests/test_build_summary.py`:
```python
import sqlite3
import sys
from pathlib import Path

REFACTOR_ROOT = Path(__file__).resolve().parent.parent
if str(REFACTOR_ROOT) not in sys.path:
    sys.path.insert(0, str(REFACTOR_ROOT))
sys.path.insert(0, str(REFACTOR_ROOT / "scripts"))

from build_summary import _build_mlo_aggregates


def _make_conn():
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE mlo_annotations (
            id INTEGER PRIMARY KEY AUTOINCREMENT, uniprot_id TEXT,
            source_db TEXT, unified_mlo TEXT, unified_role TEXT,
            dataset_active INTEGER NOT NULL DEFAULT 1
        );
        INSERT INTO mlo_annotations (uniprot_id, source_db, unified_mlo, unified_role, dataset_active)
        VALUES ('ACTIVE1', 'PhaseDB', 'stress_granule', 'driver', 1);
        INSERT INTO mlo_annotations (uniprot_id, source_db, unified_mlo, unified_role, dataset_active)
        VALUES ('REGONLY', 'DrLLPS', 'nucleolus', NULL, 0);
    """)
    conn.commit()
    return conn


def test_build_mlo_aggregates_excludes_inactive_only_protein():
    conn = _make_conn()
    result = _build_mlo_aggregates(conn)
    conn.close()

    assert result["ACTIVE1"]["mlo_count"] == 1
    assert result["ACTIVE1"]["source_db_count"] == 1
    assert result["ACTIVE1"]["mlos"] == ["stress_granule"]

    # REGONLY's only row is dataset_active=0 -- it must not appear at all
    # (no GROUP BY group is produced once the WHERE clause excludes its
    # only row), not appear with stale mlo_count/source_db_count of 1.
    assert "REGONLY" not in result
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest refactor/tests/test_build_summary.py -v
```

Expected: FAIL — `"REGONLY" not in result` fails because today's `_build_mlo_aggregates` has no `WHERE` clause and includes it with `mlo_count=1`.

- [ ] **Step 3: Fix `refactor/scripts/build_summary.py`**

Add near the top, after the existing `ROOT = Path(__file__).parent.parent` line:
```python
import sys
sys.path.insert(0, str(ROOT))
import policy
```

Replace `_build_mlo_aggregates`:
```python
def _build_mlo_aggregates(conn: sqlite3.Connection) -> dict[str, dict]:
    active = policy.active_annotation_clause("ma")
    rows = conn.execute(
        f"""
        SELECT
            uniprot_id,
            MAX(CASE WHEN LOWER(unified_role)='driver' THEN 1 ELSE 0 END) AS has_driver,
            MAX(CASE WHEN LOWER(unified_role)='client' THEN 1 ELSE 0 END) AS has_client,
            COUNT(DISTINCT source_db)  AS source_db_count,
            COUNT(DISTINCT unified_mlo) AS mlo_count,
            GROUP_CONCAT(DISTINCT unified_mlo) AS mlos_concat,
            GROUP_CONCAT(DISTINCT source_db) AS source_dbs_concat
        FROM mlo_annotations ma
        WHERE {active}
        GROUP BY uniprot_id
        """
    ).fetchall()
    result = {}
    for uid, has_driver, has_client, sdb_count, mlo_count, mlos_concat, source_dbs_concat in rows:
        result[uid] = {
            "has_driver": has_driver,
            "has_client": has_client,
            "source_db_count": sdb_count,
            "mlo_count": mlo_count,
            "mlos": sorted(mlos_concat.split(",")) if mlos_concat else [],
            "source_dbs": source_dbs_concat or None,
        }
    return result
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m pytest refactor/tests/test_build_summary.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Measure the real-world impact on `refactor/database/mlosmetadb.db`, then re-run `build_summary.py`**

Before re-running, capture how many real proteins are affected (concrete evidence for the REFACTOR_LOG entry in Task 11):

```bash
sqlite3 refactor/database/mlosmetadb.db <<'SQL'
.headers on
SELECT COUNT(DISTINCT uniprot_id) AS proteins_with_only_inactive_annotations
FROM mlo_annotations ma
WHERE dataset_active = 0
  AND uniprot_id NOT IN (SELECT uniprot_id FROM mlo_annotations WHERE dataset_active = 1);
SQL
```

Note the printed count, then re-run the fixed script:

```bash
cd refactor
python3 scripts/build_summary.py
```

Expected output ends with `Done.` (same shape as the original run documented in `REFACTOR_LOG.md` Entry 7/8) — `protein_summary` row count should be unchanged (still one row per protein), only the `mlo_count`/`source_db_count`/`mlos`/`source_dbs` values for the affected proteins should now read `0`/`0`/`NULL`/`NULL` instead of counting their inactive-only annotation.

Verify with:
```bash
sqlite3 refactor/database/mlosmetadb.db <<'SQL'
.headers on
SELECT COUNT(*) AS proteins_with_zero_mlo_count_now
FROM protein_summary
WHERE mlo_count = 0;
SQL
```

This count should be greater than or equal to the `proteins_with_only_inactive_annotations` figure captured above (it may also include proteins with genuinely zero `mlo_annotations` rows at all, which is expected and fine).

- [ ] **Step 6: Commit**

```bash
git add refactor/scripts/build_summary.py refactor/tests/test_build_summary.py refactor/database/mlosmetadb.db refactor/database/mlosmetadb.tsv
git commit -m "$(cat <<'EOF'
fix: apply dataset_active policy to build_summary.py's mlo aggregation

_build_mlo_aggregates() previously counted dataset_active=0 rows (e.g.
DrLLPS Regulator) toward a protein's mlo_count/source_db_count/mlos/
source_dbs in protein_summary. Now filtered via refactor/policy.py,
consistent with the same fix applied to the live API queries.
Re-ran build_summary.py against refactor/database/mlosmetadb.db to
regenerate protein_summary with the corrected aggregation.
EOF
)"
```

(If `refactor/database/mlosmetadb.db` is gitignored per `REFACTOR_LOG.md` Entry 9, drop it from this commit — check with `git check-ignore refactor/database/mlosmetadb.db` first and only `git add` it if that command reports nothing.)

---

### Task 9: End-to-end verification against the real DB

**Files:**
- None modified — this task only runs and records verification, following this project's test-before-batch / verification-before-completion convention.

- [ ] **Step 1: Start the API against the real, fixed DB**

```bash
cd refactor/api
python3 -m uvicorn main:app --host 127.0.0.1 --port 8010 &
sleep 2
curl -s http://127.0.0.1:8010/stats | python3 -m json.tool | head -20
```

Expected: valid JSON, no traceback in the server's stdout.

- [ ] **Step 2: Find a real protein whose only annotation is inactive**

```bash
sqlite3 refactor/database/mlosmetadb.db <<'SQL'
SELECT uniprot_id FROM mlo_annotations
WHERE dataset_active = 0
  AND uniprot_id NOT IN (SELECT uniprot_id FROM mlo_annotations WHERE dataset_active = 1)
LIMIT 1;
SQL
```

Note the printed `uniprot_id` (call it `$REG_ONLY_ID` below).

- [ ] **Step 3: curl the standard `TEST_PROTEINS` plus the regulator-only protein**

```bash
for id in P35637 Q92520 P09651 P38919 Q9NQC3 "$REG_ONLY_ID"; do
  echo "=== /protein/$id ==="
  curl -s "http://127.0.0.1:8010/protein/$id" | python3 -m json.tool | grep -E 'unified_role|"total"' 
done
```

Expected:
- FUS (`P35637`) and the other four `TEST_PROTEINS` show `mlo_annotations` with `unified_role` values that are only `"driver"`, `"client"`, or `null` — never `"component"`.
- `$REG_ONLY_ID` returns `"mlo_annotations": []` (its only annotation is inactive, correctly hidden).

- [ ] **Step 4: Confirm `/mlo/{id}` and `/proteins?role=driver` show no `"component"` anywhere**

```bash
curl -s "http://127.0.0.1:8010/mlo/stress_granule" | grep -o '"unified_role":"[^"]*"' | sort -u
curl -s "http://127.0.0.1:8010/proteins?role=driver&per_page=50" | grep -o '"unified_role":"[^"]*"' | sort -u
```

Expected: neither command's output contains `"unified_role":"component"`.

- [ ] **Step 5: Cross-check `/stats` against a direct query**

```bash
sqlite3 refactor/database/mlosmetadb.db "SELECT COUNT(*) FROM mlo_annotations WHERE dataset_active = 1;"
curl -s http://127.0.0.1:8010/stats | python3 -c "import sys,json; print(json.load(sys.stdin)['mlo_annotations']['total'])"
```

Expected: both numbers match exactly.

- [ ] **Step 6: Stop the server**

```bash
kill %1
```

- [ ] **Step 7: Record the results**

No commit for this task (nothing changed) — capture the exact output of steps 3-5 to paste into the `REFACTOR_LOG.md` Entry 11 written in Task 11, per this project's verification-before-completion convention (evidence before assertions, not just "it works").

---

### Task 10: Write `refactor/api/CLAUDE.md` and `refactor/api/API_EXAMPLES.md`

**Files:**
- Create: `refactor/api/CLAUDE.md`
- Create: `refactor/api/API_EXAMPLES.md`

**Interfaces:**
- None — pure documentation, no code interfaces produced or consumed.

- [ ] **Step 1: Write `refactor/api/CLAUDE.md`**

Follow the same format as `refactor/database/CLAUDE.md`/`refactor/scripts/CLAUDE.md`: directory layout, endpoint table (the 10 routes from Task 1-9, unchanged in shape), the in-memory-DB startup pattern, the uniform error envelope, and — the part that must not be skipped — a "Serving policy" section documenting `refactor/policy.py` verbatim from its module docstring, plus the domain rule from `docs/superpowers/specs/2026-08-04-refactor-api-phase-design.md`'s Context section (dataset_active=0 vs. NULL distinction). Cross-reference `REFACTOR_LOG.md` Entry 11 for the fix narrative, the same way `refactor/scripts/CLAUDE.md` cross-references Entry 4.

- [ ] **Step 2: Write `refactor/api/API_EXAMPLES.md`**

Regenerate example request/response pairs directly from the live curl output captured in Task 9 (real data, real corrected values) — not hand-written. Explicitly do not carry forward any example showing `"unified_role": "unmapped"` or `"unified_role": "component"` from the old `api/API_EXAMPLES.md`; every example's `unified_role` must be one of `"driver"`, `"client"`, or `null`.

- [ ] **Step 3: Commit**

```bash
git add refactor/api/CLAUDE.md refactor/api/API_EXAMPLES.md
git commit -m "$(cat <<'EOF'
docs: add refactor/api/CLAUDE.md and API_EXAMPLES.md

Fresh docs reflecting the corrected code (dataset_active filtering,
raw unified_role passthrough) -- not carried forward from the stale
api/CLAUDE_api.md / API_EXAMPLES.md, which documented pre-fix behavior
including literal "unmapped" role examples.
EOF
)"
```

---

### Task 11: `REFACTOR_LOG.md` Entry 11 + update `refactor/CLAUDE.md`

**Files:**
- Modify: `refactor/REFACTOR_LOG.md`
- Modify: `refactor/CLAUDE.md`

**Interfaces:**
- None — documentation only.

- [ ] **Step 1: Append `## Entry 11 — api/ phase: port + schema-drift fixes` to `refactor/REFACTOR_LOG.md`**

Content to include (mirroring the structure of Entries 9/10 — narrative, not just a bullet list):
- What was ported (Task 1) and the one thing confirmed *not* needing a code change (`config.py`'s `DB_PATH` auto-resolution).
- Each of the 5 findings from `docs/superpowers/specs/2026-08-04-refactor-api-phase-design.md`, with the exact fix applied and file/line references (Tasks 2-8).
- The real-world impact number captured in Task 8, Step 5 (`proteins_with_only_inactive_annotations` count, before/after `protein_summary.mlo_count=0` count).
- The full verification transcript from Task 9 (curl output showing no `"component"` anywhere, the regulator-only protein's empty `mlo_annotations`, and the `/stats` vs. direct-query count match).
- Explicit note on the `EXCLUDED_MLO_CATEGORIES` extension point's actual scope: wired only into `mlo_queries.get_all_mlos` (not `protein_queries.py`, which has no natural `mlo_vocabulary.category` join point) — a deliberate narrowing of the design spec's slightly broader wording, disclosed here rather than silently applied.

- [ ] **Step 2: Update `refactor/CLAUDE.md`**

In the "Where to look" table, add a row:
```
| API endpoints, serving policy (dataset_active, role passthrough) | [api/CLAUDE.md](api/CLAUDE.md) |
```

Remove the sentence "Do not start building them under `refactor/` until this data-layer phase is reviewed and confirmed" for `api/` specifically (frontend/ is still not started), and update the directory map to include `api/`:
```
├── api/                # FastAPI backend — see api/CLAUDE.md
```

- [ ] **Step 3: Commit**

```bash
git add refactor/REFACTOR_LOG.md refactor/CLAUDE.md
git commit -m "$(cat <<'EOF'
docs: log the api/ phase port + fixes in REFACTOR_LOG.md Entry 11

Documents the schema-drift findings, each fix applied via the new
refactor/policy.py module, the real-world protein_summary impact
measured before/after the build_summary.py fix, and the end-to-end
curl verification against the real corrected DB.
EOF
)"
```

---

## Self-Review Notes

- **Spec coverage**: every fix listed in the design spec's "Fixes to apply during the port" section (dataset_active in mlo_queries/protein_queries/search_queries/main.py, `_normalize_role` deletion, build_summary.py aggregation, config.py DB path) has a task. `EXCLUDED_MLO_CATEGORIES` extension point is wired in with a narrower, disclosed scope (Task 3/11) since `protein_queries.py` has no natural join point for it — flagged rather than silently expanded to fit the spec's exact wording.
- **Placeholder scan**: no task ends without runnable commands or full code; Task 10 (docs) is the one task without literal file content dictated, because its content is generated from live data captured in Task 9, not knowable until that task runs — this is the correct order, not a placeholder.
- **Type/signature consistency**: `active_annotation_clause(alias: str = "ma") -> str` and `excluded_mlo_category_clause(alias: str = "mv") -> tuple[str | None, list[str]]` (Task 2) are called with matching signatures in every consuming task (3-8) — verified by re-reading each call site above.
- **Scope check**: this plan covers exactly the `api/` phase from the approved spec. `frontend/` phase, OrthoDB v2 migration, and exposing currently-unused columns are explicitly out of scope per the spec and not touched by any task here.
