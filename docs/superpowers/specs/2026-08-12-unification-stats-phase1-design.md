# Data unification section — Phase 1 (data layer) design

**Source spec:** `docs/review/unification_section/INFORME_SECCION_UNIFICACION.md`
(external audit deliverable, "Claude Science"). This document covers only
Phase 1 of that report's implementation — the data layer. Phases 2 (API
exposure) and 3 (frontend section) are separate, later specs.

**Baseline commit:** `f71a5002c4395e1261d7e161533147a6a0cd5f65` — the current
tip of `fix/biology-audit-stage2` at design time. The audit's own reference
outputs (`docs/review/unification_section/data/stats.json` and `*.csv`) were
computed against this exact commit, so they double as a verification fixture
for this phase (see "Verification" below) — not a permanent regression
fixture, since the numbers will legitimately change on the next DB rebuild.

## Why Phase 1 is scoped this way

The full report covers four independent subsystems: (A) a role-harmonisation
mapping, (B) a stats-build script producing JSON + 2 downloadable CSVs, (C)
API exposure, (D) a frontend section with 6 interactive figures. Frontend
design (chart library, page placement) shouldn't be decided before the
underlying numbers are confirmed correct, so this phase stops at A+B: get the
data artifacts built, tested, and verified against the audit's own reference
output. C and D get their own spec once this lands.

## A. Architecture decision: role harmonisation mapping

**The conflict.** The report's §6.4 asks to "define `role_mapping` in one
place (`database/mappings/role_mapping.tsv`) and consume it from both the ETL
and the stats script — today the 8-label mapping is reconstructed ad hoc."
But `scripts/CLAUDE.md` documents a deliberate, audited decision that
`integrate.py`'s `compute_role_and_active()` must **not** be driven by a flat
`source_role → unified_role` table, because `dataset_active` (and, for
DrLLPS, `unified_role` itself) depends on the **combination** of `source_db`
and `source_role` — a plain `role_mapping.tsv` keyed by `source_role` alone
cannot express "DrLLPS Regulator" vs. "DrLLPS Client" needing different
treatment. `role_mapping.tsv` on disk is also stale (capitalized values the
code rejects, missing 4 of the 8 real pairs).

**Resolution.** Do not make `integrate.py` read a mapping file. Instead:

1. Create `database/mappings/role_harmonisation.csv`, keyed by
   `(source_db, source_role)` (not `source_role` alone), with the category
   the report actually needs on top of what `integrate.py` already computes:

   ```
   source_db,source_role,unified_role,category,evidence_type,note
   CDCODE,NotInformed,NULL,component,membership_only,CD-CODE asserts membership only, no role claim
   DrLLPS,Client,client,component,curator_assignment,Curator-assigned; protein-scoped (propagates to every MLO of the protein)
   DrLLPS,Regulator,NULL,regulator,curator_assignment,Curator-assigned; served with unified_role=NULL per R1-ACT-14
   DrLLPS,Scaffold,driver,driver,curator_assignment,Curator-assigned
   LLPSDB,driver,driver,driver,in_vitro_llps,Purified protein phase-separates in vitro; no cellular claim
   PhaSepDB,client,client,component,cellular_localisation,Reported present in the condensate in cells
   PhaSepDB,driver,driver,driver,cellular_requirement,Perturbing it disrupts the condensate in cells
   PhasePro,driver,driver,driver,in_vitro_llps,Purified protein phase-separates in vitro; no cellular claim
   ```

   `NULL` is the literal string (matching the pipeline's existing sentinel
   convention), not an empty field. Plain LF — this is a new file, not one of
   the two CRLF-trap files (`mlo_mapping.csv`, `mlo_definitions.csv`)
   documented in `database/CLAUDE.md`.

   `category` derivation rule, for the anti-drift test to check: `driver` iff
   `unified_role == 'driver'`; `regulator` iff `source_db == 'DrLLPS' and
   source_role == 'Regulator'`; else `component`.

