<script setup>
import { computed, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { formatMlo, formatCount, filterMlos } from '@/utils/format'
import { parseIdrRegions, parseLcdRegions, parseDomains, buildFeatureStats } from '@/utils/parseFeatures'

const props = defineProps({
  results:         { type: Array,   default: null },
  total:           { type: Number,  default: 0 },
  page:            { type: Number,  default: 1 },
  perPage:         { type: Number,  default: 25 },
  loading:         { type: Boolean, default: false },
  query:           { type: String,  default: '' },
  activeFilters:   { type: Object,  default: () => ({}) },
  error:           { type: String,  default: null },
  downloadLoading: { type: Boolean, default: false },
})

const emit = defineEmits(['page-change', 'per-page-change', 'sort-change', 'download'])

const route  = useRoute()
const router = useRouter()

// 'NotInformed' should only surface as "No MLO associated" when the protein has
// no other MLO in this scope — see filterMlos() in utils/format.js.
function displayMlos(protein) {
  return filterMlos(protein.mlos)
}

// Tracks which rows have their MLO list fully expanded (beyond the first 10)
const expandedRows = reactive(new Set())

function visibleMlos(protein) {
  const mlos = displayMlos(protein)
  if (expandedRows.has(protein.uniprot_id)) return mlos
  return mlos.slice(0, 10)
}

// Tracks which rows have the MLO sub-row open at all -- hidden by default,
// toggled by clicking the MLOS count.
const openMlos = reactive(new Set())

function toggleMlos(uniprotId) {
  if (openMlos.has(uniprotId)) openMlos.delete(uniprotId)
  else openMlos.add(uniprotId)
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
    // LCD omitted here on purpose: the results row only shows IDRs and domains.
    const featureStats = buildFeatureStats({ idrRegions, lcdRegions: [], domains, sequenceLength: p.sequence_length })
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

function onPerPageSelect(event) {
  emit('per-page-change', Number(event.target.value))
}

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
  if (protein.has_driver) return 'text-brand'
  return 'text-[#4B5563]'
}

function shortOrganism(name) {
  if (!name) return ''
  const words = name.split(' ')
  return words.length > 2 ? words.slice(0, 2).join(' ') : name
}

// ---- Architecture bands (shared max-length scale across all rows) ----
const SOURCE_ORDER = ['CDCODE', 'DrLLPS', 'LLPSDB', 'PhasePro', 'PhaSepDB']

// Only the sources that actually annotate this protein, in the canonical
// display order -- not all 5 with an on/off state.
function sourceNames(protein) {
  const dbs = protein.source_dbs ?? []
  return SOURCE_ORDER.filter(src => dbs.includes(src))
}

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
  const idr = entry.idrRegions.map(r => band(r.start, r.end, '#DD9088', 'IDR'))
  const dom = entry.domains.map(r => band(r.start, r.end, '#519185', 'Domain'))
  return [...idr, ...dom]
}
</script>

