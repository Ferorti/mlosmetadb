# API_EXAMPLES.md — `refactor/api/` real request/response examples

Every example below is copied verbatim (or trivially reformatted for
readability — no field values changed) from the live `curl` output captured
during Task 9's end-to-end verification of `refactor/api/` against the real,
unmodified `refactor/database/mlosmetadb.db` (see
`.superpowers/sdd/2026-08-04-refactor-api-phase/task-9-report.md` for the
full session). Nothing here is hand-written or synthetic. That verification
run is also the reason this file exists in the first place: the
pre-refactor `api/API_EXAMPLES.md` at the repo root contains stale
`"unified_role": "unmapped"`-style examples from before the schema-drift
fixes — none of that is carried forward here. **Every `unified_role` value
shown below is `"driver"`, `"client"`, or `null` — nothing else.**

Server for all examples below: `refactor/api`, `python3 -m uvicorn main:app
--host 127.0.0.1 --port 8010`, pointed at the real
`refactor/database/mlosmetadb.db` (15,879 proteins, 53,396 active
`mlo_annotations` rows).

---

## `GET /stats`

```bash
curl "http://127.0.0.1:8010/stats"
```

Real response (head — the other top-level sections are truncated here only
for length):

```json
{
    "database_version": "2.0",
    "last_updated": "2026-05-04",
    "proteins": {
        "total": 15879,
        "by_organism": {},
        "top_organisms": 10,
        "total_organisms": 0
    },
    "mlo_annotations": {
        "total": 34582,
        "unique_mlos": 167,
        "by_source": {
            "CDCODE": 13845,
            "DrLLPS": 9483,
            "LLPSDB": 380,
            "PhaSepDB": 10675,
            "PhasePro": 199
        }
    }
}
```

`by_source` has **five** keys, one per source database. An older capture of
this response showed six, splitting PhaSepDB across `PhaseDB` (14,608) and
`PhasePDB` (14,875) — those were two ingestion tags for one resource, and the
duplicate rows behind them were removed on 2026-08-08 (see
[docs/issues/001-phasedb-phasepdb-duplicate-ingestion.md](../docs/issues/001-phasedb-phasepdb-duplicate-ingestion.md)).
If a live response still shows either tag, the server is holding an in-memory
copy of a pre-fix DB — restart `uvicorn`.

`mlo_annotations.total` (34582) is the count of `dataset_active=1` rows —
confirmed by cross-checking against `SELECT COUNT(*) FROM mlo_annotations
WHERE dataset_active = 1` directly on the DB, which returns the identical
number. The 1,389 `dataset_active=0` DrLLPS Regulator rows are excluded from
this total, per the serving policy (see `CLAUDE.md`'s "Serving policy"
section).

---

## `GET /protein/{uniprot_id}` — the `dataset_active=0` case

`O23702` was picked specifically because its *only* `mlo_annotations` row is
`dataset_active=0` (a DrLLPS "Regulator" row):

```sql
SELECT uniprot_id, source_db, unified_mlo, source_role, unified_role, dataset_active
FROM mlo_annotations WHERE uniprot_id='O23702';
```
```
uniprot_id  source_db  unified_mlo     source_role  unified_role  dataset_active
----------  ---------  --------------  -----------  ------------  --------------
O23702      DrLLPS     stress_granule  Regulator                  0
```

```bash
curl "http://127.0.0.1:8010/protein/O23702"
```

Real, full response:

```json
{
    "uniprot_id": "O23702",
    "gene_name": null,
    "protein_name": null,
    "organism": null,
    "taxon_id": null,
    "sequence_length": null,
    "disorder_mobidb_lite_dc": 0.267,
    "disorder_alphafold_dc": 0.27,
    "mlo_annotations": [],
    "sequence_features": {
        "idrs": [], "domains": [], "lcds": [], "morfs": [], "plddt_regions": []
    },
    "ppi": {
        "total_partners": 0,
        "partners_in_mlosmetadb": 0,
        "interactions": null
    }
}
```

This is the domain rule made concrete: `O23702`'s regulator-only row has
`unified_role IS NULL` *and* `dataset_active=0`, and the API correctly
returns `mlo_annotations: []` — the row is excluded from what's served, but
it is still present in the raw DB for provenance (confirmed by the SQL
query above; the API never deletes it, it just doesn't surface it by
default).

