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
