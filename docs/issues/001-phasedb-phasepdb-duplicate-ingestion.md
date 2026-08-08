# PhaSepDB was ingested twice under two `source_db` tags, inflating every count

**Labels:** `bug`, `data-integrity`, `pipeline`, `frontend`
**Severity:** high — affected published coverage figures and hid data from the UI
**Status:** **resolved 2026-08-08.** Opened while assembling the biology review
dossier (`docs/review/`) on the same day.

---

## Summary

`PhaseDB` and `PhasePDB` were two ingestion tags for the **same upstream
resource**, PhaSepDB. Two parsers read what were described as "two different
exports" of it and wrote two interim files, which `integrate.py` concatenated
without any deduplication. PhaSepDB was therefore counted as two independent
source databases everywhere in the dataset.

`policy.py` already knew the two tags were one resource — `CANONICAL_SOURCE_NAMES`
mapped both to `"PhaSepDB"` — but that map only fixed the **display name** in two
endpoints. The duplicate rows themselves were never addressed.

## Root cause

**The two parsers read byte-identical files.** Not two exports, not two
snapshots — the same two files, copied twice under different names:

```
2d71a9af55c03ef5f4af7654de430f4d  database/raw/phasedb_mlo_entries.tsv
2d71a9af55c03ef5f4af7654de430f4d  OLD/.../phasepdb/phasepdb_mlo_entries_from_script.tsv
702bec3f19768d19e1031d2e24744beb  database/raw/phasedb_detail.csv
702bec3f19768d19e1031d2e24744beb  OLD/.../phasepdb/phasepdb_detail_database_2026-03-20.csv
```

Every row difference between `phasedb.tsv` (14,608 rows) and `phasepdb.tsv`
(14,875) came from the parsers, not from the data:

- `parse_phasepdb.py` used the summary export's `MLO Types` as a fallback for
  rows with an empty `MLO`, recovering 813 real MLO names that
  `parse_phasedb.py` filled with `NotInformed` — hence 5,596 driver rows
  vs. 3,661.
- `parse_phasepdb.py` excluded from the component dataset every protein already
  present in the driver dataset; `parse_phasedb.py` excluded nothing — hence
  9,279 client rows vs. 10,947.

Neither parser deduplicated, and both sources emit one row per supporting
publication, so identical annotations were also stacked within each file.

`parsers/CLAUDE.md` asserted these were "two separate source databases with
confusingly similar names", which is why the double ingestion went unnoticed.
That claim has been corrected.

## Evidence (against the pre-fix `database/mlosmetadb.db`)

| Check | Result |
|---|---|
| Distinct proteins under `PhaseDB` | 7,755 |
| Distinct proteins under `PhasePDB` | 7,755 |
| Shared between them | **7,755 (identical sets)** |
| Driver proteins, each tag | 1,873 / 1,873, fully shared |
| `(protein, unified_mlo, source_mlo)` triples present under both tags | **9,522** |
| Total annotation rows | 54,786 |

```sql
-- protein sets are identical
WITH a AS (SELECT DISTINCT uniprot_id FROM mlo_annotations WHERE source_db='PhaseDB'),
     b AS (SELECT DISTINCT uniprot_id FROM mlo_annotations WHERE source_db='PhasePDB')
SELECT (SELECT COUNT(*) FROM a), (SELECT COUNT(*) FROM b),
       (SELECT COUNT(*) FROM a JOIN b USING(uniprot_id));
-- 7755 | 7755 | 7755
```

## Impact (before the fix)

### 1. Inflated counts in the served dataset

| Location | Symptom |
|---|---|
| `api/main.py` — `/stats` `ann_total` | Reported 54,786 annotations |
| `api/main.py` — `/stats` `src_rows` | Raw `GROUP BY source_db`; rendered PhaseDB and PhasePDB as two separate resources in the About page charts |
| `api/queries/mlo_queries.py` — MLO detail `by_source` | Same raw grouping, per MLO |
| `scripts/build_summary.py` — `source_db_count` | `COUNT(DISTINCT source_db)` inflated **7,755 proteins by +1** |

`source_db_count` is a sortable column in the protein table, so the error was
directly visible to users:

| sources | proteins (before) | proteins (after) |
|---:|---:|---:|
| 1 | 1,981 | 6,201 |
| 2 | 9,848 | 6,646 |
| 3 | 1,029 | 2,385 |
| 4 | 2,376 | 91 |
| 5 | 89 | 54 |
| 6 | **54** | **0 — there were only ever 5 resources** |

### 2. The frontend did not know `PhasePDB` existed

`MlosPage.vue`'s `SOURCE_DBS` listed five entries with no `PhasePDB`. The filter
is applied as `ma.source_db = ?` against the raw tag, so selecting "PhaseDB"
returned only half of PhaSepDB — 14,875 annotations including 5,596 driver rows
were unreachable from the interface.

### 3. Cosmetic fallout from the same gap

