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
  results:       { type: Array,   default: null },
  total:         { type: Number,  default: 0 },
  page:          { type: Number,  default: 1 },
  perPage:       { type: Number,  default: 20 },
  loading:       { type: Boolean, default: false },
  query:         { type: String,  default: '' },
  activeFilters: { type: Object,  default: () => ({}) },
  error:         { type: String,  default: null },
})

const emit = defineEmits(['page-change', 'sort-change', 'remove-filter'])

const route  = useRoute()
const router = useRouter()
const viewMode = ref('cards') // 'cards' | 'table'

// Tracks which rows have their MLO list fully expanded
const expandedRows = reactive(new Set())

function visibleMlos(protein) {
  if (!protein.mlos?.length) return []
  if (expandedRows.has(protein.uniprot_id)) return protein.mlos
  return protein.mlos.slice(0, 5)
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
    const hasFeatures  = idrRegions.length > 0 || lcdRegions.length > 0 || domains.length > 0 || !!p.sequence_length
    return { protein: p, idrRegions, lcdRegions, domains, featureStats, hasFeatures }
  })
})

const sortField   = ref('relevance')
const tableSorting = ref([])

// ---- Active filter chips (exclude q, page, per_page, mode) ----
const SKIP_KEYS = new Set(['page', 'per_page', 'mode'])
const filterChips = computed(() =>
  Object.entries(props.activeFilters)
    .filter(([k, v]) => !SKIP_KEYS.has(k) && k !== 'q' && v)
    .map(([k, v]) => ({ key: k, label: `${chipLabel(k)}: ${v}` }))
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
  if (protein.has_client) return 'text-[#3B6D11]'
  return 'text-[#4B5563]'
}

// ---- TanStack Table ----
const col = createColumnHelper()

