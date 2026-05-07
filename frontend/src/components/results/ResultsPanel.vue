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
import { formatMlo, formatCount } from '@/utils/format'

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
      if (c) badges.push(h(RoleBadge, { role: 'client', key: 'client' }))
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
        <span v-if="total > 0" class="text-xs text-gray-400 ml-3">
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
        <div v-for="i in 5" :key="i" class="py-3 border-b border-gray-100 last:border-b-0 space-y-2 animate-pulse">
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
          <p class="text-xs text-gray-400 mt-1 max-w-xs">{{ error }}</p>
        </div>
      </template>

      <!-- Empty state: no search, no filters -->
      <template v-else-if="results === null">
        <div class="flex flex-col items-center justify-center py-24 text-center">
          <div class="text-4xl mb-4">🔬</div>
          <p class="text-sm text-gray-500 max-w-xs leading-relaxed">
            Search for proteins by gene name, UniProt accession, or organelle.
          </p>
          <p class="text-xs text-gray-400 mt-1 max-w-xs">
            Use the filters on the left to browse by role, MLO, or organism.
          </p>
        </div>
      </template>

      <!-- Empty state: query returned nothing -->
      <template v-else-if="results.length === 0">
        <div class="flex flex-col items-center justify-center py-24 text-center">
          <div class="text-4xl mb-4">😕</div>
          <p class="text-sm text-gray-600">
            No proteins found<template v-if="query"> for <span class="font-medium">"{{ query }}"</span></template>.
          </p>
          <p class="text-xs text-gray-400 mt-1">Try a different search term or remove some filters.</p>
        </div>
      </template>

      <!-- Card (row) view -->
      <template v-else-if="viewMode === 'cards'">
        <div
          v-for="protein in results"
          :key="protein.uniprot_id"
          class="py-4 border-b border-gray-100 cursor-pointer hover:bg-slate-50 transition-colors last:border-b-0"
          @click="goToProtein(protein.uniprot_id)"
        >
          <!-- Line 1: protein name + role badges -->
          <div class="flex items-start justify-between gap-4">
            <span class="text-[16px] font-medium text-[#185FA5] hover:underline leading-snug">
              {{ protein.protein_name || protein.gene_name || protein.uniprot_id }}
            </span>
            <div class="flex gap-1 flex-shrink-0">
              <RoleBadge v-if="protein.has_driver === true" role="driver" />
              <RoleBadge v-if="protein.has_client === true" role="client" />
            </div>
          </div>

          <!-- Line 2: UniProt acc · gene name · organism · reviewed star -->
          <div class="flex items-center gap-1.5 mt-1 flex-wrap">
            <span class="font-mono text-xs text-gray-500">{{ protein.uniprot_id }}</span>
            <span v-if="protein.gene_name" class="text-gray-300 text-xs" aria-hidden>·</span>
            <span v-if="protein.gene_name" class="text-xs font-medium text-gray-600">{{ protein.gene_name }}</span>
            <span class="text-gray-300 text-xs" aria-hidden>·</span>
            <span class="text-xs italic text-gray-500">{{ protein.organism }}</span>
            <span
              v-if="protein.reviewed === true"
              title="Reviewed (Swiss-Prot)"
              class="text-amber-400 text-xs ml-1"
            >★</span>
          </div>

          <!-- Row: Organelles (plain text, clickable, · separated) -->
          <div v-if="protein.mlos?.length" class="flex items-baseline gap-2 mt-2">
            <span class="text-[11px] text-gray-400 flex-shrink-0"
                  style="width:80px;font-family:'IBM Plex Sans',sans-serif;font-weight:500">
              Organelles
            </span>
            <span class="text-[11px] text-gray-600 leading-relaxed">
              <template v-for="(mlo, i) in visibleMlos(protein)" :key="mlo">
                <span
                  class="hover:text-[#185FA5] cursor-pointer transition-colors"
                  @click.stop="applyFilter('mlo', mlo)"
                >{{ formatMlo(mlo) }}</span><span
                  v-if="i < visibleMlos(protein).length - 1"
                  class="text-gray-300 mx-1"
                >·</span>
              </template>
              <button
                v-if="protein.mlos.length > 5 && !expandedRows.has(protein.uniprot_id)"
                class="text-[#185FA5] hover:underline ml-1 text-[11px]"
                @click.stop="expandedRows.add(protein.uniprot_id)"
              >+{{ protein.mlos.length - 5 }} more</button>
            </span>
          </div>

          <!-- Row: Domains (green muted badges, deduplicated) -->
          <div v-if="uniqueDomains(protein).length" class="flex items-baseline gap-2 mt-1">
            <span class="text-[11px] text-gray-400 flex-shrink-0"
                  style="width:80px;font-family:'IBM Plex Sans',sans-serif;font-weight:500">
              Domains
            </span>
            <div class="flex flex-wrap gap-1">
              <span
                v-for="domain in uniqueDomains(protein)"
                :key="domain"
                class="px-1.5 py-0.5 rounded text-[10px] bg-[#EAF3DE] text-[#27500A] border border-[#C0DD97]"
              >{{ domain }}</span>
            </div>
          </div>

          <!-- Row: Features (IDR/LCD badges + sequence length) -->
          <div
            v-if="protein.has_idr || protein.has_lcd || protein.sequence_length"
            class="flex items-center gap-2 mt-1"
          >
            <span class="text-[11px] text-gray-400 flex-shrink-0"
                  style="width:80px;font-family:'IBM Plex Sans',sans-serif;font-weight:500">
              Features
            </span>
            <div class="flex items-center gap-1.5">
              <span v-if="protein.has_idr"
                class="px-1.5 py-0.5 rounded text-[10px] bg-[#FCEBEB] text-[#791F1F] border border-[#F7C1C1]"
              >IDR</span>
              <span v-if="protein.has_lcd"
                class="px-1.5 py-0.5 rounded text-[10px] bg-[#FAEEDA] text-[#633806] border border-[#FAC775]"
              >LCD</span>
              <span v-if="protein.sequence_length" class="text-[11px] text-gray-400 ml-1">
                {{ formatCount(protein.sequence_length) }} aa
              </span>
            </div>
          </div>
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
                  <span v-else-if="header.column.getCanSort()" class="ml-1 text-gray-300">↕</span>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in table.getRowModel().rows"
                :key="row.id"
                class="border-b border-gray-100 hover:bg-slate-50 cursor-pointer transition-colors"
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
      <span class="text-xs text-gray-400">
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