- `SourceDbBadge.vue`'s `COLOR_MAP` had no `PhasePDB` key, so those badges fell
  through to `?? COLOR_MAP.DrLLPS` and rendered in DrLLPS's grey — a badge
  reading "PhasePDB" painted in another database's colour.
- `ProteinMLOs.vue`'s dedup key is `unified_mlo || source_db || source_mlo`.
  Since `source_db` differed, the 9,522 otherwise-identical triples survived as
  visible duplicate rows on the protein page.
- `ProteinHeader.vue`'s `SOURCE_ORDER.filter(s => present.has(s))` silently
  dropped `PhasePDB` from the badge row.

## The decision this needed

A first reading of the interim files suggested neither export was a superset of
the other (10,663 vs. 9,589 `(protein, MLO)` pairs, 9,515 shared), and that 214
pairs carried conflicting roles — `client` under `PhaseDB`, `driver` under
`PhasePDB`, never the reverse. Both observations were artifacts of the parser
differences described under **Root cause**, not properties of the source data.

The 214 "conflicts" are real biology, though, and the user resolved how to treat
them: PhaSepDB publishes a driver dataset and an MLO-component dataset, and a
protein can appear in both. Driving phase separation and being detected inside a
condensate are two different experimental observations, so **both annotations are
kept**, each with its own PMIDs. No source gets special treatment: the row grain
is `(uniprot_id, source_db, source_mlo, source_role)`, the same as everywhere
else. Recorded in `BIOLOGY.md`.

## What was done

1. **One parser.** `parsers/parse_phasedb.py` and `parsers/parse_phasepdb.py`
   were replaced by `parsers/parse_phasesepdb.py`, emitting
   `source_db = "PhaSepDB"` and reading all three inputs from `database/raw/`
   (which removed the pipeline's last dependency on `OLD/`). It keeps the better
   behaviour of each: the summary `MLO Types` fallback from one, no
   driver/component exclusion from the other.
2. **Deduplication at integration, for every source.**
   `scripts/integrate.py`'s `collapse_duplicates()` collapses to one row per
   `(uniprot_id, source_db, source_mlo, source_role)`, merging PMIDs into a
   semicolon-separated `evidence` string — the shape DrLLPS and LLPSDB already
   produced. No PhaSepDB-specific branch.
3. **`build_db.py` made re-runnable**, deleting `mlo_annotations` and
   `mlo_definitions` before loading. Without this, the documented three-command
   regeneration silently appended a second copy of every row — a latent
   duplication bug of the same family, found while applying this fix.
4. **Regenerated** `mlosmetadb.tsv` → `mlo_annotations` → `protein_summary`.
   `proteins`, `sequence_features`, `ppi` and `orthologs` were not rewritten.
5. **Updated consumers**: `policy.py`'s `CANONICAL_SOURCE_NAMES`,
   `schemas/intermediate.py`'s `SOURCE_DBS`, the four frontend source lists,
   `frontend/src/data/stats.json`, and the API test fixtures.

## Verification

Expected values were stated before running; these are the actuals.

```
SELECT COUNT(*) FROM mlo_annotations;                      -- expected 35,971 → 35971
SELECT COUNT(DISTINCT source_db) FROM mlo_annotations;     -- expected 5      → 5
SELECT MAX(source_db_count) FROM protein_summary;          -- expected 5      → 5
SELECT COUNT(*) FROM protein_summary WHERE source_db_count = 6;  -- expected 0 → 0
SELECT COUNT(DISTINCT uniprot_id) FROM proteins;           -- expected 15,879 unchanged → 15879
SELECT COUNT(*) FROM mlo_annotations
  WHERE source_db IN ('PhaseDB','PhasePDB');               -- expected 0      → 0
```

Rows per source, after:

```
CDCODE      13845
DrLLPS      10872
PhaSepDB    10675
LLPSDB        380
PhasePro      199
```

The protein count is unchanged, as required: the merge removed duplicate
annotation rows, never proteins. Enrichment tables were untouched
(`sequence_features` 358,867 · `ppi` 917,468 · `orthologs` 19,289). Test suites:
94 passed in `api/tests/`, 8 in `tests/`.

Dual-role preservation, spot-checked on FUS (P35637), which PhaSepDB reports as
both a driver and a component of the nucleolus — two rows, distinct PMIDs:

```
P35637  PhaSepDB  Nucleolus  nucleolus  driver  37549257;37782826;34496937;...
P35637  PhaSepDB  Nucleolus  nucleolus  client  15635413
```

214 `(protein, unified_mlo)` pairs carry both roles under PhaSepDB — the same
214 the pre-fix analysis had mistaken for conflicts.

## Notes

- This was an ingestion defect, not a curation one. No biological mapping
  decision in `mlo_mapping.csv` changed as a result.
- It changed every coverage figure the project would publish. Any number taken
  from a dataset snapshot dated before 2026-08-08 is inflated.
- A running API server holds an in-memory copy of the DB taken at boot, so it
  keeps serving the old numbers until `uvicorn` is restarted.
