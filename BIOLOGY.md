# BIOLOGY.md — Biological classification rules for MLOsMetaDB v2

This file is cross-cutting: it affects parsers, database schema, API serialization,
and frontend display. It should be loaded in every session regardless of which
directory is being worked on.

Scientific rigor is a project requirement: classification decisions require direct
experimental support, and imprecision in biological terminology is documented
explicitly rather than glossed over. Do not silently "clean up" a biological
distinction that looks redundant — check this file first.

---

## Driver vs. Component — canonical categories

The Driver vs. Client/MLO Component distinction across source databases is
**terminological, not experimental** — the same underlying evidence gets different
labels depending on which source database's curator wrote it. This project collapses
that inconsistency into two canonical categories:

- **LLPS Driver**: direct experimental evidence of phase separation (self-assembly
  or driving assembly of others).
- **MLO Component**: annotated presence in/association with an MLO, without evidence
  that the protein drives phase separation.

**Regulators (as labeled by DrLLPS) are excluded entirely** — not mapped to either
category, not included in the dataset's role field.

`unified_role` has exactly two valid non-null values: `'driver'` and `'client'`.
`NULL` is allowed (no role data, e.g. CD-CODE). `'regulator'` must never appear in
v2 schema or API output.

"MLO Component" (surfaced to users as "client" in code/API) is acknowledged
internally as an imprecise label — a protein can be structurally part of an MLO
without any claim about its causal role — but it was chosen over more accurate but
opaque alternatives for communicative clarity. The UI should carry an explicit card
description of what "Component/Client" means so this imprecision doesn't mislead users.

---

## Role assignment by source database

The `source_role` → `unified_role` mapping is fixed per source, not inferred per row:

| Source DB | Source field/section | → `unified_role` |
|---|---|---|
| PhaSepDB | `mlo_entries` file | `client` |
| PhaSepDB | `detail_database` file | `driver` |
| DrLLPS | `Scaffold` | `driver` |
| DrLLPS | `Regulator` | excluded (not inserted) |
| LLPSDB | (all rows) | `driver` (default) |
| PhasePro | (all rows) | `driver` (default) |
| CD-CODE | (all rows) | `NULL` (no structured role data in source) |

PhaSepDB publishes its two datasets separately — a curated set of LLPS drivers
(`detail_database`) and a set of proteins detected as components of MLOs
(`mlo_entries`) — and a protein can appear in both. That is not a conflict to
resolve: driving phase separation and being detected inside a condensate are
two different experimental observations, so both annotations are kept, each
with its own PMIDs. A protein can therefore be a driver and a component of the
same MLO, and the row grain that expresses this is
`(uniprot_id, source_db, source_mlo, source_role)` — the same grain used for
every other source.

## "Droplet" terminology

Where a source database (DrLLPS, LLPSDB) reports "Droplet" as the condensate/MLO
name, this means an experimentally confirmed LLPS event with **no cellular MLO
assigned** — an in vitro reconstitution, not a named organelle. Map this to
`source_mlo = "in vitro droplet"`, not to any cellular compartment.

---

## MLO mapping decisions (source_mlo → unified_mlo)

These are deliberate consolidation/separation calls made during `mlo_mapping`
construction. Do not "fix" them without re-opening the discussion:

- **Sponge body** kept separate from **P-body** (not merged, despite similarity).
- **Spindle apparatus** kept separate from **centrosome**.
- **Chromatoid body** kept separate from **nuage** — corrected 2026-audit round 2:
  an earlier draft of this file had this backwards (said they were merged). They
  are distinct categories in `mlo_mapping.csv`, with PMID justification
  (composition and developmental stage differ; the mapping file itself flags this
  as the distinction that matters: "nuage vs chromatoid_body"). **IMC
  (intermitochondrial cement)** is the one that maps → `nuage`, not chromatoid body.
- **Germ plasm** and **polar granule** → both map to `germ_plasm`.
- **PcG body** and **Polycomb body** → both map to `polycomb_body`.
- GO ontology terms that are not true MLOs (e.g. "ribonucleoprotein complex",
  "extracellular matrix") are explicitly **DISCARD**ed — not mapped to `unmapped`,
  removed from consideration entirely at the mapping stage.

Values to treat as "no mapping" (excluded from `mlo_vocabulary`, and rows with these
source_mlo values are dropped when loading `mlo_annotations`): `DISCARD`, `NULL`,
`synthetic_condensate`, empty string. (`NotInformed` is deliberately NOT on this
list — see the dedicated section below.)

---

## Protein identifier hierarchy

When choosing a display name for a protein (frontend, any human-facing label):

1. Gene name (if available)
2. UniProt protein name (if no gene name)
3. UniProt accession (fallback if neither is available)

