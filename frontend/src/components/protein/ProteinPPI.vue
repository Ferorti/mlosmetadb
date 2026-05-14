<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import * as d3 from 'd3'
import { getProteinPpi } from '@/api/proteins.js'
import { formatMlo, formatCount } from '@/utils/format.js'

const props = defineProps({
  protein: { type: Object, required: true },
})

const router = useRouter()

// ── data ─────────────────────────────────────────────────────────────────────
const allPartners  = ref([])
const loading      = ref(false)
const error        = ref(null)

// ── filters ──────────────────────────────────────────────────────────────────
const filterScope  = ref('all')     // 'all' | 'in_db'
const filterRole   = ref('all')     // 'all' | 'driver' | 'component'
const filterMlo    = ref('')        // unified_mlo slug or ''

// ── table pagination ──────────────────────────────────────────────────────────
const tablePage    = ref(1)
const TABLE_PER    = 20

// ── graph state ──────────────────────────────────────────────────────────────
const graphRef     = ref(null)
const hoveredId    = ref(null)
const simulation   = ref(null)
const tooltip      = ref({ visible: false, x: 0, y: 0, partner: null })

const GRAPH_CAP = 300

// ── mlo options from partner data ─────────────────────────────────────────────
const mloOptions = computed(() => {
  const set = new Set()
  for (const p of allPartners.value) {
    if (p.in_db) p.mlos.forEach(m => set.add(m))
  }
  return Array.from(set).sort()
})

// ── filtered partners (client-side) ──────────────────────────────────────────
const filteredPartners = computed(() => {
  let list = allPartners.value
  if (filterScope.value === 'in_db') list = list.filter(p => p.in_db)
  if (filterRole.value === 'driver')    list = list.filter(p => p.in_db && p.has_driver)
  if (filterRole.value === 'component') list = list.filter(p => p.in_db && !p.has_driver)
  if (filterMlo.value) {
    const mlo = filterMlo.value
    list = list.filter(p => p.mlos.includes(mlo))
  }
  return list
})

// ── table ─────────────────────────────────────────────────────────────────────
const totalPages = computed(() => Math.max(1, Math.ceil(filteredPartners.value.length / TABLE_PER)))
const tableRows  = computed(() => {
  const start = (tablePage.value - 1) * TABLE_PER
  return filteredPartners.value.slice(start, start + TABLE_PER)
})

watch(filteredPartners, () => { tablePage.value = 1 })

// ── fetch ─────────────────────────────────────────────────────────────────────
async function load() {
  if (!props.protein.ppi?.total_partners) return
  loading.value = true
  error.value   = null
  try {
    const res = await getProteinPpi(props.protein.uniprot_id, { limit: 2000 })
    allPartners.value = res.data.items
  } catch (e) {
    error.value = e?.message ?? 'Error loading interactions'
  } finally {
    loading.value = false
  }
}

onMounted(load)

// ── graph rendering ───────────────────────────────────────────────────────────
function nodeColor(d) {
  if (d.isCenter) return '#1B3D6F'
  if (!d.in_db)   return '#D1D5DB'
  return d.has_driver ? '#185FA5' : '#9CA3AF'
}

function nodeStroke(d) {
  if (d.isCenter) return '#0F3D6F'
  if (!d.in_db)   return '#E5E7EB'
  return 'white'
}

function nodeRadius(d) {
  if (d.isCenter)  return 16
  if (!d.in_db)    return 4
  return d.has_driver ? 8 : 6
}

