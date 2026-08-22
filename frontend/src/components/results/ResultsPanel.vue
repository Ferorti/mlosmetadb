<script setup>
import { computed, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import SequenceFeatureViewer from '@/components/results/SequenceFeatureViewer.vue'
import { formatMlo, formatCount, filterMlos } from '@/utils/format'
import { parseIdrRegions, parseLcdRegions, parseDomains, buildFeatureStats } from '@/utils/parseFeatures'

const props = defineProps({
  results:         { type: Array,   default: null },
  total:           { type: Number,  default: 0 },
  page:            { type: Number,  default: 1 },
  perPage:         { type: Number,  default: 20 },
  loading:         { type: Boolean, default: false },
  query:           { type: String,  default: '' },
  activeFilters:   { type: Object,  default: () => ({}) },
  error:           { type: String,  default: null },
  downloadLoading: { type: Boolean, default: false },
})

const emit = defineEmits(['page-change', 'sort-change', 'remove-filter', 'download'])

const route  = useRoute()
const router = useRouter()

// Tracks which rows have their MLO list fully expanded
const expandedRows = reactive(new Set())

// 'NotInformed' should only surface as "No MLO associated" when the protein has
// no other MLO in this scope — see filterMlos() in utils/format.js.
function displayMlos(protein) {
  return filterMlos(protein.mlos)
}

function visibleMlos(protein) {
  const mlos = displayMlos(protein)
  if (expandedRows.has(protein.uniprot_id)) return mlos
  return mlos.slice(0, 10)
}

function hasIdr(protein) {
  if (!protein.idr_regions) return false
  try {
    const parsed = typeof protein.idr_regions === 'string'
      ? JSON.parse(protein.idr_regions) : protein.idr_regions
    return Array.isArray(parsed) ? parsed.length > 0 : Object.keys(parsed).length > 0
  } catch { return false }
}

function hasLcd(protein) {
  if (!protein.lcr_regions) return false
  try {
    const parsed = typeof protein.lcr_regions === 'string'
      ? JSON.parse(protein.lcr_regions) : protein.lcr_regions
    return Array.isArray(parsed) ? parsed.length > 0 : Object.keys(parsed).length > 0
  } catch { return false }
}

function uniqueDomains(protein) {
  if (!protein.domains) return []
  try {
    const parsed = typeof protein.domains === 'string'
      ? JSON.parse(protein.domains) : protein.domains
    const allLabels = Object.values(parsed).flat().map(d => d.label).filter(Boolean)
    return [...new Set(allLabels)].slice(0, 4)
  } catch { return [] }
}

function domainExtra(protein) {
  if (!protein.domains) return 0
  try {
    const parsed = typeof protein.domains === 'string'
      ? JSON.parse(protein.domains) : protein.domains
    const allLabels = [...new Set(
      Object.values(parsed).flat().map(d => d.label).filter(Boolean)
    )]
    return Math.max(0, allLabels.length - 4)
  } catch { return 0 }
}

function applyFilter(key, value) {
  router.push({ query: { ...route.query, [key]: value, page: 1 } })
}

// Pre-parse feature data for all results so each card row reads from a Map
const resultsWithFeatures = computed(() => {
  if (!props.results) return []
  return props.results.map(p => {
    const idrRegions   = parseIdrRegions(p.idr_regions)
    const lcdRegions   = parseLcdRegions(p.lcr_regions)
    const domains      = parseDomains(p.domains)
    const featureStats = buildFeatureStats({ idrRegions, lcdRegions, domains, sequenceLength: p.sequence_length })
    // Strip the trailing " · NNN aa" so column 3 can show length separately
    const featureStatsShort = featureStats
      ? featureStats.replace(/\s*·\s*[\d,]+ aa$/, '').trim()
      : ''
    const hasFeatures  = idrRegions.length > 0 || lcdRegions.length > 0 || domains.length > 0 || !!p.sequence_length
    return { protein: p, idrRegions, lcdRegions, domains, featureStats, featureStatsShort, hasFeatures }
  })
})

const currentSort = computed(() => {
  const { sort_by, sort_order } = props.activeFilters
  return `${sort_by || 'mlo_count'}:${sort_order || 'desc'}`
})

function onSortSelect(event) {
  const val = event.target.value
  if (!val) return
  const [sort_by, sort_order] = val.split(':')
  const q = { ...route.query, sort_by, sort_order, page: 1 }
  // Keep URL clean when user picks the default
  if (sort_by === 'mlo_count' && sort_order === 'desc') {
    delete q.sort_by
    delete q.sort_order
  }
  router.push({ query: q })
}

// ---- Active filter chips (exclude q, page, per_page, mode) ----
const SKIP_KEYS = new Set(['page', 'per_page', 'mode', 'sort_by', 'sort_order'])
const ROLE_LABELS = { driver: 'Driver', component: 'MLO component' }

const filterChips = computed(() =>
  Object.entries(props.activeFilters)
    .filter(([k, v]) => !SKIP_KEYS.has(k) && k !== 'q' && v)
    .map(([k, v]) => ({
      key: k,
      label: k === 'role'
        ? `Role: ${ROLE_LABELS[v] ?? v}`
        : `${chipLabel(k)}: ${v}`,
    }))
)

function chipLabel(key) {
  const map = {
    role: 'Role', mlo: 'MLO', organism: 'Organism',
    source_db: 'Source', feature_type: 'Feature', feature_accession: 'Pfam',
    field: 'Field',
  }
  return map[key] ?? key
}

// ---- Pagination ----
const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.perPage)))

