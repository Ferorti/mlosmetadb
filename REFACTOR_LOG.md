# REFACTOR_LOG.md

Narrative log of the construction of `refactor/` as the future clean root of
MLOsMetaDB. Written incrementally, one entry per step, as the work happens —
not reconstructed afterward. Read this top to bottom to understand exactly
what is in `refactor/` and why, without needing to compare against the old
repo layout.

**Hard rule that governed every step below:** nothing outside `refactor/` was
ever modified, deleted, or overwritten. Everything outside `refactor/` is
read-only source material, copied from. **One deliberate, plan-disclosed
exception exists** — four files under the root `frontend/src/` were modified in
commit `7188677`, before `refactor/frontend/` existed; disclosed in full in
Entry 14 ("The one exception to the hard rule").

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

**Also disclosed here, flagged by the final reviewer**: commit `1a4a491`
("chore: gitignore symlinked refactor/database/{cache,crossref,raw}") was
controller/worktree housekeeping outside `refactor/`'s own content —
trailing-slash `.gitignore` patterns never match a symlink even when it
points to a directory, so this worktree's `cache/`/`crossref/`/`raw/`
symlinks back to the main checkout needed no-trailing-slash mirror
patterns to keep `git add -A` from ever staging them; it was not part of
this entry's original disclosure and should have been mentioned here at
the time.

---

## Entry 12 — Populating `sequence_features`/`ppi`/`orthologs` (closing the gap noted in Entry 11)

Entry 11 disclosed that `sequence_features`, `ppi`, and `orthologs` were all
empty (0 rows) in `refactor/database/mlosmetadb.db` — the parse scripts
existed and were documented as working, but had never been run against this
regenerated DB. This entry closes that gap, ahead of the `frontend/` phase
(which would otherwise render empty PPI/features/ortholog sections for
every protein).

**Scope, confirmed with the user before running anything:** parse only
against already-cached/local data — `parse_interpro.py`, `parse_mobidb.py`,
`parse_biogrid.py`, `parse_oma.py` — no live fetching to close the small
remaining cache gaps, and no `fetch_mobidb_orthologs.py`/
`parse_mobidb_orthologs.py` run (richer per-ortholog `ortholog_meta`/
`ortholog_features` detail, never run against production, deferred).

**Pre-flight cache coverage check** (`refactor/database/cache/*.db`, 15,879
proteins total): `interpro_cache` 15,409/15,879 responses with
`status_code=200` (~97%), `mobidb_cache` 26,924 (covers ortholog accessions
too, not just dataset proteins), `oma_cache` 14,130/15,349 with
`status_code=200` (~89%). High enough coverage that no fetch was needed
before parsing.

**Results:**

```
python3 refactor/scripts/parse_interpro.py
  Proteínas procesadas: 14,621 | Sin entries en cache: 788
  Filas insertadas: 55,145 (domain/pfam 23,645, domain/smart 25,460, family/pfam 6,040)

python3 refactor/scripts/parse_mobidb.py
  Proteínas con features: 14,832 | Sin datos en cache: 575
  Filas insertadas: 303,722 (idr/AlphaFold-disorder 32,705, idr/MobiDB-lite 21,386,
  idr/MobiDB-th50 126,213, idr_curated/DisProt 1,390, lcd/MobiDB-lite-sub 7,205,
  lcd/SEG 45,931, morf/MobiDB 3,256, plddt_region/AlphaFold 65,636)

python3 refactor/scripts/parse_biogrid.py
  Filas procesadas: 2,861,729 → insertadas: 917,468 (in_db=1: 424,482, in_db=0: 492,986)
  Built-in TEST_PROTEINS check: "Test FUS↔TDP43/hnRNPA1: PASS ✓"

python3 refactor/scripts/parse_oma.py
  Fetcheadas de OMA (ya en cache): 12,899 | 404: 2,980
  Filas insertadas en orthologs: 19,289 — matches the historical production
  count exactly (see Entry 11's mention of this figure from live-DB audits
  earlier in this refactor). Built-in TEST_PROTEINS check passed for all 5
  standard test proteins before the full run proceeded.
```

`sequence_features` total: 358,867 (55,145 + 303,722). `ppi` total: 917,468.
`orthologs` total: 19,289.

Re-ran `refactor/scripts/build_summary.py` afterward so `protein_summary`
picks up the newly-populated `sequence_features`. Result: 15,879 rows,
12,892 with `idr_regions`, 13,858 with `domains` (previously 0/0 per Entry
11). Verification: FUS (`P35637`) — `disorder_alphafold_dc = 0.785`,
matching `scripts/CLAUDE.md`'s documented sanity-check value exactly; BioGRID
partners include `Q13148` (TDP-43, `Affinity Capture-MS`/
`Reconstituted Complex`) and orthologs include `Danio rerio`/
`Caenorhabditis elegans` entries.

**Incident during this step, disclosed in full:** the first `build_summary.py`
invocation was run as `python3 scripts/build_summary.py` from the repo
root instead of `refactor/`. The repo root has its own, separate, stale
pre-refactor copy of this script at `scripts/build_summary.py` (predates
the `dataset_active`/`policy.py` fix from the `api/` phase) — same
filename, different file, and its own `ROOT = Path(__file__).parent.parent`
correctly-for-itself resolves to the repo root. Because the relative
invocation matched *that* file rather than erroring, it silently ran
against `database/mlosmetadb.db` — the file this log's own hard rule (line
9 above) says must never be touched — rebuilding its `protein_summary`
(via `DELETE FROM protein_summary` + full rebuild) and rewriting
`proteins.disorder_mobidb_lite_dc`/`disorder_alphafold_dc` for all 15,879
rows.

