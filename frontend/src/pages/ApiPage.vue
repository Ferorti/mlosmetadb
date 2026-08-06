<script setup>
const BASE_URL = 'https://mlos.leloir.org.ar/api'

const ENDPOINTS = [
  { method: 'GET', path: '/protein/{uniprot_id}', purpose: 'Full protein record: metadata, MLO annotations, sequence features, PPI summary' },
  { method: 'GET', path: '/protein/{uniprot_id}/ppi', purpose: 'Full PPI partner list for one protein, with optional role/mlo filters and inter-partner edges' },
  { method: 'GET', path: '/protein/{uniprot_id}/orthologs', purpose: 'OMA-derived orthologs across the 9 target organisms' },
  { method: 'GET', path: '/proteins', purpose: 'Paginated protein list with filters (organism, taxon_id, mlo, role, source_db, uniprot_id) + facets' },
  { method: 'GET', path: '/mlo/{unified_mlo}', purpose: 'One MLO's definitions (per source), aggregate stats, and paginated protein list' },
  { method: 'GET', path: '/mlos', purpose: 'Full canonical MLO vocabulary (no pagination)' },
  { method: 'GET', path: '/search', purpose: 'Basic search over gene names / UniProt IDs / protein names / MLO names' },
  { method: 'GET', path: '/search/advanced', purpose: 'Multi-filter search (gene, organism, taxon, mlo, role, source_db, sequence-feature filters)' },
  { method: 'GET', path: '/stats', purpose: 'Global counts — proteins, mlo_annotations, sequence_features, ppi' },
  { method: 'GET', path: '/organisms/search', purpose: 'Organism-name autocomplete (min 3 chars)' },
]

const ERROR_CODES = [
  { situation: 'Protein not in proteins', http: 404, error: 'protein_not_found' },
  { situation: 'MLO not in mlo_vocabulary', http: 404, error: 'mlo_not_found' },
  { situation: 'Invalid query parameter (bad sort_by, bad sort_order, etc.)', http: 422, error: 'invalid_parameter' },
  { situation: 'q shorter than the endpoint's minimum length', http: 422, error: 'invalid_parameter' },
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
      "category": "In vitro",
      "source_db": "LLPSDB",
      "source_mlo": "in vitro droplet",
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
        href="/docs"
        target="_blank"
        rel="noopener"
        class="inline-flex items-center px-4 py-2 rounded bg-[#185FA5] text-white text-sm font-medium hover:bg-[#0F4A87] transition-colors"
      >
        Interactive docs (Swagger) →
      </a>
      <a
        href="/redoc"
        target="_blank"
        rel="noopener"
        class="inline-flex items-center px-4 py-2 rounded border border-[#185FA5] text-[#185FA5] text-sm font-medium hover:bg-[#EBF3FB] transition-colors"
      >
        Reference docs (ReDoc) →
      </a>
    </section>
  </div>
</template>
