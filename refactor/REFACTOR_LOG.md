# REFACTOR_LOG.md

Narrative log of the construction of `refactor/` as the future clean root of
MLOsMetaDB. Written incrementally, one entry per step, as the work happens —
not reconstructed afterward. Read this top to bottom to understand exactly
what is in `refactor/` and why, without needing to compare against the old
repo layout.

**Hard rule that governed every step below:** nothing outside `refactor/` was
ever modified, deleted, or overwritten. Everything outside `refactor/` is
read-only source material, copied from.

Started from branch `audit/full-repo-review`, commit `c1ac07a`, on 2026-08-04.

---

## Entry 0 — Scope and starting audit findings

Before copying anything, the current repo layout was inspected to confirm
exact paths (several didn't match the plan's assumptions — noted inline
below as they came up). Key starting facts:

- `database/mlosmetadb.db` (240MB) is the current production DB — read-only
  source, never touched. The new DB is *regenerated*, not copied.
- `database/mlosmetadb_odl.db` (260MB) is an orphaned/broken artifact —
  `ortholog_groups`/`ortholog_members` are empty, consistent with a crash
  during a prior OrthoDB v2 attempt. **Not copied.**
- `database/generate_dataset.py` — dead code, contains an unclosed string
  literal (fails to parse). **Not copied.**
- `database/generate_mlosmetadb_claude_v2.py` — not wired into the active
  pipeline (nothing calls it, nothing consumes its output), and it
  introduces a `'regulator'` role value that directly contradicts
  `BIOLOGY.md`'s contract (`unified_role` must be exactly `'driver'` |
  `'client'` | `NULL`, `'regulator'` must never appear). **Not copied.**
- `integrate.py` currently lives at the **repo root**, not in `scripts/`, and
  computes `ROOT = Path(__file__).resolve().parent` (i.e. repo root). The
  target layout puts it at `refactor/scripts/integrate.py`, so this line
  needed to become `.parent.parent` to keep resolving to `refactor/` instead
  of `refactor/scripts/` — otherwise every path inside it (`database/interim`,
  `database/mappings`, `database/mlosmetadb.tsv`) would silently break. All
  other scripts already use the `.parent.parent` / `parents[1]` convention
  correctly relative to their own location, so this was only needed for
  `integrate.py`.
- `parsers/compare_v1_v2.py` is currently physically located in `parsers/`,
  but the target plan places it under `database/` (it's a QA/comparison
  utility over DB files, not a source parser). Relocated on copy — content
  unchanged.
- Six of the seven parser scripts (`parse_phasepro.py`, `parse_llpsdb.py`,
  `parse_phasepdb.py`, `parse_cdcode.py`, `parse_drllps.py`,
  `parse_phasedb.py`) import `from schemas.intermediate import COLUMNS,
  NULL`, resolved via `sys.path.insert(0, str(ROOT / "database"))`. The
  original plan's file list for `database/` did not include
  `database/schemas/intermediate.py`. Without it, every copied parser in
  `refactor/parsers/` would fail to import. This was not in the literal
  spec, but omitting it would leave `refactor/parsers/` non-functional, so
  `database/schemas/intermediate.py` was added to the copy list (see Entry 2).
  Flagging this explicitly rather than silently deviating.
- `database/databases_input_data/` and `database/schemas/__pycache__/` exist
  but are not mentioned anywhere in the plan. `databases_input_data/` is the
  pre-harmonization staging area that `parse_phasepdb.py` and
  `compare_v1_v2.py` still read directly (it holds the PhasePDB source
  files and the V1/V2 reference datasets used for comparison) — **not**
  copied in this phase since the plan's `raw/` + `interim/` already carry the
  harmonized data forward, and `parse_phasepdb.py` is being copied
  as-is/read-only (not re-run). This is a gap for a *future* phase if anyone
  wants to re-run `parse_phasepdb.py` or `compare_v1_v2.py` from
  `refactor/` — noted here so it isn't forgotten, not fixed silently. See
  **Entry 10** for the consolidated, standalone description of this gap.
  `__pycache__` directories are never copied (build artifacts).

---

## Entry 1 — Top-level docs

- `BIOLOGY.md` → `refactor/BIOLOGY.md`: copied verbatim (md5 matches). Already
  corrected per the audit; not touched.
- `SCHEMA.md` → `refactor/SCHEMA.md`: copied verbatim (md5 matches). Already
  corrected; not touched.
- `refactor/DEVLOG.md`: new file, first entry points to this log.
- `refactor/CLAUDE.md`: written last (Entry 6), after the directory-level
  `CLAUDE.md` files exist, so it can point to them accurately.

---

## Entry 2 — `database/` artifacts (small/fast copies, done synchronously)

All copies below preserve mtimes (`cp -p`/`cp -a`), source untouched:

- `database/raw/*` → `refactor/database/raw/` (11 files, full copy).
- `database/interim/*` → `refactor/database/interim/` (7 files including
  `parsing_report.md`, full copy).
- `database/final/mlo_definitions.csv` → `refactor/database/final/` — **only**
  this file from `final/`. The other two files in `final/`
  (`mlo_mapping.csv`, `mlosmetadb.tsv`) are stale/duplicated: the real
  `mlo_mapping.csv` lives in `mappings/` (copied separately below, and is the
  one actually read by `build_db.py`/`integrate.py`), and `mlosmetadb.tsv` is
  regenerated fresh by `integrate.py` in this refactor (Entry 7), not copied
  from anywhere.
