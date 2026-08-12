<script setup>
// Shown to readers as the public base of the API. Hardcoded on purpose: it has
// to name the production URL even when the page is opened from localhost.
const BASE_URL = 'https://mlos.leloir.org.ar/api'

// Where *this* deployment's API actually lives, for links that must resolve.
// '/api/' at the root, '/v2/api/' for a sub-path build.
const apiBase = `${import.meta.env.BASE_URL}api/`

const ENDPOINTS = [
  { method: 'GET', path: '/protein/{uniprot_id}', purpose: 'Full protein record: metadata, MLO annotations, sequence features, PPI summary' },
  { method: 'GET', path: '/protein/{uniprot_id}/ppi', purpose: 'Full PPI partner list for one protein, with optional role/mlo filters and inter-partner edges' },
  { method: 'GET', path: '/protein/{uniprot_id}/orthologs', purpose: 'OMA-derived orthologs across the 9 target organisms' },
  { method: 'GET', path: '/proteins', purpose: 'Paginated protein list with filters (organism, taxon_id, mlo, role, source_db, uniprot_id) + facets' },
  { method: 'GET', path: '/proteins/export', purpose: 'Unpaginated bulk export (TSV or JSON, capped at 50,000 rows) with organism/taxon_id/mlo/role/multi-value source_db filters and fields=basic|full column selection' },
  { method: 'GET', path: '/mlo/{unified_mlo}', purpose: 'One MLO\'s definitions (per source), aggregate stats (by_role splits driver / regulator / component) and paginated protein list' },
  { method: 'GET', path: '/mlos', purpose: 'Full canonical MLO vocabulary (no pagination), filterable by any of the four classification axes: spatial_location, taxonomic_scope, physiological_state, cell_type_context' },
  { method: 'GET', path: '/search', purpose: 'Basic search over gene names / UniProt IDs / protein names / MLO names' },
  { method: 'GET', path: '/search/advanced', purpose: 'Multi-filter search (gene, organism, taxon, mlo, role, source_db, sequence-feature filters)' },
  { method: 'GET', path: '/stats', purpose: 'Global counts — proteins, mlo_annotations, sequence_features, ppi' },
  { method: 'GET', path: '/organisms/search', purpose: 'Organism-name autocomplete (min 3 chars)' },
  { method: 'POST', path: '/proteins/citations', purpose: 'Given a list of UniProt IDs, return which source databases contributed annotations for them' },
]

// The four orthogonal axes that classify every canonical organelle. They replaced
// a single `category` field, whose values mixed places with lineages, cell types
// and processes — so no one of those could be queried on its own.
const AXES = [
  {
    field: 'spatial_location',
    values: 'cytoplasm · nucleus · plasma_membrane · cytoskeleton · extracellular · mitochondrion · plastid · nucleus_and_cytoplasm · in_vitro · unspecified',
    meaning: 'Where the organelle is. Populated for every term.',
  },
  {
    field: 'taxonomic_scope',
    values: 'Metazoa · Fungi · Bacteria · Viridiplantae · Protista · Virus, or pan_X+Y when no kingdom covers 80% of the term\'s proteins',
    meaning: 'Derived from the organisms of the annotated proteins, so it describes this dataset rather than the organelle concept. Read it together with taxonomic_support_n, the number of proteins behind it: 63 of the 177 terms rest on two or fewer. null where no annotated protein has a known organism.',
  },
  {
    field: 'physiological_state',
    values: 'constitutive · stress_induced · infection · pathological · in_vitro',
    meaning: 'The condition under which the organelle exists. Populated for every term.',
  },
  {
    field: 'cell_type_context',
    values: 'germline · neuron · mast_cell · t_cell · muscle · erythroid · fibroblast · podocyte · hair_cell · silk_gland · chromaffin_cell',
    meaning: 'null for 143 of the 177 terms by design — the axis applies only where the cell type is part of the organelle\'s definition.',
  },
  {
    field: 'spatial_location_evidence',
    values: 'from_category · hand_assigned',
    meaning: 'How the location was determined: derived from the previous curated classification (121 terms), or assigned from the organelle\'s biology by the external biological audit and pending curator review (56).',
  },
]

// Served on /mlos and /mlo/{unified_mlo}. The first four also travel with every
// mlo_annotations[] entry of /protein/{uniprot_id}.
const ROLE_VALUES = [
  {
    value: '"driver"',
    meaning: 'Direct experimental evidence that the protein drives phase separation or organelle formation. From a driver/scaffold annotation in at least one source.',
  },
  {
    value: '"client"',
    meaning: 'Annotated presence in or association with the organelle, with no evidence of driving phase separation.',
  },
  {
    value: 'null',
    meaning: 'No driver/client verdict in the sources. Two different situations share this value, and source_role tells them apart: CD-CODE reports membership without any role data, while a DrLLPS source_role of "Regulator" is a curator\'s claim that the protein modulates the organelle rather than residing in it. A regulator label applies to the whole protein, not to one compartment.',
  },
]