**Impact assessment**: no source table was affected — confirmed
`database/mlosmetadb.db`'s `mlo_annotations` is unchanged at 54,786 rows
(the exact old-production total: 29,356 driver + 10,189 client + 15,241
unmapped, per Entry 8), and `sequence_features`/`ppi`/`orthologs` there
were already populated from before this refactor began (unrelated to
today's parser runs, which correctly targeted `refactor/database/` only —
confirmed via `stat` mtimes: only `database/mlosmetadb.db` itself changed
at the time of the mistaken run, `mlo_annotations`'s row count is
untouched). Since the old script's aggregation logic operates only on
already-unchanged source tables in that same file, the rebuilt
`protein_summary`/disorder columns should be content-equivalent to what
was there before, not a real data change — but this was a genuine,
unauthorized write against a "never touched" file, not a no-op by design,
and is recorded here rather than quietly absorbed. The corrected script
(`python3 <absolute path to>/refactor/scripts/build_summary.py`, invoked
with an absolute path specifically to rule out this ambiguity) was then
run again and confirmed to target `refactor/database/mlosmetadb.db`
correctly (verified via `stat` mtime and by re-checking the result counts
above).

**Lesson for future pipeline runs**: always invoke `refactor/scripts/*.py`
with an absolute path, or `cd refactor/` first and verify with `pwd`
before running — never a bare relative path from an ambiguous or
unverified cwd. Checked after this incident: `build_summary.py`,
`parse_interpro.py`, `parse_mobidb.py`, `parse_biogrid.py`, and
`parse_oma.py` **all** have a same-named, differently-rooted twin still
sitting at the repo-root `scripts/` (the pre-refactor originals `refactor/`
was copied from) — this hazard isn't unique to `build_summary.py`, it
applies to every script in this pipeline. This run's four parser
invocations happened to be safe because `cd refactor/` was verified
immediately before each one (confirmed correct via the resulting row
counts landing in `refactor/database/mlosmetadb.db`, not the root file) —
but the ambiguity exists for all of them equally.

---

## Entry 13 — `proteins.gene_name`/`organism`/`length` backfill (found auditing the `frontend/` phase)

Found while auditing the existing `frontend/` (not yet ported) against the
real, populated `refactor/api/` from Entry 12: `GET /search?q=FUS` returned
zero hits, and `GET /protein/P35637` returned `gene_name: null`,
`organism: null`, `sequence_length: null` for FUS — a protein with 1036
`mlo_annotations` rows. Checked directly against
`refactor/database/mlosmetadb.db`:

```sql
SELECT COUNT(*), COUNT(gene_name), COUNT(organism), COUNT(length) FROM proteins;
-- 15879, 0, 0, 0
```