// TODO: server-side sort not yet supported — currently sorts client-side on loaded page only
const columns = [
  col.accessor('uniprot_id',    { header: 'UniProt Acc', enableSorting: true }),
  col.accessor('gene_name',     { header: 'Gene name',   enableSorting: true }),
  col.accessor('organism',      { header: 'Organism',    enableSorting: true,
    cell: info => h('span', { class: 'italic' }, info.getValue()) }),
  col.accessor(row => [row.has_driver, row.has_client], {
    id: 'role', header: 'Role', enableSorting: false,
    cell: info => {
      const [d, c] = info.getValue()
      const badges = []
      if (d) badges.push(h(RoleBadge, { role: 'driver', key: 'driver' }))
      if (c && !d) badges.push(h(RoleBadge, { role: 'client', key: 'client' }))
      return h('div', { class: 'flex gap-1 flex-wrap' }, badges)
    },
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
          v-model="sortField"
          class="text-xs border border-gray-200 rounded px-2 py-1.5 text-gray-600 focus:outline-none"
        >
          <option value="relevance">Relevance</option>
          <option value="gene_name">Gene name</option>
          <option value="organism">Organism</option>
          <option value="sequence_length">Length</option>
        </select>

        <!-- Download placeholder -->
        <button class="text-xs text-gray-500 border border-gray-200 rounded px-2 py-1.5 hover:border-gray-400 transition-colors">
          ↓ Download
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

        <!-- Track legend — shown once above the results list -->
        <div class="flex items-center gap-4 text-[10px] text-gray-500 mb-3 mt-1">
          <span class="font-medium">Track:</span>
          <span class="flex items-center gap-1.5">
            <span class="inline-block w-3 h-3 rounded-sm bg-[#e9bdbd]"></span> IDR
          </span>
          <span class="flex items-center gap-1.5">
            <span class="inline-block w-3 h-3 rounded-sm bg-[#86b9eb]"></span> Domain
          </span>
        </div>

        <div
          v-for="{ protein, idrRegions, lcdRegions, domains, featureStats, hasFeatures } in resultsWithFeatures"
          :key="protein.uniprot_id"
          class="py-4 border-b border-gray-200 hover:bg-slate-50 transition-colors last:border-b-0"
        >
          <!-- Line 1: gene name (or uniprot_id) + UniProt accession + role badges -->
          <div class="flex items-start justify-between gap-4">
            <div class="flex items-baseline gap-2 flex-1 min-w-0">
              <span
                :class="['text-[18px] font-semibold hover:underline cursor-pointer leading-snug', titleColor(protein)]"
                @click.stop="goToProtein(protein.uniprot_id)"
              >
                {{ protein.gene_name || protein.uniprot_id }}
              </span>
              <span class="font-mono text-[12px] text-gray-500 flex-shrink-0">
                {{ protein.uniprot_id }}
              </span>
            </div>
            <div class="flex gap-1 flex-shrink-0 mt-1">
              <RoleBadge v-if="protein.has_driver" role="driver" />
              <RoleBadge v-if="protein.has_client && !protein.has_driver" role="client" />
            </div>
          </div>

          <!-- Lines 2–5: indented body -->
          <div class="pl-4">

          <!-- Line 2: organism · reviewed star -->
          <div class="flex items-center gap-2 mt-0.5">
            <span class="text-[13px] italic text-gray-600">{{ protein.organism }}</span>
            <span
              v-if="protein.reviewed === 1"
              title="Reviewed (Swiss-Prot)"
              class="text-amber-400 text-xs"
            >★</span>
          </div>

          <!-- Row: MLOs (plain text, clickable, · separated) -->
          <!-- mlo values are raw slugs from the API — formatMlo() is display only -->
          <div v-if="protein.mlos?.length" class="flex items-baseline gap-2 mt-2.5">
            <span class="text-[11px] text-gray-500 flex-shrink-0"
                  style="width:72px;font-family:'IBM Plex Sans',sans-serif;font-weight:500">
              MLOs
            </span>
            <span class="text-[12px] text-gray-700 leading-relaxed">
              <template v-for="(mlo, i) in visibleMlos(protein)" :key="mlo">
                <span
                  class="hover:text-[#185FA5] cursor-pointer transition-colors"
                  @click.stop="applyFilter('mlo', mlo)"
                >{{ formatMlo(mlo) }}</span>
                <span v-if="i < visibleMlos(protein).length - 1" class="text-gray-400 mx-1">·</span>
              </template>
              <button
                v-if="protein.mlos.length > 5 && !expandedRows.has(protein.uniprot_id)"
                class="text-[#185FA5] hover:underline ml-1 text-[12px] font-medium"
                @click.stop="expandedRows.add(protein.uniprot_id)"
              >+{{ protein.mlos.length - 5 }} more</button>
            </span>
          </div>

          <!-- Row: Source databases -->
          <div v-if="protein.source_dbs?.length" class="flex items-baseline gap-2 mt-1">
            <span class="text-[11px] text-gray-500 flex-shrink-0"
                  style="width: 72px; font-family: 'IBM Plex Sans', sans-serif; font-weight: 500;">
              Source
            </span>
            <span class="text-[12px] text-gray-600">
              {{ protein.source_dbs.join(' · ') }}
            </span>
          </div>

          <!-- Row: Features — inline stats + D3 sequence track -->
          <div v-if="hasFeatures" class="flex items-start gap-2 mt-1">
            <span
              class="text-[11px] text-gray-500 flex-shrink-0 mt-0.5"
              style="width:72px;font-family:'IBM Plex Sans',sans-serif;font-weight:500"
            >
              Features
            </span>
            <div class="flex-1 min-w-0">
              <div class="text-[12px] text-gray-600 mb-1.5">{{ featureStats }}</div>
              <div style="max-width: 65%; margin-left: -8px;">
                <SequenceFeatureViewer
                  v-if="protein.sequence_length"
                  :sequence-length="protein.sequence_length"
                  :idr-regions="idrRegions"
                  :lcd-regions="lcdRegions"
                  :domains="domains"
                  :llps-regions="[]"
                />
              </div>
            </div>
          </div>

          </div><!-- end indented body -->
        </div>
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
