# MLOsMetaDB

A meta-database unifying protein annotations from five source databases
(PhaSepDB, DrLLPS, LLPSDB, PhasePro, CD-CODE) related to
liquid-liquid phase separation (LLPS) and membraneless organelles (MLOs),
enriched with UniProt metadata, InterPro/MobiDB sequence features, BioGRID
protein-protein interactions, and OMA orthologs.

Serves `mlos.leloir.org.ar`'s public REST API and SPA frontend.

## Structure

- `api/` — FastAPI backend. See `api/CLAUDE.md`.
- `frontend/` — Vue 3 SPA. See `frontend/CLAUDE.md`.
- `database/` — data, mappings, cache, the built SQLite DB. See `database/CLAUDE.md`.
- `scripts/` — fetch/parse/build pipeline. See `scripts/CLAUDE.md`.
- `parsers/` — per-source raw-to-interim parsers. See `parsers/CLAUDE.md`.
- `tests/` — tests for `policy.py`/`build_summary.py` (shared, non-API modules).
- `policy.py` — shared serving policy (`dataset_active` filtering, MLO category exclusion), imported by both `api/` and `scripts/build_summary.py`.
- `BIOLOGY.md` — biological classification rules (driver/client, MLO mapping decisions).
- `SCHEMA.md` — full database schema.
- `CLAUDE.md` — start here for anything not covered above.
- `DEVLOG.md` — session-by-session narrative history.
- `REFACTOR_LOG.md` — narrative history of how this repo reached its current structure.
- `docs/` — spec/plan history for this restructuring.
- `OLD/` — the pre-restructuring codebase, retired. No *code* here is
  depended on by anything current, but `OLD/database/databases_input_data/`
  is still the only copy of the V1 source inputs `database/compare_v1_v2.py`
  and `database/get_phasepdb_mlo_entries.py` need — see `REFACTOR_LOG.md`
  Entry 10 before deleting anything under `OLD/`. Its `phasepdb/`
  subdirectory holds byte-identical copies of two PhaSepDB exports already
  present in `database/raw/`; nothing in the pipeline reads them since the
  PhaSepDB parsers were merged.

## Running it

```bash
pip install -r api/requirements.txt
cd api && python3 -m uvicorn main:app --host 127.0.0.1 --port 8010
cd frontend && npm install && npm run dev
```

See `api/CLAUDE.md` and `frontend/CLAUDE.md` for details (in-memory DB load,
API contract, frontend conventions).

## Citation and contact

Orti F, Fernández ML, Marino-Buslje C. *Protein Science.* 2024;33(1):e4858.
<https://doi.org/10.1002/pro.4858>

Scientific — cmb@leloir.org.ar
Technical — forti@leloir.org.ar
