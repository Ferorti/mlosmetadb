export const MLOSMETADB_CITATION = {
  authors: 'Ortí F, Fernández ML, Marino-Buslje C.',
  title: 'MLOsMetaDB, a meta-database to centralize the information on liquid-liquid phase separation proteins and membraneless organelles.',
  journal: 'Protein Science.',
  year: '2024;33(1):e4858.',
  url: 'https://doi.org/10.1002/pro.4858',
}

export const RELATED_PUBLICATION_CITATION = {
  authors: 'Ortí F, Navarro AM, Rabinovich A, Wodak SJ, Marino-Buslje C.',
  title: 'Insight into membraneless organelles and their associated proteins: Drivers, Clients and Regulators.',
  journal: 'Computational and Structural Biotechnology Journal.',
  year: '2021;19:3964–3977.',
  url: 'https://doi.org/10.1016/j.csbj.2021.06.042',
}

export const LLPS_SOURCES = [
  {
    key: 'phasepdb',
    name: 'PhaSepDB',
    description: 'PhaSepDB is a manually curated database of proteins associated with liquid–liquid phase separation (LLPS), the process underlying the formation of membraneless organelles. It compiles thousands of non-redundant proteins from different organelles, drawn from the published literature and other databases, and reports for each a functional summary, supporting references and the sequence features linked to LLPS behaviour.',
    citationText: 'You K, Huang Q, Yu C, Shen B, Sevilla C, Shi M, Hermjakob H, Chen Y, Li T. PhaSepDB: a database of liquid–liquid phase separation related proteins. Nucleic Acids Research. 2020;48(D1):D354–D359.',
    citationUrl: 'https://doi.org/10.1093/nar/gkz847',
    color: { bg: '#EBF3FB', text: '#1B4F8A', border: '#BFDBFE' },
  },
  {
    key: 'drllps',
    name: 'DrLLPS',
    description: 'DrLLPS is an integrative resource for proteins involved in liquid–liquid phase separation in eukaryotes. It distinguishes scaffold proteins that drive LLPS, regulators that modulate it and potential client proteins, organised into dozens of biomolecular condensates, and extends this set to more than 160 eukaryotic species through orthology. For eight model organisms it adds detailed annotation integrated from over a hundred external resources, covering disordered regions, domains, post-translational modifications, interactions, subcellular localisation and structures, among others.',
    citationText: 'Ning W, Guo Y, Lin S, Mei B, Wu Y, Jiang P, Tan X, Zhang W, Chen G, Peng D, Chu L, Xue Y. DrLLPS: a data resource of liquid–liquid phase separation in eukaryotes. Nucleic Acids Research. 2020;48(D1):D288–D295.',
    citationUrl: 'https://doi.org/10.1093/nar/gkz1027',
    color: { bg: '#F1F5F9', text: '#484E59', border: '#CBD5E1' },
  },
  {
    key: 'llpsdb',
    name: 'LLPSDB',
    description: 'LLPSDB is a curated collection of proteins shown to undergo liquid–liquid phase separation in vitro, together with the specific experimental conditions reported for each observation. Entries combine biomolecular information (protein sequence, modifications, associated nucleic acids), phase-behaviour data (buffer and assay conditions, description of the observed behaviour) and additional annotation, making it a reference for relating protein sequence to phase behaviour and for training predictive methods.',
    citationText: 'Li Q, Peng X, Li Y, Tang W, Zhu J, Huang J, Qi Y, Zhang Z. LLPSDB: a database of proteins undergoing liquid–liquid phase separation in vitro. Nucleic Acids Research. 2020;48(D1):D320–D327.',
    citationUrl: 'https://doi.org/10.1093/nar/gkz778',
    color: { bg: '#D1FAE5', text: '#0F6E56', border: '#6EE7B7' },
  },
  {
    key: 'phasepro',
    name: 'PhaSePro',
    description: 'PhaSePro is an open, manually curated database of experimentally validated protein and protein-region drivers of liquid–liquid phase separation. Beyond the curated records, it introduces LLPS-specific controlled vocabularies that standardise how these systems are described, addressing the gap between the rapid growth of experimental reports and the lack of a dedicated, structured resource for computational identification of LLPS drivers.',
    citationText: 'Mészáros B, Erdős G, Szabó B, Schád É, Tantos Á, Abukhairan R, Horváth T, Murvai N, Kovács OP, Kovács M, Tosatto SCE, Tompa P, Dosztányi Z, Pancsa R. PhaSePro: the database of proteins driving liquid–liquid phase separation. Nucleic Acids Research. 2020;48(D1):D360–D367.',
    citationUrl: 'https://doi.org/10.1093/nar/gkz848',
    color: { bg: '#F3E8FF', text: '#6B21A8', border: '#D8B4FE' },
  },
  {
    key: 'cdcode',
    name: 'CD-CODE',
    description: 'CD-CODE (Crowdsourcing Condensate Database and Encyclopedia) is a community-editable platform that integrates interdisciplinary knowledge on the function and composition of biomolecular condensates. It combines a literature-based condensate database, an encyclopedia of relevant scientific terms and a crowdsourcing web application, with the aim of accelerating the discovery and validation of condensates and their study as disease mechanisms and therapeutic targets.',
    citationText: 'Rostam N, Ghosh S, Chow CFW, Hadarovich A, Landerer C, Ghosh R, Moon H, Hersemann L, Mitrea DM, Klein IA, Hyman AA, Toth-Petroczy A. CD-CODE: crowdsourcing condensate database and encyclopedia. Nature Methods. 2023;20(5):673–676.',
    citationUrl: 'https://doi.org/10.1038/s41592-023-01831-0',
    color: { bg: '#FEF3C7', text: '#854F0B', border: '#FAC775' },
  },
]