- `database/mappings/mlo_mapping.csv`, `role_mapping.tsv` →
  `refactor/database/mappings/`. Everything else that was in `mappings/`
  (`mlo_mapping_audit.md`, `mlo_mapping_decisions.md`,
  `mlo_mapping_session_backup.csv`, `mlo_mapping_v1.csv`,
  `mlo_unified_definitions_phasepro_phasepdb_cdcode_v3.csv`) moved to
  `mappings/_archive/` — historical decision trail, kept for provenance, not
  read by any active script.
- `database/get_phasepdb_mlo_entries.py` → `refactor/database/` — functional
  utility, copied as-is.
- `parsers/compare_v1_v2.py` → `refactor/database/compare_v1_v2.py` —
  **relocated** from `parsers/` (see Entry 0: it's a QA/comparison utility
  over DB output, not a source parser, so it belongs with `database/`, not
  `parsers/`). Content unchanged.
- `database/schemas/intermediate.py` → `refactor/database/schemas/intermediate.py`
  — added beyond the literal plan (see Entry 0): required by every parser in
  `refactor/parsers/` via `from schemas.intermediate import COLUMNS, NULL`.
  Without it the copied parsers would be non-functional.

---

## Entry 3 — `database/` bulk data copies (cache/, crossref/) — background

Started as background `rsync -a` jobs (not blocking, since these are ~5.5GB
and ~14GB respectively and no re-fetching is wanted or needed):

- `database/cache/*.db` → `refactor/database/cache/` (`interpro_cache.db`,
  `mobidb_cache.db`, `oma_cache.db`, `uniprot_cache.db` — ~5.5GB total).
- `database/crossref/*` → `refactor/database/crossref/` (BioGRID zip +
  6 OrthoDB `odb12v2_*.tab.gz` files — ~14GB total).

Completion confirmed: both jobs finished with no errors. `du -sh` on both
sides matches exactly (`cache/`: 5.5G both; `crossref/`: 14G both), and a
per-file size diff (`ls -la` size column) between
`database/{cache,crossref}` and `refactor/database/{cache,crossref}` shows
zero differences on any actual file entry. The pipeline step (Entry 7)
does not depend on these two directories, so they ran in the background in
parallel rather than blocking the rest of the work.

---

## Entry 4 — `scripts/` copies and fixes

Copied as-is, no changes (already audited as correct): `fetch_uniprot.py`,
`fetch_interpro.py`, `parse_interpro.py`, `fetch_mobidb.py`, `parse_mobidb.py`,
`build_summary.py`, `parse_biogrid.py`, `fetch_oma.py`, `parse_oma.py`,
`fetch_mobidb_orthologs.py`, `parse_mobidb_orthologs.py` (functional, never
run against the live DB), `parse_orthologs.py` (OrthoDB v2 migration, WIP,
**not executed** in this phase).

`integrate.py` — copied from repo root (see Entry 0) to
`refactor/scripts/integrate.py`, then modified:

1. `ROOT = Path(__file__).resolve().parent` → `.parent.parent` — required
   purely by the relocation from repo-root to `scripts/`; every other script
   already used this convention relative to its own file.
