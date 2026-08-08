# MLOsMetaDB — Biological Curation Dossier for External Review

**Prepared:** 2026-08-08 · **Dataset version:** v2 · **Mapping version:** v4
**Audience:** external biological reviewer (no repository access assumed)

---

## 1. Purpose and scope of this review

MLOsMetaDB is a meta-database that unifies protein annotations from five
upstream LLPS/MLO resources into a single controlled vocabulary, enriched with
UniProt metadata, InterPro/MobiDB sequence features, BioGRID interactions and
OMA orthologs. It serves the public API and SPA at `mlos.leloir.org.ar`.

Two curation layers carry essentially all of the biological judgement in the
project, and both are what we are asking you to review:

1. **The role model** — collapsing each source's own role vocabulary
   (`Scaffold`, `Client`, `Regulator`, `driver`, `client`, none) into two
   canonical categories, `driver` and `client` (surfaced as "MLO Component").
2. **The MLO vocabulary** — collapsing 841 curated source condensate names
   into 170 canonical `unified_mlo` terms, each assigned to one of 22
   categories.

### What we are asking you to assess

| # | Question |
|---|---|
| **A** | **Biological correctness of the equivalences.** Are the source→canonical merges and separations defensible? Which unlisted synonyms should have been merged, and which merges collapse genuinely distinct compartments? |
| **B** | **Coherence of the category scheme.** The categories mix subcellular localisation, organism domain, pathology and assay context. Where does that break down, what belongs in more than one category, and what is missing? |
| **C** | **The driver/component model.** Is it defensible to collapse `Scaffold`/`driver` → driver and `Client` → component, and to exclude `Regulator` from the served dataset? What biases does that introduce? |
| **D** | **Nomenclature and coverage.** Do the canonical names match current literature usage? Which entries are not real MLOs, and which well-established MLOs are absent from the vocabulary? |

### What is explicitly out of scope

- `unified_mlo` is **not a formal ontology**. It is an internal controlled
  vocabulary in `snake_case`, designed to be unambiguous within this dataset,
  not to be interoperable with GO or a condensate ontology. Suggestions to
  align with an external ontology are welcome as a separate recommendation,
  but "this is not the GO term" is not by itself a finding.
- Software engineering, schema design and API behaviour.
- The enrichment layers (InterPro, MobiDB, BioGRID, OMA), which apply no
  biological curation of their own.

### Two hard project rules that constrain any proposed change

- **Data coverage gates granularity.** A canonical term is not created unless
  at least one source database actually annotates proteins at that level of
  resolution. Several biologically correct refinements were rejected on this
  basis alone (§6.4) — they would produce empty vocabulary entries.
- **Provenance is never destroyed.** Rows excluded from the served dataset
  (today only DrLLPS `Regulator`) stay in the database flagged
  `dataset_active = 0`. Nothing is dropped at the pipeline stage on
  biological grounds.

---

## 2. Source databases

Five upstream resources, one `source_db` tag each. Counts are actual row counts
from the shipped database.

| `source_db` tag | Real-world database | Input used | Annotations | Distinct proteins |
|---|---|---|---:|---:|
| `PhaSepDB` | PhaSepDB | `detail` (curated drivers) + `mlo_entries` (HT screens) | 10,675 | 7,755 |
| `DrLLPS` | DrLLPS | `drllps_llps.tsv` | 10,872 | 8,588 |
| `CDCODE` | CD-CODE | `protein2condensate` | 13,845 | 10,883 |
| `LLPSDB` | LLPSDB | `entries` + `proteins` | 380 | 380 |
| `PhasePro` | PhaSePro | `phasepro.tsv` | 199 | 116 |
| | | **Total** | **35,971** | **15,879** |

> **⚠ Counts changed on 2026-08-08 — earlier drafts of this dossier were
> inflated.** An initial version of this section listed *six* resources under
> six tags, with `PhaseDB` (14,608 rows) and `PhasePDB` (14,875) as separate
> entries and a total of 54,786. Both tags denoted a single resource, PhaSepDB,
> which two parsers ingested twice from byte-identical copies of the same
> export files; nothing downstream deduplicated the rows. The tags were merged
> and the duplicates removed. Protein counts were never affected (15,879 before
> and after) — only annotation rows.
>
> Two consequences for reading the rest of this document: any absolute
> annotation count carried over from the earlier draft is too high, and the
> per-MLO figures in the attached inventory were regenerated against the
> corrected database. `protein_summary.source_db_count` now maxes out at 5;
> the 54 proteins it previously reported as appearing in six source databases
> were an artifact.
>
> Full account: `docs/issues/001-phasedb-phasepdb-duplicate-ingestion.md`.

### Evidence (PMID) coverage

| Source | Annotations with PMID |
|---|---|
| PhaSepDB / DrLLPS / PhasePro | 100% |
| LLPSDB | 378 / 380 |
| **CD-CODE** | **0 / 13,845** |

CD-CODE contributes 25% of all annotations with no per-annotation PMID and no
role field. This is a property of the export we ingest, not a parsing loss.

### Organism coverage

15,879 proteins. Top: *Homo sapiens* 6,802 · *Mus musculus* 2,543 ·
*Arabidopsis thaliana* 2,088 · *C. elegans* 950 · *S. cerevisiae* 801 ·
*Xenopus laevis* 706 · *Bos taurus* 253 · *Danio rerio* 243 ·
*D. melanogaster* 233 · *R. norvegicus* 115 · *S. pombe* 94 ·
*C. reinhardtii* 88 · *E. coli* K12 46 · *T. gondii* 32 · *O. sativa* 26 ·
*Caulobacter* 13 · *C. albicans* 11 · *T. brucei* 10. 474 proteins have no
organism assigned.

The Arabidopsis over-representation relative to classic model organisms
(2,088, third overall, ahead of *C. elegans*, yeast and *Drosophila*) reflects
a large plant HT screen in the upstream data. Worth noting when interpreting
which MLO categories look well populated.

---

## 3. Normalisation into the intermediate schema

Every parser emits exactly six columns, then all sources are concatenated:

`uniprot_id` · `source_db` · `source_mlo` · `source_role` · `evidence` (PMIDs) · `organism`

Rules applied uniformly, chosen so that curation decisions happen at the
mapping stage and never silently inside a parser:

- One row per `(uniprot_id, source_db, source_mlo, source_role)`, enforced
  uniformly for every source at the integration stage; the PMIDs of rows that
  collapse into one annotation are merged into its `evidence` field.
- **Rows are dropped only when `uniprot_id` is missing or empty.** Never for a
  missing MLO name, never for a missing role.