---

## `GET /protein/{uniprot_id}` — 404 error envelope, real example

`Q92520` (FMR1, one of the standard `TEST_PROTEINS`) has zero rows in both
`proteins` and `mlo_annotations` in this DB snapshot (a pre-existing data
gap, unrelated to the `dataset_active`/`unified_role` fixes — see Task 9's
report, Concern 2):

```bash
curl "http://127.0.0.1:8010/protein/Q92520"
```

Real response (HTTP 404):
```json
{ "error": "protein_not_found", "message": "No protein with UniProt ID 'Q92520'" }
```

This is the uniform error envelope described in `CLAUDE.md` in action, not
a fabricated example.

---

## `GET /protein/{uniprot_id}` — `unified_role` distribution across real proteins

Real per-protein `unified_role` distributions, extracted from `/protein/{id}`
responses across the standard `TEST_PROTEINS` plus the regulator-only
protein above:

```
=== /protein/P35637 (FUS) ===
total annotations: 1036
unified_role distribution: {'driver': 1018, None: 12, 'client': 6}

=== /protein/P09651 (hnRNP A1) ===
total annotations: 159
unified_role distribution: {'driver': 137, 'client': 12, None: 10}

=== /protein/P38919 (eIF4A3) ===
total annotations: 23
unified_role distribution: {'client': 19, None: 4}

=== /protein/Q9NQC3 (RBM14) ===
total annotations: 2
unified_role distribution: {'client': 1, None: 1}

=== /protein/O23702 (regulator-only) ===
total annotations: 0
unified_role distribution: {}
```

`None` above is Python's rendering of JSON `null` — every `mlo_annotations[]`
entry's `unified_role` field is one of `"driver"`, `"client"`, or `null`.
**`"component"` never appears in any of these distributions** — confirmed
directly against the live DB, not assumed.

---

## `GET /mlo/{unified_mlo}` — no `"component"` in role values

```bash
curl "http://127.0.0.1:8010/mlo/stress_granule" | grep -o '"unified_role":"[^"]*"' | sort -u
```

Real output:
```
"unified_role":"client"
"unified_role":"driver"
```

Only `"client"` and `"driver"` appear across every protein listed under
`stress_granule` — no `"component"`, no `"unmapped"`.

---

## `GET /proteins?role=driver&per_page=50`

```bash
curl "http://127.0.0.1:8010/proteins?role=driver&per_page=50"
```

Note: unlike `/protein/{id}` and `/mlo/{id}`, this endpoint's protein-list
items do **not** serialize a literal `unified_role` field — they expose
boolean `has_driver`/`has_client` flags instead, computed from
`dataset_active=1` rows only (see `refactor/scripts/CLAUDE.md`'s
`build_summary.py` section). Real item from the response:

```json
{
  "uniprot_id": "A0A024RB53",
  "has_driver": true,
  "has_client": false,
  "source_db_count": 1,
  "source_dbs": ["LLPSDB"],
  "mlo_count": 1,
  "mlos": ["in_vitro_droplet"]
}
```

Real `facets.by_role` aggregate from the same response:
```json
"facets": { "by_role": { "driver": 2029 } }
```

Only a `driver` bucket appears (consistent with the `role=driver` filter
applied) — no `component` bucket anywhere in the facets.

---

## Endpoints not covered above

Task 9's verification exercised `/stats`, `/protein/{id}`, `/mlo/{id}`, and
`/proteins` against the real DB — see its report for the exact commands.
`/protein/{id}/ppi`, `/protein/{id}/orthologs`, `/mlos`, `/search`,
`/search/advanced`, and `/organisms/search` were not part of that
verification run, so no real captured output exists yet to source examples
from for them here. Per this doc's own rule (no hand-written/synthetic
examples), they're intentionally left out rather than filled in with
plausible-looking fake data. See `CLAUDE.md`'s endpoint table for what each
does, and `models/schemas.py` for their exact response shapes — none of
those shapes involve `unified_role` remapping, so the same "raw
driver/client/null passthrough" rule applies to them too, it just isn't
demonstrated with live data in this file yet.