function renderGraph() {
  if (!graphRef.value) return
  simulation.value?.stop()
  d3.select(graphRef.value).selectAll('*').remove()

  const partners = filteredPartners.value
  const graphPartners = partners.slice(0, GRAPH_CAP)
  const truncated = partners.length > GRAPH_CAP

  const el = graphRef.value
  const W  = el.clientWidth  || 560
  const H  = el.clientHeight || 480

  const centerNode = {
    id: props.protein.uniprot_id,
    label: props.protein.gene_name || props.protein.uniprot_id,
    isCenter: true,
    in_db: true,
    has_driver: true,
    mlos: (props.protein.mlo_annotations ?? []).map(a => a.unified_mlo),
  }

  const nodes = [
    centerNode,
    ...graphPartners.map(p => ({
      id:         p.partner_uniprot_id,
      label:      p.partner_gene || p.partner_uniprot_id,
      isCenter:   false,
      in_db:      p.in_db,
      has_driver: p.has_driver,
      mlos:       p.mlos,
    })),
  ]

  const links = graphPartners.map(p => ({
    source: props.protein.uniprot_id,
    target: p.partner_uniprot_id,
  }))

  const svg = d3.select(graphRef.value)
    .append('svg')
    .attr('width', W)
    .attr('height', H)
    .attr('style', 'background:#FAFAFA')

  // truncation notice
  if (truncated) {
    svg.append('text')
      .attr('x', W / 2).attr('y', 14)
      .attr('text-anchor', 'middle')
      .attr('font-size', 10)
      .attr('fill', '#9CA3AF')
      .text(`Showing ${GRAPH_CAP} of ${partners.length} partners`)
  }

  const g = svg.append('g')

  svg.call(
    d3.zoom().scaleExtent([0.15, 4]).on('zoom', e => g.attr('transform', e.transform))
  )

  const link = g.append('g')
    .selectAll('line')
    .data(links)
    .join('line')
    .attr('stroke', '#E5E7EB')
    .attr('stroke-width', 1)

  const node = g.append('g')
    .selectAll('circle')
    .data(nodes)
    .join('circle')
    .attr('r', nodeRadius)
    .attr('fill', nodeColor)
    .attr('stroke', nodeStroke)
    .attr('stroke-width', d => d.isCenter ? 2.5 : 1)
    .style('cursor', d => d.isCenter ? 'default' : 'pointer')

  // center label
  const centerLabel = g.append('g')
    .selectAll('text')
    .data(nodes.filter(n => n.isCenter))
    .join('text')
    .text(d => d.label)
    .attr('font-size', 9)
    .attr('font-weight', '600')
    .attr('fill', '#1B3D6F')
    .attr('text-anchor', 'middle')
    .attr('dy', -20)
    .attr('pointer-events', 'none')

  // drag
  node.call(
    d3.drag()
      .on('start', (e, d) => { if (!e.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y })
      .on('drag',  (e, d) => { d.fx = e.x; d.fy = e.y })
      .on('end',   (e, d) => { if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null })
  )

  // tooltip & click
  node.on('mouseover', (event, d) => {
    if (d.isCenter) return
    hoveredId.value = d.id
    node.attr('opacity', n => (n.id === d.id || n.isCenter) ? 1 : 0.25)
    link.attr('opacity', l => l.target.id === d.id ? 1 : 0.08)

    const rect = graphRef.value.getBoundingClientRect()
    const partner = allPartners.value.find(p => p.partner_uniprot_id === d.id)
    tooltip.value = {
      visible: true,
      x: event.clientX - rect.left + 12,
      y: event.clientY - rect.top - 8,
      partner: partner ? { ...partner, label: d.label } : { label: d.label },
    }
  })
  .on('mousemove', (event) => {
    if (!tooltip.value.visible) return
    const rect = graphRef.value.getBoundingClientRect()
    tooltip.value = { ...tooltip.value, x: event.clientX - rect.left + 12, y: event.clientY - rect.top - 8 }
  })
  .on('mouseout', () => {
    hoveredId.value = null
    node.attr('opacity', 1)
    link.attr('opacity', 1)
    tooltip.value = { ...tooltip.value, visible: false }
  })
  .on('click', (e, d) => {
    if (!d.isCenter) router.push(`/protein/${d.id}`)
  })

  const sim = d3.forceSimulation(nodes)
    .force('link',      d3.forceLink(links).id(d => d.id).distance(55).strength(0.6))
    .force('charge',    d3.forceManyBody().strength(graphPartners.length > 100 ? -40 : -80))
    .force('center',    d3.forceCenter(W / 2, H / 2))
    .force('collision', d3.forceCollide().radius(d => nodeRadius(d) + 2))

  simulation.value = sim

  sim.on('tick', () => {
    link
      .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x).attr('y2', d => d.target.y)
    node.attr('cx', d => d.x).attr('cy', d => d.y)
    centerLabel.attr('x', d => d.x).attr('y', d => d.y)
  })
}

