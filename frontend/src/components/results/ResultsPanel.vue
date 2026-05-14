<script setup>
import { ref, computed, reactive, h } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  createColumnHelper,
  getCoreRowModel,
  getSortedRowModel,
  useVueTable,
  FlexRender,
} from '@tanstack/vue-table'
import RoleBadge from '@/components/ui/RoleBadge.vue'
import SequenceFeatureViewer from '@/components/results/SequenceFeatureViewer.vue'
import { formatMlo, formatCount } from '@/utils/format'
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
const viewMode = ref('cards') // 'cards' | 'table'

// Tracks which rows have their MLO list fully expanded
const expandedRows = reactive(new Set())

function visibleMlos(protein) {
  if (!protein.mlos?.length) return []
  if (expandedRows.has(protein.uniprot_id)) return protein.mlos
  return protein.mlos.slice(0, 10)
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

const tableSorting = ref([])

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

// ---- TanStack Table ----
const col = createColumnHelper()

// TODO: server-side sort not yet supported — currently sorts client-side on loaded page only
const columns = [
  col.accessor('uniprot_id',    { header: 'UniProt Acc', enableSorting: true }),
  col.accessor('gene_name',     { header: 'Gene name',   enableSorting: true }),
  col.accessor('organism',      { header: 'Organism',    enableSorting: true,
    cell: info => h('span', { class: 'italic' }, info.getValue()) }),
  col.accessor('has_driver', {
    id: 'role', header: 'Role', enableSorting: false,
    cell: info => info.getValue()
      ? h(RoleBadge, { role: 'driver' })
      : h('span', { class: 'text-gray-400 text-xs' }, '—'),
  }),
  col.accessor(row => row.mlos?.length ?? 0, {
    id: 'mlos', header: 'MLOs', enableSorting: true,
  }),
  col.accessor('sequence_length', { header: 'Length (aa)', enableSorting: true,
    cell: info => info.getValue() ? formatCount(info.getValue()) : '—' }),
]

const tableData = computed(() => props.results ?? [])

const table = useVueTable({
  get data()    { return tableData.value },
  columns,
  state:        { get sorting() { return tableSorting.value } },
  onSortingChange: updater => {
    tableSorting.value = typeof updater === 'function'
      ? updater(tableSorting.value)
      : updater
  },
  getCoreRowModel:    getCoreRowModel(),
  getSortedRowModel:  getSortedRowModel(),
  manualSorting:      false,
})
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
        <!-- Cards / Table toggle -->
        <div class="inline-flex border border-gray-200 rounded overflow-hidden text-xs">
          <button
            :class="viewMode === 'cards' ? 'bg-[#1B3D6F] text-white' : 'bg-white text-gray-500 hover:bg-gray-50'"
            class="px-3 py-1.5 transition-colors"
            @click="viewMode = 'cards'"
          >
            Cards
          </button>
          <button
            :class="viewMode === 'table' ? 'bg-[#1B3D6F] text-white' : 'bg-white text-gray-500 hover:bg-gray-50'"
            class="px-3 py-1.5 border-l border-gray-200 transition-colors"
            @click="viewMode = 'table'"
          >
            Table
          </button>
        </div>

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
        class="inline-flex items-center gap-1 px-2 py-0.5 bg-[#EBF3FB] text-[#185FA5] rounded-full text-xs border border-[#C8DFF2]"
      >
        {{ chip.label }}
        <button
          class="ml-0.5 text-[#185FA5] hover:text-[#0F3D6F] leading-none"
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

      <!-- Card (row) view -->
      <template v-else-if="viewMode === 'cards'">

        <!-- mlo values are raw slugs from the API — formatMlo() is display only -->
        <div
          v-for="{ protein, idrRegions, lcdRegions, domains, featureStats, hasFeatures } in resultsWithFeatures"
          :key="protein.uniprot_id"
          class="py-4 px-6 border-b border-gray-200 hover:bg-slate-50/70 transition-colors last:border-b-0"
        >
          <!-- Two-column layout -->
          <div class="flex gap-8">

            <!-- Column 1: Identity (~150px) -->
            <div class="w-[150px] flex-shrink-0 flex flex-col gap-0.5">
              <!-- Gene name + role badge inline -->
              <div class="flex items-center gap-2 flex-wrap">
                <span
                  class="text-[18px] font-semibold cursor-pointer hover:underline leading-snug"
                  :class="titleColor(protein)"
                  @click.stop="goToProtein(protein.uniprot_id)"
                >
                  {{ protein.gene_name || protein.uniprot_id }}
                </span>
                <RoleBadge v-if="protein.has_driver" role="driver" />
              </div>
              <span class="font-mono text-[12px] text-gray-400 mt-0.5">
                {{ protein.uniprot_id }}
              </span>
              <span class="text-[12px] italic text-[#484E59] mt-0.5">
                {{ shortOrganism(protein.organism) }}
              </span>
            </div>

            <!-- Column 2: Annotations (flex-1) -->
            <div class="flex-1 min-w-0 flex flex-col gap-1.5 justify-center">
              <!-- MLOs row -->
              <div v-if="protein.mlos?.length" class="flex items-baseline gap-2">
                <span class="text-[9px] font-medium text-gray-400 flex-shrink-0 w-14">MLOs</span>
                <div class="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 leading-snug">
                  <template v-for="mlo in visibleMlos(protein)" :key="mlo">
                    <span
                      class="text-[13px] text-gray-700 cursor-pointer hover:underline"
                      @click.stop="applyFilter('mlo', mlo)"
                    >{{ formatMlo(mlo) }}</span>
                  </template>
                  <button
                    v-if="protein.mlos.length > 10 && !expandedRows.has(protein.uniprot_id)"
                    class="text-[12px] text-gray-500 hover:underline"
                    @click.stop="expandedRows.add(protein.uniprot_id)"
                  >+{{ protein.mlos.length - 10 }} more</button>
                </div>
              </div>
              <!-- Sources row -->
              <div v-if="protein.source_dbs?.length" class="flex items-baseline gap-2">
                <span class="text-[9px] font-medium text-gray-400 flex-shrink-0 w-14">Sources</span>
                <span class="text-[11px] text-gray-500">{{ protein.source_dbs.join(' · ') }}</span>
              </div>
              <!-- Features row -->
              <div v-if="featureStats" class="flex items-baseline gap-2">
                <span class="text-[9px] font-medium text-gray-400 flex-shrink-0 w-14">Features</span>
                <span class="text-[12px] text-gray-700">{{ featureStats }}</span>
              </div>
              <!-- Compact D3 track — aligned with value column, max 75% of column width -->
              <div v-if="hasFeatures && protein.sequence_length" class="flex items-center gap-2">
                <span class="flex-shrink-0 w-14"></span>
                <div class="flex-1 min-w-0 max-w-[80%]">
                  <SequenceFeatureViewer
                    :sequence-length="protein.sequence_length"
                    :idr-regions="idrRegions"
                    :lcd-regions="lcdRegions"
                    :domains="domains"
                    :llps-regions="[]"
                    :compact="true"
                  />
                </div>
              </div>
            </div>

          </div><!-- end two columns -->

        </div><!-- end row -->
      </template>

      <!-- Table view -->
      <template v-else>
        <div class="overflow-x-auto -mx-6">
          <table class="w-full text-xs">
            <thead>
              <tr
                v-for="headerGroup in table.getHeaderGroups()"
                :key="headerGroup.id"
              >
                <th
                  v-for="header in headerGroup.headers"
                  :key="header.id"
                  class="text-left px-4 py-2 text-gray-500 font-medium bg-gray-50 border-b border-gray-200 whitespace-nowrap"
                  :class="header.column.getCanSort() ? 'cursor-pointer hover:text-gray-700 select-none' : ''"
                  @click="header.column.getCanSort() && header.column.toggleSorting()"
                >
                  <FlexRender
                    :render="header.column.columnDef.header"
                    :props="header.getContext()"
                  />
                  <span v-if="header.column.getIsSorted() === 'asc'" class="ml-1">↑</span>
                  <span v-else-if="header.column.getIsSorted() === 'desc'" class="ml-1">↓</span>
                  <span v-else-if="header.column.getCanSort()" class="ml-1 text-gray-400">↕</span>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in table.getRowModel().rows"
                :key="row.id"
                class="border-b border-gray-200 hover:bg-slate-50 cursor-pointer transition-colors"
                @click="goToProtein(row.original.uniprot_id)"
              >
                <td
                  v-for="cell in row.getVisibleCells()"
                  :key="cell.id"
                  class="px-4 py-2 text-gray-700"
                >
                  <FlexRender
                    :render="cell.column.columnDef.cell"
                    :props="cell.getContext()"
                  />
                </td>
              </tr>
            </tbody>
          </table>
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
              ? 'bg-[#1B3D6F] text-white border-[#1B3D6F]'
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
