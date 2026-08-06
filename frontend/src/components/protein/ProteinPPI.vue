<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import * as d3 from 'd3'
import { getProteinPpi } from '@/api/proteins.js'
import { formatMlo, formatCount, filterMlos } from '@/utils/format.js'

const props = defineProps({
  protein: { type: Object, required: true },
})

const router = useRouter()

// ── data ─────────────────────────────────────────────────────────────────────
const allPartners  = ref([])
const interEdges   = ref([])   // edges between partners (from API)
const loading      = ref(false)
const error        = ref(null)

// ── filters ──────────────────────────────────────────────────────────────────
const filterRole   = ref('driver')   // 'all' | 'driver' | 'component'
const filterMlo    = ref('')         // unified_mlo slug or ''

// ── table pagination ──────────────────────────────────────────────────────────
const tablePage    = ref(1)
const TABLE_PER    = 20

// ── graph state ──────────────────────────────────────────────────────────────
const graphRef     = ref(null)
const hoveredId    = ref(null)
const selectedId   = ref(null)   // persistent selection (survives mouseout), set by graph node click
const simulation   = ref(null)
const tooltip      = ref({ visible: false, x: 0, y: 0, partner: null })
const rowRefs      = {}          // plain (non-reactive) DOM-node lookup, keyed by partner_uniprot_id

const GRAPH_CAP = 300

// ── mlo options (distinct across all in-db partners) ──────────────────────────
const mloOptions = computed(() => {
  const set = new Set()
  for (const p of allPartners.value) p.mlos.forEach(m => set.add(m))
  return Array.from(set).sort()
})

