# Data unification section — Phase 2 (API exposure) design

**Source spec:** `docs/review/unification_section/INFORME_SECCION_UNIFICACION.md`
(external audit deliverable). Phase 1 (data layer — see
`2026-08-12-unification-stats-phase1-design.md`) is complete: `scripts/
build_unification_stats.py` writes `database/exports/unification_stats.json`,
`discrepant_pairs.csv`, and `mlo_term_mapping.csv`, all verified against the
audit's own reference computation. This document covers only Phase 2 — the
API layer that serves those three artifacts to the frontend. Phase 3
(the actual "Data unification" SPA section, chart library, copy) is a
separate, later spec.

## Why a new router, not an extension of `stats.py`

`api/CLAUDE.md`'s directory map gives each router one domain
(`proteins.py`, `mlos.py`, `search.py`, `stats.py`, `organisms.py`). The
three new endpoints are file-serving, not SQL-querying, and don't share a
concern with `/stats`'s live-DB aggregate beyond both being "numbers about
the dataset" — that's not enough to justify mixing them into `stats.py`.
`api/routers/unification.py` + `api/queries/unification_queries.py` (thin —
see below) keeps the one-file-one-responsibility convention this codebase
already follows.

## Endpoints

| Method | Path | Returns |
|---|---|---|
| GET | `/unification/stats` | `unification_stats.json`'s parsed content, as-is |
| GET | `/unification/discrepant-pairs/export` | `discrepant_pairs.csv`, as a file download |
| GET | `/unification/mlo-term-mapping/export` | `mlo_term_mapping.csv`, as a file download |

Path style matches existing convention (`/proteins/export`, `/organisms/search`):
plural-noun-then-verb, `/export` suffix for a bulk-download endpoint.
`discrepant-pairs`/`mlo-term-mapping` are hyphenated in the URL (REST path
convention already used nowhere else in this API, since no other path has a
multi-word segment — this establishes it, consistently with hyphenation
being the standard for URL segments, as opposed to the snake_case Python
identifiers `discrepant_pairs`/`mlo_term_mapping` used internally).

## Data loading

**`/unification/stats`**: the JSON is parsed **once at startup**, in
`main.py`'s `lifespan()`, alongside the existing `/stats` precompute
(`app.state.stats`) — added as `app.state.unification_stats`. This mirrors
the contract the whole app already has for `database/mlosmetadb.db` itself
(`api/CLAUDE.md`: "rebuilding mlosmetadb.db has zero effect on a running
server ... restart uvicorn to pick up a rebuilt DB") rather than introducing
a second, inconsistent freshness contract for one endpoint. If
`database/exports/unification_stats.json` is missing or fails to parse at
startup, log a warning and set `app.state.unification_stats = None` — do
**not** raise and crash app startup over a missing optional artifact.

**The two `/export` endpoints**: read their CSV fresh from disk on every
request via `FileResponse` (`api/routers/unification.py`) — no in-memory
caching. These are downloads, not data consumed by the SPA's own rendering,
so there's no benefit to holding them in memory, and `FileResponse` handles
content-type/streaming/headers correctly without custom code.

## Missing-artifact handling

If `app.state.unification_stats` is `None` (file absent/unparseable at
startup): `/unification/stats` returns **503** with the existing error
envelope shape (`api/CLAUDE.md`'s "Error envelope" section):
```json
{ "error": "unification_stats_unavailable", "message": "unification_stats.json has not been generated yet — run scripts/build_unification_stats.py" }
```
The two `/export` endpoints check file existence independently (they don't
depend on the startup precompute) and return the same 503 shape,
`error: "unification_export_unavailable"`, per missing file, naming which
one in the message.

This is a genuinely optional artifact (a fresh dev checkout that hasn't run
the Phase 1 build script yet), unlike `mlosmetadb.db` itself, which the app
cannot function without at all — hence 503-per-request rather than refusing
to boot.

## Response shape: raw `dict`, not a Pydantic model

`/unification/stats` returns the parsed JSON directly (FastAPI serializes a
plain `dict` return value the same as a Pydantic model). No new
`models/schemas.py` class re-declares `unification_stats.json`'s shape
field-by-field. The shape is already defined once, by
`scripts/build_unification_stats.py`, and already covered by
`tests/test_unification_stats.py`'s invariants — a parallel Pydantic
schema would be a second source of truth for the same shape, the exact
failure mode Phase 1's `role_harmonisation.csv` design explicitly avoided
for the role/category mapping. If Phase 3 needs stronger typing on the
frontend side, that's a frontend-side (JSDoc/PropTypes-equivalent, this repo
has no TypeScript) concern, not an API-side Pydantic model.

## `unification_queries.py`

Thin by design — no SQL. Three functions:
- `load_unification_stats() -> dict | None` — reads and parses
  `database/exports/unification_stats.json`, returns `None` on any failure
  (missing file, malformed JSON), logging the reason. Called once from
  `main.py`'s `lifespan()`.
- `discrepant_pairs_csv_path() -> Path` / `mlo_term_mapping_csv_path() -> Path`
  — return the fixed paths under `database/exports/`; the router checks
  `.exists()` before returning a `FileResponse`.

`config.py` gains `EXPORTS_DIR = ROOT / "database" / "exports"` alongside the
existing `DB_PATH`.

## Tests

`api/tests/test_unification_router.py`:
- `/unification/stats` happy path: build a temp `database/exports/
  unification_stats.json` fixture, confirm 200 and the response echoes it
  verbatim (no reshaping).
- `/unification/stats` when `app.state.unification_stats` is `None`: 503,
  correct error envelope.
- Each `/export` endpoint: 200 + correct `Content-Type`/`Content-Disposition`
  when the fixture CSV exists, 503 when it doesn't.

No live-DB integration test is needed here (unlike Phase 1) — this layer
does no SQL, so a fixture JSON/CSV is a complete, faithful test double.

## Out of scope for this phase

- Any frontend code, chart library choice, or SPA page (Phase 3).
- Filtering/pagination on the two export endpoints — the report asks for
  whole-table downloads, matching `mlo_term_mapping`'s "debe ser
  descargable entero" requirement; if per-column filters are wanted later
  for `discrepant_pairs`, that's a new, separate ask (unlike `/proteins/
  export`, which already supports query filters — these two do not, on
  purpose, since the source report didn't ask for it).
- Updating `DEPLOY.md`'s rsync recipe to include `database/exports/` —
  an operational/deployment step, not application code. Flagged here so
  it isn't forgotten before this phase ships to the production server.