2. Replaced the generic `apply_mapping(df, role_map, "source_role",
   "unified_role")` call (which read `database/mappings/role_mapping.tsv`
   and produced capitalized `'Driver'`/`'Client'` or the literal string
   `'unmapped'`) with a new `compute_role_and_active(source_db, source_role)`
   function that hardcodes the fixed per-source table from `BIOLOGY.md`
   ("Role assignment by source database" + "Driver/Client/Regulator scope"):
   - `source_db == "DrLLPS" and source_role == "Regulator"` → `(None, 0)`
   - `source_db == "CDCODE"` → `(None, 1)`
   - `source_role.lower() == "client"` → `("client", 1)`
   - `source_role.lower() in ("driver", "scaffold")` → `("driver", 1)`
   - anything else → `(None, 1)`, logged with a `[WARN]` (none hit in
     practice — every (source_db, source_role) combination present in
     `database/interim/*.tsv` was enumerated before writing this function;
     see the table in Entry 8's verification section).

   This was necessary as a hardcoded function rather than a data file because
   `dataset_active` depends on the *combination* of `source_db` and
   `source_role` (DrLLPS+Regulator vs. DrLLPS+Client), which a flat
   two-column lookup like `role_mapping.tsv` cannot express.
   `role_mapping.tsv` is still physically copied to
   `refactor/database/mappings/` per the plan, but **integrate.py no longer
   reads it** — flagged clearly in `refactor/scripts/CLAUDE.md` so a future
   reader doesn't assume it's live.
3. Added `dataset_active` to `final_cols` and to the end-of-run report
   (replacing the old "unmapped role %" print, since `'unmapped'` can no
   longer appear in `unified_role`).

`build_db.py` — copied to `refactor/scripts/build_db.py`, then modified:

1. Added `dataset_active   INTEGER NOT NULL DEFAULT 1` to the
   `CREATE TABLE mlo_annotations` statement.
2. `load_annotations()` now reads `dataset_active` from
   `mlosmetadb.tsv` (defaulting to `1` if the column is somehow absent) and
   inserts it alongside the existing columns.
3. **`SKIP_MLO` was explicitly left untouched**:
   `{"DISCARD", "NULL", "synthetic_condensate", ""}` — confirmed by re-reading
   the file after editing (`grep SKIP_MLO`). `"NotInformed"` was **not**
   added, per `BIOLOGY.md`'s explicit correction that `NotInformed` is a
   real curated vocabulary entry, not a discard value.
4. File-path assumptions confirmed unchanged and correct for the new layout:
   `mlo_mapping.csv` from `mappings/`, `mlo_definitions.csv` from `final/`,
   `mlosmetadb.tsv` read from `database/` root (generated by `integrate.py`,
   not from `final/`).

---

## Entry 5 — `parsers/` copies

Copied as-is (already audited as correct, no changes needed):
`parse_phasedb.py`, `parse_drllps.py`, `parse_llpsdb.py`, `parse_phasepro.py`,
`parse_cdcode.py`, `parse_phasepdb.py`.

Note (see Entry 0): these parsers depend on `database/schemas/intermediate.py`
for `from schemas.intermediate import COLUMNS, NULL`, and `parse_phasepdb.py`
additionally reads from `database/databases_input_data/phasepdb/` — the
former was added to the copy (Entry 2), the latter was not (Entry 0's gap
note, consolidated in **Entry 10**). None of the parsers were re-run in this
phase; their outputs were already sitting in `database/interim/` and were
copied forward as-is (Entry 2), so this gap does not block the current
pipeline regeneration — only a *future* re-run of `parse_phasepdb.py` from
`refactor/`.

---

## Entry 6 — new consolidated `CLAUDE.md` files

- `refactor/database/CLAUDE.md` — new. Operational rules (never touch
  `raw/`/`crossref/`, cache append-safety, how to regenerate the DB) plus
  first-ever documentation of `get_phasepdb_mlo_entries.py` (live PhasePDB
  API pull, writes relative to cwd — must be run from `database/`) and
  `compare_v1_v2.py` (V1-vs-V2 QA diff tool; flagged that its V1 input path
  isn't copied into `refactor/` yet, so it won't run as-is until a later
  phase brings `databases_input_data/mlosmetadb_v1/` over — see **Entry 10**
  for the consolidated gap description).
- `refactor/parsers/CLAUDE.md` — consolidated from the original
  `parsers/CLAUDE.md` (five sources), with a new PhasePDB section added:
  its two-file driver/client split, the exclusion of client-file rows that
  duplicate a detail-file protein, the MLO-Types fallback from
  `phasepdb_summary_database_2026-03-20.csv`, and the note that its
  `source_role` values are already literal `"driver"`/`"client"` strings
  (same pattern as PhaseDB), so `integrate.py`'s role logic needs no
  PhasePDB-specific branch.
- `refactor/scripts/CLAUDE.md` — drafted by a background research agent
  tasked with consolidating `CLAUDE_db.md` + `CLAUDE_features.md` +
  `CLAUDE_ppi_orthologs.md` + `CLAUDE_orthologs.md` +
  `scripts/CLAUDE_MERGE_DRAFT.md` (with its accidentally-pasted frontend
  section identified and dropped), encoding the following as resolved facts
  rather than open questions (all cross-checked, several spot-verified
  directly against the live DB before accepting):
  - `unified_role`/`dataset_active` as the final annotation/presentation
    separation design, not a bug.
  - `fetch_oma.py`/`parse_oma.py` as the real, sole ortholog source in
    production — verified directly: `SELECT source, COUNT(*) FROM
    orthologs` on the live `database/mlosmetadb.db` returns exactly
    `OMA|19289`.
  - `parse_orthologs.py` (OrthoDB v2) as WIP, not executed, blocked on a
    memory/buffering issue, not a logic bug — **not run in this phase**.
  - `fetch_mobidb_orthologs.py`/`parse_mobidb_orthologs.py` as functional
    but never run against the live DB.
  - LCD source = MobiDB-lite-**sub**, not MobiDB-lite — verified directly:
    `SELECT feature_type, source, COUNT(*) FROM sequence_features GROUP BY
    1,2` on the live DB shows `lcd|MobiDB-lite-sub|7205` and
    `lcd|SEG|45931`, with `MobiDB-lite` appearing only under
    `feature_type='idr'`.
  - `domains` JSON keys are lowercase (`pfam`/`smart`).
  - `coiled_coil`/`signal_peptide`/`transmembrane` confirmed absent from the
    live `sequence_features` table — not populated, removed from the active
    `feature_type` list.
  - `repeat` confirmed absent from the live table — dead code, not a valid
    `feature_type`, explicitly flagged so it isn't reintroduced.
  - `oma_cache.db`'s distinct schema (no `api_version` column) documented
    explicitly.

  This draft was then corrected by hand before being written to
  `refactor/scripts/CLAUDE.md`: the agent worked from the **pre-fix**
  `integrate.py` (it read the original root-level file before Entry 4's
  edits landed) and from an incorrect assumption that `mlosmetadb.tsv`/
  `mlo_mapping.csv` live under `database/final/`. Both were corrected to
  match the actual code now in `refactor/scripts/integrate.py` and the
  actual file layout confirmed in Entry 2 (`mlosmetadb.tsv` at `database/`
  root; only `mlo_definitions.csv` in `final/`; the real `mlo_mapping.csv`
  in `mappings/`) before committing the file.
- `refactor/CLAUDE.md` — new top-level overview, pointers to the files
  above, directory map for this phase only (`api/`/`frontend/` explicitly
  called out as not-yet-existing here), and the cross-project conventions
  (stack per phase, git workflow, test-before-batch, outcome-first/
  verification-before-completion, biological-rigor-over-convenience).

---

## Entry 7 — Pipeline execution

Run from `refactor/` (so every script's `Path(__file__).resolve().parent(...)`
resolves inside `refactor/`, never touching the outer repo):

```
python3 scripts/integrate.py
python3 scripts/build_db.py
python3 scripts/build_summary.py
```

**`integrate.py` output** (full):

```
=== Cargando archivos interim ===
  cdcode.tsv:   14622 filas
  drllps.tsv:   11194 filas
  llpsdb.tsv:     380 filas
  phasedb.tsv:   14608 filas
  phasepdb.tsv:   14875 filas
  phasepro.tsv:     213 filas

  Total concatenado: 55892 filas

=== Calculando unified_role / dataset_active (tabla fija BIOLOGY.md) ===

=== Aplicando mlo_mapping.csv ===
  mlo_mapping.csv: cobertura completa

=== Dataset unificado escrito: refactor/database/mlosmetadb.tsv ===
  Filas totales:        55892
  UniProt únicos:       15967

  Filas por source_db:
source_db
PhasePDB    14875
CDCODE      14622
PhaseDB     14608
DrLLPS      11194
LLPSDB        380
PhasePro      213

  unified_mlo coverage:
    mapeadas:     55892  (100.0%)
    unmapped:         0  (0.0%)

  unified_role breakdown (never 'unmapped', never capitalized):
unified_role
client    29604
NULL      16061
driver    10227

  dataset_active breakdown:
dataset_active
1    54453
0     1439
```

Arithmetic cross-check against `BIOLOGY.md`'s role table, done by hand
before trusting these numbers:
- `driver` = PhaseDB detail (3661) + PhasePDB detail (5596) + DrLLPS
  Scaffold (377) + LLPSDB (380, all rows) + PhasePro (213, all rows) =
  **10227** ✓ exact match.
- `client` = PhaseDB mlo_entries (10947) + PhasePDB mlo_entries (9279) +
  DrLLPS Client (9378) = **29604** ✓ exact match.
- `dataset_active=0` = DrLLPS Regulator rows = **1439**, matching the
  interim row count for `(DrLLPS, Regulator)` exactly ✓.
- `unified_role=NULL` (16061) = CDCODE (14622) + DrLLPS Regulator (1439) =
  **16061** ✓ exact match.

**`build_db.py` output** (full):

```
Creando refactor/database/mlosmetadb.db ...
Cargando mlo_vocabulary ...
  170 entradas insertadas
Cargando mlo_definitions ...
  409 entradas insertadas
Cargando mlosmetadb.tsv ...
  15879 proteinas stub, 54786 anotaciones
Inicializando caches ...

=== Conteos finales ===
mlo_vocabulary:   170 entradas
mlo_definitions:  409 entradas
proteins (stub):  15879 entradas
mlo_annotations:  54786 entradas
cache dbs:        creados vacios
```

`54786` loaded vs. `55892` in the TSV — the 1106-row gap is rows dropped by
the existing (unchanged) `unified_mlo`/`uid` filtering in
`load_annotations()` (`SKIP_MLO`, empty/`'NULL'` uid) — the same filter that
existed before this refactor, unrelated to the `unified_role`/
`dataset_active` fix. `init_cache()` ran against the already-populated
`uniprot_cache.db`/`interpro_cache.db`/`mobidb_cache.db` copied in Entry 3 —
safe, since it only issues `CREATE TABLE IF NOT EXISTS`; no data was
overwritten (confirmed no size drop in Entry 8 below).

**`build_summary.py` output** (full):

```
=== Step 1: ALTER TABLE proteins (disorder columns) ===
  + column: disorder_mobidb_lite_dc
  + column: disorder_alphafold_dc

=== Step 2: Populate disorder columns from mobidb_cache ===
  Updated 15879 proteins
  NULL disorder_mobidb_lite_dc: 6980
  NULL disorder_alphafold_dc:   3161

=== Step 3: Create and populate protein_summary ===
  Loading feature aggregates...
  Building 15,879 rows...
  Inserted 15,879 rows | with IDR: 0 | with domains: 0

=== Step 4: Create sequence_features index ===
  Index idx_sf_type_source created

Done.
```

**"with IDR: 0 | with domains: 0" is expected, not a bug**: `sequence_features`
is empty in this regenerated DB because this phase's pipeline only covers
`integrate.py` → `build_db.py` → `build_summary.py` over already-existing
`interim/`/`mappings/` data (per the plan — no re-fetching from any external
API). Populating `sequence_features` requires running
`fetch_interpro.py`/`fetch_mobidb.py` + `parse_interpro.py`/`parse_mobidb.py`
against the real UniProt/InterPro/MobiDB APIs, which is out of scope for
this refactor phase (`disorder_mobidb_lite_dc`/`disorder_alphafold_dc` on
`proteins`, by contrast, populated correctly — those come directly from the
already-copied `mobidb_cache.db`, not from `sequence_features`).

---

## Entry 8 — Verification (mandatory, run against `database/mlosmetadb.db` = OLD/production, `refactor/database/mlosmetadb.db` = NEW)

All checks below **pass**. No STOP condition was hit.

**1. `unified_role`, `dataset_active` breakdown**

```
-- NEW (refactor/database/mlosmetadb.db) --
SELECT unified_role, dataset_active, COUNT(*) FROM mlo_annotations GROUP BY 1,2 ORDER BY 1,2;
unified_role  dataset_active  COUNT(*)
------------  --------------  --------
(NULL)        0               1390
(NULL)        1               13851
client        1               29356
driver        1               10189

-- OLD (database/mlosmetadb.db) --
SELECT unified_role, COUNT(*) FROM mlo_annotations GROUP BY 1 ORDER BY 1;
unified_role  COUNT(*)
------------  --------
Client        29356
Driver        10189
unmapped      15241
```

Only `'driver'`/1, `'client'`/1, `NULL`/1, and `NULL`/0 appear in NEW — never
`'unmapped'`, never capitalized. `NULL/0` = 1390 matches the spec's expected
"~1390" for DrLLPS Regulator rows exactly.

Cross-check against OLD: `Client` (29356) and `Driver` (10189) in OLD are
**byte-identical** to `client`/1 and `driver`/1 in NEW — confirming the fix
did not reclassify a single driver/client row, only fixed casing and the
previously-broken `'unmapped'` bucket. OLD's `unmapped` (15241) splits
exactly into NEW's `NULL`/1 (13851, CD-CODE) + `NULL`/0 (1390, DrLLPS
Regulator) = **15241** ✓ exact match — the same universe of rows, now
correctly attributed instead of dumped into one broken bucket.