- Compound MLO fields (`"Nucleolus; Stress granule"`) are exploded into one
  row per name. This was a real bug fix: 66 compound tokens in PhaSepDB were
  previously treated as single unmappable strings.
- An empty `source_mlo` becomes the literal token `NotInformed` — a curated
  vocabulary entry, not a discard marker (§8).
- Generic-looking tokens (`Others`, `Unknown`, `Droplet`) are **kept verbatim**
  by the parser and resolved at the mapping stage, so that every discard
  decision is visible in one reviewable file.

Note that `evidence` is a PMID list attached to the source row, not to the
specific MLO assignment. After a compound field is exploded, each resulting
row inherits the full PMID list of the parent row. **A PMID on a row is
therefore not a guarantee that that paper supports that specific
protein–MLO pair.**

---

## 4. The role model — review question C

### 4.1 The canonical categories

The driver vs. client/component distinction across the five sources is
**terminological, not experimental**: the same underlying evidence receives
different labels depending on which curator wrote it. The project collapses
this into two categories:

- **LLPS driver** — direct experimental evidence of phase separation
  (self-assembly, or driving the assembly of others).
- **MLO component** (stored as `client`) — annotated presence in or
  association with an MLO, with no evidence that the protein drives phase
  separation.

`unified_role` therefore has exactly two non-null values, `driver` and
`client`, plus `NULL`.

We record internally that **"MLO Component" is an imprecise label** — a
protein can be structurally part of a condensate without any claim about its
causal role. It was chosen over more accurate but opaque alternatives for
communicative clarity, and the UI carries an explicit definition card.

### 4.2 Assignment table

The mapping is **fixed per source file, not inferred per row**:

| Source | Source field / file | `source_role` | → `unified_role` | `dataset_active` |
|---|---|---|---|---|
| PhaSepDB | `mlo_entries` (HT screen) | `client` | `client` | 1 |
| PhaSepDB | `detail` (curated) | `driver` | `driver` | 1 |
| DrLLPS | `LLPS Type = Scaffold` | `Scaffold` | `driver` | 1 |
| DrLLPS | `LLPS Type = Client` | `Client` | `client` | 1 |
| DrLLPS | `LLPS Type = Regulator` | `Regulator` | `NULL` | **0** |
| LLPSDB | all rows | `driver` | `driver` | 1 |
| PhasePro | all rows | `driver` | `driver` | 1 |
| CD-CODE | all rows | `NotInformed` | `NULL` | 1 |

Realised distribution:

| Source | driver | client | NULL | excluded (`active=0`) |
|---|---:|---:|---:|---:|
| PhaSepDB | 2,138 | 8,537 | — | — |
| DrLLPS | 353 | 9,130 | — | 1,389 |
| CDCODE | — | — | 13,845 | — |
| LLPSDB | 380 | — | — | — |
| PhasePro | 199 | — | — | — |

A protein can hold both a driver and a client row for the same MLO under
PhaSepDB — 214 `(protein, MLO)` pairs do. That is not a contradiction to
resolve: PhaSepDB publishes a curated driver dataset and an MLO-component
dataset separately, and being shown to drive phase separation is a different
experiment from being detected inside a condensate. Both annotations are kept,
each with its own PMIDs.

In the served dataset: 15,377 proteins, of which **2,029 carry at least one
driver annotation**.

### 4.3 Regulators

DrLLPS `Regulator` rows (1,390 annotations, 977 proteins) are **retained in
the database** with `unified_role = NULL` and `dataset_active = 0`: present
for provenance, excluded from served counts and default listings.

The rationale is that a regulator — a kinase, a chaperone, an RNA helicase
that modulates condensate assembly — is not evidence that the protein is
*in* the condensate or that it drives phase separation, so including it would
inflate both categories with a third, unrelated kind of claim. `dataset_active
= 0` is reserved exclusively for deliberate scope exclusions of this kind.
**A NULL role or an indeterminate MLO name is an annotation gap, never a
reason to exclude**; those rows always stay active and visible.

### 4.4 Specific concerns we want you to weigh

1. **Role is a property of the source file, not of the evidence.** Every row
   in PhaSepDB's `detail` export becomes `driver` — including entries the
   upstream resource classifies as *PS-other* (drives phase separation of a
   partner) alongside *PS-self*. Likewise, all 380 LLPSDB rows and all 199
   PhaSePro rows are `driver` by construction. Is "PS-self ∪ PS-other" a
   defensible single driver category, or does it need to be split?

2. **`client` conflates HT screen membership with curated association.**
   PhaSepDB's `mlo_entries` are high-throughput proteomic screens of isolated
   condensates. DrLLPS `Client` is literature-curated. Both become the same
   `client` label, and HT screens dominate the count (8,537 of 17,667 client
   annotations). Should confidence be distinguished at this level?

3. **CD-CODE's NULL is treated as "component" at query time.** The API's
   `role=component` filter is defined as "not a driver", which includes NULL,
   so 13,845 CD-CODE annotations are displayed under Component despite having
   no role evidence at all. The alternative — showing them as a third
   "unknown" bucket — was deferred as a UI decision. Is the current default
   misleading?

4. **The absence of an "excluded" audit trail in the served data.** A user of
   the API cannot see that 977 proteins have DrLLPS regulator evidence,
   because those rows never surface. Should regulator status be exposed as a
   separate flag rather than an exclusion?

---

## 5. MLO name unification — the criteria

The mapping file `mlo_mapping.csv` has four columns: `Nombre Original`
(verbatim source name), `Nombre Sugerido` (canonical `snake_case`),
`Categoria`, `Justificacion Biologica` (rationale, with PMID where
applicable). 841 rows, 173 distinct canonicals, 101 rows carry an explicit
PMID.

### 5.1 When two names are merged

In descending order of weight:

1. **Documented compositional identity** — same structural marker components
   (e.g. coilin for the Cajal body).
2. **Functional equivalence in the same organism** — same biological process,
   same subcellular localisation.
3. **Explicit synonymy in the primary literature** — the original paper
   defines the term as a synonym.
4. **Typographic or capitalisation variants** — formatting differences with no
   semantic change.

### 5.2 When names are kept separate

- The literature distinguishes composition or function, even for spatially
  adjacent condensates.
- The structure has a specific function not captured by the more general
  canonical.
- The term comes from an organism or compartment with no direct equivalent in
  the canonical's context.

### 5.3 When a term is discarded (`DISCARD`, 15 rows)