function pageRange() {
  const total = totalPages.value
  const cur   = props.page
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)
  const pages = []
  if (cur <= 4) {
    for (let i = 1; i <= 5; i++) pages.push(i)
    pages.push('...', total)
  } else if (cur >= total - 3) {
    pages.push(1, '...')
    for (let i = total - 4; i <= total; i++) pages.push(i)
  } else {
    pages.push(1, '...', cur - 1, cur, cur + 1, '...', total)
  }
  return pages
}

const rangeStart = computed(() => (props.page - 1) * props.perPage + 1)
const rangeEnd   = computed(() => Math.min(props.page * props.perPage, props.total))

// ---- Navigation ----
function goToProtein(id) {
  router.push(`/protein/${id}`)
}

function titleColor(protein) {
  if (protein.has_driver) return 'text-[#185FA5]'
  return 'text-[#4B5563]'
}

function shortOrganism(name) {
  if (!name) return ''
  const words = name.split(' ')
  return words.length > 2 ? words.slice(0, 2).join(' ') : name
}

// ---- Architecture bands (shared max-length scale across all rows) ----
const SOURCE_ORDER = ['CDCODE', 'DrLLPS', 'LLPSDB', 'PhasePro', 'PhaSepDB']

const MAX_LENGTH = computed(() =>
  Math.max(1, ...resultsWithFeatures.value.map(r => r.protein.sequence_length || 0))
)

function architectureBands(entry) {
  const len = entry.protein.sequence_length
  if (!len) return []
  const band = (start, end, color, label) => ({
    key: `${label}-${start}`,
    title: `${label} ${start}–${end}`,
    style: {
      position: 'absolute', top: 0, bottom: 0,
      left:  `${((start - 1) / len) * 100}%`,
      width: `${((end - start + 1) / len) * 100}%`,
      background: color, borderRadius: '1px',
    },
  })
  const idr = entry.idrRegions.map(r => band(r.start, r.end, '#B8362B', 'IDR'))
  const dom = entry.domains.map(r => band(r.start, r.end, '#2C7A6B', 'Domain'))
  return [...idr, ...dom]
}
</script>