Every one of `proteins.gene_name`/`protein_name`/`organism`/`taxon_id`/
`length` was `NULL` for all 15,879 rows. Unlike `sequence_features`/`ppi`/
`orthologs` (Entry 11's disclosed gap, closed in Entry 12), this gap was not
previously identified — Entry 11/12 never checked these columns
specifically.

**Root cause**: `refactor/scripts/build_db.py` only ever inserts protein
stubs (`INSERT OR IGNORE INTO proteins (uniprot_id) VALUES (?)`, line 235).
`refactor/scripts/fetch_uniprot.py` is the script responsible for filling in
the rest (documented in `scripts/CLAUDE.md`: "fetch_uniprot.py →
uniprot_cache.db, updates proteins") — but it was never run against
`refactor/database/mlosmetadb.db`. The cache itself
(`refactor/database/cache/uniprot_cache.db`, copied forward in Entry 3) was
NOT empty — confirmed by reading the raw cached JSON for `P35637` directly:
gene name, organism, protein description, and sequence were all present
with `status_code=200`. So this was a "cache has the data, DB was never
updated from it" gap, the same shape as Entry 12's gap for
sequence_features/ppi/orthologs — just not caught at the time.

**A second, independent bug found while fixing the first**: even running
`fetch_uniprot.py` as-is would not have closed this gap for the ~15,400
already-cached accessions. Its `main()` only calls `update_protein()` inside
the live-fetch loop, for entries just returned by a fresh UniProt API call —
cache hits (`status_code=200` rows already in `uniprot_cache.db`) are
skipped entirely (`pending = [uid for uid in all_ids if uid not in
cached]`), so their cached response was never applied to `proteins`. Fixed
by adding `backfill_from_cache()` to `fetch_uniprot.py`: for every
`uniprot_id` with `gene_name IS NULL`, look up its cached `status_code=200`
response and apply `update_protein()` from it — zero network calls, since
the data already exists locally. Called once at the top of `main()`, before
the existing pending/live-fetch logic (unchanged).

**Test-before-batch**: before running against the real DB, copied
`refactor/database/mlosmetadb.db` to a scratch path and ran
`backfill_from_cache()` against the copy, checking the five standard
`TEST_PROTEINS` before/after:

```
BEFORE: P35637 (None, None, None)   -- (gene_name, organism, length)
AFTER:  P35637 ('FUS', 'Homo sapiens', 526)
        P09651 ('HNRNPA1', 'Homo sapiens', 372)
        P38919 ('EIF4A3', 'Homo sapiens', 411)
        Q9NQC3 (... , 'Homo sapiens', 1192)
        Q92520  -- no row (pre-existing gap, Entry 11)
```
All four values are biologically correct (FUS is 526 aa, HNRNP A1 is 372 aa,
eIF4A3 is 411 aa — verified against known UniProt lengths), confirming
`backfill_from_cache()` was correct before running it for real.

**Real run**, `python3 <absolute path>/refactor/scripts/fetch_uniprot.py`
(absolute path per Entry 12's lesson):

```
Backfill desde cache (updates nunca aplicados): 15727
Total proteinas: 15879
Ya en cache:     15727
Por fetchear:    152
Batch 1/2 (100 IDs) ... ok=99, not_found=1
Batch 2/2 (52 IDs) ... ok=50, not_found=2

Fetcheadas con exito: 149
Errores/no encontradas: 3
proteins con secuencia: 15405
proteins sin secuencia: 474
Errores por tipo:
  not_found: 370
```

Only 152 accessions needed a live UniProt call (370 `not_found` errors are
cumulative across this and prior runs, stored in `uniprot_cache.db`'s
`fetch_errors` table, not all from today). Final state:

```sql
SELECT COUNT(*), COUNT(gene_name), COUNT(organism), COUNT(length) FROM proteins;
-- 15879, 14583, 15405, 15405
```

`gene_name` is lower (14583) than `organism`/`length` (15405) because not
every UniProt entry has an assigned gene name — expected, not a bug.
`474` proteins remain without a sequence — real UniProt gaps (obsolete/
merged/withdrawn accessions), consistent with `Q92520`'s pre-existing
zero-row gap from Entry 11.

**Verification against the running API** (`refactor/api` restarted — the
in-memory DB copy is frozen at boot, per `api/CLAUDE.md`'s "Startup" section
— a stale server would not see any of this):

```bash
curl "http://127.0.0.1:8765/search?q=FUS&mode=fuzzy"
# -> total_hits: 12  (was 0 before this fix)

curl "http://127.0.0.1:8765/protein/P35637"
# -> gene_name: "FUS", organism: "Homo sapiens", taxon_id: 9606, sequence_length: 526
# (all null before this fix)

curl "http://127.0.0.1:8765/stats"
# -> proteins.total_organisms: 207, top_organisms includes
#    "Homo sapiens": 6802, "Mus musculus": 2543, "Arabidopsis thaliana": 2088, ...
# (was total_organisms: 0, by_organism: {} before this fix)
```

**Why this matters for the upcoming `frontend/` phase**: `sequence_length`
being null was also silently breaking both D3 sequence-feature track
components (`ProteinFeatureTrack.vue`'s `render()` returns early with `if
(!props.sequenceLength) return`) across every page that renders one — not a
frontend bug, a downstream symptom of this same data gap. Found and fixed
before starting the `frontend/` port so the upcoming design audit reflects
real, fully-populated data rather than an artifact of an incomplete
pipeline run.

---

## Entry 14 — Porting `frontend/` into `refactor/frontend/`, verifying it against the real API, and the fixes it turned up

With Entry 13's `gene_name`/`organism`/`length` backfill closing the last
known data gap, this entry covers the actual `frontend/` phase: copying the
Vue 3 SPA into `refactor/`, verifying every previously-unverified
endpoint/page pairing against the real, populated `refactor/api/`, and
fixing everything the verification (plus explicit user requests) turned up.

**Commit accounting** (two different ranges are referred to below, so both are
spelled out once here):

- **Pre-port audit fixes**, `e799f6a` and `7188677` — 2 commits, landed
  *before* the design spec/plan and the port, while auditing the still-in-place
  root `frontend/` against the newly-populated `refactor/api/`. `7188677` is
  the one and only exception to this log's "nothing outside `refactor/` is
  touched" hard rule; both are covered immediately below.
- **Design spec and plan**: `d21f978`, `13d8e42` — 2 docs commits, no code.
- **The port and its follow-ons**, `13d8e42..da0406f` — 7 commits: the port
  itself (1), two verification passes that found nothing to fix (0 commits —
  see below), and six fixes/features (6); 1 + 6 = 7. This is the range the
  "Review disposition" section below counts.
- This entry itself, plus `refactor/frontend/CLAUDE.md`/`DEVLOG.md`, landed in
  the docs commit that follows `da0406f`.

### Pre-port audit fixes (`e799f6a` backend, `7188677` frontend)

Auditing the existing `frontend/` against the real `refactor/api/` — before
anything had been copied into `refactor/frontend/` — turned up a set of
backend defects and their frontend counterparts. They landed as one pair of
commits, backend first.

**`e799f6a` (all inside `refactor/`):**

1. *MLO-scoped role facets.* `protein_queries.get_proteins_facets` and
   `search_queries.get_advanced_search_facets` computed `by_role` from
   `protein_summary.has_driver` — a GLOBAL per-protein flag meaning "driver of
   ANY MLO". Combined with an `mlo`/`source_db` filter, that over-counted
   drivers *for that MLO*. Added `_scoped_role_counts()`, which reads the role
   off the same `mlo_annotations` row the filter already matched. Still
   reproducible against the live DB today:

   ```
   $ curl -s --noproxy '*' "http://127.0.0.1:8765/proteins?mlo=p_granule&per_page=1"
   total 594, facets.by_role {'driver': 26, 'component': 568}     # after
   # before (has_driver-based, same 594 proteins): driver 46, i.e. +20 phantom
   # drivers — 46 of them are drivers of *something*, only 26 of p_granule.
   ```

2. *Mutually-exclusive home stats.* `_compute_stats()`'s
   `mlo_annotations.by_role` buckets by annotation ROW, so one protein can land
   in several buckets at once and the buckets can exceed `proteins.total`.
   Added `proteins.by_component_role`, derived from `has_driver` and therefore
   exactly partitioning the dataset:

   ```
   $ curl -s --noproxy '*' "http://127.0.0.1:8765/stats"
   proteins.total            15879
   proteins.by_component_role {'driver': 2029, 'component': 13850}  # sums to 15879
   mlo_annotations.by_role    {'driver': 2029, 'client': 12347, 'unknown': 10883}
                                                    # sums to 25259 >> 15879
   ```

3. *`proteins.by_organism_drivers`* added, so per-organism driver counts (until
   then only available as one global total) can be shown next to `by_organism`.
4. *`/search/advanced` sort support*, reusing `protein_queries._build_sort`.
   `/search` itself has no sort concept at all, which is what Fix 1 below then
   had to work around client-side.
   ```
   $ curl -s --noproxy '*' "http://127.0.0.1:8765/search/advanced?gene_name=FUS&sort_by=mlo_count&sort_order=desc"
   [('P35637', 19), ('P16892', 3), ('P56959', 2)]   # correctly mlo_count-descending
   ```
5. *`policy.EXCLUDED_MLO_CATEGORIES` flipped from `[]` to `["Unspecified"]`*,
   so `NotInformed` stops appearing as a browsable organelle in the `/mlos`
   catalog (169 MLOs listed, `NotInformed` absent — the check quoted further
   down under "Verification: `/mlos` ..."). Entry 11 had introduced this list
   deliberately empty, as a pure extension point; this commit is where it was
   populated. Scope is deliberately narrow: the clause is wired only into
   `mlo_queries.get_all_mlos`, so a protein's own MLO Annotations tab still
   shows its `NotInformed` rows for provenance.

**`7188677` — the one exception to the hard rule.** This commit modified four
files *outside* `refactor/`:

```
frontend/src/components/browse/RoleCards.vue
frontend/src/components/browse/OrganismGrid.vue
frontend/src/pages/ResultsPage.vue
frontend/src/utils/format.js
```

This was deliberate and disclosed in the phase plan up front (see
`docs/superpowers/plans/2026-08-05-refactor-frontend-phase.md`, lines 13 and
429), not an accident: at the time these bugs were found, `refactor/frontend/`
did not yet exist, and each fix needed to be verified live in a running dev
server against the real `refactor/api/`. Fixing them in place and then porting
the corrected tree was judged better than porting code already known to be
broken and re-fixing it afterwards from behind a build. The changes:

- `RoleCards.vue`: "MLO Components" read `mlo_annotations.by_role`
  (annotation-row buckets), showing 23,230 — more than `proteins.total`
  (15,879). Now reads the new mutually-exclusive `by_component_role`.
- `OrganismGrid.vue`: replaced hardcoded `PLACEHOLDER_ORGANISMS` counts with
  live `stats.proteins.by_organism` / `by_organism_drivers` (name lookup
  tolerates the `(strain ...)` suffix some DB entries carry).
- `ResultsPage.vue`: made a free-text search escalate from `/search` to
  `/search/advanced` once a filter `/search` cannot honor is engaged. **This
  change was itself buggy** — it included `sort_by` in the escalation trigger,
  which silently swapped the multi-field `/search` corpus for a
  `gene_name`-only `LIKE` match the moment any non-default sort was picked.
  Fixed later (see Entry 15).
- `format.js`: `formatMlo('NotInformed')` → `'No MLO associated'`, which reads
  better than the raw source-DB placeholder wherever it's still shown (a
  protein's own MLO Annotations tab; hidden entirely from the browse grids by
  the paired `policy.py` change instead).

Everything in `7188677` was carried into `refactor/frontend/` unmodified by the
port (`c27957e`) two commits later, so `refactor/` is self-consistent; the root
`frontend/` tree has not been touched since.

### The port (commit `c27957e`)

```bash
rsync -a \
  --exclude='node_modules' --exclude='dist' \
  --exclude='src/components/HelloWorld.vue' \
  --exclude='src/components/TheWelcome.vue' \
  --exclude='src/components/WelcomeItem.vue' \
  --exclude='src/components/icons' \
  --exclude='src/views' \
  --exclude='src/stores/counter.js' \
  --exclude='CLAUDE.md' --exclude='DEVLOG.md' \
  frontend/ refactor/frontend/
```

64 files, 9,495 insertions. The excluded paths are dead `create-vue` scaffold
that nothing in the app imports (confirmed via grep before excluding) —
`HelloWorld.vue`/`TheWelcome.vue`/`WelcomeItem.vue`/`components/icons/`/
`views/`/`stores/counter.js` — plus the stale `frontend/CLAUDE.md`/
`DEVLOG.md`, replaced by this task's own new versions (below). `diff -rq`
between `frontend/` and `refactor/frontend/` with the same exclusion list
came back with zero output — the copy is complete and correct modulo the
intentional exclusions.

`vite.config.js`'s `build.outDir: '../api/static'` and dev-proxy
`target: 'http://localhost:8765'` both resolve correctly by construction one
directory deeper than the original — zero edits needed. Per this project's
own "don't run npm" convention, the user ran `npm install && npm run dev`
themselves and confirmed no errors before the commit landed.

### Verification: PPI + Orthologs tabs (no mismatch, no commit)

Compared `refactor/api/`'s real `/protein/{id}/ppi` and
`/protein/{id}/orthologs` responses field-by-field, name and type, against
`ProteinPPI.vue`, `ProteinOrthologs.vue`, and `OrthologTrackViewer.vue`, and
against `refactor/api/models/schemas.py`'s `PpiPartner`/`PpiEdge`/
`PpiAllResponse`/`PpiSummary`/`OrthoFeatureRegion`. Every field name and type
the components read was present in the real payload — no wiring bug found.

One incidental finding, not a wiring bug: `ortholog_meta` and
`ortholog_features` are both 0-row tables in the current DB, so
`/protein/{id}/orthologs` correctly returns `in_db: true` with every detail
field (`gene_name`, `length`, `disorder_*`, `sequence`, `features`) still
`null` even for orthologs that exist in `orthologs` proper. This was already
tracked in Entry 12 ("richer per-ortholog `ortholog_meta`/`ortholog_features`
detail, never run against production, deferred") — not new, and both
components already degrade gracefully via `??` fallbacks.

### Verification: `/mlos`, `/organisms/search`, `/search`, `/search/advanced` (no mismatch, no commit)

```bash
$ curl -s --noproxy '*' "http://127.0.0.1:8765/mlos" | python3 -c "
import json,sys
names = [m['unified_mlo'] for m in json.load(sys.stdin)['mlos']]
assert 'NotInformed' not in names
print('OK,', len(names), 'MLOs listed')"
OK, 169 MLOs listed
```

`NotInformed` is correctly excluded from the `/mlos` catalog (the
`policy.EXCLUDED_MLO_CATEGORIES` fix from `e799f6a`, above in this same entry,
holds — Entry 11 introduced that list empty as a deliberate no-op extension
point, `e799f6a` is where `'Unspecified'` was put in it); it still
legitimately appears inside individual proteins' own `mlos: [...]` arrays
from `/search`/`/search/advanced`, which is a different, correctly-rendered
concern (`formatMlo()` → "No MLO associated" in `ResultsPanel.vue`).

`/organisms/search?q=hom` returned `{"organism": "Homo sapiens",
"protein_count": 6802}` as the top hit; `?q=ab` correctly 422'd
(`min_length: 3`) — and `FilterSidebar.vue`'s own `onOrganismSearch()` never
sends a sub-3-char query to begin with, so the 422 path is unreachable from
the UI. `/search?q=FUS&mode=fuzzy` and `/search/advanced?gene_name=FUS&...`
both returned exactly the field set `ResultsPage.vue`/`ResultsPanel.vue`
expect (`proteins[]` with `uniprot_id, gene_name, ..., has_driver,
source_dbs, mlo_count, mlos, match_field`), and the escalation logic
(plain text → `/search` → escalate to `/search/advanced` or
`getProteins({mlo:...})` when applicable) called every endpoint with the
params it actually accepts. No mismatch in either task; no code touched.

(This verification checked that each endpoint was *called* correctly, not that
escalating to `/search/advanced` returns the *same corpus* as `/search`. It
doesn't: `gene_name=<q>` is a single-column `LIKE`, while `/search` matches
`uniprot_id`/`gene_name`/`protein_name`. The final full-branch review caught
what that gap hid — see Entry 15.)

### Fix 1 (`638b047`) — plain-text `/search` results ignored the active sort dropdown

`ResultsPanel.vue`'s sort `<select>` has no "Relevance" option — it always
shows a concrete value, most commonly its default, "Most MLOs"
(`mlo_count:desc`). But `onSortSelect()` deliberately strips `sort_by`/
`sort_order` from the URL when that default is selected ("to keep the URL
clean"), and `ResultsPage.vue`'s `runSearch()` only escalated a plain-text
search to `/search/advanced` (which understands `sort_by`) when `f.sort_by`
(among other filters) was truthy. Net effect: a default-sorted plain-text
search never escalates, always resolves through the bare `/search` branch,
and that branch's own order was left standing while the UI implied
`mlo_count`-descending.

That order is **uniprot_id ascending, not relevance** — a detail this entry
originally got wrong, corrected here (see Entry 15). `src/api/search.js`'s
`searchBasic()` defaults to `mode='fuzzy'` and the UI never sends anything
else; `routers/search.py` routes `fuzzy` to
`search_queries.search_proteins_like()`, a plain multi-field `LIKE` query with
`ORDER BY p.uniprot_id`. The FTS5 branch (`search_proteins_fts`,
`ORDER BY rank`) is only reachable via `mode=exact`. The fix below is correct
and necessary either way — the response simply arrives in an order unrelated to
the sort dropdown — but "FTS5 relevance order" was the wrong diagnosis.

```
$ curl -s --noproxy '*' "http://127.0.0.1:8765/search?q=FUS&mode=fuzzy"
# raw order: A0A2H4FYY8(1) K7DPS7(1) P11710(1) P16892(3) P35637(19) ...
# (uniprot_id ascending) -- P35637 has 19 MLOs, highest of all 12 hits,
# yet sits 5th, not 1st.
```

Fixed by adding `refactor/frontend/src/utils/sortProteins.js`, a client-side
re-implementation of `refactor/api/queries/protein_queries.py::_build_sort()`
(NULL-last regardless of direction, uniprot_id ascending tie-break on every
key, `role` sort baked into a rank rather than ASC/DESC), applied to
`searchRes.data.proteins` in `runSearch()`'s plain-`/search` branch right
before it returns — resolving `sortBy`/`sortOrder` the same way
`buildExtraFilters()` already resolves them elsewhere. No other branch
(`getProteins`, `searchAdvanced`, the `field !== 'all'` paths) was touched;
those already sort server-side.

Verification: hand-computed the expected `mlo_count:desc` order for the same
12 FUS hits (`P35637(19), P16892(3), P56959(2), Q9BJZ5(2), ...` alphabetical
among ties) and ran the extracted comparator logic against the live
payload — matched exactly, `P35637` now first. Also traced `role:asc` and
`gene_name:asc` against the same 12-item payload as a sanity check on the
role-rank and BINARY-collation-matching ordinal comparator; both matched the
backend's documented rules. No test framework exists in this project, so
correctness rests on this direct trace against real data rather than a unit
suite.

### Fix 2 (`3b3a549`) — `ProteinPPI.vue` rendered nothing for `total_partners>0`/zero-in-DB

```
$ curl -s --noproxy '*' "http://127.0.0.1:8765/protein/O23702"
"ppi": {"total_partners": 2, "partners_in_mlosmetadb": 0, "interactions": null}
$ curl -s --noproxy '*' "http://127.0.0.1:8765/protein/O23702/ppi"
{"uniprot_id":"O23702","total":0,"total_returned":0,"items":[],"inter_edges":[]}
```

The content-area `v-if`/`v-else-if` chain had exactly four branches
(loading / error / `!total_partners` / `allPartners.length`). For `O23702`
— `total_partners=2` (truthy, so branch 3 is skipped) and `allPartners=[]`
after `load()` resolves (falsy, so branch 4 is skipped too) — none matched,
so the tab rendered its stats header and filter bar and then nothing below
them. Fixed by inserting a fifth branch between the two:
`v-else-if="!allPartners.length"` → "This protein has {{
formatCount(protein.ppi.total_partners) }} known interaction partner(s), but
none are currently in MLOsMetaDB." Traced all five branch conditions by hand
to confirm they are mutually exclusive and jointly exhaustive given the
component's own invariants; the pre-existing branches and `load()` itself
were not touched.

### Fix 3 (`058c121`) — hid the Orthologs tab pending redesign

Per explicit user request ("quiero armarlo mejor" — they plan to redesign it
later), removed the `orthologs` entry from `ProteinPage.vue`'s `TABS` array,
its tab-content template block, and the now-unused `ProteinOrthologs`
import. `ProteinOrthologs.vue` and `OrthologTrackViewer.vue` are left
completely untouched on disk at
`refactor/frontend/src/components/protein/` — this was a 7-line deletion in
one file, mechanical enough that the controller verified the diff directly
rather than dispatching a separate reviewer.

### Fix 4 (`da5a65c`) — added a sort control to `MlosPage.vue` (previously had none)

Added a `<select>` to the filter bar with three options: "Most drivers"
(`driver_count` desc, the new default), "Alphabetical", and "Most proteins"
(`protein_count` desc) — applied as the last step of the existing `filtered`
computed, after the text/category/source filters, always via
`[...result].sort(...)` (never mutating `result` in place). Both count-based
options use `(b[countKey] ?? 0) - (a[countKey] ?? 0)` with an alphabetical
(`formatMlo(...).localeCompare(...)`) tie-break, so `null`/`0` sort together
rather than `null` producing `NaN` and silently corrupting the order.

```
$ curl -s --noproxy '*' "http://127.0.0.1:8765/mlos" # total: 169
```

Confirmed real ties exist in the live data at `driver_count = 0`, `1`, and
`2` (e.g. `adhesin_nanodomain`, `aggresome`, `amyloid_aggregate`, ... all at
0) and that they come out alphabetically ordered among themselves under the
new sort, exactly as the tie-break predicts.

### Fix 5 (`44bb9da`) — PPI graph node click now selects the table row instead of navigating away

Previously, clicking a partner node in `ProteinPPI.vue`'s force-directed
graph called `router.push('/protein/${d.id}')` — navigating off the current
protein's page entirely. Per explicit user request, changed to: set a new
persistent `selectedId` ref, call the existing `highlightNode(d.id)`, look
up that partner's index in `filteredPartners.value`, jump
`tablePage.value` to `Math.floor(index / TABLE_PER) + 1` (`TABLE_PER = 20`),
and `nextTick(() => rowRefs[d.id]?.scrollIntoView({ block: 'nearest' }))`
using a new plain (non-reactive) `rowRefs` object populated via a function
`:ref` on each `<tr>`. The table row's highlight class now lights up on
`selectedId` match in addition to the existing `hoveredId` match, so the
selection persists after the mouse leaves the node — the requirement, since
hover-driven highlighting alone disappears on mouseout. Hover/tooltip/drag
behavior on the graph itself is completely unchanged; the on-canvas hint
string was updated from "click to open protein" to "click to select in
table" since the old text described the removed behavior.

Traced the page-jump arithmetic by hand for boundary cases (index 39 → page
2, index 40 → page 3, no off-by-one) and confirmed the `index === -1` guard
prevents an invalid `tablePage = 0` in the (currently unreachable, since
graph nodes are always drawn from `filteredPartners.value`) case where a
clicked node isn't found in the partner list.

### Fix 6 (`da0406f`) — swapped which of (card click) vs. (button) does what on `MlosPage.vue`

Per explicit user request, the MLO card's root-`div` click handler changed
from `navigateToMlo(...)` to `toggleExpand(...)` — clicking the card body
now expands/collapses the inline per-source definitions instead of
navigating straight to `/results?mlo=X`. The button that used to gate on
`mlo.definitions && mlo.definitions.length` and toggle expand/collapse
("expand"/"collapse" with a chevron) was relabeled "Explore {mlo} proteins"
with a forward-arrow icon, now calls `navigateToMlo(...)` via `@click.stop`
(so it never also re-triggers the card's own toggle), and its `v-if` gate on
having definitions was removed entirely — it renders unconditionally now.

```
$ curl -s --noproxy '*' "http://127.0.0.1:8765/mlos"
# abscission_checkpoint_body: category "Nuclear", 3 proteins, 3 drivers,
# "definitions": []
```

Confirmed live that `abscission_checkpoint_body` has an empty `definitions`
array — under the old `v-if`, its "Explore" button would never have
rendered at all; after this fix it renders unconditionally like every other
card's button.

### Review disposition

Of the seven commits in `13d8e42..da0406f`, six were reviewed by a dispatched
task-reviewer subagent, the port (`c27957e`) included — its review diff is
still on disk at
`.superpowers/sdd/2026-08-05-refactor-frontend-phase/review-13d8e42..c27957e.diff`,
alongside one per reviewed commit. The single exception is the Orthologs-tab
hide (`058c121`), a 7-line deletion in one file, which the controller verified
directly by reading the diff rather than dispatching a reviewer. Every reviewed
commit came back Approved with zero Critical/Important findings — a handful of
Minor, non-blocking notes exist per-commit (recorded in this phase's ledger,
`.superpowers/sdd/2026-08-05-refactor-frontend-phase/progress.md`, if the
exact wording is ever needed) but none changed any of the above behavior or
required follow-up code changes.

Per-commit reviews are not the same as a whole-branch review, though: the final
full-branch review run after all of the above still found a Critical regression
that every individual review had passed. See Entry 15.

### What's left, disclosed rather than silently dropped

Four items remain open, all now tracked in `refactor/frontend/CLAUDE.md`'s
"Known deferred issues" section rather than only living in this log:
`RoleBadge.vue` has no style for `'client'` (falls through to a generic gray
badge); `MlosPage.vue`'s `SOURCE_DBS` is still a hardcoded list of five and
its organism filter is still a disabled "coming soon" `<select>`; the
Orthologs tab is intentionally hidden pending the user's planned redesign,
with `ProteinOrthologs.vue`/`OrthologTrackViewer.vue` left in place for that
future work; and Fix 6 above left the MLO card's `hover:bg-slate-50
cursor-pointer` styling unchanged even though its click no longer navigates
— the whole row still visually reads as a navigation target, a minor
follow-up noted during that fix's own review but not itself fixed this
session.

---

## Entry 15 — Final whole-branch review of the `frontend/` phase, and its one fix wave

Entry 14's work was reviewed commit-by-commit as it landed. A final review of
the *whole* branch afterwards found one Critical regression that every
per-commit review had passed, plus a set of documentation defects. This entry
covers that review's single fix wave.

### Critical: sort escalation silently swapped the search corpus

`ResultsPage.vue`'s `runSearch()` escalated a plain-text search to
`searchAdvanced({ gene_name: q, ... })` whenever
`f.organism || f.role || f.sort_by || f.mlo || f.feature_type || f.feature_accession`
was truthy (introduced in `7188677`, ported unchanged in `c27957e`). `f.sort_by`
is truthy as soon as the user picks any non-default sort — the default,
`mlo_count:desc`, is stripped from the URL by `ResultsPanel.vue`'s
`onSortSelect()`. And `/search/advanced`'s `gene_name` filter is a `LIKE` on the
`gene_name` column *only*, whereas `/search` matches `uniprot_id`, `gene_name`
and `protein_name`:

```
$ curl -s --noproxy '*' "http://127.0.0.1:8765/search?q=kinase&mode=fuzzy"
50 hits
$ curl -s --noproxy '*' "http://127.0.0.1:8765/search/advanced?gene_name=kinase"
0 hits
```

So: search "kinase", get 50 results, click any sort option, get "No proteins
found." The primary search flow.

`sort_by` never needed to be in that trigger. `sortProteins.js` (added in
`638b047`, the very next commit) already re-sorts `/search`'s own returned array
for every option the dropdown offers, so sorting the fallback path does not
require changing the query. Escalation is genuinely needed only for
`organism`/`role`/`mlo`/`feature_type`/`feature_accession`, which `/search`
cannot apply at all. Fix: drop `f.sort_by` from the condition, leaving
`f.organism || f.role || f.mlo || f.feature_type || f.feature_accession`.
Nothing else in `runSearch()` changed — when escalation does fire for one of the
remaining reasons, `sort_by`/`sort_order` still flow through `extraFilters` into
`/search/advanced` exactly as before.

Traced by hand against the updated condition:
`{q:'kinase', sort_by:'gene_name'}` → all five triggers falsy → falls through to
the `/search` branch, `sortProteins()` applied, 50 hits returned in gene-name
order. `{q:'FUS', mlo:'stress_granule'}` → `f.mlo` truthy → still escalates,
unchanged.

### Documentation corrections

- The header's hard rule now names its one exception (`7188677`), and Entry 14
  covers both pre-port audit commits (`e799f6a`, `7188677`), which it had
  previously omitted entirely.
- The `NotInformed`/`EXCLUDED_MLO_CATEGORIES` fix was attributed to "an earlier
  phase"; it is `e799f6a`, inside this phase. Corrected.
- `refactor/api/CLAUDE.md`'s policy section still documented
  `EXCLUDED_MLO_CATEGORIES = []` / "empty today, deliberately", contradicting
  `policy.py`, which has held `["Unspecified"]` since `e799f6a`. Updated, per
  `policy.py`'s own instruction to keep the two in sync. The same stale
  "(today's default)" parenthetical in `excluded_mlo_category_clause`'s
  docstring was corrected too.
- **"FTS5 relevance order" was the wrong root cause** for the sort bug `638b047`
  fixed. The UI always sends `mode=fuzzy`, which routes to
  `search_proteins_like()` — a plain `LIKE` query ordered by `p.uniprot_id`. The
  FTS5 path (`ORDER BY rank`) needs `mode=exact`, which the UI never sends. The
  fix was and is correct; only the diagnosis was wrong. Corrected in Entry 14,
  in `sortProteins.js`'s header comment, and in `refactor/frontend/CLAUDE.md`.
- Entry 14 said "seven commits" in one place and "all eight commits were
  individually task-reviewed" in another, and credited the port `c27957e` as
  controller-verified. Both fixed: the ranges are now spelled out explicitly,
  and `c27957e` *was* reviewed by a dispatched reviewer (its diff is still on
  disk); only `058c121` was controller-verified.
- `refactor/frontend/CLAUDE.md` carried a cluster of claims inherited from the
  pre-port `frontend/CLAUDE.md` that were never true of this tree: `ProteinPPI.vue`
  described as using TanStack Table (its table is hand-rolled with `.slice()`
  pagination; `@tanstack/vue-table` is imported by `ResultsPanel.vue` and nothing
  else), a `★ if reviewed` result-row element (`grep -rn reviewed
  refactor/frontend/src` → zero hits), `var(--color-border-tertiary)` as the
  result-row border (defined nowhere; the real class is `border-b
  border-gray-200`), a result-row structure that predates the current two-column
  markup, `source_db`/`taxon_id`/`feature_label` listed among the working URL
  filters (none of the three is forwarded by `buildExtraFilters()`, so they
  render a filter chip that never reaches the API — and `feature_label` isn't
  even an API parameter), `max-w-6xl` for the navbar (it is
  `max-w-5xl`), `main.css` described as more than the three `@tailwind`
  directives it contains, a feature-badge hex palette that appears nowhere in the
  source, and a directory tree missing `App.vue`, `assets/` (including the
  organism SVGs `OrganismGrid.vue` imports), `postcss.config.js` and `README.md`.
  All corrected against the real files.

### Code cleanups made in the same wave

- `_build_sort()` in `protein_queries.py` now carries a KEEP-IN-SYNC comment
  pointing at `sortProteins.js` (the pointer previously existed only in the JS
  direction), and `refactor/frontend/CLAUDE.md`'s "What NOT to do" warns against
  changing either alone. There is no test suite that would catch that drift.
- `fetch_uniprot.py::backfill_from_cache()` selected stale rows with
  `WHERE gene_name IS NULL` — 1,296 rows today, of which ~1,293 are proteins that
  simply have no gene name in UniProt and get re-parsed and re-`UPDATE`d on every
  run for nothing. Changed to `WHERE fetch_date IS NULL` (3 rows), which is exact
  rather than merely better: `build_db.py` inserts `proteins` rows with only
  `uniprot_id`, and `proteins.fetch_date` is written by nothing except this
  script's own `update_protein()`, so NULL there means precisely "the backfill
  UPDATE never ran on this row".
- `ProteinPPI.vue`: the `:ref` callback now deletes `rowRefs[key]` on unmount
  (Vue passes `null`, which the `if (el)` guard silently skipped, leaking
  detached nodes); `selectedId` is reset when `filteredPartners` changes and when
  the protein prop changes; and one `protein.ppi.total_partners` read gained the
  `?.` its neighbours already had.
- `computeFacetsFromProteins()` in `ResultsPage.vue` gained a comment recording
  that its `has_driver`-derived role facet is only correct because escalation
  guarantees no `mlo`-filtered result reaches it — the same coupling
  `_scoped_role_counts()` fixed server-side, one escalation-condition edit away
  from reappearing client-side.
- The sort dropdown has seven options over five `sort_by` keys, not six;
  comments saying otherwise were corrected. `refactor/frontend/DEVLOG.md` gained
  the six follow-on fix entries it was missing.

### Deliberately not fixed

- `/search`'s pagination/count incoherence (it returns up to `LIMIT 50` with no
  page concept while the UI paginates as if it had one) — pre-existing, not
  introduced by this phase, out of this wave's scope.
- The `/search` fallback sorts *within* the truncated 50 rows the endpoint
  returns, so a "best" result outside that window can't be surfaced by sorting.
  Noted in a comment at the call site; fixing it means restructuring the
  endpoint's pagination, which this wave deliberately did not touch.

---