- It is a generic GO subcellular-localisation term, not an MLO.
- It is marked obsolete in the source.
- It describes a membrane-bounded structure or a molecular machine (a protein
  complex), not a condensate.

Discarded terms and their stated reasons:

| Term | Reason |
|---|---|
| `ribonucleoprotein complex` | generic GO RNP-complex term |
| `intracellular non-membrane-bounded organelle` | generic GO structural term |
| `protein-containing complex` | generic GO term |
| `protein complex involved in cell-cell adhesion` | generic GO term |
| `extracellular matrix`, `collagen-containing extracellular matrix` | not an MLO |
| `cytoplasmic microtubule`, `Microtubule` | cytoskeletal structure |
| `obsolete cytoskeletal part` | obsolete GO term |
| `PcG protein complex` | molecular machinery, not the body it forms |
| `neuron projection`, `synaptosome, neuron projection`, `synaptosome` | neuronal morphology / membrane-bounded |
| `TRIM45 bodies` | CD-CODE definition is only "Cytoplasmic Puncta" — insufficient evidence |
| `Others` (DrLLPS) | proteins with no MLO assigned in DrLLPS |
| `_` | PhaSepDB placeholder |

**A discard is a hard removal at the mapping stage** — the term is not mapped
to a fallback, and its rows do not enter `mlo_annotations`. This is the one
place where the "never destroy provenance" rule does not hold, and it is worth
your scrutiny: `Microtubule` in particular is discarded as a cytoskeletal
structure, yet the mapping retains `spindle_apparatus` for microtubule-
associated condensates, and the literature does describe RNA-binding-protein
condensates nucleated on microtubules.

### 5.4 Canonical naming convention

`snake_case`, all lowercase, no articles or prepositions, specific enough to
be unambiguous within this vocabulary. Not a formal ontology.

---

## 6. Documented curation decisions — review question A

These were made across four mapping revisions (v1 2026-03-31 → v4
2026-04-29). Reversals are recorded rather than overwritten, because the
reasoning behind a reversal is what a reviewer needs. Presented in that form
below.

### 6.1 Centrosome and mitotic structures

| Source names | → canonical |
|---|---|
| `Centrosome`, `Pericentriolar matrix`, `Pericentriolar material`, `Pericentriolar compartment` | `centrosome` (1,069 annot.) |
| `Centrosome/Spindle pole body`, `Spindle pole body`, `Spindle pole` | `spindle_pole_body` (910) |
| `Spindle apparatus`, `Spindle matrix`, `+TIP`, `+TIP body`, `Birc5b assembly`, `EB1F condensate`, `GAS2L3 condensates`, `condensed compartments of microtubule bundling` | `spindle_apparatus` (104) |

- **PCM is not an independent MLO.** LLPS data for the pericentriolar material
  (SPD-5 in *C. elegans*, pericentrin in human) describe the assembly
  mechanism of the centrosome, not a separate structure.
- **SPB was split from centrosome in v4** (reversing v1–v3). The fungal spindle
  pole body is permanently embedded in the nuclear envelope (closed mitosis)
  and is not structurally homologous to the metazoan centrosome; functional
  equivalence as an MTOC does not justify unification given the differences in
  architecture, protein composition and duplication mechanism. This single
  reversal moved 910 annotations.
- **Spindle apparatus kept separate from centrosome.** The spindle matrix is a
  distinct proteinaceous structure embedding the spindle microtubules
  pole-to-pole in a microtubule-independent manner; BuGZ forms condensates
  independent of the PCM.

### 6.2 Germ-cell structures

| Source names | → canonical |
|---|---|
| `Nuage`, `IMC (intermitochondrial cement)` | `nuage` (47) |
| `Chromatoid body` | `chromatoid_body` (222) |
| `P granule`, `P-granule`, `PGL granules`, `Germ granule` (CD-CODE) | `p_granule` (1,476) |
| `Germ plasm`, `germ plasm`, `Germ plasm/Polar granule`, `Founder granule` | `germ_plasm` (11) |
| `pi-body` | `pi_body` (separate from both `p_body` and `p_granule`) |
| `SIMR foci` | `simr_foci` |
| `MARDO` | `mardo` |

- **Chromatoid body split from nuage in v4** (reversing v1–v3, 222
  annotations). The chromatoid body is post-meiotic, appears in spermatids and
  associates with the Golgi; the IMC is meiotic, perinuclear and mitochondria-
  associated. Distinct stages, distinct structures.
- **IMC → `nuage` was retained** against an external suggestion to split it.
  Reasoning: "nuage" refers morphologically to electron-dense perinuclear
  granulofibrillar material in germ cells, and the IMC satisfies that
  definition in spermatocytes. The error being corrected was collapsing the
  *chromatoid body* with the IMC, not the IMC assignment itself.
- **PGL granules → `p_granule`.** PGL-1/PGL-3 are the scaffolding components
  of *C. elegans* P granules, not a separate MLO.
- **CD-CODE `Germ granule` → `p_granule`.** Across zebrafish, *Drosophila* and
  human contexts the term denotes the organism-specific P-granule equivalent.
  **This is one of the merges we would most like challenged** — it treats
  "germ granule" as an organism-agnostic synonym of a *C. elegans*-defined
  term.
- **`Founder granule` → `germ_plasm`.** Founder granules in *Drosophila*
  embryos are the germ plasm precursor at the posterior pole.
- **SIMR foci split from mutator foci in v4** (reversing v1–v3). SIMR-1 foci
  mediate the primary→secondary piRNA transition with their own components
  (SIMR-1, ENRI-1) and are molecularly separable, though adjacent.
- **MARDO split from Balbiani body in v4** (reversing v1–v3). The Balbiani
  body in early oocytes has amyloid/solid properties [PMID:27135929]; MARDO is
  a late-stage hydrogel in mammalian oocytes with its own composition.
  Biophysically distinct, different oogenesis stages.

### 6.3 Remaining decisions by system

**RNP granules and P-bodies**

- `Sponge body` → **`sponge_body`, kept separate from `p_body`** (reversing an
  early draft). *Drosophila* sponge bodies share components with P-bodies but
  differ compositionally between nurse cells and oocyte, contain embedded ER,
  and function primarily in maternal mRNA transport rather than degradation.
- `P-body`, `GW-body`, `PB-like Assembly`, `p62-dependent P-bodies (pd-PBs)`,
  `CCR4-NOT1 complex` → `p_body` (3,243).
- `axonal TIAR-2 granules` → **`axonal_tiar2_granule`, split from
  `stress_granule` in v4.** TIAR-2 is the *C. elegans* TIA-1 homologue, which
  had motivated the original merge; the split was accepted on the grounds that
  *protein homology is not compartment identity*. These granules form
  post-injury, localise to the distal axon and inhibit growth-cone
  regeneration [PMID:31378567].