2. `scripts/build_unification_stats.py` (Phase 1 §B) reads this file and
   joins on it — this is the file's only consumer at runtime.

3. `tests/test_role_harmonisation.py` cross-checks every row against
   `integrate.py`'s existing `compute_role_and_active()` and
   `compute_evidence_type()`, and checks the row set is exactly the pair-set
   `integrate.py`'s own `EVIDENCE_TYPE` dict enumerates — no more, no fewer.
   This is what "un solo lugar" actually protects against (drift), without
   requiring `integrate.py` to read a file whose grain can't express what its
   code already correctly expresses. If a 9th `(source_db, source_role)` pair
   is ever ingested, this test fails until both `EVIDENCE_TYPE` and
   `role_harmonisation.csv` are updated together.

`dataset_active` is deliberately **not** a column in this file: it's serving
policy (what gets shown), not a biological mapping (what a source claims).
Baking it into a lookup table would misrepresent it as a mapping fact instead
of a policy decision. It stays as code in `compute_role_and_active()`, which
is also the correct extension point if a future exclusion is ever justified
(see `docs/review/findings.csv` process).

**Correctness note for later phases:** the report's own prose (§4, figure
F4) says "`driver` groups `in_vitro_llps` with `cellular_requirement`" — two
evidence types. The real mapping has **three** (`in_vitro_llps`,
`cellular_requirement`, and `curator_assignment` via DrLLPS Scaffold), per
the audit's own `f4_role_mapping.csv`. `build_unification_stats.py` must
report the true distinct count; the report's copy gets corrected against
that when Phase 3 writes the actual web text — not fixed here.

**Cleanup, bundled into this phase:**
- Move `database/mappings/role_mapping.tsv` to
  `database/mappings/_archive/role_mapping.tsv` (same pattern as other
  superseded mapping drafts already archived there) — its current content
  actively misleads (capitalized values the code rejects, 4 of 8 pairs
  missing).
- Fix `compute_role_and_active()`'s docstring/comment in `integrate.py`: it
  currently narrates the pre-`R1-ACT-14` behavior (`dataset_active=0` for
  DrLLPS Regulator) as if still in effect. Update it to describe the current
  branch and mention `role_harmonisation.csv` as the audited, tested
  companion table (not the source of truth — `integrate.py`'s code remains
  that).

## B. `scripts/build_unification_stats.py`

**Inputs:** `database/mlosmetadb.db` (rows filtered by
`policy.active_annotation_clause()`), `database/mappings/role_harmonisation.csv`.

**Outputs**, written to **`database/exports/`** (new directory, sibling to
`mappings/` and `final/` — pipeline-owned derived artifacts, no dependency on
`frontend/` existing; Phase 2/3 decide how these reach the API/SPA):

### 1. `unification_stats.json`

```json
{
  "meta": {
    "db_commit": "<git rev-parse HEAD at build time>",
    "build_date": "<ISO timestamp>",
    "n_annotations": 35732
  },
  "summary": {
    "n_annotations": 35732,
    "n_proteins": 15694,
    "n_unified_mlo_terms": 177,
    "n_source_entries": 481,
    "collapse_ratio": 2.72,
    "proteins_multi_source": 9327,
    "proteins_single_source": 6367,
    "shared_pairs": 10617,
    "concordant_pairs": 9299,
    "discordant_pairs": 1318,
    "disc_patterns": { "component|driver": 713, "...": "..." },
    "cat3_annotations": { "component": 31275, "driver": 3068, "regulator": 1389 },
    "cat3_evidence_types": { "component": 3, "driver": 3, "regulator": 1 },
    "unique_pmids": 3766,
    "annotations_without_pmid": 13733,
    "pairs_pmid_comparable": 2205,
    "pairs_independent_pub": 1312,
    "pairs_shared_pub": 893
  },
  "f1_source_contribution": [ {"source_db": "...", "annotations": 0, "proteins": 0, "source_terms": 0, "unified_terms": 0} ],
  "f2_protein_source_combos": [ {"combo_label": "...", "n_proteins": 0, "n_sources": 0} ],
  "f3_vocab_collapse": [ {"unified_mlo": "...", "n_source_names": 0, "n_sources": 0, "annotations": 0, "proteins": 0} ],
  "f4_role_mapping": [ {"source_db": "...", "source_role": "...", "evidence_type": "...", "category": "...", "annotations": 0, "proteins": 0} ],
  "f5b_discrepancy_by_mlo": [ {"unified_mlo": "...", "n_discordant": 0} ],
  "f6_pmid_overlap_sources": [ {"db_a": "...", "db_b": "...", "n_a": 0, "n_b": 0, "shared": 0, "jaccard": 0.0} ]
}
```