export const ANNOTATION_SOURCES = [
  {
    key: 'uniprot',
    name: 'UniProt',
    citationText: 'The UniProt Consortium. UniProt: the Universal Protein Knowledgebase in 2025. Nucleic Acids Research. 2025;53(D1):D609–D617.',
    citationUrl: 'https://doi.org/10.1093/nar/gkae1010',
  },
  {
    key: 'interpro',
    name: 'InterPro',
    citationText: 'Blum M, Andreeva A, Florentino LC, Chuguransky SR, Grego T, Hobbs E, Pinto BL, Orr A, Paysan-Lafosse T, Ponamareva I, Salazar GA, Bordin N, Bork P, Bridge A, Colwell L, Gough J, Haft DH, Letunic I, Llinares-López F, Marchler-Bauer A, Meng-Papaxanthos L, Mi H, Natale DA, Orengo CA, Pandurangan AP, Piovesan D, Rivoire C, Sigrist CJA, Thanki N, Thibaud-Nissen F, Thomas PD, Tosatto SCE, Wu CH, Bateman A. InterPro: the protein sequence classification resource in 2025. Nucleic Acids Research. 2025;53(D1):D444–D456.',
    citationUrl: 'https://doi.org/10.1093/nar/gkae1082',
  },
  {
    key: 'mobidb',
    name: 'MobiDB',
    citationText: 'Piovesan D, Del Conte A, Clementel D, Monzon AM, Bevilacqua M, Aspromonte MC, Iserte JA, Orti FE, Marino-Buslje C, Tosatto SCE. MobiDB: 10 years of intrinsically disordered proteins. Nucleic Acids Research. 2023;51(D1):D438–D444.',
    citationUrl: 'https://doi.org/10.1093/nar/gkac1065',
  },
  {
    key: 'biogrid',
    name: 'BioGRID',
    citationText: 'Oughtred R, Rust J, Chang C, Breitkreutz BJ, Stark C, Willems A, Boucher L, Leung G, Kolas N, Zhang F, Dolma S, Coulombe-Huntington J, Chatr-aryamontri A, Dolinski K, Tyers M. The BioGRID database: A comprehensive biomedical resource of curated protein, genetic, and chemical interactions. Protein Science. 2021;30(1):187–200.',
    citationUrl: 'https://doi.org/10.1002/pro.3978',
  },
  {
    key: 'oma',
    name: 'OMA (Orthologous MAtrix)',
    citationText: 'Altenhoff AM, Warwick Vesztrocy A, Bernard C, Train CM, Nicheperovich A, Prieto Baños S, Julca I, Moi D, Nevers Y, Majidian S, Dessimoz C, Glover NM. OMA orthology in 2024: improved prokaryote coverage, ancestral and extant GO enrichment, a revamped synteny viewer and more in the OMA Ecosystem. Nucleic Acids Research. 2024;52(D1):D513–D521.',
    citationUrl: 'https://doi.org/10.1093/nar/gkad1020',
  },
]