// ── filtered partners ─────────────────────────────────────────────────────────
const filteredPartners = computed(() => {
  let list = allPartners.value
  if (filterRole.value === 'driver')    list = list.filter(p => p.has_driver)
  if (filterRole.value === 'component') list = list.filter(p => !p.has_driver)
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
// Reset paging AND the persistent selection whenever the visible partner set
// changes: the selected row may no longer be in `filteredPartners` at all, and
// a stale `selectedId` would either highlight nothing or (worse) light up a
// different partner that happens to reappear later.
watch(filteredPartners, () => {
  tablePage.value  = 1
  selectedId.value = null
})

// ── driver count (all in-db partners, no filter) ──────────────────────────────
const inDbDriverCount = computed(() => allPartners.value.filter(p => p.has_driver).length)

// ── graph data ────────────────────────────────────────────────────────────────
// Smart cap: always show all drivers first, fill remainder with components
const graphData = computed(() => {
  let visible
  if (filteredPartners.value.length > GRAPH_CAP) {
    const drivers    = filteredPartners.value.filter(p => p.has_driver)
    const components = filteredPartners.value.filter(p => !p.has_driver)
    visible = [
      ...drivers.slice(0, GRAPH_CAP),
      ...components.slice(0, Math.max(0, GRAPH_CAP - drivers.length)),
    ]
  } else {
    visible = filteredPartners.value
  }
  const visibleSet = new Set(visible.map(p => p.partner_uniprot_id))

  const nodes = [
    {
      id:         props.protein.uniprot_id,
      label:      props.protein.gene_name || props.protein.uniprot_id,
      isCenter:   true,
      has_driver: true,
      mlos:       [],
    },
    ...visible.map(p => ({
      id:         p.partner_uniprot_id,
      label:      p.partner_gene || p.partner_uniprot_id,
      isCenter:   false,
      has_driver: p.has_driver,
      mlos:       p.mlos,
    })),
  ]

  // Hub edges (center → each visible partner)
  const hubLinks = visible.map(p => ({
    source:   props.protein.uniprot_id,
    target:   p.partner_uniprot_id,
    isHub:    true,
  }))

  // Inter-partner edges (filtered to visible nodes only)
  const partnerLinks = interEdges.value
    .filter(e => visibleSet.has(e.source) && visibleSet.has(e.target))
    .map(e => ({ source: e.source, target: e.target, isHub: false }))

  return { nodes, links: [...hubLinks, ...partnerLinks] }
})

// ── fetch ─────────────────────────────────────────────────────────────────────
async function load() {
  if (!props.protein.ppi?.total_partners) return
  loading.value = true
  error.value   = null
  try {
    const res = await getProteinPpi(props.protein.uniprot_id, { limit: 500 })
    allPartners.value = res.data.items
    interEdges.value  = res.data.inter_edges ?? []
  } catch (e) {
    error.value = e?.message ?? 'Error loading interactions'
  } finally {
    loading.value = false
  }
}

onMounted(load)

// Defensive: today ProteinPage.vue unmounts this component on every route change
// (its `mountedTabs.clear()` flips the wrapping `v-if` to false), so the protein
// prop never changes in place. If that ever stops being true, a selection made
// on the previous protein must not survive into the next one.
watch(() => props.protein?.uniprot_id, () => {
  selectedId.value = null
  hoveredId.value  = null
  tablePage.value  = 1
})

// ── graph rendering ───────────────────────────────────────────────────────────
function nodeColor(d) {
  if (d.isCenter)   return '#1B3D6F'
  return d.has_driver ? '#60A5FA' : '#9CA3AF'
}

function nodeRadius(d) {
  if (d.isCenter)   return 16
  return d.has_driver ? 8 : 6
}

function renderGraph() {
  if (!graphRef.value || !graphData.value.nodes.length) return
  simulation.value?.stop()
  d3.select(graphRef.value).selectAll('*').remove()

  const { nodes, links } = graphData.value
  const truncated = filteredPartners.value.length > GRAPH_CAP
  const el = graphRef.value
  const W  = el.clientWidth  || 560
  const H  = el.clientHeight || 480

  // Pin center node to canvas middle so inter-partner edges can't push it out
  nodes[0].fx = W / 2
  nodes[0].fy = H / 2

  const svg = d3.select(el)
    .append('svg')
    .attr('width', W)
    .attr('height', H)
    .attr('style', 'background:#FAFAFA;border-radius:4px')

  if (truncated) {
    svg.append('text')
      .attr('x', W / 2).attr('y', 14)
      .attr('text-anchor', 'middle')
      .attr('font-size', 10)
      .attr('fill', '#9CA3AF')
      .text(`Graph capped at ${nodes.length - 1} of ${filteredPartners.value.length} partners`)
  }

  const g = svg.append('g')
  svg.call(
    d3.zoom().scaleExtent([0.1, 5]).on('zoom', e => g.attr('transform', e.transform))
  )

  const linkSel = g.append('g')
    .selectAll('line')
    .data(links)
    .join('line')
    .attr('stroke', d => d.isHub ? '#D1D5DB' : '#93B8E8')
    .attr('stroke-width', d => d.isHub ? 0.7 : 1.4)
    .attr('stroke-opacity', d => d.isHub ? 0.5 : 0.8)

  const nodeSel = g.append('g')
    .selectAll('circle')
    .data(nodes)
    .join('circle')
    .attr('r', nodeRadius)
    .attr('fill', nodeColor)
    .attr('stroke', d => d.isCenter ? '#0F3D6F' : 'white')
    .attr('stroke-width', d => d.isCenter ? 2.5 : 1)
    .style('cursor', d => d.isCenter ? 'default' : 'pointer')

  // center label always visible
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

  // drag — only non-center nodes
  nodeSel.filter(d => !d.isCenter).call(
    d3.drag()
      .on('start', (e, d) => { if (!e.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y })
      .on('drag',  (e, d) => { d.fx = e.x; d.fy = e.y })
      .on('end',   (e, d) => { if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null })
  )

  // tooltip + highlight
  nodeSel
    .on('mouseover', (event, d) => {
      if (d.isCenter) return
      hoveredId.value = d.id
      nodeSel.attr('opacity', n => (n.id === d.id || n.isCenter) ? 1 : 0.25)
      linkSel.attr('opacity', l => {
        const sid = typeof l.source === 'object' ? l.source.id : l.source
        const tid = typeof l.target === 'object' ? l.target.id : l.target
        return sid === d.id || tid === d.id ? 1 : 0.05
      })
      const rect = graphRef.value.getBoundingClientRect()
      const partner = allPartners.value.find(p => p.partner_uniprot_id === d.id)
      tooltip.value = {
        visible: true,
        x: event.clientX - rect.left + 14,
        y: event.clientY - rect.top - 8,
        partner: partner ? { ...partner, label: d.label } : { label: d.label, partner_uniprot_id: d.id },
      }
    })
    .on('mousemove', (event) => {
      if (!tooltip.value.visible) return
      const rect = graphRef.value.getBoundingClientRect()
      tooltip.value = { ...tooltip.value, x: event.clientX - rect.left + 14, y: event.clientY - rect.top - 8 }
    })
    .on('mouseout', () => {
      hoveredId.value = null
      nodeSel.attr('opacity', 1)
      linkSel.attr('opacity', 1)
      tooltip.value = { ...tooltip.value, visible: false }
    })
    .on('click', (e, d) => {
      if (d.isCenter) return
      selectedId.value = d.id
      highlightNode(d.id)
      const index = filteredPartners.value.findIndex(p => p.partner_uniprot_id === d.id)
      if (index === -1) return
      tablePage.value = Math.floor(index / TABLE_PER) + 1
      nextTick(() => rowRefs[d.id]?.scrollIntoView({ block: 'nearest' }))
    })

  const partnerCount = nodes.length - 1
  const charge = partnerCount > 150 ? -80 : partnerCount > 50 ? -140 : -220

  const sim = d3.forceSimulation(nodes)
    .force('link',      d3.forceLink(links).id(d => d.id)
      .distance(d => d.isHub ? 120 : 60)
      .strength(d => d.isHub ? 0.7 : 0.1))
    .force('charge',    d3.forceManyBody().strength(d => d.isCenter ? -300 : charge))
    .force('center',    d3.forceCenter(W / 2, H / 2))
    .force('collision', d3.forceCollide().radius(d => nodeRadius(d) + 8))

  simulation.value = sim

  sim.on('tick', () => {
    linkSel
      .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x).attr('y2', d => d.target.y)
    nodeSel.attr('cx', d => d.x).attr('cy', d => d.y)
    centerLabel.attr('x', d => d.x).attr('y', d => d.y)
  })
}

// highlight from table hover
function highlightNode(id) {
  if (!graphRef.value) return
  const svg = d3.select(graphRef.value).select('svg')
  svg.selectAll('circle').attr('opacity', n => !id || n.id === id || n.isCenter ? 1 : 0.2)
  svg.selectAll('line').attr('opacity', l => {
    if (!id) return 1
    const sid = typeof l.source === 'object' ? l.source.id : l.source
    const tid = typeof l.target === 'object' ? l.target.id : l.target
    return sid === id || tid === id ? 1 : 0.04
  })
}

watch(graphData, () => nextTick(renderGraph))
watch(graphRef,  val => { if (val) nextTick(renderGraph) })
onUnmounted(() => simulation.value?.stop())

// ── helpers ───────────────────────────────────────────────────────────────────
function resetFilters() {
  filterRole.value = 'all'
  filterMlo.value  = ''
}

function shortSystems(systems) {
  if (!systems?.length) return '—'
  const abbr = {
    'Affinity Capture-MS': 'AP-MS', 'Affinity Capture-Western': 'AP-WB',
    'Two-hybrid': 'Y2H', 'Co-purification': 'Co-purif',
    'Co-crystal Structure': 'Co-crystal', 'Biochemical Activity': 'Biochem.',
    'Proximity Label-MS': 'ProxLabel-MS',
  }
  const labels = [...new Set(systems.map(s => abbr[s] ?? s))]
  return labels.slice(0, 2).join(', ') + (labels.length > 2 ? ` +${labels.length - 2}` : '')
}
</script>

<template>
  <div class="space-y-4">

    <!-- Stats header -->
    <div class="text-sm text-[#484E59] space-y-1">
      <div class="flex flex-wrap gap-x-5 gap-y-1 items-baseline">
        <span>
          <span class="font-semibold text-gray-800">{{ formatCount(protein.ppi?.partners_in_mlosmetadb ?? 0) }}</span>
          partners
          <span v-if="inDbDriverCount > 0" class="text-gray-500">({{ formatCount(inDbDriverCount) }} drivers)</span>
          in MLOsMetaDB
        </span>
        <span class="text-gray-400 text-xs">
          {{ formatCount(protein.ppi?.total_partners ?? 0) }} total known ·
          <a href="https://thebiogrid.org/" target="_blank" rel="noopener" class="text-[#185FA5] hover:underline">BioGRID</a>
          /
          <a href="https://string-db.org/" target="_blank" rel="noopener" class="text-[#185FA5] hover:underline">STRING</a>
          for the full network
        </span>
      </div>
      <p class="text-xs text-gray-400">
        Only partners present in MLOsMetaDB are shown. Graph edges include interactions between partners.
      </p>
    </div>

    <!-- Filters bar -->
    <div class="flex flex-wrap items-center gap-3 pb-3 border-b border-gray-100">

      <!-- Role filter -->
      <div class="inline-flex border border-gray-200 rounded overflow-hidden text-xs">
        <button
          v-for="opt in [['driver','Drivers'],['component','Components'],['all','All roles']]"
          :key="opt[0]"
          :class="filterRole === opt[0] ? 'bg-[#1B3D6F] text-white' : 'bg-white text-gray-600 hover:bg-gray-50'"
          class="px-3 py-1.5 border-l border-gray-200 first:border-l-0 transition-colors"
          @click="filterRole = opt[0]"
        >{{ opt[1] }}</button>
      </div>

      <!-- MLO filter -->
      <select
        v-model="filterMlo"
        class="text-xs border border-gray-200 rounded px-2 py-1.5 text-gray-600 focus:outline-none focus:border-[#185FA5] max-w-[190px]"
      >
        <option value="">All organelles</option>
        <option v-for="m in mloOptions" :key="m" :value="m">{{ formatMlo(m) }}</option>
      </select>

      <!-- Reset -->
      <button
        v-if="filterRole !== 'all' || filterMlo"
        class="text-xs text-[#185FA5] hover:underline"
        @click="resetFilters"
      >Reset filters</button>
    </div>

    <!-- Loading / error / empty -->
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
    <div v-else-if="!allPartners.length" class="text-sm text-[#484E59] py-4">
      This protein has {{ formatCount(protein.ppi?.total_partners) }} known interaction partner(s), but none are currently in MLOsMetaDB.
    </div>

    <!-- Two-column: table + graph -->
    <div v-else-if="allPartners.length" class="flex gap-4" style="min-height:500px">

      <!-- LEFT: Table -->
      <div class="w-[52%] flex flex-col min-w-0">
        <div class="flex-1 overflow-auto border border-gray-200 rounded text-xs">
          <table class="w-full">
            <thead class="bg-gray-50 sticky top-0 z-10">
              <tr>
                <th class="text-left px-3 py-2 font-medium text-gray-500 whitespace-nowrap">Gene</th>
                <th class="text-left px-3 py-2 font-medium text-gray-500 whitespace-nowrap">UniProt</th>
                <th class="text-left px-3 py-2 font-medium text-gray-500 whitespace-nowrap">Role</th>
                <th class="text-left px-3 py-2 font-medium text-gray-500 whitespace-nowrap">MLOs</th>
                <th class="text-left px-3 py-2 font-medium text-gray-500 whitespace-nowrap">Evidence</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!filteredPartners.length">
                <td colspan="5" class="px-3 py-8 text-center text-gray-400">
                  <template v-if="filterRole === 'driver'">
                    No driver partners found.
                    <button class="text-[#185FA5] hover:underline ml-1" @click="filterRole = 'all'">Show all roles</button>
                  </template>
                  <template v-else>No partners match current filters.</template>
                </td>
              </tr>
              <tr
                v-for="p in tableRows"
                :key="p.partner_uniprot_id"
                :ref="el => { if (el) rowRefs[p.partner_uniprot_id] = el; else delete rowRefs[p.partner_uniprot_id] }"
                class="border-t border-gray-100 hover:bg-slate-50/60 transition-colors"
                :class="(hoveredId === p.partner_uniprot_id || selectedId === p.partner_uniprot_id) ? 'bg-blue-50/50' : ''"
                @mouseenter="hoveredId = p.partner_uniprot_id; highlightNode(p.partner_uniprot_id)"
                @mouseleave="hoveredId = null; highlightNode(null)"
              >
                <td class="px-3 py-1.5 font-medium">
                  <span
                    class="text-[#185FA5] hover:underline cursor-pointer"
                    @click="router.push(`/protein/${p.partner_uniprot_id}`)"
                  >{{ p.partner_gene || p.partner_uniprot_id }}</span>
                </td>
                <td class="px-3 py-1.5 font-mono text-gray-500">
                  {{ p.partner_uniprot_id }}
                </td>
                <td class="px-3 py-1.5">
                  <span
                    v-if="p.has_driver"
                    class="text-[10px] text-[#185FA5] font-medium"
                  >Driver</span>
                  <span v-else class="text-gray-400 text-[10px]">Component</span>
                </td>
                <td class="px-3 py-1.5 text-gray-600">
                  <template v-if="filterMlos(p.mlos).length">
                    <span>{{ filterMlos(p.mlos).slice(0, 2).map(formatMlo).join(', ') }}</span>
                    <span v-if="filterMlos(p.mlos).length > 2" class="text-gray-400"> +{{ filterMlos(p.mlos).length - 2 }}</span>
                  </template>
                  <span v-else class="text-gray-300">—</span>
                </td>
                <td
                  class="px-3 py-1.5 text-gray-500"
                  :title="p.experimental_systems.join(', ')"
                >
                  {{ shortSystems(p.experimental_systems) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Table pagination -->
        <div v-if="totalPages > 1" class="flex items-center justify-between pt-2 text-xs text-gray-500">
          <span>
            {{ (tablePage - 1) * TABLE_PER + 1 }}–{{ Math.min(tablePage * TABLE_PER, filteredPartners.length) }}
            of {{ formatCount(filteredPartners.length) }}
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

        <!-- Legend -->
        <div class="flex flex-wrap gap-3 mb-2 text-[10px] text-gray-500">
          <span class="flex items-center gap-1">
            <span class="inline-block w-3 h-3 rounded-full bg-[#1B3D6F]"></span> Query protein
          </span>
          <span class="flex items-center gap-1">
            <span class="inline-block w-3 h-3 rounded-full bg-[#60A5FA]"></span> Driver
          </span>
          <span class="flex items-center gap-1">
            <span class="inline-block w-3 h-3 rounded-full bg-[#9CA3AF]"></span> Component
          </span>
          <span class="flex items-center gap-1 ml-3 text-gray-400">
            <span class="inline-block w-5 border-t border-gray-300"></span> hub edge
          </span>
          <span class="flex items-center gap-1">
            <span class="inline-block w-5 border-t-2 border-[#C7D9F0]"></span> partner–partner
          </span>
        </div>

        <!-- Graph canvas -->
        <div
          ref="graphRef"
          class="relative flex-1 border border-gray-200 rounded overflow-hidden"
          style="min-height:450px"
        >
          <!-- Tooltip -->
          <div
            v-if="tooltip.visible && tooltip.partner"
            class="absolute z-20 bg-white border border-gray-200 rounded shadow-md px-3 py-2 text-xs max-w-[220px] pointer-events-none"
            :style="{ left: tooltip.x + 'px', top: tooltip.y + 'px' }"
          >
            <div class="font-semibold text-gray-800">
              {{ tooltip.partner.label || tooltip.partner.partner_uniprot_id }}
            </div>
            <div class="text-gray-400 font-mono text-[10px]">{{ tooltip.partner.partner_uniprot_id }}</div>
            <div class="mt-1">
              <span
                v-if="tooltip.partner.has_driver"
                class="px-1.5 py-0.5 rounded text-[10px] bg-[#E8F1FB] text-[#185FA5] border border-[#BFD7F0]"
              >Driver</span>
              <span v-else class="text-gray-500 text-[10px]">Component</span>
            </div>
            <div v-if="filterMlos(tooltip.partner.mlos).length" class="mt-1 text-gray-500">
              {{ filterMlos(tooltip.partner.mlos).slice(0, 3).map(formatMlo).join(', ') }}
              <span v-if="filterMlos(tooltip.partner.mlos).length > 3"> +{{ filterMlos(tooltip.partner.mlos).length - 3 }}</span>
            </div>
            <div v-if="tooltip.partner.experimental_systems?.length" class="mt-1 text-gray-400">
              {{ shortSystems(tooltip.partner.experimental_systems) }}
            </div>
          </div>
        </div>

        <p class="text-[10px] text-gray-400 mt-1">
          Scroll to zoom · drag canvas to pan · drag nodes to reposition · click to select in table
        </p>
      </div>

    </div>
  </div>
</template>