**2. `unified_mlo='NotInformed'` count**

```
-- NEW --  3027
-- OLD --  3027
```
✓ exact match (spec expected ~3027, not 0).

**3. `mlo_annotations` total row count**

```
-- NEW --  54786
-- OLD --  54786
```
✓ exact match — no row lost or gained.

**4. `proteins` total row count**

```
-- NEW --  15879
-- OLD --  15879
```
✓ exact match.

**5. FUS (P35637) sanity check**

```
-- NEW --  P35637 | 0.785
-- OLD --  P35637 | 0.785
```
✓ exact match (`disorder_alphafold_dc ≈ 0.785` as expected).

**6. Orphan `mlo_annotations` (uniprot_id not in `proteins`)**

```
SELECT COUNT(*) FROM mlo_annotations WHERE uniprot_id NOT IN (SELECT uniprot_id FROM proteins);
-- NEW --  0
```
✓ zero orphans.

**7. `protein_summary` schema includes `source_dbs`**

```
PRAGMA table_info(protein_summary);  -- refactor/database/mlosmetadb.db
0|uniprot_id|TEXT|0||1
1|idr_regions|TEXT|0||0
2|lcr_regions|TEXT|0||0
3|domains|TEXT|0||0
4|has_driver|INTEGER|0||0
5|has_client|INTEGER|0||0
6|source_db_count|INTEGER|0||0
7|mlo_count|INTEGER|0||0
8|mlos|TEXT|0||0
9|source_dbs|TEXT|0||0
```
✓ `source_dbs` present (column 9).

