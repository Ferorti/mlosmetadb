from __future__ import annotations

from typing import Any

from pydantic import BaseModel, field_validator


# ── shared ──────────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    error: str
    message: str


class MloAxes(BaseModel):
    """The four orthogonal axes that replaced `category` (R1-ACT-06).

    Mixed into every model that used to carry `category`, so the four travel
    together wherever the one used to. Values come straight from
    mlo_vocabulary — the API classifies nothing at read time.

    `taxonomic_scope` is NULL only for rho_body (nothing to derive it from) and
    `cell_type_context` for the 143 terms where cell type is not part of the
    organelle's definition. Neither absence is an error.
    """
    spatial_location: str | None = None
    taxonomic_scope: str | None = None
    physiological_state: str | None = None
    cell_type_context: str | None = None


class MloAxesWithProvenance(MloAxes):
    """The axes plus the two fields that say how much to trust two of them.

    Carried by /mlos and /mlo/{id}, where the axis is the subject of the
    response, and not by per-annotation objects, where it is a badge.

    - `spatial_location_evidence`: `from_category` for the 121 terms whose value
      was derived from the curated v6 category, `hand_assigned` for the 56 where
      the category named a lineage, a process or a cell type instead of a place
      and the auditor assigned the location from the organelle's biology. Those
      56 are pending curator review (see docs/review/findings.csv R1-ACT-06).
    - `taxonomic_support_n`: how many of the term's proteins have a known
      organism. The axis is derived from those and nothing else, so 63 of the 177
      terms rest on two proteins or fewer and 42 on a single one. Serve it next
      to the scope or the scope reads as a claim about the organelle when it is a
      statement about this dataset's annotations: `aggresome` is `Bacteria` here
      because its six annotated proteins are all E. coli.
    """
    spatial_location_evidence: str | None = None
    taxonomic_support_n: int | None = None


# ── /proteins (list) ─────────────────────────────────────────────────────────

class ProteinSummary(BaseModel):
    uniprot_id: str
    gene_name: str | None = None
    protein_name: str | None = None
    organism: str | None = None
    sequence_length: int | None = None
    disorder_mobidb_lite_dc: float | None = None
    disorder_alphafold_dc: float | None = None
    reviewed: int | None = None
    idr_regions: dict | None = None
    lcr_regions: dict | None = None
    domains: dict | None = None
    has_driver: bool = False
    has_client: bool = False
    has_regulator: bool = False
    source_db_count: int = 0
    source_dbs: list[str] = []
    mlo_count: int = 0
    mlos: list[str] = []
    match_field: str | None = None


class SearchFacets(BaseModel):
    by_organism: dict[str, int] = {}
    by_role: dict[str, int] = {}
    by_mlo: dict[str, int] = {}


class ProteinsResponse(BaseModel):
    total: int
    page: int
    per_page: int
    filters_applied: dict[str, Any]
    facets: SearchFacets | None = None
    proteins: list[ProteinSummary]


# ── /protein/{id} ────────────────────────────────────────────────────────────

class MloAnnotation(MloAxes):
    unified_mlo: str
    source_db: str
    source_mlo: str | None
    # The raw role string the source reported, passed through unmodified (the DB
    # never rewrites it). Added 2026-08-12: with regulator rows now served
    # (R1-ACT-14) and `unified_role` NULL on them, this is the only field that
    # lets a client tell "DrLLPS says this protein regulates the organelle" from
    # "CD-CODE reports membership and no role at all". Deriving it from
    # source_db + a NULL role would work today and would rebuild, client-side,
    # exactly the per-resource inference policy.regulator_annotation_clause()
    # exists to avoid.
    source_role: str | None
    unified_role: str | None
    evidence_pmids: list[str]   # parsed from semicolon-separated evidence field


class IdrRegion(BaseModel):
    start: int
    end: int
    score: float | None
    source: str


class DomainRegion(BaseModel):
    start: int
    end: int
    label: str | None
    accession: str | None
    database: str | None    # source field value (pfam / smart / etc.)


class LcdRegion(BaseModel):
    start: int
    end: int
    label: str | None
    source: str


class MorfRegion(BaseModel):
    start: int
    end: int
    score: float | None
    source: str


class PlddtRegion(BaseModel):
    start: int
    end: int
    mean_score: float | None
    category: str | None    # very_low / low / confident / very_high


class SequenceFeatures(BaseModel):
    idrs: list[IdrRegion]
    domains: list[DomainRegion]
    lcds: list[LcdRegion]
    morfs: list[MorfRegion]
    plddt_regions: list[PlddtRegion]


class PpiInteractionItem(BaseModel):
    partner_uniprot_id: str
    partner_gene: str | None
    in_mlosmetadb: bool
    evidence_types: list[str]
    evidence_count: int
    pubmed_ids: list[str]
    source: str


class PpiInteractions(BaseModel):
    page: int
    per_page: int
    total: int
    items: list[PpiInteractionItem]


class PpiSummary(BaseModel):
    total_partners: int
    partners_in_mlosmetadb: int
    interactions: PpiInteractions | None


class ProteinDetail(BaseModel):
    uniprot_id: str
    gene_name: str | None
    protein_name: str | None
    organism: str | None
    taxon_id: int | None
    sequence_length: int | None
    sequence: str | None
    disorder_mobidb_lite_dc: float | None
    disorder_alphafold_dc: float | None
    mlo_annotations: list[MloAnnotation]
    sequence_features: SequenceFeatures
    ppi: PpiSummary


# ── /protein/{id}/ppi ────────────────────────────────────────────────────────

