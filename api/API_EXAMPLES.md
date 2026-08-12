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

## `GET /protein/{uniprot_id}` — the regulator-only case (**reversed 2026-08-12**)

`O23702` was picked in the api/ phase because its *only* `mlo_annotations` row was
`dataset_active=0` (a DrLLPS "Regulator" row), and it returned
`"mlo_annotations": []` — a protein served with nothing in it. `R1-ACT-14` closed
that against us: 501 proteins were in exactly this state, indistinguishable from
proteins no resource reports. Regulator rows are now served.

```sql
SELECT uniprot_id, source_db, unified_mlo, source_role, unified_role, evidence_type, dataset_active
FROM mlo_annotations WHERE uniprot_id='O23702';
```
```
uniprot_id  source_db  unified_mlo     source_role  unified_role  evidence_type       dataset_active
----------  ---------  --------------  -----------  ------------  ------------------  --------------
O23702      DrLLPS     stress_granule  Regulator                  curator_assignment  1
```

```bash
curl "http://127.0.0.1:8018/protein/O23702"
```

Real response, `mlo_annotations` and the identifying fields only (re-measured
2026-08-12 against the regenerated DB):

```json
{
    "uniprot_id": "O23702",
    "gene_name": "AN",
    "protein_name": "C-terminal binding protein AN",
    "organism": "Arabidopsis thaliana",
    "taxon_id": 3702,
    "sequence_length": 636,
    "mlo_annotations": [
        {
            "spatial_location": "cytoplasm",
            "taxonomic_scope": "pan_Fungi+Metazoa",
            "physiological_state": "stress_induced",
            "cell_type_context": null,
            "unified_mlo": "stress_granule",
            "source_db": "DrLLPS",
            "source_mlo": "Stress granule",
            "unified_role": null,
            "evidence_pmids": ["28659951"]
        }
    ]
}
```

Two things this shows at once. `unified_role` is still `null` — "regulator" never
became a stored role value; it is derived at read time from
`(evidence_type, source_role)`. And the four axis fields have replaced `category`
on every annotation object (`R1-ACT-06`).

---

## `GET /mlo/{unified_mlo}` — the three `by_role` buckets

```bash
curl "http://127.0.0.1:8018/mlo/stress_granule?per_page=50"
```

Real output (`stats` only):
```json
"by_role": { "driver": 209, "regulator": 418, "component": 2595 },
"total_proteins": 2836
```

Those 418 proteins used to be counted as `component`s of the stress granule,
which asserts residency DrLLPS never claimed. The buckets do **not** sum to
`total_proteins`: they bucket annotation rows while the count is distinct
proteins, so a protein one resource calls a driver and another calls a regulator
appears in both.

`/mlo/{id}` is the only endpoint with this third bucket. `/stats` still folds
regulators into `unknown` and `/proteins`' facets into `component` — measured the
same day:

```
/stats      .mlo_annotations.by_role  {"client": 12180, "driver": 2029, "unknown": 11480}
/proteins   .facets.by_role           {"driver": 2029, "component": 13665}
```

---

## `GET /mlos` — the four axes and their provenance

```bash
curl "http://127.0.0.1:8018/mlos?spatial_location=nucleus&physiological_state=stress_induced"
```

Two orthogonal axes conjoin, which the single `category` column could not express:
that query returns **5** of the 176 listed terms (`NotInformed` is hidden by
`policy.EXCLUDED_MLO_SPATIAL_LOCATIONS`, exactly as `category='Unspecified'` used
to be). Real items from `curl "http://127.0.0.1:8018/mlos"`:

```json
{ "unified_mlo": "p_body", "spatial_location": "cytoplasm",
  "spatial_location_evidence": "from_category", "taxonomic_scope": "Metazoa",
  "taxonomic_support_n": 1503, "physiological_state": "constitutive",
  "cell_type_context": null, "protein_count": 1507, "driver_count": 90 }

{ "unified_mlo": "mast_cell_granule", "spatial_location": "cytoplasm",
  "spatial_location_evidence": "hand_assigned", "taxonomic_scope": "Metazoa",
  "taxonomic_support_n": 529, "physiological_state": "constitutive",
  "cell_type_context": "mast_cell", "protein_count": 533, "driver_count": 0 }

{ "unified_mlo": "aggresome", "spatial_location": "cytoplasm",
  "spatial_location_evidence": "from_category", "taxonomic_scope": "Bacteria",
  "taxonomic_support_n": 6, "physiological_state": "stress_induced",
  "cell_type_context": null, "protein_count": 6, "driver_count": 0 }

{ "unified_mlo": "rho_body", "spatial_location": "cytoplasm",
  "spatial_location_evidence": "hand_assigned", "taxonomic_scope": null,
  "taxonomic_support_n": 0, "physiological_state": "constitutive",
  "cell_type_context": null, "protein_count": 1, "driver_count": 0 }
```

`aggresome` is why `taxonomic_support_n` ships next to the scope rather than
nowhere: `Bacteria` is a correct derivation from this dataset's six annotated
*E. coli* proteins, and a wrong statement about the organelle, which in the
literature is a microtubule-dependent mammalian structure. `rho_body` shows the
NULL case — its single protein is deleted in UniProt, so there is nothing to
derive from (`R3-OWN-rho-body`).

`?category=` is gone with the column. It is not translated, and FastAPI ignores
unknown query params, so an old client passing it gets the unfiltered list.

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

Re-measured 2026-08-12 against the regenerated DB. The api/-phase capture of this
block predated both the PhaSepDB double-ingestion fix and the accession merge, so
its per-protein totals were several times too high (FUS read 1036 rows against
today's 37); these are the current numbers:

```
=== /protein/P35637 (FUS) ===
total annotations: 37
unified_role distribution: {None: 12, 'driver': 21, 'client': 4}

=== /protein/P09651 (hnRNP A1) ===
total annotations: 30
unified_role distribution: {'client': 8, 'driver': 12, None: 10}

=== /protein/P38919 (eIF4A3) ===
total annotations: 13
unified_role distribution: {'client': 9, None: 4}

=== /protein/Q9NQC3 (RBM14) ===
total annotations: 2
unified_role distribution: {None: 1, 'client': 1}

=== /protein/O23702 (regulator-only) ===
total annotations: 1
unified_role distribution: {None: 1}
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