<template>
  <div class="flex-1 flex flex-col min-w-0 overflow-y-auto bg-white">

    <!-- Results header bar: browsing text, per-page, pagination, sort, download -- all one line -->
    <div class="border-b border-gray-200 px-6 py-3 flex items-center justify-between gap-4 flex-shrink-0">
      <div class="flex-shrink-0">
        <span class="text-xs text-gray-500">
          <template v-if="query">
            Results for <span class="font-medium text-gray-700">"{{ query }}"</span> —
          </template>
          <template v-else-if="total > 0">Browsing</template>
          {{ rangeStart }}–{{ rangeEnd }} of {{ total.toLocaleString() }} proteins
        </span>
      </div>

      <div class="flex items-center gap-2 flex-shrink-0">
        <!-- Per-page -->
        <select
          :value="perPage"
          class="h-7 text-xs border border-gray-200 rounded px-2 text-gray-600 bg-white focus:outline-none"
          @change="onPerPageSelect"
        >
          <option :value="10">10</option>
          <option :value="25">25</option>
          <option :value="50">50</option>
          <option :value="100">100</option>
        </select>

        <!-- Pagination -->
        <div v-if="results && results.length > 0 && totalPages > 1" class="flex items-center gap-1">
          <button
            class="h-7 px-2 text-xs rounded border border-gray-200 text-gray-500 hover:border-gray-400 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            :disabled="page <= 1"
            @click="emit('page-change', page - 1)"
          >
            ← Prev
          </button>

          <template v-for="p in pageRange()" :key="p">
            <span v-if="p === '...'" class="px-1 text-xs text-gray-400">…</span>
            <button
              v-else
              class="w-7 h-7 flex-shrink-0 text-xs rounded border transition-colors"
              :class="p === page
                ? 'bg-gray-200 text-gray-800 border-gray-300 font-medium'
                : 'border-gray-200 text-gray-600 hover:border-gray-400'"
              @click="emit('page-change', p)"
            >
              {{ p }}
            </button>
          </template>

          <button
            class="h-7 px-2 text-xs rounded border border-gray-200 text-gray-500 hover:border-gray-400 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            :disabled="page >= totalPages"
            @click="emit('page-change', page + 1)"
          >
            Next →
          </button>
        </div>

        <!-- Sort -->
        <select
          :value="currentSort"
          class="h-7 text-xs border border-gray-200 rounded px-2 text-gray-600 bg-white focus:outline-none"
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
          class="h-7 text-xs border border-gray-200 rounded px-2 transition-colors"
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
                <th class="text-left pl-6 pr-3 pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 tracking-[0.07em] w-[300px]">PROTEIN</th>
                <th class="text-left px-3 pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 tracking-[0.07em] w-[82px]">ROLE</th>
                <th class="text-left px-3 pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 tracking-[0.07em] w-[90px]">SOURCES</th>
                <th class="text-right px-3 pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 tracking-[0.07em] w-[58px]">LENGTH</th>
                <th class="text-right px-3 pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 tracking-[0.07em] w-[52px]">MLOS</th>
                <th class="text-left pl-3 pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 tracking-[0.07em] min-w-[210px]">ARCHITECTURE</th>
              </tr>
            </thead>
            <tbody v-for="entry in resultsWithFeatures" :key="entry.protein.uniprot_id" class="group">
              <tr
                class="group-hover:bg-page cursor-pointer transition-colors"
                :class="openMlos.has(entry.protein.uniprot_id) ? 'border-b-0' : 'border-b border-border-soft'"
                @click="goToProtein(entry.protein.uniprot_id)"
              >
                <td class="align-top pl-6 pr-3 py-3.5">
                  <div class="flex items-baseline gap-2">
                    <span class="text-[15px] font-semibold tracking-[-0.01em]" :class="titleColor(entry.protein)">
                      {{ entry.protein.gene_name || entry.protein.uniprot_id }}
                    </span>
                    <span class="font-mono text-[11.5px] text-ink3">{{ entry.protein.uniprot_id }}</span>
                  </div>
                  <div class="text-[13px] text-ink2 mt-0.5">{{ entry.protein.protein_name }}</div>
                  <div class="text-[12.5px] italic text-muted mt-0.5">{{ shortOrganism(entry.protein.organism) }}</div>
                </td>
                <td
                  class="align-top px-3 py-3.5 font-mono text-[11px]"
                  :class="entry.protein.has_driver ? 'text-brand' : entry.protein.has_regulator ? 'text-regulator' : 'text-ink3'"
                  :title="!entry.protein.has_driver && entry.protein.has_regulator ? 'Annotated as a regulator of this organelle, not as a resident of it — a curator assignment that applies to the whole protein, not to this compartment specifically' : undefined"
                >
                  {{ [entry.protein.has_driver && 'Driver', entry.protein.has_regulator && 'Regulator'].filter(Boolean).join(' · ') || 'Component' }}
                </td>
                <td class="align-top px-3 py-3.5">
                  <div class="flex flex-col gap-0.5">
                    <span v-for="src in sourceNames(entry.protein)" :key="src" class="font-mono text-[10.5px] text-ink3 whitespace-nowrap">{{ src }}</span>
                  </div>
                </td>
                <td class="align-top px-3 py-3.5 text-right font-mono text-xs text-ink">{{ formatCount(entry.protein.sequence_length) }}</td>
                <td class="align-top px-3 py-3.5 text-right">
                  <button
                    v-if="displayMlos(entry.protein).length"
                    class="font-mono text-xs text-ink hover:text-brand inline-flex items-center gap-1"
                    :title="openMlos.has(entry.protein.uniprot_id) ? 'Hide MLOs' : 'Show MLOs'"
                    @click.stop="toggleMlos(entry.protein.uniprot_id)"
                  >
                    {{ displayMlos(entry.protein).length }}
                    <span class="text-[9px] text-ink3">{{ openMlos.has(entry.protein.uniprot_id) ? '▾' : '▸' }}</span>
                  </button>
                  <span v-else class="font-mono text-xs text-ink3">0</span>
                </td>
                <td class="align-top pl-3 py-3.5">
                  <div class="relative h-3 bg-track rounded-[1px] w-[95%]">
                    <div v-for="b in architectureBands(entry)" :key="b.key" :title="b.title" :style="b.style"></div>
                  </div>
                  <div v-if="entry.featureStatsShort" class="font-mono text-[10.5px] text-ink3 mt-1.5">{{ entry.featureStatsShort }}</div>
                </td>
              </tr>
              <!-- MLO sub-row: hidden by default, opened by clicking the MLOS count above.
                   Same tbody + group-hover as the row above, so the two are one
                   clickable/hoverable unit -- the split into two <tr>s is a layout device only. -->
              <tr
                v-if="openMlos.has(entry.protein.uniprot_id) && displayMlos(entry.protein).length"
                class="border-b border-border-soft group-hover:bg-page cursor-pointer transition-colors"
                @click="goToProtein(entry.protein.uniprot_id)"
              >
                <td colspan="6" class="px-3 pb-3.5 pt-0 text-[12.5px] text-ink3">
                  {{ visibleMlos(entry.protein).map(formatMlo).join(' · ') }}
                  <button
                    v-if="displayMlos(entry.protein).length > 10 && !expandedRows.has(entry.protein.uniprot_id)"
                    class="text-muted hover:underline"
                    @click.stop="expandedRows.add(entry.protein.uniprot_id)"
                  >+{{ displayMlos(entry.protein).length - 10 }} more</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="flex flex-wrap gap-6 mt-6 pt-4 border-t border-border-soft font-mono text-[11px] text-ink2">
          <div class="flex items-center gap-2"><span class="w-[9px] h-[9px] bg-feature-idr"></span>Disordered region</div>
          <div class="flex items-center gap-2"><span class="w-[9px] h-[9px] bg-feature-domain"></span>Pfam domain</div>
          <div class="text-ink3">Each bar is normalized to its own protein's length</div>
        </div>
      </template>

    </div>

    <!-- Results footer bar: exact copy of the header bar, so paging doesn't require scrolling back up -->
    <div
      v-if="results && results.length > 0"
      class="border-t border-gray-200 px-6 py-3 flex items-center justify-between gap-4 flex-shrink-0"
    >
      <div class="flex-shrink-0">
        <span class="text-xs text-gray-500">
          <template v-if="query">
            Results for <span class="font-medium text-gray-700">"{{ query }}"</span> —
          </template>
          <template v-else-if="total > 0">Browsing</template>
          {{ rangeStart }}–{{ rangeEnd }} of {{ total.toLocaleString() }} proteins
        </span>
      </div>

      <div class="flex items-center gap-2 flex-shrink-0">
        <!-- Per-page -->
        <select
          :value="perPage"
          class="h-7 text-xs border border-gray-200 rounded px-2 text-gray-600 bg-white focus:outline-none"
          @change="onPerPageSelect"
        >
          <option :value="10">10</option>
          <option :value="25">25</option>
          <option :value="50">50</option>
          <option :value="100">100</option>
        </select>

        <!-- Pagination -->
        <div v-if="totalPages > 1" class="flex items-center gap-1">
          <button
            class="h-7 px-2 text-xs rounded border border-gray-200 text-gray-500 hover:border-gray-400 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            :disabled="page <= 1"
            @click="emit('page-change', page - 1)"
          >
            ← Prev
          </button>

          <template v-for="p in pageRange()" :key="p">
            <span v-if="p === '...'" class="px-1 text-xs text-gray-400">…</span>
            <button
              v-else
              class="w-7 h-7 flex-shrink-0 text-xs rounded border transition-colors"
              :class="p === page
                ? 'bg-gray-200 text-gray-800 border-gray-300 font-medium'
                : 'border-gray-200 text-gray-600 hover:border-gray-400'"
              @click="emit('page-change', p)"
            >
              {{ p }}
            </button>
          </template>

          <button
            class="h-7 px-2 text-xs rounded border border-gray-200 text-gray-500 hover:border-gray-400 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            :disabled="page >= totalPages"
            @click="emit('page-change', page + 1)"
          >
            Next →
          </button>
        </div>

        <!-- Sort -->
        <select
          :value="currentSort"
          class="h-7 text-xs border border-gray-200 rounded px-2 text-gray-600 bg-white focus:outline-none"
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
          class="h-7 text-xs border border-gray-200 rounded px-2 transition-colors"
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

  </div>
</template>