// highlight table-hovered node in graph
function highlightNode(id) {
  if (!graphRef.value) return
  const svg = d3.select(graphRef.value).select('svg')
  svg.selectAll('circle')
    .attr('opacity', n => !id || n.id === id || n.isCenter ? 1 : 0.2)
  svg.selectAll('line')
    .attr('opacity', l => !id || l.target.id === id ? 1 : 0.05)
}

watch(filteredPartners, () => nextTick(renderGraph))
watch(graphRef, val => { if (val) nextTick(renderGraph) })

onUnmounted(() => simulation.value?.stop())

// ── helpers ───────────────────────────────────────────────────────────────────
function resetFilters() {
  filterScope.value = 'all'
  filterRole.value  = 'all'
  filterMlo.value   = ''
}

function shortSystems(systems) {
  if (!systems?.length) return '—'
  const abbr = { 'Affinity Capture-MS': 'AP-MS', 'Affinity Capture-Western': 'AP-WB',
    'Two-hybrid': 'Y2H', 'Co-purification': 'Co-purif', 'Co-crystal Structure': 'Co-crystal',
    'Biochemical Activity': 'Biochem.', 'Proximity Label-MS': 'ProxLabel-MS' }
  const labels = [...new Set(systems.map(s => abbr[s] ?? s))]
  return labels.slice(0, 2).join(', ') + (labels.length > 2 ? ` +${labels.length - 2}` : '')
}
</script>

