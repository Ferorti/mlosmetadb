<script setup>
import { ref, computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { getProteinOrthologs } from '@/api/proteins.js'
import { parseIdrRegions, parseLcdRegions, parseDomains } from '@/utils/parseFeatures.js'
import OrthologTrackViewer from '@/components/protein/OrthologTrackViewer.vue'

const props = defineProps({
  protein: { type: Object, required: true },
})

const loading = ref(false)
const error   = ref(null)
const data    = ref(null)

async function fetchData() {
  loading.value = true
  error.value   = null
  try {
    const res = await getProteinOrthologs(props.protein.uniprot_id)
    data.value = res.data
  } catch {
    error.value = 'Could not load ortholog data.'
  } finally {
    loading.value = false
  }
}

onMounted(fetchData)

// ── Build normalized track objects for OrthologTrackViewer ────────────────────
const tracks = computed(() => {
  if (!data.value) return []
  const result = []

  // Reference protein (the query)
  const sf = props.protein.sequence_features
  if (sf) {
    const refIdrs    = parseIdrRegions(sf?.idr_regions ?? sf?.idrs ?? null).filter(r => r.source === 'MobiDB-lite')
    const refLcds    = parseLcdRegions(sf?.lcr_regions ?? sf?.lcds ?? null).filter(r => r.source === 'MobiDB-lite-sub')
    const refDomains = parseDomains(sf?.domains ?? null)
    const refMorfs   = sf?.morfs ?? []
    result.push({
      id:          props.protein.uniprot_id,
      organism:    props.protein.organism ?? 'Homo sapiens',
      geneLabel:   props.protein.gene_name ?? props.protein.uniprot_id,
      length:      props.protein.sequence_length ?? 0,
      idrs:        refIdrs,
      lcds:        refLcds,
      domains:     refDomains,
      morfs:       refMorfs,
      isReference: true,
    })
  }

  // Orthologs
  for (const o of data.value.orthologs) {
    const feats = o.features ?? {}
    result.push({
      id:          o.ortholog_id,
      organism:    o.organism,
      geneLabel:   o.gene_name ?? o.ortholog_id,
      length:      o.length ?? 0,
      idrs:        (feats.idrs   ?? []).filter(r => !r.source || r.source === 'MobiDB-lite'),
      lcds:        (feats.lcds   ?? []).filter(r => !r.source || r.source === 'MobiDB-lite-sub'),
      domains:     feats.domains ?? [],
      morfs:       feats.morfs   ?? [],
      isReference: false,
    })
  }

  return result
})

// ── Table helpers ─────────────────────────────────────────────────────────────
function fmtPct(val) {
  if (val == null) return '—'
  return (val * 100).toFixed(0) + '%'
}

function idrCount(o) {
  const n = (o.features?.idrs ?? []).filter(r => !r.source || r.source === 'MobiDB-lite').length
  return n || '—'
}

function lcdCount(o) {
  const n = (o.features?.lcds ?? []).filter(r => !r.source || r.source === 'MobiDB-lite-sub').length
  return n || '—'
}

function domainCount(o) {
  if (!o.features?.domains?.length) return '—'
  const unique = new Set(o.features.domains.map(d => d.accession ?? `${d.start}-${d.end}`))
  return unique.size
}

function disorderClass(val) {
  if (val == null) return 'text-[#484E59]'
  return val > 0.3 ? 'text-rose-600 font-medium' : 'text-gray-700'
}
</script>

<template>
  <div>
    <div class="text-lg font-semibold text-gray-800 mb-1">Orthologs</div>

    <div v-if="loading" class="text-sm text-[#484E59] py-6">Loading orthologs…</div>
    <div v-else-if="error" class="text-sm text-[#484E59] py-6">{{ error }}</div>

    <template v-else-if="data">

      <!-- Summary line -->
      <p class="text-xs text-[#484E59] mb-5">
        {{ data.total }} ortholog{{ data.total !== 1 ? 's' : '' }} across
        {{ data.organisms.length }} organism{{ data.organisms.length !== 1 ? 's' : '' }}
        sourced from OMA and OrthoDB.
        Sequences are normalized to the same display width for visual comparison.
      </p>

      <!-- Sequence feature comparison viewer -->
      <div class="mb-8 p-3 bg-white border border-gray-100 rounded-md">
        <div class="text-xs font-medium text-gray-700 mb-3">Sequence feature comparison</div>
        <OrthologTrackViewer :tracks="tracks" />
        <!-- colour legend text -->
        <div class="mt-2 text-[10px] text-[#484E59]">
          Each sequence is scaled to the full width. Hover for position details.
          Only MobiDB-lite IDRs and MobiDB-lite-sub LCDs are shown.
        </div>
      </div>

      <!-- Comparison table -->
      <div class="text-sm font-medium text-gray-700 mb-2">Ortholog details</div>
      <div class="overflow-x-auto rounded-md border border-gray-100">
        <table class="w-full text-xs border-collapse">
          <thead>
            <tr class="bg-gray-50">
              <th class="text-left py-2 px-3 text-[#484E59] font-medium border-b border-gray-200 whitespace-nowrap">Organism</th>
              <th class="text-left py-2 px-3 text-[#484E59] font-medium border-b border-gray-200 whitespace-nowrap">UniProt ID</th>
              <th class="text-left py-2 px-3 text-[#484E59] font-medium border-b border-gray-200">Gene</th>
              <th class="text-right py-2 px-3 text-[#484E59] font-medium border-b border-gray-200 whitespace-nowrap">Length (aa)</th>
              <th class="text-right py-2 px-3 text-[#484E59] font-medium border-b border-gray-200 whitespace-nowrap">
                <span title="MobiDB-lite content fraction">Disorder %</span>
              </th>
              <th class="text-right py-2 px-3 text-[#484E59] font-medium border-b border-gray-200 whitespace-nowrap">
                <span title="MobiDB-lite IDR count">IDRs</span>
              </th>
              <th class="text-right py-2 px-3 text-[#484E59] font-medium border-b border-gray-200 whitespace-nowrap">
                <span title="MobiDB-lite-sub LCD count">LCDs</span>
              </th>
              <th class="text-right py-2 px-3 text-[#484E59] font-medium border-b border-gray-200 whitespace-nowrap">
                <span title="Unique Pfam domains">Domains</span>
              </th>
              <th class="text-left py-2 px-3 text-[#484E59] font-medium border-b border-gray-200">DB</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="o in data.orthologs"
              :key="o.ortholog_id"
              class="border-b border-gray-100 hover:bg-slate-50 transition-colors"
            >
              <!-- Organism -->
              <td class="py-2 px-3 italic text-[#484E59] whitespace-nowrap">{{ o.organism }}</td>

              <!-- UniProt ID — internal link if in DB, external otherwise -->
              <td class="py-2 px-3 font-mono whitespace-nowrap">
                <RouterLink
                  v-if="o.in_db"
                  :to="`/protein/${o.ortholog_id}`"
                  class="text-[#185FA5] hover:underline"
                >{{ o.ortholog_id }}</RouterLink>
                <a
                  v-else
                  :href="`https://www.uniprot.org/uniprotkb/${o.ortholog_id}`"
                  target="_blank" rel="noopener"
                  class="text-[#484E59] hover:text-[#185FA5] hover:underline"
                >{{ o.ortholog_id }}<span class="text-[10px] ml-0.5 opacity-60">↗</span></a>
              </td>

              <!-- Gene name -->
              <td class="py-2 px-3 text-gray-700">{{ o.gene_name ?? '—' }}</td>

              <!-- Length -->
              <td class="py-2 px-3 text-right tabular-nums text-gray-700">
                {{ o.length != null ? o.length.toLocaleString() : '—' }}
              </td>

              <!-- Disorder % -->
              <td class="py-2 px-3 text-right tabular-nums" :class="disorderClass(o.disorder_mobidb_lite_dc)">
                {{ fmtPct(o.disorder_mobidb_lite_dc) }}
              </td>

              <!-- IDR count -->
              <td class="py-2 px-3 text-right tabular-nums text-gray-700">{{ idrCount(o) }}</td>

              <!-- LCD count -->
              <td class="py-2 px-3 text-right tabular-nums text-gray-700">{{ lcdCount(o) }}</td>

              <!-- Domain count -->
              <td class="py-2 px-3 text-right tabular-nums text-gray-700">{{ domainCount(o) }}</td>

              <!-- Source (OMA / OrthoDB) -->
              <td class="py-2 px-3 text-[#484E59]">{{ o.sources ?? '—' }}</td>
            </tr>

            <!-- No orthologs -->
            <tr v-if="!data.orthologs.length">
              <td colspan="9" class="py-4 px-3 text-center text-[#484E59]">No orthologs found.</td>
            </tr>
          </tbody>
        </table>
      </div>

    </template>
  </div>
</template>