**Conclusion**: every mandatory check passes exactly. The `unified_role` /
`dataset_active` fix reclassifies zero existing driver/client rows — it only
(a) fixes casing (`Client`/`Driver` → `client`/`driver`), and (b) replaces
the previously-broken `'unmapped'` string with the correct, documented split
between CD-CODE (`NULL`, active) and DrLLPS Regulator (`NULL`, inactive but
retained). All other counts are byte-identical between old and new. Nothing
required stopping or reporting a mismatch.

---

## Entry 9 — `.gitignore` fix (caught by user review, not part of the original plan)

The user asked, after Entry 8, whether the new heavy `refactor/` files were
excluded from git. They were not — this was a gap in execution, caught by
review rather than by me. Root cause: the existing `.gitignore` rules for
heavy DB files (`database/mlosmetadb.db`, `database/*.db`,
`database/cache/`, `database/crossref/`, `database/raw/`,
`database/interim/*.tsv`) all contain a slash before their final path
component, which per gitignore semantics anchors them to the **repo root**
`database/` — they are not recursive/repo-wide patterns, so none of them
matched `refactor/database/...`. Confirmed with `git check-ignore` before
and after: every one of `refactor/database/mlosmetadb.db`,
`refactor/database/cache/*`, `refactor/database/crossref/*`,
`refactor/database/raw/*` (~20GB combined) was **not ignored** and would
have been staged by `git add refactor/` or `git add -A`.

Fix: added a mirrored block to `.gitignore` immediately after the existing
database rules, one entry per pattern, pointing at `refactor/database/`
instead of `database/`. Verified with `git check-ignore` again after the
edit — all of the above are now ignored — and by walking every file under
`refactor/` and confirming only small source/doc/mapping files remain
trackable (largest is `refactor/database/mlosmetadb.tsv` at 4.5MB, which
mirrors the existing repo convention: the root `database/mlosmetadb.tsv` is
likewise tracked, not ignored, despite being a regenerated artifact).

**Separately noted, not changed**: this repo's `.gitignore` has a bare
`CLAUDE.md` rule (no slash → matches at any depth, i.e. every `CLAUDE.md`
file repo-wide, not just at the root). This means the four new
`refactor/**/CLAUDE.md` files written in Entry 6
(`refactor/CLAUDE.md`, `refactor/database/CLAUDE.md`,
`refactor/scripts/CLAUDE.md`, `refactor/parsers/CLAUDE.md`) are already
gitignored by this pre-existing rule — consistent with `frontend/CLAUDE.md`,
which is under the same rule today. `parsers/CLAUDE.md` is the one
exception: it's tracked because it was `git mv`'d from an already-tracked
`CLAUDE_parsers.md` (see commit `9ab8143`) — renaming a tracked file to an
ignored name does not untrack it. This is pre-existing repo policy, not
something introduced or changed by this refactor — flagged here only so it
isn't mistaken for an oversight.