- `IMP1 RNP granule` → `neuronal_granule` — **flagged internally as a
  pragmatic grouping.** Composition overlaps neuronal granules (IMP, ribosomes,
  Staufen) but the literature also describes differences from both SGs and
  P-bodies.
- `Mimi granules` → `neuronal_granule` (was `p_granule`; *Drosophila* granules
  containing synaptic-process mRNAs).

**Nucleolus**

- `granular component`, `dense fibrillar component`, `rDNA locus` → `nucleolus`
  (12,690 annotations, the largest entry). No source annotates proteins to
  nucleolar sub-compartments systematically; annotation is always at
  whole-nucleolus level. A `nucleolar_subcompartment` canonical was proposed
  externally, judged biologically correct, and **rejected for lack of data
  coverage** (§6.4).

**Chromatin**

- `Heterochromatin` → `heterochromatin` (kept separate; HP1α-driven condensate
  identity, PMID:28636597).
- `Euchromatin`, `Chromatin` (DrLLPS), `eukaryotic topoisomerase ii` →
  `chromatin_compartment`.
- `sex body` → **`sex_body`, split from `heterochromatin` in v4.** The
  inactive X has layered organisation and specific molecular dynamics (XIST,
  SHARP, HDAC3) distinguishing facultative from constitutive heterochromatin.
- `PcG body`, `PcG chromatin condensates`, `Polycomb body` → `polycomb_body`.
  A PRC1/PRC2 split was proposed and rejected for lack of coverage (§6.4).

**Signalling**

- `TCR signalosome`, `LAT signalosome` → `t_cell_signalosome`.
- `Receptor cluster`, `membrane cluster` → `signaling_cluster` — an explicit
  catch-all for membrane condensates with no more specific identity.
- `Hippo signalosome`, `TAZ Condensate`, `DDR1 condensate`, `NEDD4
  condensates` → `hippo_condensate`. **Acknowledged simplification**: the
  Hippo signalosome is cytoplasmic (inactive YAP/TAZ) while the TAZ condensate
  is nuclear (active co-activator) — different compartments, different
  composition, merged because CD-CODE does not annotate them with enough
  granularity to support two entries.
- `Beta-Catenin Destruction Complex`, `Destruction complex condensate` →
  **`wnt_destruction_complex`, split from `wnt_signaling_condensate` in v4**:
  cytoplasmic, Wnt-OFF, centrosome-nucleated, versus membrane/nuclear Wnt-ON
  (DVL2, Dishevelled, LEF1/β-catenin, which stay in
  `wnt_signaling_condensate`). Spatially separated, compositionally distinct,
  functionally opposed.

**Viral**

- `viroplasm`, `viroplasm viral factory` → `viroplasm` — kept separate from
  `viral_factory` because rotavirus/reovirus viroplasms have a specific
  documented protein composition.
- `Viral factory`, `cytoplasmic viral factory`, `cVACs`, `LANA body`, `HIV
  core condensate`, `RdRp condensates`, `RPSA-VIM-ENO Condensate` →
  `viral_factory` — the general term for factories with no specific identity.
- `viral replication compartment (VRC)`, `Pre-replication compartment (PRC)`,
  `VIR condensate`, `ORC1 bodies` → `replication_compartment` — replication
  compartments as distinct from full factories, which include assembly.
- `SARS-CoV-2 condensate`, `FXR-driven SARS-CoV-2 condensate` →
  `sars_cov2_n_condensate`.

**Autophagy and proteostasis**

- `ATG condensate`, `ATG4B condensate` → `pre_autophagosomal_structure`.
- `BAG2` → `proteasome_foci` (was `aggresome`): ubiquitin-independent 20S
  degradation under hyperosmotic stress.
- `Plectin condensates` → `signaling_condensate` (was `aggresome`): a
  differentiation-signalling condensate, not a misfolded-protein deposit.

**Prokaryotic and plastid** — kept as separate canonicals under `Procariota` /
`Plastídico` because MLOsMetaDB is multi-organism: `bacterial_rnp_body`
(BR-bodies), `carboxysome`, `degradosome`, `ftsz_droplet`, `parabs_condensate`,
`polyp_granule`, `polarity_condensate` (PopZ, PodJ), `chloroplast_stress_granule`,
`plant_photobody`, `plant_signaling_condensate`, `pyrenoid`.

**Reclassifications made once CD-CODE textual definitions became available**
(v3) — these had been assigned to catch-all canonicals without access to the
source definitions:

| Source name | From | To | Reason |
|---|---|---|---|
| `SCOTIN condensate` | `stress_granule` | `eres_condensate` | ER-membrane condensate sequestering Sec31/13 |
| `YBX1 condensate` | `stress_granule` | `exosomal_condensate` | miRNA sorting into exosomes |
| `HSP condensate` | `stress_granule` | `signaling_condensate` | *Dictyostelium* developmental chaperone condensate |
| `PCBP2 condensates` | `stress_granule` | `signaling_condensate` | mitochondrial signalling / BACE1 mRNA decay |
| `Nur77 condensate` | `transcriptional_condensate` | `signaling_condensate` | pro-apoptotic, on ubiquitinated mitochondria |
| `METTL14 condensate` | `transcriptional_condensate` | `nuclear_speckle` | m6A mRNA processing |
| `NP bodies` | `nuclear_body` | `norad_pum_body` | NORAD-inhibited Pumilio condensates |
| `AFAP1-AS1 condensates` | `nuclear_body` | `nuclear_speckle` | recruits splicing factors |
| `nYAC` | `nuclear_body` | `transcriptional_condensate` | YTHDC1/m6A transcriptional condensates in AML |
| `Nuclear poly(A) domains` | `nuclear_speckle` | `maternal_mrna_condensate` | maternal transcript hubs in oocytes |
| `SSB condensate` | `dna_damage_foci` | `signaling_condensate` | bacterial repair-protein storage depot |

Two duplicate-canonical conflicts were also resolved: `cytoplasmic protein
granule` (dropped the `cytoplasmic_rnp_granule` alternative) and `galectin
complex` (dropped `galectin_condensate`, keeping `galectin_lattice`).

### 6.4 Proposed refinements that were rejected

Recorded because a reviewer should be able to see what was considered and
declined, and re-open it if the reasoning is wrong.