<template>
  <div class="space-y-4">

    <!-- Stats header -->
    <div class="flex items-center gap-6 text-sm text-[#484E59]">
      <span>
        <span class="font-semibold text-gray-800">{{ formatCount(protein.ppi?.total_partners ?? 0) }}</span>
        known partners
      </span>
      <span>
        <span class="font-semibold text-gray-800">{{ formatCount(protein.ppi?.partners_in_mlosmetadb ?? 0) }}</span>
        in MLOsMetaDB
      </span>
      <span v-if="allPartners.length" class="text-gray-400">
        ({{ formatCount(filteredPartners.length) }} shown after filters)
      </span>
    </div>

    <!-- Filters bar -->
    <div class="flex flex-wrap items-center gap-3 pb-3 border-b border-gray-100">

      <!-- Scope toggle -->
      <div class="inline-flex border border-gray-200 rounded overflow-hidden text-xs">
        <button
          :class="filterScope === 'all'   ? 'bg-[#1B3D6F] text-white' : 'bg-white text-gray-600 hover:bg-gray-50'"
          class="px-3 py-1.5 transition-colors"
          @click="filterScope = 'all'"
        >All partners</button>
        <button
          :class="filterScope === 'in_db' ? 'bg-[#1B3D6F] text-white' : 'bg-white text-gray-600 hover:bg-gray-50'"
          class="px-3 py-1.5 border-l border-gray-200 transition-colors"
          @click="filterScope = 'in_db'"
        >In MLOsMetaDB</button>
      </div>

      <!-- Role filter -->
      <div class="inline-flex border border-gray-200 rounded overflow-hidden text-xs">
        <button
          v-for="opt in [['all','Any role'],['driver','Driver'],['component','Component']]"
          :key="opt[0]"
          :class="filterRole === opt[0] ? 'bg-[#1B3D6F] text-white' : 'bg-white text-gray-600 hover:bg-gray-50'"
          class="px-3 py-1.5 border-l border-gray-200 first:border-l-0 transition-colors"
          @click="filterRole = opt[0]"
        >{{ opt[1] }}</button>
      </div>

      <!-- MLO filter -->
      <select
        v-model="filterMlo"
        class="text-xs border border-gray-200 rounded px-2 py-1.5 text-gray-600 focus:outline-none focus:border-[#185FA5] max-w-[180px]"
      >
        <option value="">All organelles</option>
        <option v-for="m in mloOptions" :key="m" :value="m">{{ formatMlo(m) }}</option>
      </select>

      <!-- Reset -->
      <button
        v-if="filterScope !== 'all' || filterRole !== 'all' || filterMlo"
        class="text-xs text-[#185FA5] hover:underline"
        @click="resetFilters"
      >Reset filters</button>
    </div>

    <!-- Loading / error -->
    <div v-if="loading" class="flex items-center gap-2 text-sm text-gray-400 py-8 justify-center">
      <svg class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
      </svg>
      Loading interactions…
    </div>
    <div v-else-if="error" class="text-sm text-red-500 py-4">{{ error }}</div>
    <div v-else-if="!protein.ppi?.total_partners" class="text-sm text-[#484E59] py-4">
      No PPI data available for this protein.
    </div>

    <!-- Two-column: table + graph -->
    <div v-else-if="allPartners.length" class="flex gap-4 min-h-[480px]">

      <!-- LEFT: Table -->
      <div class="w-[52%] flex flex-col min-w-0">
        <div class="flex-1 overflow-auto border border-gray-200 rounded text-xs">
          <table class="w-full">
            <thead class="bg-gray-50 sticky top-0 z-10">
              <tr>
                <th class="text-left px-3 py-2 font-medium text-gray-500 whitespace-nowrap">Gene</th>
                <th class="text-left px-3 py-2 font-medium text-gray-500 whitespace-nowrap">UniProt</th>
                <th class="text-left px-3 py-2 font-medium text-gray-500 whitespace-nowrap">In DB</th>
                <th class="text-left px-3 py-2 font-medium text-gray-500 whitespace-nowrap">Role</th>
                <th class="text-left px-3 py-2 font-medium text-gray-500 whitespace-nowrap">MLOs</th>
                <th class="text-left px-3 py-2 font-medium text-gray-500 whitespace-nowrap">Evidence</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="p in tableRows"
                :key="p.partner_uniprot_id"
                class="border-t border-gray-100 hover:bg-blue-50/40 transition-colors cursor-pointer"
                :class="hoveredId === p.partner_uniprot_id ? 'bg-blue-50' : ''"
                @mouseenter="hoveredId = p.partner_uniprot_id; highlightNode(p.partner_uniprot_id)"
                @mouseleave="hoveredId = null; highlightNode(null)"
                @click="router.push(`/protein/${p.partner_uniprot_id}`)"
              >
                <td class="px-3 py-1.5 font-medium text-[#185FA5]">
                  {{ p.partner_gene || '—' }}
                </td>
                <td class="px-3 py-1.5 font-mono text-gray-500">
                  {{ p.partner_uniprot_id }}
                </td>
                <td class="px-3 py-1.5">
                  <span
                    v-if="p.in_db"
                    class="inline-block px-1.5 py-0.5 rounded text-[10px] bg-[#E8F1FB] text-[#185FA5] border border-[#BFD7F0]"
                  >Yes</span>
                  <span v-else class="text-gray-300">—</span>
                </td>
                <td class="px-3 py-1.5">
                  <span
                    v-if="p.in_db && p.has_driver"
                    class="inline-block px-1.5 py-0.5 rounded text-[10px] bg-[#E8F1FB] text-[#185FA5] border border-[#BFD7F0]"
                  >Driver</span>
                  <span v-else-if="p.in_db" class="text-gray-400 text-[10px]">Component</span>
                  <span v-else class="text-gray-300">—</span>
                </td>
                <td class="px-3 py-1.5 text-gray-600 max-w-[160px]">
                  <template v-if="p.mlos.length">
                    <span>{{ p.mlos.slice(0, 2).map(formatMlo).join(', ') }}</span>
                    <span v-if="p.mlos.length > 2" class="text-gray-400"> +{{ p.mlos.length - 2 }}</span>
                  </template>
                  <span v-else class="text-gray-300">—</span>
                </td>
                <td class="px-3 py-1.5 text-gray-500" :title="p.experimental_systems.join(', ')">
                  {{ shortSystems(p.experimental_systems) }}
                </td>
              </tr>
              <tr v-if="!filteredPartners.length">
                <td colspan="6" class="px-3 py-8 text-center text-gray-400">
                  No partners match current filters.
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Table pagination -->
        <div v-if="totalPages > 1" class="flex items-center justify-between pt-2 text-xs text-gray-500">
          <span>
            {{ (tablePage - 1) * TABLE_PER + 1 }}–{{ Math.min(tablePage * TABLE_PER, filteredPartners.length) }}
            of {{ filteredPartners.length }}
          </span>
          <div class="flex items-center gap-1">
            <button
              class="px-2 py-1 border border-gray-200 rounded disabled:opacity-40 hover:border-gray-400 transition-colors"
              :disabled="tablePage <= 1"
              @click="tablePage--"
            >← Prev</button>
            <span class="px-2">{{ tablePage }} / {{ totalPages }}</span>
            <button
              class="px-2 py-1 border border-gray-200 rounded disabled:opacity-40 hover:border-gray-400 transition-colors"
              :disabled="tablePage >= totalPages"
              @click="tablePage++"
            >Next →</button>
          </div>
        </div>
      </div>

      <!-- RIGHT: Graph -->
      <div class="w-[48%] flex flex-col">
        <!-- Graph legend -->
        <div class="flex flex-wrap gap-3 mb-2 text-[10px] text-gray-500">
          <span class="flex items-center gap-1">
            <span class="inline-block w-3 h-3 rounded-full bg-[#1B3D6F]"></span> Query protein
          </span>
          <span class="flex items-center gap-1">
            <span class="inline-block w-3 h-3 rounded-full bg-[#185FA5]"></span> Driver (in DB)
          </span>
          <span class="flex items-center gap-1">
            <span class="inline-block w-3 h-3 rounded-full bg-[#9CA3AF]"></span> Component (in DB)
          </span>
          <span class="flex items-center gap-1">
            <span class="inline-block w-3 h-3 rounded-full bg-[#D1D5DB]"></span> Not in DB
          </span>
        </div>
        <!-- Graph container (relative for tooltip) -->
        <div ref="graphRef" class="relative flex-1 border border-gray-200 rounded overflow-hidden min-h-[440px]">
          <!-- D3 renders inside here -->

          <!-- Tooltip overlay -->
          <div
            v-if="tooltip.visible && tooltip.partner"
            class="absolute z-20 bg-white border border-gray-200 rounded shadow-md px-3 py-2 text-xs max-w-[220px] pointer-events-none"
            :style="{ left: tooltip.x + 'px', top: tooltip.y + 'px' }"
          >
            <div class="font-semibold text-gray-800">
              {{ tooltip.partner.label || tooltip.partner.partner_uniprot_id }}
            </div>
            <div class="text-gray-400 font-mono text-[10px]">{{ tooltip.partner.partner_uniprot_id }}</div>
            <div v-if="tooltip.partner.in_db" class="mt-1 flex items-center gap-1">
              <span
                v-if="tooltip.partner.has_driver"
                class="px-1.5 py-0.5 rounded text-[10px] bg-[#E8F1FB] text-[#185FA5] border border-[#BFD7F0]"
              >Driver</span>
              <span v-else class="text-gray-500">Component</span>
            </div>
            <div v-if="tooltip.partner.mlos?.length" class="mt-1 text-gray-500">
              {{ tooltip.partner.mlos.slice(0, 3).map(formatMlo).join(', ') }}
              <span v-if="tooltip.partner.mlos.length > 3">+{{ tooltip.partner.mlos.length - 3 }} more</span>
            </div>
            <div v-if="tooltip.partner.experimental_systems?.length" class="mt-1 text-gray-400">
              {{ shortSystems(tooltip.partner.experimental_systems) }}
            </div>
          </div>
        </div>
        <p class="text-[10px] text-gray-400 mt-1">Scroll to zoom · drag to pan · drag nodes · click to open</p>
      </div>

    </div>
  </div>
</template>