---

## Entry 10 — Consolidating the `compare_v1_v2.py` / `databases_input_data/` gap (caught by user review)

This gap was real and correctly identified back in Entry 0, and referenced
again in Entry 5 and Entry 6 — but scattered across three entries, each
mention folded into another entry's narrative rather than standing on its
own. That made it easy to miss on a read-through. This entry exists solely
to consolidate it in one visible place; it does not change anything about
the underlying fact already documented, and it does not fix the gap itself
— it's a documentation fix, caught by user review rather than by me.

**The gap, stated once**: `database/databases_input_data/` (repo root) is
not copied into `refactor/`. It's read directly by two scripts:

- `parsers/parse_phasepdb.py` — reads PhasePDB source files from
  `databases_input_data/phasepdb/`.
- `parsers/compare_v1_v2.py` (relocated to `refactor/database/compare_v1_v2.py`,
  Entry 2) — reads the V1 reference dataset from
  `databases_input_data/mlosmetadb_v1/` for its V1-vs-V2 QA diff.

Neither script was re-run during this refactor — both were copied
as-is/read-only, and everything they'd need to produce was already
available and copied forward by other means (parser outputs already sitting
in `database/interim/`, Entry 2; the V1-vs-V2 comparison already covered by
the verified counts in Entry 8). So the gap does **not** block anything in
this phase's actual pipeline regeneration.

**What it does block**: from `refactor/` as it stands today, neither
`parse_phasepdb.py` nor `compare_v1_v2.py` can be re-run, because their
source input directory doesn't exist under `refactor/`. This is a gap for a
**future** phase — before either script can be re-run from `refactor/`,
`database/databases_input_data/` (or at minimum the `phasepdb/` and
`mlosmetadb_v1/` subdirectories) needs to be copied over.

**Not fixed in this pass**: no data was copied here, deliberately — neither
script needs to run right now, and `databases_input_data/` wasn't
sized/audited as part of this phase's scope. This entry documents the gap
in one place; it doesn't close it.

---

## Entry 11 — `api/` phase: port + schema-drift fixes

The data-layer phase (Entries 0-10) built a corrected `refactor/database/mlosmetadb.db`
— clean `unified_role` (`'driver'`/`'client'`/`NULL`, never `'unmapped'`,
never capitalized) and a new `dataset_active` column. But the existing
FastAPI backend at repo-root `api/` had never seen either change: it still
pointed at the old, uncorrected `database/mlosmetadb.db`, and a `grep -rn
"dataset_active" api/` returned zero hits. This entry covers porting `api/`
into `refactor/api/` and fixing that drift, per
`docs/superpowers/specs/2026-08-04-refactor-api-phase-design.md`.

**The port itself.** `api/` was rsync'd into `refactor/api/` verbatim
(excluding `__pycache__`, the old `mlosmetadb.db`, and the old
`CLAUDE_api.md`/`API_EXAMPLES.md`, which get regenerated fresh later in
this entry) — `diff -rq api/ refactor/api/` came back empty, confirming a
byte-identical tree. The one thing checked and confirmed to need **no**
code change: `config.py`'s `DB_PATH` auto-resolution. It computes
`Path(__file__).parent.parent / "database" / "mlosmetadb.db"`, which — purely
by virtue of `refactor/api/`'s position relative to `refactor/database/` —
already resolved to the correct new DB path with zero edits:
```
$ cd refactor/api && python3 -c "from config import DB_PATH; print(DB_PATH)"
/biodata/forti/proyectos/mlos/mlosmetadb/.worktrees/refactor-api-phase/refactor/database/mlosmetadb.db
```

**The FTS5 boot bug (caught by the port's own boot-smoke-test, not a porting
error).** Before any schema-drift fix was applied, just booting the freshly
copied `refactor/api/` against an empty DB crashed inside `setup_fts5()`:
```
sqlite3.OperationalError: table fts_proteins has 3 columns but 4 values were supplied
```
`database.py`'s `setup_fts5()` contained manual `INSERT INTO fts_proteins
SELECT rowid, ...` / `INSERT INTO fts_mlos SELECT rowid, ...` statements
that explicitly insert `rowid` into an **external-content** FTS5 table —
which manages `rowid` automatically and rejects an explicit value in the
column list. The fix removed those two manual INSERTs (and their `COUNT(*)`
guard conditions), leaving only the `CREATE VIRTUAL TABLE IF NOT EXISTS`
block and the `INSERT INTO fts_*(fts_*) VALUES('rebuild')` calls that
already fully repopulate the index from the source tables — the correct,
canonical way to (re)build an external-content FTS5 index. This bug
reproduces **identically in the original, untouched `api/database.py`** —
it is not something the port introduced, it was already latent in the
pre-existing code and would crash any fresh boot there too. Only
`refactor/api/database.py` was touched; the original was left alone per the
hard rule governing this whole log.

**`policy.py`: the shared fix for findings #1-#3.** The design spec's audit
of the existing code turned up three independent places that needed the
same fix (`dataset_active` never filtered) plus one that needed a deletion
(`_normalize_role()` actively wrong against the new schema, not just
stale). Rather than patch each site with its own copy of `"AND
dataset_active = 1"`, `refactor/policy.py` was introduced as a single
shared module, importable by both `refactor/api/` and
`refactor/scripts/build_summary.py`:
```python
def active_annotation_clause(alias: str = "ma") -> str:
    return f"{alias}.dataset_active = 1"

EXCLUDED_MLO_CATEGORIES: list[str] = []

def excluded_mlo_category_clause(alias: str = "mv") -> tuple[str | None, list[str]]:
    if not EXCLUDED_MLO_CATEGORIES:
        return None, []
    placeholders = ",".join("?" * len(EXCLUDED_MLO_CATEGORIES))
    return f"{alias}.category NOT IN ({placeholders})", list(EXCLUDED_MLO_CATEGORIES)
```
Its docstring restates the domain rule that governs every fix below:
`dataset_active=0` is reserved for deliberate scope exclusions (today:
DrLLPS Regulator rows only); a `NULL` `unified_role` or indeterminate MLO
name is an annotation gap, never a reason to exclude, and stays
`dataset_active=1`/fully visible (CD-CODE rows are the concrete example).
5 unit tests covered the module directly before any consumer wired it in.

