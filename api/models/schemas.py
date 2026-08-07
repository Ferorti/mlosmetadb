from __future__ import annotations

from typing import Any

from pydantic import BaseModel, field_validator


# ── shared ──────────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    error: str
    message: str


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

class MloAnnotation(BaseModel):
    unified_mlo: str
    category: str | None
    source_db: str
    source_mlo: str | None
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
    pubmed_id: str | None
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


class MloDetail(BaseModel):
    unified_mlo: str
    category: str | None
    definitions: list[MloDefinition]
    stats: MloStats
    proteins: MloProteins


# ── /mlos ────────────────────────────────────────────────────────────────────

class MloListItem(BaseModel):
    unified_mlo: str
    category: str | None
    protein_count: int
    driver_count: int = 0
    sources: list[str] = []
    definitions: list[MloDefinition] = []


class MlosResponse(BaseModel):
    total: int
    mlos: list[MloListItem]


# ── /search ──────────────────────────────────────────────────────────────────

class SearchMloHit(BaseModel):
    unified_mlo: str
    category: str | None
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
