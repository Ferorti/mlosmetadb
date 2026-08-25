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

**Regulators (as labeled by DrLLPS) are a third category the role field does not
model.** They are *not* excluded from the dataset — that was reversed on 2026-08-12,
see "Driver/Client/Regulator scope" below — they simply carry no driver/client
verdict, because regulating an organelle's assembly is neither driving phase
separation nor being detected inside the condensate.

`unified_role` has exactly two valid non-null values: `'driver'` and `'client'`.
`NULL` is allowed (no role data, e.g. CD-CODE; or a regulator call). `'regulator'`
must never appear as a **stored** value or as a per-row `unified_role` in API output.
It does appear as an aggregate **bucket name** in `/mlo/{id}`'s `by_role`, computed at
read time from `(evidence_type, source_role)` — a summary key, not a role value.

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
| DrLLPS | `Regulator` | `NULL` (served; no driver/client verdict) |
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

### PhaSepDB in vitro reclassification (implemented 2026-08-25)

`phasedb_detail.csv`'s driver rows can leave `MLO` empty for two biologically
different reasons: the record is a real cellular observation whose specific
condensate was never named, or the record is an in vitro reconstitution with
no cellular claim at all — the same case "Droplet" captures for DrLLPS/LLPSDB.
Before this fix, both cases fell into `NotInformed` (a curated "no compartment
named" bucket, see below), collapsing them into one label.

`phasedb_detail.csv` carries two columns the parser previously discarded,
`Location` and `Experiment Types`, that distinguish the two cases directly —
no literature review needed, this is a mapping fix (reading a source field
correctly), not evidence curation. `parsers/parse_phasesepdb.py`'s
`parse_detail()` now reclassifies a detail row to `source_mlo = "in vitro
droplet"` instead of `NotInformed` when, after the summary-export fallback
also fails to resolve a name:

- `Location == "NA"` — no cellular compartment reported at all, and
- `Experiment Types` names only in-vitro assays (contains "in vitro", never
  "in vivo").

Any row with a reported `Location` (`Cytoplasm`, `Nucleus`, or a compound of
the two) is left as `NotInformed`, even with no named condensate — a known
cytoplasmic/nuclear location is a real cellular claim, not an in vitro one.
Rows whose `Experiment Types` mixes in-vitro and in-vivo assays are also left
as `NotInformed`: mixed evidence is not an in-vitro-only claim.

**Verified counts (this dataset, `database/raw/phasedb_detail.csv`)**: 311 `phasedb_detail.csv` rows
reclassified, covering 272 distinct proteins — confirmed independently by PMID
overlap against LLPSDB/DrLLPS: of the proteins that carry both a PhaSepDB
`NotInformed` row and an LLPSDB/DrLLPS `in_vitro_droplet` row, 71/100 cite the
exact same PMID, i.e. PhaSepDB is citing the identical in-vitro paper without
naming a compartment. PhaSepDB's `NotInformed` protein count drops from 930 to
694; `unified_mlo = 'in_vitro_droplet'` protein count rises from 551
(DrLLPS 171 + LLPSDB 380) to 823 (+ PhaSepDB 272). `mlo_annotations` gains 36
net rows (35,732 → 35,768) — the byproduct of the row grain
`(uniprot_id, source_db, source_mlo, source_role)`: a protein whose collapsed
`NotInformed` row absorbed PMIDs from several `phasedb_detail.csv` records now
splits into two rows (`in vitro droplet` + the remaining `NotInformed`) when
some but not all of those records qualify for reclassification.

**Known gap left open by this fix**: `evidence_type` is assigned from
`(source_db, source_role)` only (`compute_evidence_type()` in
`scripts/integrate.py`), not per-row from `source_mlo`. These 272 proteins'
reclassified rows keep `source_role = "driver"` and therefore
`evidence_type = "cellular_requirement"` ("perturbing it disrupts the
condensate in cells") even though they now read as `in_vitro_droplet`
("purified protein phase-separates; no cellular claim") — the same
inconsistency `evidence_type` was introduced to catch elsewhere (see
"`evidence_type`" in `SCHEMA.md`). Fixing this would mean making
`evidence_type` a per-row function of `source_mlo` as well, which changes the
"verified exhaustive and homogeneous per (source_db, source_role) pair"
property the external audit checked — left open rather than reversed
silently. Do not "fix" this by hand without re-deriving that exhaustiveness
check.

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

### Corrections from the external biological audit (2026-08-08, mapping v5)

Full account in `database/mappings/_archive/mlo_mapping_decisions.md` §11;
the audit itself is in `docs/review/devolucion/`. The calls that change how the
biology reads:

- **A source label can be compound in ways `;` does not catch.** `X/Y` and
  `X and Y` both slipped through. DrLLPS's `Centrosome/Spindle pole body` put
  775 metazoan proteins into the fungal spindle pole body, and CD-CODE's
  `Presynaptic clusters and postsynaptic densities` put 1,366 proteins on the
  presynaptic side and dropped the postsynaptic half. When a label's meaning
  depends on the organism, the rule lives in
  `database/mappings/mlo_organism_scoped.csv`, never inside a parser.
- **`XY body` and `sex body` are the same meiotic structure** and both map to
  `xy_body`. The old `sex_body` canonical carried a justification describing the
  Barr body while holding meiotic proteins. **No `barr_body` canonical exists** —
  nothing annotates it, and coverage gates granularity.
- **`polarity_condensate` was split three ways** (bacterial / fungal fusion
  focus / metazoan cell polarity). It had merged three unrelated systems on the
  strength of the word "polarity".
- **Protein homology is not compartment identity, and neither is pathway
  membership.** `DDR1 condensate` left `hippo_condensate`, `TIFA-TRAF6` left
  `inflammasome`, `SSB condensate` returned to `dna_damage_foci`, and
  `FATZ-1 condensate` (sarcomeric Z-disc) left `postsynaptic_density`.
- **A membrane-bounded structure is still not an MLO, but its contents may be.**
  `Golgi ribbon` is discarded; `Large dense-core vesicles` keeps its protein
  under `chromogranin_condensate`, because the condensate is the intravesicular
  dense core rather than the vesicle.
- **One curated category per canonical.** 23 canonicals had their category
  decided by file-read order. `Citoplasma` and `Citoplasmático` were one
  category under two spellings.

### Second review round (2026-08-10, mapping v6)

Documento in `docs/review/ultima/`. It verified v5, accepted the two places we
had argued back, and reversed one of our calls. Details in
`mlo_mapping_decisions.md` §12.

- **`synaptic_compartment` was wrong and is retired.** v5 created it to avoid
  inventing a side of the synapse for CD-CODE's compound label. But 1,353 of its
  1,366 proteins are annotated `postsynaptic_density` by **DrLLPS**, and only 3
  as presynaptic. The label is a synonym of `postsynaptic_density`. The lesson
  generalises: **before creating a canonical at a coarser resolution because one
  source is vague, check whether another source already resolves the same protein
  set.** Cross-resource agreement is evidence; it is not the same as one resource
  duplicating itself.
- **`plant_mtoc`.** Plants have neither a centrosome nor a spindle pole body, so
  neither branch of the fungal/metazoan split fits them. This term exists **only
  in `mlo_organism_scoped.csv`** — the first canonical no source name reaches
  unconditionally.
- **`evidence_type` records what kind of claim a row makes**, which
  `unified_role` structurally cannot. See `SCHEMA.md`. The key consequence for
  reading the biology: rows with no role are not missing data — for CD-CODE they
  are `membership_only`, its declared scope. And `curator_assignment` carries the
  warning that DrLLPS roles are **protein-scoped**: the same label propagates to
  every MLO of that protein, so a DrLLPS "driver" is not a claim about that
  compartment.
- **Cases closed as correct**, worth recording because two were flagged as
  exposed: CD-CODE `Germ granule` → `p_granule` (the merge the dossier most
  wanted challenged) and `Mitochondrial cloud` → `balbiani_body`, both confirmed
  from gene lists.

Still open after this round, and deliberately so: the category-axis migration
(now **four** axes, not five — omitting `functional_process` leaves only three
terms unclassified), reinstating DrLLPS regulators as a third role value,
removing `NotInformed` and `in_vitro_droplet` from the organelle vocabulary, and
the review equivalences still unadjudicated. Three of those need the original
publication: `Receptor cluster`, `Peri-nucleolar condensate`, `ORC1 bodies`.
Also unadjudicated despite the second round assuming otherwise: `RNA polymerase
II, holoenzyme`, which no document has ever given a verdict.

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
  never discarded at the pipeline stage) with `unified_role = NULL`.
- **They are served (`dataset_active = 1`) since 2026-08-12.** They carried
  `dataset_active = 0` until then, and the external biological audit closed that
  against us (`R1-ACT-14`): the exclusion did not just hide a weak claim, it
  removed **501 proteins** from the served dataset entirely, because a regulator
  annotation was the only annotation they had. Hiding an assertion is defensible;
  making the protein that carries it indistinguishable from a protein no source
  reports is not. There is no `dataset_active = 0` row in the database today —
  see `SCHEMA.md` and `policy.py`.
- What identifies a regulator row is `evidence_type = 'curator_assignment'`
  together with `source_role = 'Regulator'`
  (`policy.regulator_annotation_clause()`), and the claim it makes is weak in a
  specific way: DrLLPS assigns the role **per protein**, so the same label
  propagates to every MLO of that protein and is not a per-compartment assertion.
  `/mlo/{id}` counts these in their own `by_role` bucket rather than as
  components, since "component" would assert residency the source never claimed.
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
(`spatial_location = 'unspecified'` since the four-axis migration, `category =
'Unspecified'` before it — see `mlo_definitions.csv`) for sources that gave no
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
- **272 PhaSepDB proteins now carry `unified_mlo = 'in_vitro_droplet'` with
  `evidence_type = 'cellular_requirement'`**, a combination that reads as
  contradictory (`cellular_requirement` means "disrupts the condensate in
  cells"; these rows have no cellular claim) — see "PhaSepDB in vitro
  reclassification" above for why this was left open rather than fixed at the
  same time.
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
- **`Arabidopsis` rows of `Centrosome/Spindle pole body` (12) resolve to
  `centrosome`, and plants are acentrosomal.** The organism-scoped rule
  separates fungal from everything else, which is as far as the audit's finding
  goes; inventing a third destination would exceed it. Revisit if a source ever
  annotates plant MTOCs directly.
- **Wide canonicals are functional aggregations, not synonym sets.**
  `transcriptional_condensate` absorbs 20 source names including
  factor-specific condensates (BRD4, cBAF, EWS-FLI1) that share function but not
  composition; the same holds for `cytoplasmic_rnp_granule`, `viral_factory` and
  `signaling_condensate`. This is defensible under the coverage rule — no source
  annotates at factor resolution — but presenting them as equivalences misleads.
- **Protein-set overlap is not a valid test of whether a merge was right in this
  dataset.** Of 825 merged pairs, 365 share no organism and 238 more share no
  resource, so zero overlap is usually an artefact of disjoint coverage. Only 22
  pairs are actually evaluable. Absence of overlap signal does not validate a
  merge, and its presence is what exposed the `XY body` error.