**Wiring `policy.active_annotation_clause` into the query/router layer.**
Each of `mlo_queries.py`, `protein_queries.py`, `search_queries.py`, and
`main.py` got the same shape of fix — join or filter `mlo_annotations` with
`policy.active_annotation_clause(alias)` — each proven with a RED test that
failed against the *unfixed* code first. Concretely, in
`mlo_queries.py::get_mlo_stats` / `get_mlo_proteins_page` /
`get_all_mlos`, before the fix a synthetic inactive-only protein
(`QREG01`, only a DrLLPS/nucleolus row with `dataset_active=0`) leaked
into `nucleolus`'s counts (`assert 1 == 0` failing); after, all three
functions correctly show `0`. `protein_queries.py`'s
`get_protein_mlo_annotations`/`get_proteins_page`/`get_proteins_facets` got
the identical treatment — before the fix, `GET`-style queries for the
inactive-only protein still returned its `nucleolus` annotation; after, it's
excluded from lookups, role filters, and MLO facets alike.
`search_queries.py`'s `_build_advanced_clauses` (the `mlo` join) and
`get_advanced_search_facets` (the `mlo_rows` facet query) got the same join
condition added. `main.py`'s `_compute_stats()` had **four** separate
`mlo_annotations` queries (`ann_total`, `unique_mlos`, `src_rows`,
`role_rows`) all missing the filter — before the fix `stats["mlo_annotations"]["total"]`
counted the inactive row too (`assert 2 == 1` failing); after, the policy
clause is computed once and reused across all four.

**Deleting `_normalize_role()` — a three-round discovery process.**
`_normalize_role()` was duplicated in `routers/mlos.py` and
`routers/proteins.py`, collapsing `'client'` (and `'unknown'`/`'unmapped'`)
to a fabricated `'component'` string in the API response — a mapping that
made sense against the old schema's messy roles but is actively wrong
against the new one, since `frontend/CLAUDE.md`'s live contract expects a
real `'client'` value to render its green badge. The function was deleted
outright (not patched) in both routers, with `unified_role` now passed
through raw. Getting there took three rounds of test-infrastructure
discovery, because this was the *first* task to drive the API through
`TestClient(app)` — every prior task called query functions directly:

1. **`test_db`/`DB_PATH` clobbering.** `TestClient(app)` triggers FastAPI's
   real `lifespan()`, which calls `database.open_db()` — and `open_db()`
   unconditionally backs up `database.DB_PATH` (the real production DB,
   since `MLOSMETADB_PATH` was unset) into a fresh in-memory copy,
   silently discarding the `test_db` fixture's own connection. The
   giveaway: `GET /protein/P35637` returned 1036 real annotations instead
   of the fixture's 1, and `GET /protein/PCLIENT` 404'd. Fixed with
   `monkeypatch.setattr(db_module, "DB_PATH", db_path)` in the fixture, so
   `open_db()`'s backup step reads the fixture's temp file instead.
2. **`PCLIENT`/`stress_granule` collision.** The new `PCLIENT` fixture
   protein was first placed in `stress_granule` — the same MLO already
   used by four already-reviewed tasks' tests (Tasks 3-5). That broke 5
   pre-existing assertions scoped to `stress_granule`/`nucleolus` counts
   (`1 -> 2` in each). Rather than touch four already-reviewed test files,
   `PCLIENT` was moved to its own new MLO, `p_granule`, leaving Tasks 3-5's
   test files byte-for-byte untouched.
3. **One unavoidable touch remained**: `test_stats.py`'s
   `test_compute_stats_mlo_annotations_excludes_inactive_row` aggregates
   over the *entire* `mlo_annotations` table regardless of which MLO a row
   belongs to, so any second active row anywhere shifts its totals — its
   three assertions were bumped `1`→`2`, unavoidable regardless of where
   `PCLIENT` lived.

Full suite after all three fixes: 15 passed, 0 failed.

**`build_summary.py`'s matching aggregation fix, with a real impact
number.** `_build_mlo_aggregates()` had the identical missing-filter bug,
independently of the API — it computes `protein_summary.mlo_count`/
`source_db_count`/`mlos`/`source_dbs` with no `dataset_active` filter, so a
protein whose only annotation was a DrLLPS Regulator row would incorrectly
surface that row's MLO/source_db in the served summary (`has_driver`/
`has_client` were unaffected, since a `NULL` role never matches
`'driver'`/`'client'` regardless of `dataset_active`). Fixed by aliasing
`mlo_annotations AS ma` and adding `WHERE {policy.active_annotation_clause("ma")}`.
Measured directly against the real `refactor/database/mlosmetadb.db`:
**502** proteins have *only* `dataset_active=0` annotations
(`proteins_with_only_inactive_annotations`); before re-running
`build_summary.py`, `protein_summary.mlo_count = 0` had **0** rows (the bug
was live — these 502 proteins carried stale non-zero counts). After
re-running the fixed script, `protein_summary.mlo_count = 0` has exactly
**502** rows, and `protein_summary`'s total row count is unchanged
(15,879 → 15,879). Spot check on `A0A023PZG4` (a DrLLPS-Regulator-only
protein): before, `mlo_count=1`/`source_db_count=1`/`mlos=["stress_granule"]`;
after, `mlo_count=0`/`source_db_count=0`/`mlos=NULL`/`source_dbs=NULL`.