`cat3_evidence_types` (distinct evidence_type count per category) is the
field that makes the "driver has 3, not 2" correction machine-checkable
instead of a comment.

The full 1,318-row per-pair detail (`f5_role_discrepancy_pairs`) is **not**
embedded in the JSON — it is exactly the grain of the `discrepant_pairs.csv`
downloadable table below, so embedding it would duplicate the same data in
two formats for no reader; F5's chart only needs `disc_patterns` and
`f5b_discrepancy_by_mlo`, both already in the JSON. `f7_evidence_independence`
(the 2,205-row per-pair PMID-overlap detail) is **not** output anywhere in
this phase either — the report only asks for it as chart input, not as a
downloadable table, and its only chart-relevant aggregate
(`pairs_independent_pub`/`pairs_shared_pub`, F6's left panel) is already in
`summary`. If Phase 3 ends up needing the raw per-pair rows (e.g. for a
click-through), add them then — no chart in the report's F1-F6 needs them
directly.

### 2. `discrepant_pairs.csv` (1,318 rows)

Columns: `uniprot_id, gene_name, unified_mlo, sources, categories,
source_roles, evidence_types, pmids_per_source`.

`sources`/`categories`/`source_roles`/`evidence_types` are `;`-joined lists,
**aligned by position** across all four columns, ordered by `source_db`
ascending, so column *N* of each is about the same contributing source.
`pmids_per_source` uses `source_db=pmid1,pmid2` pairs joined by `;`
(`source_db=` with nothing after `=` when that source cited no PMID for this
pair), e.g. `DrLLPS=12345,67890;PhaSepDB=`.

### 3. `mlo_term_mapping.csv` (~481 rows)

Columns: `unified_mlo, source_db, source_mlo, annotations, proteins,
definition`. One row per `(unified_mlo, source_db, source_mlo)` triple found
in `mlo_definitions` joined against `mlo_annotations` aggregates (`annotations`
= row count, `proteins` = distinct `uniprot_id` count) for that exact triple;
`LEFT JOIN` so a triple with no curated definition still appears with
`definition = NULL` rather than being dropped.

### Regression test: `tests/test_unification_stats.py`

- `sum(summary.cat3_annotations.values()) == summary.n_annotations`.
- `summary.n_annotations == SELECT COUNT(*) FROM mlo_annotations WHERE
  dataset_active = 1` (direct DB query, not reusing the script's own number).
- Every `(source_db, source_role)` pair present in `mlo_annotations` has a row
  in `role_harmonisation.csv` — fails loudly on an unmapped pair, per the
  report's own §6.3 requirement.

### Verification (one-time, not a permanent test)

Because the live DB is at the exact commit the audit computed its reference
output against, diff the script's fresh output against
`docs/review/unification_section/data/stats.json` and the `f*.csv` files
field-by-field before calling this phase done. Any difference must be
explained (rounding, a genuinely different grain) — not silently accepted.

## Out of scope for this phase (unchanged from the report's §8)

No reclassification, no inferring missing roles, no source-quality ranking.
Also out of scope here specifically: the API endpoint(s) that will serve
these artifacts, and everything frontend (chart library choice, page
placement, copy). Those are Phase 2 and Phase 3.