const ERROR_CODES = [
  { situation: 'Protein not in proteins', http: 404, error: 'protein_not_found' },
  { situation: 'MLO not in mlo_vocabulary', http: 404, error: 'mlo_not_found' },
  { situation: 'Invalid query parameter (bad sort_by, bad sort_order, etc.)', http: 422, error: 'invalid_parameter' },
  { situation: 'q shorter than the endpoint\'s minimum length', http: 422, error: 'invalid_parameter' },
  { situation: 'No filters given to /search/advanced', http: 422, error: 'no_filters_provided' },
  { situation: 'mode=exact requested but FTS5 unavailable', http: 501, error: 'fts5_unavailable' },
  { situation: 'Any database error', http: 500, error: 'database_error' },
]

const CURL_EXAMPLE = `curl "${BASE_URL}/protein/A1ZBW4"`

const RESPONSE_EXAMPLE = `{
  "uniprot_id": "A1ZBW4",
  "gene_name": "HnRNP-K",
  "protein_name": null,
  "organism": "Drosophila melanogaster",
  "taxon_id": 7227,
  "sequence_length": 315,
  "disorder_mobidb_lite_dc": 0.502,
  "disorder_alphafold_dc": null,
  "mlo_annotations": [
    {
      "unified_mlo": "in_vitro_droplet",
      "spatial_location": "in_vitro",
      "taxonomic_scope": "pan_Metazoa",
      "physiological_state": "in_vitro",
      "cell_type_context": null,
      "source_db": "LLPSDB",
      "source_mlo": "in vitro droplet",
      "source_role": "driver",
      "unified_role": "driver",
      "evidence_pmids": ["32302572"]
    }
  ],
  "sequence_features": {
    "idrs": [
      { "start": 1, "end": 69, "score": null, "source": "MobiDB-lite" }
      // ... more IDR regions
    ],
    "domains": [
      { "start": 245, "end": 308, "label": "KH domain", "accession": "PF00013", "database": "pfam" }
    ],
    "lcds": [ /* ... */ ],
    "morfs": [],
    "plddt_regions": []
  },
  "ppi": {
    "total_partners": 0,
    "partners_in_mlosmetadb": 0,
    "interactions": null
  }
}`

const ERROR_EXAMPLE = `{ "error": "protein_not_found", "message": "No protein with UniProt ID 'Q92520'" }`
</script>