<template>
  <div class="flex-1 flex flex-col min-w-0 overflow-y-auto bg-white">

    <!-- Results header bar -->
    <div class="border-b border-gray-200 px-6 py-3 flex items-center justify-between gap-4 flex-shrink-0">
      <div>
        <span class="text-sm text-gray-700">
          <template v-if="query">
            Results for <span class="font-medium">"{{ query }}"</span>
          </template>
          <template v-else-if="total > 0">Browsing proteins</template>
        </span>
        <span v-if="total > 0" class="text-xs text-gray-500 ml-3">
          {{ rangeStart }}–{{ rangeEnd }} of {{ total.toLocaleString() }} proteins
        </span>
      </div>

      <div class="flex items-center gap-2 flex-shrink-0">
        <!-- Sort -->
        <select
          :value="currentSort"
          class="text-xs border border-gray-200 rounded px-2 py-1.5 text-gray-600 focus:outline-none"
          @change="onSortSelect"
        >
          <option value="mlo_count:desc">Most MLOs</option>
          <option value="gene_name:asc">Gene name A→Z</option>
          <option value="gene_name:desc">Gene name Z→A</option>
          <option value="source_db_count:desc">Best supported</option>
          <option value="disorder_mobidb_lite_dc:desc">Highly disordered</option>
          <option value="disorder_mobidb_lite_dc:asc">Least disordered</option>
          <option value="role:asc">Drivers first</option>
        </select>

        <!-- Download -->
        <button
          class="text-xs border border-gray-200 rounded px-2 py-1.5 transition-colors"
          :class="downloadLoading
            ? 'text-gray-400 cursor-not-allowed'
            : 'text-gray-500 hover:border-gray-400'"
          :disabled="downloadLoading"
          @click="emit('download')"
        >
          {{ downloadLoading ? 'Downloading…' : '↓ Download' }}
        </button>
      </div>
    </div>

    <!-- Active filter chips -->
    <div v-if="filterChips.length" class="px-6 py-2 flex flex-wrap gap-1.5 border-b border-gray-100 flex-shrink-0">
      <span
        v-for="chip in filterChips"
        :key="chip.key"
        class="inline-flex items-center gap-1 px-2 py-0.5 bg-[#E8F1FB] text-brand rounded-full text-xs border border-[#BFD7F0]"
      >
        {{ chip.label }}
        <button
          class="ml-0.5 text-brand hover:text-[#0F3D6F] leading-none"
          @click="emit('remove-filter', chip.key)"
        >
          ×
        </button>
      </span>
    </div>

    <!-- Content area -->
    <div class="flex-1 px-6 py-4">

      <!-- Loading skeleton -->
      <template v-if="loading">
        <div v-for="i in 5" :key="i" class="py-3 border-b border-gray-200 last:border-b-0 space-y-2 animate-pulse">
          <div class="flex justify-between">
            <div class="h-3.5 bg-gray-200 rounded w-48"></div>
            <div class="h-3.5 bg-gray-100 rounded w-16"></div>
          </div>
          <div class="h-3 bg-gray-100 rounded w-64"></div>
          <div class="flex gap-1">
            <div v-for="j in 3" :key="j" class="h-4 bg-gray-100 rounded-full w-20"></div>
          </div>
          <div class="h-3 bg-gray-100 rounded w-40"></div>
        </div>
      </template>

      <!-- Error state -->
      <template v-if="error">
        <div class="flex flex-col items-center justify-center py-24 text-center">
          <div class="text-4xl mb-4">⚠️</div>
          <p class="text-sm text-red-600 font-medium">Search error</p>
          <p class="text-xs text-gray-500 mt-1 max-w-xs">{{ error }}</p>
        </div>
      </template>

      <!-- Empty state: no search, no filters -->
      <template v-else-if="results === null && !loading">
        <div class="flex flex-col items-center justify-center py-24 text-center">
          <div class="text-4xl mb-4">🔬</div>
          <p class="text-sm text-gray-500 max-w-xs leading-relaxed">
            Search for proteins by gene name, UniProt accession, or organelle.
          </p>
          <p class="text-xs text-gray-500 mt-1 max-w-xs">
            Use the filters on the left to browse by role, MLO, or organism.
          </p>
        </div>
      </template>

      <!-- No results: filters applied but nothing found -->
      <template v-else-if="results !== null && results.length === 0 && !loading">
        <div class="flex flex-col items-center justify-center py-16 text-center">
          <p class="text-sm text-gray-600">No proteins found matching your search.</p>
          <p class="mt-1 text-xs text-gray-500">Try different search terms or remove some filters.</p>
        </div>
      </template>

      <!-- Results table -->
      <template v-else>
        <div class="overflow-x-auto -mx-6">
          <table class="w-full border-collapse">
            <thead>
              <tr>
                <th class="text-left px-3 pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 tracking-[0.07em]">PROTEIN</th>
                <th class="text-left px-3 pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 tracking-[0.07em] w-[210px]">ARCHITECTURE</th>
                <th class="text-right px-3 pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 tracking-[0.07em] w-[58px]">LENGTH</th>
                <th class="text-right px-3 pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 tracking-[0.07em] w-[52px]">MLOS</th>
                <th class="text-center px-3 pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 tracking-[0.07em] w-[96px]">SOURCES</th>
                <th class="text-right pl-3 pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 tracking-[0.07em] w-[82px]">ROLE</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="entry in resultsWithFeatures"
                :key="entry.protein.uniprot_id"
                class="border-b border-border-soft hover:bg-page cursor-pointer transition-colors"
                @click="goToProtein(entry.protein.uniprot_id)"
              >
                <td class="align-top px-3 py-3.5">
                  <div class="flex items-baseline gap-2">
                    <span class="text-[15px] font-semibold tracking-[-0.01em]" :class="titleColor(entry.protein)">
                      {{ entry.protein.gene_name || entry.protein.uniprot_id }}
                    </span>
                    <span class="font-mono text-[11.5px] text-ink3">{{ entry.protein.uniprot_id }}</span>
                  </div>
                  <div class="text-[13px] text-ink2 mt-0.5">{{ entry.protein.protein_name }}</div>
                  <div class="text-[12.5px] italic text-muted mt-0.5">{{ shortOrganism(entry.protein.organism) }}</div>
                  <div v-if="displayMlos(entry.protein).length" class="text-[12.5px] text-ink3 mt-1.5">
                    {{ visibleMlos(entry.protein).map(formatMlo).join(' · ') }}
                    <button
                      v-if="displayMlos(entry.protein).length > 10 && !expandedRows.has(entry.protein.uniprot_id)"
                      class="text-muted hover:underline"
                      @click.stop="expandedRows.add(entry.protein.uniprot_id)"
                    >+{{ displayMlos(entry.protein).length - 10 }} more</button>
                  </div>
                </td>
                <td class="align-top px-3 py-3.5">
                  <div class="relative h-3 bg-track rounded-[1px]" :style="{ width: entry.protein.sequence_length ? (entry.protein.sequence_length / MAX_LENGTH * 100) + '%' : '0%' }">
                    <div v-for="b in architectureBands(entry)" :key="b.key" :title="b.title" :style="b.style"></div>
                  </div>
                  <div v-if="entry.featureStatsShort" class="font-mono text-[10.5px] text-ink3 mt-1.5">{{ entry.featureStatsShort }}</div>
                </td>
                <td class="align-top px-3 py-3.5 text-right font-mono text-xs text-ink">{{ formatCount(entry.protein.sequence_length) }}</td>
                <td class="align-top px-3 py-3.5 text-right font-mono text-xs text-ink">{{ displayMlos(entry.protein).length }}</td>
                <td class="align-top px-3 py-3.5">
                  <div class="flex gap-1.5 justify-center">
                    <span
                      v-for="src in SOURCE_ORDER"
                      :key="src"
                      :title="entry.protein.source_dbs?.includes(src) ? src : `${src}: not annotated`"
                      class="inline-block"
                      :class="entry.protein.source_dbs?.includes(src) ? 'w-[7px] h-[7px] rounded-full bg-ink' : 'w-[7px] h-px bg-border-strong mt-[3px]'"
                    ></span>
                  </div>
                </td>
                <td class="align-top pl-3 py-3.5 text-right font-mono text-[11px]" :class="entry.protein.has_driver ? 'text-brand' : 'text-ink3'">
                  {{ entry.protein.has_driver ? 'Driver' : 'Component' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="flex flex-wrap gap-6 mt-6 pt-4 border-t border-border-soft font-mono text-[11px] text-ink2">
          <div class="flex items-center gap-2"><span class="w-[9px] h-[9px] bg-feature-idr"></span>Disordered region</div>
          <div class="flex items-center gap-2"><span class="w-[9px] h-[9px] bg-feature-domain"></span>Pfam domain</div>
          <div class="flex items-center gap-2"><span class="w-[9px] h-[9px] rounded-full bg-ink"></span>Annotated in source</div>
          <div class="text-ink3">Bars share one scale · widest = {{ formatCount(MAX_LENGTH) }} aa · source order {{ SOURCE_ORDER.join(' · ') }}</div>
        </div>
      </template>

    </div>

    <!-- Pagination -->
    <div
      v-if="results?.length && total > perPage"
      class="border-t border-gray-200 px-6 py-3 flex items-center justify-between flex-shrink-0"
    >
      <span class="text-xs text-gray-500">
        Showing {{ rangeStart }}–{{ rangeEnd }} of {{ total.toLocaleString() }} proteins
      </span>

      <div class="flex items-center gap-1">
        <button
          class="px-2 py-1 text-xs rounded border border-gray-200 text-gray-500 hover:border-gray-400 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          :disabled="page <= 1"
          @click="emit('page-change', page - 1)"
        >
          ← Prev
        </button>

        <template v-for="p in pageRange()" :key="p">
          <span v-if="p === '...'" class="px-1 text-xs text-gray-400">…</span>
          <button
            v-else
            class="w-7 h-7 text-xs rounded border transition-colors"
            :class="p === page
              ? 'bg-navy text-white border-navy'
              : 'border-gray-200 text-gray-600 hover:border-gray-400'"
            @click="emit('page-change', p)"
          >
            {{ p }}
          </button>
        </template>

        <button
          class="px-2 py-1 text-xs rounded border border-gray-200 text-gray-500 hover:border-gray-400 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          :disabled="page >= totalPages"
          @click="emit('page-change', page + 1)"
        >
          Next →
        </button>
      </div>
    </div>

  </div>
</template>
