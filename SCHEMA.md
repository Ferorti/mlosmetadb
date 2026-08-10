# SCHEMA.md — mlosmetadb.db schema reference

Consolidated from CLAUDE_db.md, CLAUDE_features.md, CLAUDE_ppi_orthologs.md, and
CLAUDE_api.md. This is the reference other domain CLAUDE.md files should point to
instead of repeating table definitions.

**Before trusting this file for implementation work**: run `PRAGMA table_info(...)`
against the real `database/mlosmetadb.db` and reconcile. This file can drift from
the actual database the same way the old per-phase CLAUDE_*.md files did — treat it
as a starting reference, not a guarantee, until an audit pass confirms it against
the live DB.

**Known gap**: the `orthologs` table below is being replaced (see "Orthologs
redesign" section) per `CLAUDE_orthologs.md`. That file's exact `ortholog_groups` /
`ortholog_members` schema should be copied into this file once the rebuild is
implemented — it is not reproduced here because the source spec wasn't available
when this file was drafted.

---

## proteins

```sql
CREATE TABLE proteins (
    uniprot_id       TEXT PRIMARY KEY,
    gene_name        TEXT,
    protein_name     TEXT,
    organism         TEXT,
    taxon_id         INTEGER,
    sequence         TEXT,
    length           INTEGER,              -- exposed as `sequence_length` in API
    lineage          TEXT,                 -- JSON array, kingdom → species
    reviewed         INTEGER,              -- 1 = Swiss-Prot, 0 = TrEMBL
    fetch_date       TEXT,
    disorder_mobidb_lite_dc  REAL,         -- content_fraction, NULL if absent
    disorder_alphafold_dc    REAL          -- content_fraction, NULL if absent
);
```

## mlo_annotations

```sql
CREATE TABLE mlo_annotations (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    uniprot_id       TEXT NOT NULL REFERENCES proteins(uniprot_id),
    source_db        TEXT NOT NULL,        -- PhaSepDB | DrLLPS | PhasePro | LLPSDB | CDCODE
    source_mlo       TEXT NOT NULL,
    unified_mlo      TEXT NOT NULL REFERENCES mlo_vocabulary(unified_mlo),
    source_role      TEXT,                 -- raw value as reported by source — never overwritten/normalized away
    unified_role     TEXT,                 -- 'driver' | 'client' | NULL only. NULL means "this row carries
                                            -- no driver/client signal" — true both for DrLLPS-Regulator (a real
                                            -- third category the project chooses not to model as a role) and
                                            -- for CD-CODE (source provides no role data at all). Never a
                                            -- placeholder string like 'unmapped', never 'Driver'/'Client' cased.
    evidence_type    TEXT,                 -- what kind of claim the row makes, which unified_role cannot
                                            -- express: 'in_vitro_llps' | 'cellular_localisation' |
                                            -- 'cellular_requirement' | 'curator_assignment' |
                                            -- 'membership_only'. Assigned from (source_db, source_role) by
                                            -- compute_evidence_type() in integrate.py; never NULL.
    dataset_active   INTEGER NOT NULL DEFAULT 1,  -- 0 = retained for full provenance but excluded from the
                                            -- served/counted MLOsMetaDB dataset by default (currently: DrLLPS
                                            -- Regulator rows). This is a presentation-layer decision, not data
                                            -- loss — the row stays in the table. API queries should filter on
                                            -- this explicitly (WHERE dataset_active = 1) rather than relying on
                                            -- rows having been excluded at build time.
    evidence         TEXT,                 -- PMIDs, semicolon-separated, or NULL
    dataset_version  TEXT DEFAULT 'v2'
);
```

**Design principle (fixed 2026, do not revert)**: annotation logic (what evidence
exists, what role/scope it has) is fully separate from presentation/filtering logic
(what counts as "client" for display, what's shown by default). Ambiguous-role
display policy (e.g. "unknown role displays as client") belongs in the API query
layer as a computed expression over `unified_role`/`dataset_active`, never baked
into the stored value. If that policy changes, only the API layer changes — the
table and the pipeline that populates it do not need to be touched or rerun.

**`source_db` correction (2026-08-08)**: there are **five** source databases, one
tag each. An earlier note here claimed `PhasePDB` was a sixth source alongside
`PhaseDB`; that was wrong. Both tags were the same resource, **PhaSepDB**,
ingested twice by two parsers reading byte-identical copies of the same export
files, which double-counted every PhaSepDB annotation. The two tags no longer
exist in the data — one parser (`parsers/parse_phasesepdb.py`), one tag
(`PhaSepDB`). A query returning `PhaseDB` or `PhasePDB` is reading a stale
database file, not a sixth source. See
[docs/issues/001-phasedb-phasepdb-duplicate-ingestion.md](docs/issues/001-phasedb-phasepdb-duplicate-ingestion.md).

**`evidence_type` (added 2026-08-10)**: `unified_role` collapses five source
vocabularies into two values, which hides that the underlying assertions are not
comparable. A PhaSePro `driver` means a purified protein phase-separates in a
buffer; a PhaSepDB `driver` means perturbing it disrupts the condensate in cells.
The two resources agree on only 58.6% of the annotations they share, and that
disagreement is this difference rather than curation noise. `evidence_type`
records the kind of claim, orthogonally to the role:

| value | meaning | sources |
|---|---|---|
| `in_vitro_llps` | purified protein phase-separates; no cellular claim | LLPSDB, PhaSePro |
| `cellular_localisation` | reported present in the condensate in cells | PhaSepDB `client` |
| `cellular_requirement` | perturbing it disrupts the condensate in cells | PhaSepDB `driver` |
| `curator_assignment` | curator-assigned, and **protein-scoped** in DrLLPS: the same label propagates to every MLO of that protein, so it is not a per-compartment claim | DrLLPS |
| `membership_only` | the resource asserts membership and makes no role claim | CD-CODE |

`membership_only` is the value that changes how the data reads: the 13,844 rows
with `unified_role IS NULL` are CD-CODE's **declared scope**, not a gap in
ingestion. Assigned from the `(source_db, source_role)` pair, which was verified
exhaustive and homogeneous per resource — eight pairs, five values. Two tests in
`tests/test_dataset_invariants.py` assert no NULL and no value outside the five.

**Row grain**: one row per `(uniprot_id, source_db, source_mlo, source_role)`,
enforced by `scripts/integrate.py`'s `collapse_duplicates()` for every source.
Sources that report one row per supporting publication have those rows collapsed
into a single annotation whose `evidence` holds all the PMIDs. Note the role is
part of the key: a protein annotated as both a driver and a component of the
same MLO by the same source keeps both rows, because those are two different
experimental observations (see `BIOLOGY.md`).

## mlo_vocabulary

```sql
CREATE TABLE mlo_vocabulary (
    unified_mlo      TEXT PRIMARY KEY,
    category         TEXT,
    mapping_version  TEXT DEFAULT 'v3'
);
```

**`mapping_version` is stamped explicitly, not left to the column DEFAULT.**
`build_db.py` writes `MAPPING_VERSION` (currently `'v6'`) onto every row and
fails the load if any row ends up on a different value. Until 2026-08-08
nothing stamped it at all, so all rows carried the DEFAULT `'v3'` while the
shipped mapping was already v4 — bump the constant in the same commit that
changes `mlo_mapping.csv`.

**One curated category per canonical.** Many source names collapse into one
canonical, so the same canonical appears in many mapping rows. When those rows
disagreed on `Categoria` the loader used to keep whichever it read first, which
made the stored category arbitrary for 23 of the terms. It now raises instead —
resolve the conflict in `mlo_mapping.csv`.

**Terms with zero annotations do not survive the load.** `build_db.py` prunes
them after loading `mlo_annotations` and reports which ones, enforcing the
project rule that data coverage gates granularity. Their rows stay in
`mlo_mapping.csv`: the curation record is not what was wrong.

**`NotInformed` stays in this table (fixed 2026, do not exclude at build time)**:
rows where a source gave no specific MLO name map to `unified_mlo = 'NotInformed'`,
`category = 'Unspecified'` — a real, deliberately curated entry (see
`mlo_definitions.csv` for the hand-written definition), not something to drop from
`mlo_vocabulary` or from `mlo_annotations`. `category = 'Unspecified'` is the
mechanism for filtering it out of default "real MLO" views at the API/frontend
layer, without removing the underlying rows (~3,027 in `mlo_annotations`). Same
principle as `dataset_active` above: filtering is presentation logic, not a reason
to lose data at the pipeline stage.

## mlo_definitions

```sql
CREATE TABLE mlo_definitions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    unified_mlo      TEXT NOT NULL REFERENCES mlo_vocabulary(unified_mlo),
    source_db        TEXT NOT NULL,
    source_name      TEXT NOT NULL,        -- original MLO name in that source
    definition       TEXT
);
```

## sequence_features

```sql
CREATE TABLE sequence_features (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    uniprot_id       TEXT NOT NULL REFERENCES proteins(uniprot_id),
    feature_type     TEXT NOT NULL,   -- domain | family | idr | idr_curated | lcd |
                                       -- morf | coiled_coil | signal_peptide |
                                       -- transmembrane | plddt_region
    source           TEXT NOT NULL,   -- Pfam | SMART | MobiDB-lite | AlphaFold |
                                       -- Coils | SignalP | TMHMM | DisProt | ...
    label            TEXT,
    accession        TEXT,            -- Pfam/SMART/IPR accession, NULL if n/a
    start            INTEGER,
    end              INTEGER,
    score            REAL,            -- e-value / disorder score / pLDDT, NULL if n/a
    metadata         TEXT,            -- JSON, source-specific extra fields
    fetch_date       TEXT
);
```

`feature_type` → API response field:
`idr`, `idr_curated` → `idrs[]` · `domain`, `family` → `domains[]` · `lcd` → `lcds[]`
· `morf` → `morfs[]` · `plddt_region` → `plddt_regions[]`

**`repeat` — resolved (2026-audit, round 2)**: confirmed dead. Only exists in the
orphaned `archive/prot-page-gcli` branch; `main`'s `api/routers/proteins.py` has
no reference to it, and neither `parse_interpro.py` nor `parse_mobidb.py` ever
writes it. `SELECT DISTINCT feature_type FROM sequence_features` on the live DB
confirms: `domain, family, idr, idr_curated, lcd, morf, plddt_region` — no `repeat`.
Not a real value; don't special-case it anywhere.

**Not currently populated, despite being listed as a `feature_type` in the original
design (2026-audit)**: `coiled_coil`, `signal_peptide`, `transmembrane`. InterPro's
public API no longer exposes the `protein.sequence_features` block these depended
on (`coils`/`signal_p`/`tmhmm`) — `parse_interpro.py` documents this in its own
docstring. Not a bug, but the original spec assumed API surface that no longer exists.

pLDDT region categories (mean score): `very_low` <50 · `low` 50–70 · `confident`
70–90 · `very_high` ≥90.

## protein_summary (precomputed, populated by scripts/build_summary.py)

```sql
CREATE TABLE protein_summary (
    uniprot_id      TEXT PRIMARY KEY REFERENCES proteins(uniprot_id),
    idr_regions     TEXT,     -- JSON: {"mobidb_lite": [[s,e],...], "alphafold": [...]}
    lcr_regions     TEXT,     -- JSON: {"mobidb_lite": [{"start","end","label"},...]} — see casing note
    domains         TEXT,     -- JSON: {"pfam": [{"start","end","label","accession"}], "smart": [...]} — lowercase keys
    has_driver      INTEGER,  -- 1 if any mlo_annotations row has unified_role='Driver'
    has_client      INTEGER,  -- 1 if any mlo_annotations row has unified_role='Client'
    source_db_count INTEGER,
    source_dbs      TEXT,     -- JSON array of source_db strings — missing from earlier draft, confirmed via PRAGMA table_info
    mlo_count       INTEGER,
    mlos            TEXT      -- JSON array of unified_mlo strings
);
```

**Corrections (2026-audit)**:
- `domains` top-level keys are lowercase in the real DB (`pfam`, `smart`), not
  capitalized as earlier drafts of this file said. `build_summary.py` remaps this
  explicitly.
- `lcr_regions.mobidb_lite` is actually sourced from `sequence_features` rows with
  `source='MobiDB-lite-sub'`, not `'MobiDB-lite'` (that source is for `idr`, not
  `lcd`). Verified: `lcd|MobiDB-lite-sub` exists in the DB, `lcd|MobiDB-lite` does not.

**Note**: `has_driver`, `has_client`, `source_db_count` exist in the table but were
not yet exposed in the API's `ProteinSummary` model as of the last check — confirm
current status in the api/ audit before assuming either way.

## ppi

```sql
CREATE TABLE ppi (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    uniprot_id_a        TEXT NOT NULL REFERENCES proteins(uniprot_id),  -- always in dataset
    uniprot_id_b        TEXT NOT NULL,     -- may or may not be in proteins
    in_db               INTEGER NOT NULL DEFAULT 0,  -- 1 if uniprot_id_b in proteins
    experimental_system TEXT NOT NULL,
    throughput          TEXT,              -- 'Low Throughput' | 'High Throughput'
    organism_id_a       INTEGER,
    organism_id_b       INTEGER,
    pubmed_id           TEXT,
    source_version      TEXT DEFAULT 'BIOGRID-5.0.257'
);
```

## orthologs — current production table

```sql
CREATE TABLE orthologs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    uniprot_id      TEXT NOT NULL REFERENCES proteins(uniprot_id),
    ortholog_id     TEXT NOT NULL,
    organism        TEXT NOT NULL,
    taxon_id        INTEGER NOT NULL,
    og_id           TEXT,
    in_db           INTEGER NOT NULL DEFAULT 0,
    source          TEXT DEFAULT 'OMA',
    source_version  TEXT DEFAULT 'OMA-2024'
);
```

**Correction (2026-audit)**: this table's actual data source in the live DB
(`database/mlosmetadb.db`) is **OMA Browser** (`fetch_oma.py` / `parse_oma.py`,
19,289 rows, `source='OMA'`), not OrthoDB. Earlier drafts of this file assumed the
OrthoDB v2 migration below had already happened — it hasn't, against production.

### Orthologs redesign (OrthoDB v2) — WIP, not live

A migration to two new tables (`ortholog_groups`, `ortholog_members`) built from
local OrthoDB v2 files (`odb12v2_*.tab.gz`) was attempted, but **only against an
orphaned copy** of the database (`database/mlosmetadb_odl.db`, not referenced by
`api/config.py` or any active script). In that copy, `orthologs` was renamed to
`orthologs_oma_backup` but `ortholog_groups`/`ortholog_members` ended up empty —
consistent with a crash (likely OOM loading several GB of OrthoDB data) partway
through. **Zero impact on production** — the live DB still has the original
`orthologs` table as shown above, fully populated.

`ortholog_meta` and `ortholog_features` (populated by `fetch_mobidb_orthologs.py` /
`parse_mobidb_orthologs.py`) also exist in `build_db.py`'s schema and are proven to
work (populated in the orphaned `_odl` copy) but have never run against the live
DB and aren't documented in any CLAUDE.md yet.

**Do not treat the OrthoDB v2 migration as done.** Update this section with the
real `ortholog_groups`/`ortholog_members` schema once it's actually implemented
against `database/mlosmetadb.db`.

---

## Cache databases (database/cache/*.db)

Same structure across `uniprot_cache.db`, `interpro_cache.db`, `mobidb_cache.db`:

```sql
CREATE TABLE responses (
    uniprot_id   TEXT PRIMARY KEY,
    response     TEXT NOT NULL,     -- raw JSON
    fetched_at   TEXT NOT NULL,     -- ISO timestamp
    api_version  TEXT,
    status_code  INTEGER
);

CREATE TABLE fetch_errors (
    uniprot_id   TEXT NOT NULL,
    error_type   TEXT,              -- 'timeout' | 'http_error' | 'parse_error'
    error_detail TEXT,
    attempted_at TEXT NOT NULL,
    attempts     INTEGER DEFAULT 1
);
```

**`oma_cache.db` — different schema, don't assume it matches the above (2026-audit,
round 2)**: no `api_version` column. Confirmed via `PRAGMA table_info`:
```sql
CREATE TABLE responses (
    uniprot_id   TEXT PRIMARY KEY,
    response     TEXT NOT NULL,
    fetched_at   TEXT NOT NULL,
    status_code  INTEGER
);
```