<template>
  <div class="max-w-6xl mx-auto px-6 py-8">
    <!-- Page header -->
    <div class="mb-6">
      <h1 class="text-2xl font-semibold text-gray-800">API</h1>
      <p class="text-sm text-gray-600 mt-1">
        MLOsMetaDB's REST API is public and read-only — no API key required, no rate
        limit enforced today.
      </p>
    </div>

    <!-- Base URL -->
    <section class="mb-8">
      <h2 class="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-2">Base URL</h2>
      <code class="block bg-gray-900 text-gray-100 text-sm rounded px-4 py-2 font-mono">{{ BASE_URL }}</code>
    </section>

    <!-- Endpoint table -->
    <section class="mb-8">
      <h2 class="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-2">Endpoints</h2>
      <div class="overflow-x-auto border border-gray-200 rounded-lg">
        <table class="w-full text-sm">
          <thead class="bg-gray-50 text-left text-gray-600">
            <tr>
              <th class="px-4 py-2 font-medium">Method</th>
              <th class="px-4 py-2 font-medium">Path</th>
              <th class="px-4 py-2 font-medium">Purpose</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="ep in ENDPOINTS" :key="ep.path" class="border-t border-gray-100">
              <td class="px-4 py-2 font-mono text-[#185FA5]">{{ ep.method }}</td>
              <td class="px-4 py-2 font-mono text-gray-800">{{ ep.path }}</td>
              <td class="px-4 py-2 text-gray-600">{{ ep.purpose }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Classification axes -->
    <section class="mb-8">
      <h2 class="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-2">Organelle classification</h2>
      <p class="text-sm text-gray-600 mb-2">
        Every canonical organelle is classified along four orthogonal axes, served by
        <code class="font-mono text-xs">/mlos</code> and <code class="font-mono text-xs">/mlo/{unified_mlo}</code>
        and accepted as filters by the former — they conjoin, so
        <code class="font-mono text-xs">?spatial_location=nucleus&amp;physiological_state=stress_induced</code>
        returns the nuclear stress-induced ones.
      </p>
      <div class="overflow-x-auto border border-gray-200 rounded-lg">
        <table class="w-full text-sm">
          <thead class="bg-gray-50 text-left text-gray-600">
            <tr>
              <th class="px-4 py-2 font-medium">Field</th>
              <th class="px-4 py-2 font-medium">Values</th>
              <th class="px-4 py-2 font-medium">Notes</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="axis in AXES" :key="axis.field" class="border-t border-gray-100 align-top">
              <td class="px-4 py-2 font-mono text-gray-800 whitespace-nowrap">{{ axis.field }}</td>
              <td class="px-4 py-2 font-mono text-xs text-gray-600">{{ axis.values }}</td>
              <td class="px-4 py-2 text-gray-600">{{ axis.meaning }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Role vocabulary -->
    <section class="mb-8">
      <h2 class="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-2">Role values</h2>
      <p class="text-sm text-gray-600 mb-2">
        <code class="font-mono text-xs">unified_role</code> is one of three values on every annotation, and
        <code class="font-mono text-xs">source_role</code> carries the raw string the source database used,
        unmodified.
      </p>
      <div class="overflow-x-auto border border-gray-200 rounded-lg">
        <table class="w-full text-sm">
          <thead class="bg-gray-50 text-left text-gray-600">
            <tr>
              <th class="px-4 py-2 font-medium">unified_role</th>
              <th class="px-4 py-2 font-medium">Meaning</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="role in ROLE_VALUES" :key="role.value" class="border-t border-gray-100 align-top">
              <td class="px-4 py-2 font-mono text-gray-800 whitespace-nowrap">{{ role.value }}</td>
              <td class="px-4 py-2 text-gray-600">{{ role.meaning }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="text-xs text-gray-600 mt-2">
        Aggregates use their own bucket names, which are not role values:
        <code class="font-mono">/mlo/{unified_mlo}</code>'s <code class="font-mono">stats.by_role</code> splits
        <code class="font-mono">driver</code> / <code class="font-mono">regulator</code> / <code class="font-mono">component</code>,
        counting distinct proteins per annotation bucket — a protein one source calls a driver and another calls a
        regulator counts in both, so the buckets do not sum to <code class="font-mono">total_proteins</code>.
      </p>
    </section>

    <!-- Curl example -->
    <section class="mb-8">
      <h2 class="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-2">Example</h2>
      <pre class="bg-gray-900 text-gray-100 text-sm rounded px-4 py-3 overflow-x-auto"><code>{{ CURL_EXAMPLE }}</code></pre>
      <pre class="bg-gray-50 border border-gray-200 text-gray-800 text-xs rounded px-4 py-3 overflow-x-auto mt-2"><code>{{ RESPONSE_EXAMPLE }}</code></pre>
    </section>

    <!-- Error format -->
    <section class="mb-8">
      <h2 class="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-2">Error format</h2>
      <p class="text-sm text-gray-600 mb-2">
        Every error response, regardless of endpoint, has this shape:
      </p>
      <pre class="bg-gray-50 border border-gray-200 text-gray-800 text-xs rounded px-4 py-3 overflow-x-auto"><code>{{ ERROR_EXAMPLE }}</code></pre>
      <div class="overflow-x-auto border border-gray-200 rounded-lg mt-3">
        <table class="w-full text-sm">
          <thead class="bg-gray-50 text-left text-gray-600">
            <tr>
              <th class="px-4 py-2 font-medium">Situation</th>
              <th class="px-4 py-2 font-medium">HTTP</th>
              <th class="px-4 py-2 font-medium">error</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="ec in ERROR_CODES" :key="ec.error + ec.http" class="border-t border-gray-100">
              <td class="px-4 py-2 text-gray-600">{{ ec.situation }}</td>
              <td class="px-4 py-2 font-mono text-gray-800">{{ ec.http }}</td>
              <td class="px-4 py-2 font-mono text-[#185FA5]">{{ ec.error }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Citation -->
    <section class="mb-8">
      <h2 class="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-2">Citation</h2>
      <p class="text-sm text-gray-600">
        If you use this data in derived work, please cite:
      </p>
      <p class="text-sm text-gray-800 mt-1">
        Orti F, Fernández ML, Marino-Buslje C. <em>Protein Science.</em> 2024;33(1):e4858.
        <a href="https://doi.org/10.1002/pro.4858" class="text-[#185FA5] hover:underline" target="_blank" rel="noopener">
          https://doi.org/10.1002/pro.4858
        </a>
      </p>
    </section>

    <!-- Links out -->
    <section class="flex gap-3">
      <a
        :href="`${apiBase}docs`"
        target="_blank"
        rel="noopener"
        class="inline-flex items-center px-4 py-2 rounded bg-[#185FA5] text-white text-sm font-medium hover:bg-[#0F4A87] transition-colors"
      >
        Interactive docs (Swagger) →
      </a>
      <a
        :href="`${apiBase}redoc`"
        target="_blank"
        rel="noopener"
        class="inline-flex items-center px-4 py-2 rounded border border-[#185FA5] text-[#185FA5] text-sm font-medium hover:bg-[#EBF3FB] transition-colors"
      >
        Reference docs (ReDoc) →
      </a>
    </section>
  </div>
</template>