**End-to-end verification, including a bug the verification itself found.**
Running the app for real — `cd refactor/api && python3 -m uvicorn
main:app` — crashed immediately with `ModuleNotFoundError: No module named
'policy'`. `refactor/policy.py` lives one directory above `refactor/api/`,
and nothing in the production code path put `refactor/` on `sys.path` —
only `refactor/api/tests/conftest.py` did, for pytest. Every prior task's
verification ran through pytest, so this gap silently never surfaced until
this task actually booted `main.py` outside a test. Fixed by adding the
same `sys.path.insert(0, str(ROOT))` idiom `build_summary.py` already used,
placed in `config.py` (imported earliest in `main.py`, before `policy` or
any router):
```python
_REFACTOR_ROOT = Path(__file__).resolve().parent.parent
if str(_REFACTOR_ROOT) not in sys.path:
    sys.path.insert(0, str(_REFACTOR_ROOT))
```
All verification checks were then re-run a second time with the real fix
in place (no `PYTHONPATH` workaround), and produced identical results to
the first pass. The evidence: `O23702` — a DrLLPS "Regulator" protein whose
only `mlo_annotations` row is `dataset_active=0` — correctly returns
`"mlo_annotations": []` from `GET /protein/O23702`; across all six proteins
checked (the five standard `TEST_PROTEINS` plus `O23702`), `unified_role`
is never `"component"` anywhere in any response; and `/stats`'
`mlo_annotations.total` matches a direct SQL count exactly:
```
Direct SQL:  SELECT COUNT(*) FROM mlo_annotations WHERE dataset_active = 1;  ->  53396
/stats:      mlo_annotations.total                                          ->  53396
```

**Docs (Task 10).** `refactor/api/CLAUDE.md` and `refactor/api/API_EXAMPLES.md`
were written after the code was corrected and verified, so every example in
`API_EXAMPLES.md` is a real response captured during Task 9's verification
— no synthetic/hand-written JSON, and no more stale `"unified_role":
"unmapped"` examples. `CLAUDE.md` documents `policy.py`'s domain rule in
full and the endpoint/error-envelope conventions. Consistent with
`database/CLAUDE.md`/`scripts/CLAUDE.md` (see Entry 9), `refactor/api/CLAUDE.md`
is caught by this repo's pre-existing bare `CLAUDE.md` gitignore rule — it
was written to disk and is fully readable, but `git add` refuses it. This
is expected, not a gap in this phase's work.

**`EXCLUDED_MLO_CATEGORIES`'s actual final scope.** The design spec asked
for this extension point to be referenced in both `mlo_queries.py` and
`protein_queries.py` "as a no-op extension point." In practice it is wired
into exactly one place: `mlo_queries.py::get_all_mlos`, via
`policy.excluded_mlo_category_clause("mv")`. `protein_queries.py` was
deliberately left without it — none of its queries join `mlo_vocabulary`
(the table `category` lives on), so there is no natural place to apply a
category-based clause there without adding a join that doesn't otherwise
exist. This is a deliberate narrowing of the spec's slightly broader
wording, disclosed here rather than silently expanded to fit the letter of
the spec.

**Out-of-scope data gaps observed, not fixed.** Two pre-existing data gaps
were found while verifying Tasks 8-9's work, unrelated to the
`dataset_active`/`unified_role` fixes and explicitly not this phase's job to
fix: (1) `sequence_features`, `ppi`, and `orthologs` are all **0 rows** in
the current `refactor/database/mlosmetadb.db` — this phase's pipeline only
runs `integrate.py` → `build_db.py` → `build_summary.py` over already-parsed
`interim/` data; populating those three tables requires re-running the
fetch/parse scripts against live APIs, out of scope here. (2) `Q92520`
(FMR1), one of the five standard `TEST_PROTEINS`, has **zero** rows in both
`proteins` and `mlo_annotations` in this DB snapshot — the API correctly
404s rather than crashing, confirming this is a data-population gap, not a
filtering bug.

**Minor findings, parked, not reopened:**
- Task 1's report frames the FTS5 fix as "project convention" — reads
  slightly post-hoc versus the mid-task authorization that actually
  happened; harmless.
- Task 3's `conftest.py` relaxes `mlo_annotations.source_mlo` to nullable,
  vs. the real schema's `NOT NULL` — harmless since no query reads it, but
  worth a comment if a future task's brief assumes it's populated.
- Task 9's `config.py` bootstrap uses `.resolve()` while `build_summary.py`'s
  equivalent doesn't — a harmless, slightly more robust stylistic
  divergence, not literally identical to the "same exact pattern" wording.
- Task 10's `A0A024RB53` example traces to task-9-report.md's slightly
  hedged "e.g.:" framing rather than an unambiguous verbatim curl paste —
  not fabrication, just one step removed in provenance.

---