| Proposal | Verdict | Reason |
|---|---|---|
| `granular component` → `nucleolar_subcompartment` | **Rejected** | Judged biologically correct — the GC has immiscible subphases and a fourth chromatin-anchoring layer — but no source annotates at nucleolar-subcompartment resolution. Would create an empty entry. Revisit if a future source makes the distinction. |
| `PcG body` → `prc1_condensate` / `prc2_condensate` | **Rejected** | PRC1 and PRC2 condensates form by distinct mechanisms, but no source distinguishes them. The annotated entity is the microscopically visible Polycomb body, predominantly PRC1. |
| `YBX1 condensate` → `ybx1_sorting_condensate` | **Rejected** | `exosomal_condensate` captures the specificity adequately; a protein-specific canonical would imply the same for dozens of specialised exosomal proteins. Excessive granularity for this resolution level. |
| Split `IMC` from `nuage` | **Rejected** | See §6.2. |

---

## 7. The category scheme — review question B

Every canonical carries one `category`. The scheme is not a single axis: it
mixes subcellular localisation (Nuclear, Citoplasmático, Membrana), organism
domain (Procariota, Vegetal, Viral), cell type (Neuronal, Germinal),
pathology (Patológico) and assay context (In vitro). **Category labels are
stored in Spanish** while every other vocabulary term is in English.

| Category | Entries | Reading |
|---|---:|---|
| `Nuclear` | 48 | nuclear compartments |
| `Citoplasmático` | 39 | cytoplasmic |
| `Germinal` | 14 | germ-cell |
| `Membrana` | 13 | membrane-associated |
| `Procariota` | 12 | prokaryotic |
| `Neuronal` | 8 | neuronal |
| `Citoesqueleto` | 6 | cytoskeletal |
| `Viral` | 5 | viral |
| `Citoplasma` | 5 | **duplicate of `Citoplasmático`** |
| `Plastídico` | 3 | plastid |
| `Extracelular` | 3 | extracellular |
| `Vegetal` | 2 | plant |
| `Patológico` | 2 | pathological |
| `Mitocondrial` | 2 | mitochondrial |
| `Viral/Nuclear` | 1 | hybrid |
| `Unspecified` | 1 | `NotInformed` only |
| `Secretor` | 1 | secretory |
| `Nuclear/Mitótico` | 1 | hybrid |
| `Nuclear/Citoplasmático` | 1 | hybrid |
| `Mitótico` | 1 | mitotic |
| `In vitro` | 1 | `in_vitro_droplet` only |
| `Autofagia` | 1 | autophagy |

### Known defects in the scheme

1. **`Citoplasmático` (39) and `Citoplasma` (5) are the same category** under
   two spellings.
2. **Six singleton and hybrid categories** (`Viral/Nuclear`, `Nuclear/Mitótico`,
   `Nuclear/Citoplasmático`, `Mitótico`, `Secretor`, `Autofagia`) exist because
   a single canonical needed them. Hybrids are ad hoc rather than a designed
   multi-localisation mechanism.
3. **23 canonicals are assigned conflicting categories inside the mapping
   file.** When several source names map to one canonical and those rows carry
   different `Categoria` values, the vocabulary loader keeps whichever row it
   reads first (`INSERT OR IGNORE`), so the stored category for these 23 is
   **arbitrary, not curated**. Examples:

   | Canonical | Competing categories in the mapping file |
   |---|---|
   | `polarity_condensate` | Citoesqueleto / Neuronal / Procariota |
   | `inclusion_body` | Citoplasma / Patológico / Patológico/Viral |
   | `replication_compartment` | Nuclear/Viral / Viral / Viral/Nuclear |
   | `proteasome_foci` | Citoplasmático / Nuclear |
   | `neuronal_granule` | Germinal / Neuronal |
   | `l_body` | Citoplasma / Germinal |
   | `spindle_apparatus` | Citoesqueleto / Mitótico |
   | `viral_factory` | Citoplasmático / Viral |
   | `tau_condensate` | Citoplasma / Neuronal |
   | `stress_granule`, `p62_body`, `cytoplasmic_rnp_granule`, `sirna_body`, `ubqln_puncta`, `necrosome` | Citoplasma / Citoplasmático (the duplicate-label case) |

   The full list is in the attached `mlo_mapping_curated.csv`.

**Specifically for you:** `polarity_condensate` covering bacterial PopZ/PodJ,
cytoskeletal polarity and neuronal polarity in one canonical looks like a
merge across three unrelated biological systems, driven by the word "polarity"
rather than by composition. We would like a verdict on that one in particular.

---

## 8. Special vocabulary values

| Value | Meaning | Volume |
|---|---|---|
| `in_vitro_droplet` | LLPS demonstrated **in vitro only**, with no cellular MLO assigned. Sources: DrLLPS `Droplet` token (172) and all of LLPSDB (380). Category `In vitro`. | 552 |
| `NotInformed` | The source gave no MLO name. Category `Unspecified`. A **curated entry, not a discard value** — proteins with `NotInformed` rows remain fully in the database. Source: PhaSepDB's two datasets. | 930 |
| `synthetic_condensate` | CD-CODE's 386 engineered condensates (`Synthetic Condensate 000001`–`000386`), built to study LLPS biophysics. **Excluded at load time** — no rows enter `mlo_annotations`. | 0 loaded |
| `DISCARD` | Not an MLO (§5.3). Removed at the mapping stage. | 15 terms |

Two consequences worth your judgement:

- **`in_vitro_droplet` is an entry in the organelle vocabulary but is not an
  organelle.** It is an assay context. It appears in the same table and the
  same category namespace as `nucleolus` and `stress_granule`. Browse views
  hide it, but any analysis over `mlo_vocabulary` will treat it as an MLO.
- **`NotInformed` is hidden by category, not by deletion.** Top-level MLO
  browse grids exclude `category = 'Unspecified'`, while a protein's own
  annotation list still shows its `NotInformed` rows for full provenance. The
  frontend additionally shows `NotInformed` only when it is the *only* entry
  for a protein, dropping it as soon as a real MLO is present.

---

## 9. Full vocabulary inventory — review questions A and D

170 canonical entries. Columns: number of distinct source names collapsed into
the canonical, annotation rows, distinct proteins, and which resources report
it. Counts were regenerated on 2026-08-08 against the deduplicated database
(§2); an earlier draft of this table roughly doubled the annotation count of
every canonical that PhaSepDB reports. Protein counts are unaffected.

Resource abbreviations: `PsDB` = PhaSepDB, `Dr` = DrLLPS, `CD` = CD-CODE,
`LDB` = LLPSDB, `PPro` = PhaSePro.