class PpiPartner(BaseModel):
    partner_uniprot_id: str
    partner_gene: str | None
    has_driver: bool
    has_regulator: bool
    mlos: list[str]
    experimental_systems: list[str]
    evidence_count: int
    pubmed_ids: list[str]


class PpiEdge(BaseModel):
    source: str
    target: str


class PpiAllResponse(BaseModel):
    uniprot_id: str
    total: int           # in-DB partners matching filters
    total_returned: int  # actually returned (may be capped by limit)
    items: list[PpiPartner]
    inter_edges: list[PpiEdge]


# ── /mlo/{id} ────────────────────────────────────────────────────────────────

class MloDefinition(BaseModel):
    source_db: str
    source_name: str | None
    definition: str | None


class MloStats(BaseModel):
    total_proteins: int
    by_source: dict[str, int]
    by_role: dict[str, int]
    organisms: list[str]


class MloProteinItem(BaseModel):
    uniprot_id: str
    gene_name: str | None
    organism: str | None
    unified_role: str | None
    sources: list[str]
    disorder_mobidb_lite_dc: float | None
    disorder_alphafold_dc: float | None
    idr_regions: dict | None
    lcr_regions: dict | None
    domains: dict | None


class MloProteins(BaseModel):
    page: int
    per_page: int
    total: int
    items: list[MloProteinItem]


class MloDetail(MloAxesWithProvenance):
    unified_mlo: str
    definitions: list[MloDefinition]
    stats: MloStats
    proteins: MloProteins


# ── /mlos ────────────────────────────────────────────────────────────────────

class MloListItem(MloAxesWithProvenance):
    unified_mlo: str
    protein_count: int
    driver_count: int = 0
    sources: list[str] = []
    # Names the source databases use for this organelle, excluding the unified
    # name itself. Lets a client match "GW-body" to p_body, or "Dense Fibrillar
    # Component" to nucleolus — 241 such aliases exist across 102 organelles
    # and none of them are findable from the unified name alone.
    source_names: list[str] = []
    definitions: list[MloDefinition] = []


class MlosResponse(BaseModel):
    total: int
    mlos: list[MloListItem]


# ── /search ──────────────────────────────────────────────────────────────────

class SearchMloHit(MloAxes):
    unified_mlo: str
    match_field: str


class SearchResponse(BaseModel):
    query: str
    mode: str
    total_hits: int
    proteins: list[ProteinSummary]
    mlos: list[SearchMloHit]


# ── /stats ───────────────────────────────────────────────────────────────────

class ProteinStats(BaseModel):
    total: int
    by_organism: dict[str, int]
    by_organism_drivers: dict[str, int] = {}
    top_organisms: int
    total_organisms: int = 0
    other_organisms_count: int = 0
    by_component_role: dict[str, int] = {}


class MloAnnotationStats(BaseModel):
    total: int
    unique_mlos: int
    by_source: dict[str, int]
    unique_proteins_by_source: dict[str, int] = {}
    by_role: dict[str, int]


class FeatureStats(BaseModel):
    total: int
    by_type: dict[str, int]
    proteins_with_features: int


class PpiStats(BaseModel):
    total_interactions: int
    proteins_with_ppi: int


class StatsResponse(BaseModel):
    database_version: str
    last_updated: str
    proteins: ProteinStats
    mlo_annotations: MloAnnotationStats
    sequence_features: FeatureStats
    ppi: PpiStats


# ── /organisms/search ────────────────────────────────────────────────────────

class OrganismResult(BaseModel):
    organism: str
    protein_count: int


class OrganismsSearchResponse(BaseModel):
    query: str
    results: list[OrganismResult]


# ── /protein/{id}/orthologs ───────────────────────────────────────────────────

class OrthoFeatureRegion(BaseModel):
    start: int
    end: int
    score: float | None = None
    label: str | None = None
    accession: str | None = None
    source: str | None = None
    metadata: dict | None = None


class OrthoFeatures(BaseModel):
    idrs: list[OrthoFeatureRegion] = []
    lcds: list[OrthoFeatureRegion] = []
    morfs: list[OrthoFeatureRegion] = []
    plddt_regions: list[OrthoFeatureRegion] = []
    domains: list[OrthoFeatureRegion] = []


class OrthologDetail(BaseModel):
    ortholog_id: str
    organism: str
    taxon_id: int | None = None
    og_id: str | None = None
    sources: str | None = None
    in_db: bool
    gene_name: str | None = None
    protein_name: str | None = None
    length: int | None = None
    disorder_mobidb_lite_dc: float | None = None
    disorder_alphafold_dc: float | None = None
    sequence: str | None = None
    features: OrthoFeatures | None = None


class OrthologsResponse(BaseModel):
    uniprot_id: str
    total: int
    organisms: list[str]
    orthologs: list[OrthologDetail]


# ── /proteins/citations ──────────────────────────────────────────────────────

class CitationCheckRequest(BaseModel):
    uniprot_ids: list[str]

    @field_validator("uniprot_ids")
    @classmethod
    def _clean_ids(cls, v: list[str]) -> list[str]:
        cleaned = []
        seen = set()
        for raw in v:
            uid = raw.strip().upper()
            if uid and uid not in seen:
                seen.add(uid)
                cleaned.append(uid)
        if not cleaned:
            raise ValueError("at least one non-empty uniprot_id is required")
        if len(cleaned) > 500:
            raise ValueError("at most 500 uniprot_ids allowed per request")
        return cleaned


class CitationCheckResponse(BaseModel):
    by_source: dict[str, int]