This hierarchy is fixed — do not reorder it per-component; it should be a single
shared utility (`formatProteinName()` or equivalent), not reimplemented ad hoc.

---

## Source database badge display rule

Show a source-database badge only for sources that have an actual annotation for
that specific protein — never show a greyed-out/absent badge for a source with no
data, since that visually implies "checked, not found" (a negative claim we can't
actually support) rather than "no annotation from this source" (the true state,
which could mean not checked, not in scope, etc.).

DrLLPS links to its homepage rather than a per-protein deep link — DrLLPS internal
IDs are not derivable from UniProt accessions, so no reliable deep link exists.

---

## Driver/Client/Regulator scope (fixed 2026, corrects earlier drafts of this file)

An earlier draft of this file said Regulators (DrLLPS) are "excluded entirely."
That was imprecise about *where* the exclusion happens, and it got implemented
wrong as a result (silently dropped into a broken `'unmapped'` role string instead
of a clean exclusion). The corrected rule:

- Regulator rows from DrLLPS **stay in `mlo_annotations`** (full provenance is
  never discarded at the pipeline stage) with `unified_role = NULL` and
  `dataset_active = 0` — present in the source-level table, excluded from the
  served/counted MLOsMetaDB dataset by default. See `SCHEMA.md` for the column.
- CD-CODE rows get `unified_role = NULL` and `dataset_active = 1` — no role
  signal, but still part of the served dataset (CD-CODE contributes MLO
  membership, just not role).
- Ambiguous-role display policy (e.g. "unknown/NULL role displays as client") is
  never written into `unified_role` itself. It is a query-time decision in the API
  layer. This can change without touching the pipeline or re-running any build step.

## "NotInformed" (fixed 2026, corrects earlier drafts of this file)

An earlier draft of this file listed `NotInformed` as a value to be excluded when
building `mlo_vocabulary`. That's wrong — all proteins with `NotInformed` rows must
stay in the database. `NotInformed` is a deliberate, curated vocabulary entry
(`category = 'Unspecified'`, see `mlo_definitions.csv`) for sources that gave no
specific MLO name. It is **not** in the discard list. The discard list for
`mlo_vocabulary`/`mlo_annotations` at build time is only:
`DISCARD`, `NULL` (literal string), `synthetic_condensate`, empty string.

If a view needs to exclude `NotInformed` from what it displays as a "real" MLO,
filter on `category != 'Unspecified'` at query time — do not drop the rows from
`mlo_annotations` or `mlo_vocabulary` to achieve that.

**Frontend display rule (2026-08-06):** a protein's MLO list/table should show
`NotInformed` ("No MLO associated") only when it is the *only* entry for that
protein in the scope being displayed — drop it the moment a real MLO is also
present in that scope, since "has MLO X" already implies "not uninformed" and
repeating both adds nothing. Today "scope" is always the whole protein; if a
future view splits a protein's MLOs per source database, apply the same rule
per source db instead (show `NotInformed` for a source db only if *that* source
db reported no real MLO for the protein). See
[frontend/CLAUDE.md](frontend/CLAUDE.md)'s "NotInformed display rule" section
for the implementation (`filterMlos()` in `frontend/src/utils/format.js`).

## Known gaps and imprecision (documented, not hidden)

- "MLO Component" (client) is a chosen simplification of underlying complexity in
  source annotation practices — see "Driver vs. Component" above.
- CD-CODE contributes MLO associations with **no role data at all** — always `NULL`,
  not an oversight to be "fixed" by inferring a role.
- **There are five source databases, not six.** `PhaseDB` and `PhasePDB` were
  two `source_db` tags for a single resource, **PhaSepDB**, ingested twice by
  two parsers reading byte-identical copies of the same two export files. It
  was a naming mistake, never a biological distinction. Fixed 2026-08-08: one
  parser, one tag (`PhaSepDB`), and the rows deduplicated — annotation rows
  went from 54,786 to 35,971 and `protein_summary.source_db_count` now maxes
  out at 5 instead of a nonexistent 6. Any figure quoted from a dataset
  snapshot older than that date is inflated. This was an ingestion defect, not
  a curation one — no mapping decision above changed as a result. Full account
  in [docs/issues/001-phasedb-phasepdb-duplicate-ingestion.md](docs/issues/001-phasedb-phasepdb-duplicate-ingestion.md).
- The MLO count discrepancy between PhaSepDB (124 organelles) and MLOsMetaDB (91) has
  two causes, not one: intentional consolidation of synonymous names (see mapping
  decisions above) AND genuinely missing entries in `mlo_mapping.tsv` coverage
  (~50-60 PhaSepDB rows). Do not assume all discrepancy is intentional consolidation.