Three canonicals have **no annotations at all** and should probably be removed
or investigated: `adhesin_nanodomain` (Membrana), `npr1_condensate`
(Citoplasmático), `rosenthal_fiber` (Patológico).

#### `Nuclear` — 48 entries

| `unified_mlo` | src names | annot. | proteins | reported by |
|---|---:|---:|---:|---|
| `nucleolus` | 8 | 9408 | 5011 | CD, Dr, PsDB, PPro |
| `nuclear_speckle` | 6 | 1050 | 710 | CD, Dr, PsDB, PPro |
| `pml_nuclear_body` | 3 | 1019 | 798 | CD, Dr, PsDB, PPro |
| `nuclear_stress_body` | 2 | 596 | 585 | CD, Dr, PsDB |
| `paraspeckle` | 3 | 382 | 273 | CD, Dr, PsDB, PPro |
| `cajal_body` | 1 | 368 | 257 | CD, Dr, PsDB |
| `nuclear_body` | 8 | 271 | 242 | CD, PsDB, PPro |
| `transcriptional_condensate` | 20 | 220 | 163 | CD, PsDB, PPro |
| `nuclear_pore_complex` | 3 | 120 | 63 | CD, Dr, PsDB, PPro |
| `dna_damage_foci` | 5 | 85 | 60 | CD, Dr, PsDB |
| `polycomb_body` | 3 | 82 | 44 | CD, Dr, PsDB, PPro |
| `heterochromatin` | 3 | 65 | 52 | CD, PsDB, PPro |
| `histone_locus_body` | 2 | 49 | 28 | CD, Dr, PsDB |
| `sam68_nuclear_body` | 2 | 40 | 17 | CD, Dr, PsDB, PPro |
| `proteasome_foci` | 5 | 26 | 18 | CD, PsDB |
| `tam_body` | 2 | 22 | 11 | CD, Dr |
| `insulator_body` | 1 | 21 | 15 | CD, Dr |
| `gem` | 3 | 14 | 13 | CD, Dr, PsDB |
| `elva` | 1 | 13 | 13 | CD |
| `anisosome` | 1 | 12 | 6 | CD, PsDB |
| `enhancer_condensate` | 5 | 11 | 9 | CD, PsDB, PPro |
| `perinucleolar_compartment` | 2 | 8 | 8 | CD, Dr |
| `chromatin_compartment` | 4 | 7 | 5 | CD, Dr, PPro |
| `opt_domain` | 1 | 7 | 7 | Dr |
| `mediator_condensate` | 1 | 6 | 6 | PsDB |
| `nuclear_dicing_body` | 1 | 6 | 3 | CD, PsDB |
| `cleavage_body` | 1 | 6 | 3 | CD, Dr |
| `nuclear_protein_granule` | 1 | 6 | 6 | PPro |
| `assemblysome` | 1 | 4 | 4 | CD, PsDB |
| `norad_pum_body` | 2 | 4 | 2 | CD, PsDB |
| `ddx1_body` | 1 | 4 | 2 | CD, Dr |
| `enhanceosome` | 1 | 4 | 4 | PPro |
| `spop_daxx_body` | 1 | 4 | 2 | CD, PPro |
| `cytoplasmic_nucleoporin_granule` | 1 | 3 | 3 | PsDB |
| `abscission_checkpoint_body` | 1 | 3 | 3 | PsDB |
| `nono_condensate` | 1 | 3 | 3 | PsDB |
| `tdp43_nuclear_condensate` | 1 | 2 | 2 | PsDB |
| `vipr_body` | 1 | 2 | 2 | PsDB |
| `amyloid_body` | 1 | 2 | 2 | PsDB |
| `u1_snrnp_condensate` | 1 | 2 | 2 | PsDB |
| `maternal_mrna_condensate` | 2 | 2 | 2 | CD, PsDB |
| `morc3_nuclear_body` | 2 | 2 | 1 | CD, PPro |
| `sex_body` | 1 | 2 | 2 | CD |
| `spliceosome` | 1 | 1 | 1 | PsDB |
| `inq_compartment` | 1 | 1 | 1 | PsDB |
| `kat6a_condensate` | 1 | 1 | 1 | PsDB |
| `pab2_condensate` | 1 | 1 | 1 | PsDB |
| `baz2a_body` | 1 | 1 | 1 | CD |

#### `Citoplasmático` — 39 entries

| `unified_mlo` | src names | annot. | proteins | reported by |
|---|---:|---:|---:|---|
| `stress_granule` | 6 | 5020 | 2838 | CD, Dr, PsDB, PPro |
| `p_body` | 5 | 2325 | 1507 | CD, Dr, PsDB, PPro |
| `p62_body` | 5 | 796 | 785 | CD, PsDB, PPro |
| `cytoplasmic_rnp_granule` | 12 | 71 | 66 | CD, PsDB, PPro |
| `hyperosmotic_shock_foci` | 2 | 35 | 18 | CD, PsDB |
| `signaling_condensate` | 12 | 21 | 21 | CD |
| `sec_body` | 2 | 19 | 11 | CD, PsDB, PPro |
| `cytoplasmic_protein_granule` | 2 | 17 | 17 | CD, PPro |
| `glycolytic_body` | 3 | 15 | 9 | CD, PsDB |
| `golgin_condensate` | 2 | 15 | 7 | CD, PsDB |
| `wnt_destruction_complex` | 2 | 12 | 7 | CD, PsDB |
| `pre_autophagosomal_structure` | 3 | 11 | 7 | CD, PsDB |
| `eres_condensate` | 2 | 11 | 10 | CD |
| `mirisc` | 4 | 10 | 2 | CD, PsDB, PPro |
| `wnt_signaling_condensate` | 5 | 9 | 7 | CD, PsDB |
| `sint_speckle` | 2 | 9 | 5 | CD, PsDB |
| `necrosome` | 2 | 9 | 9 | CD, PsDB |
| `inflammasome` | 2 | 9 | 9 | CD |
| `cgas_dna_complex` | 2 | 8 | 4 | CD, PsDB, PPro |
| `purinosome` | 1 | 8 | 5 | CD, PsDB |
| `u_body` | 2 | 8 | 5 | CD, Dr |
| `ubqln_puncta` | 2 | 7 | 4 | CD, PsDB |
| `plant_signaling_condensate` | 5 | 7 | 7 | CD |
| `sirna_body` | 2 | 7 | 5 | CD, Dr |
| `aggresome` | 1 | 6 | 6 | CD |
| `chromogranin_condensate` | 2 | 4 | 4 | CD |
| `sup35_condensate` | 1 | 4 | 2 | CD, PPro |
| `wnk_body` | 1 | 4 | 4 | CD |
| `sting_phase_separator` | 1 | 3 | 2 | CD, PsDB |
| `tis_granule` | 1 | 3 | 1 | CD, PsDB, PPro |
| `ferritin_condensate` | 1 | 3 | 3 | CD |
| `inava_condensate` | 2 | 2 | 1 | CD |
| `std1_body` | 2 | 2 | 1 | CD, PPro |
| `amyloid_aggregate` | 1 | 1 | 1 | CD |
| `cojusome` | 1 | 1 | 1 | CD |
| `d_granule` | 1 | 1 | 1 | CD |
| `frq_condensate` | 1 | 1 | 1 | CD |
| `intracellular_dna_protein_granule` | 1 | 1 | 1 | PPro |
| `npr1_condensate` | 1 | 0 | 0 | — |

#### `Germinal` — 14 entries

| `unified_mlo` | src names | annot. | proteins | reported by |
|---|---:|---:|---:|---|
| `balbiani_body` | 3 | 960 | 887 | CD, Dr, PsDB, PPro |
| `p_granule` | 5 | 833 | 707 | CD, Dr, PsDB, PPro |
| `chromatoid_body` | 1 | 222 | 114 | CD, Dr |
| `l_body` | 2 | 86 | 83 | CD, PsDB |
| `z_granule` | 2 | 51 | 46 | CD, PsDB |
| `sponge_body` | 1 | 27 | 14 | CD, Dr |
| `nuage` | 2 | 14 | 11 | CD, Dr, PsDB |
| `yb_body` | 2 | 9 | 5 | CD, PsDB, PPro |
| `germ_plasm` | 4 | 9 | 8 | CD, Dr, PsDB, PPro |
| `mardo` | 1 | 7 | 7 | CD |
| `oskar_granule` | 1 | 4 | 4 | PsDB |
| `mutator_foci` | 4 | 4 | 1 | CD, PsDB, PPro |
| `simr_foci` | 1 | 2 | 2 | CD |
| `pi_body` | 1 | 1 | 1 | PPro |

#### `Membrana` — 13 entries

| `unified_mlo` | src names | annot. | proteins | reported by |
|---|---:|---:|---:|---|
| `signaling_cluster` | 3 | 52 | 36 | CD, Dr, PsDB, PPro |
| `hippo_condensate` | 4 | 20 | 18 | CD |
| `endocytic_condensate` | 2 | 14 | 12 | CD |
| `t_cell_signalosome` | 3 | 9 | 3 | CD, PPro |
| `ankle_link_condensate` | 2 | 8 | 8 | CD |
| `integrin_adhesion_complex` | 2 | 6 | 6 | CD, PsDB |
| `zo_protein_compartment` | 1 | 5 | 5 | CD |
| `slit_diaphragm_condensate` | 1 | 3 | 3 | CD |
| `galectin_lattice` | 2 | 2 | 1 | PPro |
| `cortical_condensate` | 1 | 1 | 1 | PsDB |
| `escrt_condensate` | 1 | 1 | 1 | CD |
| `galectin_condensate` | 1 | 1 | 1 | CD |
| `adhesin_nanodomain` | 1 | 0 | 0 | — |

#### `Procariota` — 12 entries

| `unified_mlo` | src names | annot. | proteins | reported by |
|---|---:|---:|---:|---|
| `bacterial_rnp_body` | 4 | 19 | 18 | CD, PsDB, PPro |
| `degradosome` | 1 | 12 | 12 | CD |
| `carboxysome` | 2 | 5 | 5 | CD, PsDB |
| `ftsz_droplet` | 3 | 5 | 2 | CD, PPro |
| `mcd_condensate` | 1 | 2 | 2 | CD |
| `tmar_condensate` | 1 | 1 | 1 | PsDB |
| `nikr_compartment` | 1 | 1 | 1 | PsDB |
| `dps_condensate` | 1 | 1 | 1 | CD |
| `parabs_condensate` | 1 | 1 | 1 | CD |
| `polyp_granule` | 1 | 1 | 1 | CD |
| `refractile_body` | 1 | 1 | 1 | CD |
| `rho_body` | 1 | 1 | 1 | CD |

#### `Neuronal` — 8 entries

| `unified_mlo` | src names | annot. | proteins | reported by |
|---|---:|---:|---:|---|
| `postsynaptic_density` | 5 | 4479 | 2957 | CD, Dr, PsDB, PPro |
| `presynaptic_active_zone` | 4 | 1394 | 1383 | CD, PsDB, PPro |
| `tau_condensate` | 3 | 276 | 274 | CD, PsDB |
| `neuronal_granule` | 8 | 185 | 118 | CD, Dr, PsDB, PPro |
| `polarity_condensate` | 6 | 21 | 17 | CD, PsDB, PPro |
| `synapsin_condensate` | 4 | 15 | 11 | CD, PsDB, PPro |
| `elks_condensate` | 1 | 1 | 1 | PsDB |
| `axonal_tiar2_granule` | 1 | 1 | 1 | PPro |

#### `Citoesqueleto` — 6 entries

| `unified_mlo` | src names | annot. | proteins | reported by |
|---|---:|---:|---:|---|
| `centrosome` | 5 | 1015 | 978 | CD, Dr, PsDB, PPro |
| `spindle_pole_body` | 1 | 910 | 910 | Dr |
| `spindle_apparatus` | 9 | 93 | 89 | CD, Dr, PsDB, PPro |
| `actin_cortical_patch` | 3 | 5 | 5 | CD, PPro |
| `contractile_ring` | 2 | 2 | 1 | CD, PPro |
| `polarisome` | 1 | 1 | 1 | CD |

#### `Citoplasma` — 5 entries

| `unified_mlo` | src names | annot. | proteins | reported by |
|---|---:|---:|---:|---|
| `mesh_condensate` | 1 | 3 | 3 | PsDB |
| `haemoglobin_body` | 1 | 2 | 2 | PsDB |
| `antiviral_condensate` | 1 | 1 | 1 | PsDB |
| `bag2_condensate` | 1 | 1 | 1 | PsDB |
| `rna_helicase_condensate` | 1 | 1 | 1 | PsDB |

#### `Viral` — 5 entries

| `unified_mlo` | src names | annot. | proteins | reported by |
|---|---:|---:|---:|---|
| `viroplasm` | 3 | 39 | 36 | CD, PsDB, PPro |
| `viral_factory` | 12 | 35 | 30 | CD, PsDB, PPro |
| `sars_cov2_n_condensate` | 3 | 13 | 10 | CD, PsDB |
| `negri_body` | 1 | 9 | 5 | CD, PsDB, PPro |
| `icp22_condensate` | 1 | 2 | 2 | PsDB |

#### `Extracelular` — 3 entries

| `unified_mlo` | src names | annot. | proteins | reported by |
|---|---:|---:|---:|---|
| `exosomal_condensate` | 2 | 2 | 2 | CD |
| `elastin_granule` | 1 | 1 | 1 | CD |
| `spider_silk_condensate` | 1 | 1 | 1 | CD |

#### `Plastídico` — 3 entries

| `unified_mlo` | src names | annot. | proteins | reported by |
|---|---:|---:|---:|---|
| `pyrenoid` | 3 | 267 | 182 | CD, Dr, PPro |
| `chloroplast_stress_granule` | 1 | 79 | 79 | CD |
| `plant_photobody` | 3 | 15 | 10 | CD, PsDB |

#### `Mitocondrial` — 2 entries

| `unified_mlo` | src names | annot. | proteins | reported by |
|---|---:|---:|---:|---|
| `mitochondrial_rna_granule` | 2 | 84 | 44 | CD, Dr |
| `mitochondrial_nucleoid` | 1 | 6 | 6 | PsDB |

#### `Patológico` — 2 entries

| `unified_mlo` | src names | annot. | proteins | reported by |
|---|---:|---:|---:|---|
| `inclusion_body` | 7 | 95 | 78 | CD, PsDB, PPro |
| `rosenthal_fiber` | 1 | 0 | 0 | — |

#### `Vegetal` — 2 entries

| `unified_mlo` | src names | annot. | proteins | reported by |
|---|---:|---:|---:|---|
| `twn_body` | 1 | 3 | 3 | PsDB |
| `gbpl_condensate` | 1 | 1 | 1 | PsDB |

#### `Autofagia` — 1 entries

| `unified_mlo` | src names | annot. | proteins | reported by |
|---|---:|---:|---:|---|
| `fip200_puncta` | 1 | 2 | 2 | PsDB |

#### `In vitro` — 1 entries

| `unified_mlo` | src names | annot. | proteins | reported by |
|---|---:|---:|---:|---|
| `in_vitro_droplet` | 1 | 551 | 442 | Dr, LDB |

#### `Mitótico` — 1 entries

| `unified_mlo` | src names | annot. | proteins | reported by |
|---|---:|---:|---:|---|
| `midbody_granule` | 1 | 7 | 7 | CD |

#### `Nuclear/Citoplasmático` — 1 entries

| `unified_mlo` | src names | annot. | proteins | reported by |
|---|---:|---:|---:|---|
| `smn_complex` | 1 | 1 | 1 | CD |

#### `Nuclear/Mitótico` — 1 entries

| `unified_mlo` | src names | annot. | proteins | reported by |
|---|---:|---:|---:|---|
| `liquid_dyrk3_speckle` | 2 | 2 | 1 | CD, PPro |

#### `Secretor` — 1 entries

| `unified_mlo` | src names | annot. | proteins | reported by |
|---|---:|---:|---:|---|
| `mast_cell_granule` | 1 | 533 | 533 | CD |

#### `Unspecified` — 1 entries

| `unified_mlo` | src names | annot. | proteins | reported by |
|---|---:|---:|---:|---|
| `NotInformed` | 1 | 930 | 930 | PsDB |

#### `Viral/Nuclear` — 1 entries

| `unified_mlo` | src names | annot. | proteins | reported by |
|---|---:|---:|---:|---|
| `replication_compartment` | 6 | 23 | 21 | CD, PsDB |

---

## 10. Open questions and known issues

Consolidated. Items 1–3 are verified data defects that affect how the biology
should be read; items 4–11 are curation questions.

1. ~~**PhaseDB/PhasePDB double-ingestion** (§2)~~ — **fixed 2026-08-08**, after
   this dossier was first drafted. PhaSepDB had been ingested twice under two
   tags; 54,786 annotation rows became 35,971. Every count in this document was
   regenerated against the corrected database. Listed here because a reviewer
   working from an earlier copy will see the inflated figures.
2. **23 canonicals have arbitrary categories** (§7), resolved by file-read
   order rather than curation.
3. **`Citoplasmático` / `Citoplasma` duplicate category** (§7).
4. **Role reflects the source file, not the evidence** (§4.4): PS-self and
   PS-other are one `driver` category; all LLPSDB and PhaSePro rows are
   `driver` by construction.
5. **HT-screen membership and curated association share the `client` label**
   (§4.4), with HT screens dominating 8,537 / 17,667.
6. **CD-CODE NULL roles display as Component** (§4.4) — 13,845 annotations
   with no role evidence.
7. **`in_vitro_droplet` sits in the organelle vocabulary** (§8).
8. **PMIDs are row-level, not assignment-level** (§3) — after compound-field
   explosion, a PMID does not necessarily support the specific protein–MLO
   pair on its row.
9. **Merges we consider most exposed**: CD-CODE `Germ granule` → `p_granule`
   (§6.2); `polarity_condensate` across bacteria/cytoskeleton/neurons (§7);
   `hippo_condensate` merging cytoplasmic and nuclear states (§6.3);
   `IMP1 RNP granule` → `neuronal_granule` (§6.3); `signaling_cluster` and
   `signaling_condensate` as catch-alls; `Microtubule` discarded while
   microtubule-nucleated condensates are documented (§5.3).
10. **Three orphan canonicals** with zero annotations (§9).
11. **Coverage gaps**: PhaSepDB reports ~124 organelles against our 170
    canonicals. Some of the difference is intentional consolidation, but an
    earlier audit identified ~50–60 PhaSepDB rows genuinely missing from
    mapping coverage. **Do not assume the entire discrepancy is intentional.**
    Which well-established MLOs are absent from §9 altogether?

---

## 11. Attached files

| File | Contents |
|---|---|
| `mlo_inventory.csv` | The 170 canonicals: category, source names collapsed, annotations, proteins, reporting resources. |
| `mlo_synonyms_observed.csv` | Every `(source_mlo → unified_mlo)` pair actually present in the shipped database, with reporting resources and counts (411 pairs). The equivalence table to review directly. |
| `mlo_mapping_curated.csv` | The complete curation file: 841 rows, `Nombre Original` / `Nombre Sugerido` / `Categoria` / `Justificacion Biologica` (rationale in Spanish, 101 with PMID). Includes `DISCARD` and `synthetic_condensate` rows, and the 386 CD-CODE synthetic condensates. |
