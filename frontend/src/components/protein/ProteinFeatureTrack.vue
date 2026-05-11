<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import * as d3 from 'd3'
import {
  parseIdrRegions,
  parseLcdRegions,
  parseDomains,
  buildFeatureStats,
} from '@/utils/parseFeatures.js'

const props = defineProps({
  sequenceFeatures: { type: Object, required: true },
  sequenceLength:   { type: Number, required: true },
})

// ─── Feature parsing ──────────────────────────────────────────────────────────
const idrRegions  = computed(() => parseIdrRegions(
  props.sequenceFeatures?.idr_regions ?? props.sequenceFeatures?.idrs ?? null
))
const lcdRegions  = computed(() => parseLcdRegions(
  props.sequenceFeatures?.lcr_regions ?? props.sequenceFeatures?.lcds ?? null
))
const domains      = computed(() => parseDomains(props.sequenceFeatures?.domains ?? null))
const morfs        = computed(() => props.sequenceFeatures?.morfs ?? [])
const plddtRegions = computed(() => props.sequenceFeatures?.plddt_regions ?? [])

// ─── Track-visible subsets (SVG only shows primary curated sources) ───────────
const trackIdrs = computed(() => idrRegions.value.filter(r => r.source === 'MobiDB-lite'))
const trackLcds = computed(() => lcdRegions.value.filter(r => r.source === 'MobiDB-lite-sub'))

// ─── Table-visible subsets (broader, but still curated) ──────────────────────
const IDR_TABLE_SOURCES = new Set(['MobiDB-lite', 'AlphaFold-disorder'])
const tableIdrs = computed(() => idrRegions.value.filter(r => IDR_TABLE_SOURCES.has(r.source)))
const tableLcds = computed(() => lcdRegions.value.filter(r => r.source === 'MobiDB-lite-sub'))

// Table: deduplicate domains by accession (show each domain type once)
const tableDomainsDeduped = computed(() => {
  const seen = new Set()
  return domains.value.filter(d => {
    const key = d.accession ?? `${d.label}|${d.start}|${d.end}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
})

const featureStats = computed(() => buildFeatureStats({
  idrRegions:     trackIdrs.value,
  lcdRegions:     trackLcds.value,
  domains:        tableDomainsDeduped.value,
  sequenceLength: props.sequenceLength,
}))

const hasFeatures = computed(() =>
  idrRegions.value.length > 0 ||
  lcdRegions.value.length > 0 ||
  domains.value.length > 0 ||
  morfs.value.length > 0 ||
  plddtRegions.value.length > 0
)

// ─── SVG constants — all layers share a single centerY ───────────────────────
const TRACK_HEIGHT = 80
const CENTER_Y = TRACK_HEIGHT / 2   // 40
const BG_Y = CENTER_Y - 8          // 32
const BG_H = 16

const LAYERS = {
  IDR:  { y: CENTER_Y - 7,  h: 14, fill: '#F5A0A0', textFill: '#7F1D1D' },
  LCD:  { y: CENTER_Y - 4,  h: 8,  fill: '#FAC775', textFill: '#7C2D12' },
  DOM:  { y: CENTER_Y - 10, h: 20, fill: '#86C865', textFill: '#ffffff' },
  MORF: { y: CENTER_Y - 14, h: 5,  fill: '#C4B5FD', textFill: '#6B21A8' },
}

const CHAR_W = 6.5
const MIN_CHARS = 3

function fitLabel(label, avail) {
  if (!label) return null
  if (label.length * CHAR_W + 8 <= avail) return label
  for (let len = label.length - 1; len >= MIN_CHARS; len--) {
    const t = label.slice(0, len) + '…'
    if (t.length * CHAR_W + 8 <= avail) return t
  }
  return null
}

// ─── Display helpers ──────────────────────────────────────────────────────────
function formatSource(src) {
  if (!src) return '—'
  if (src.toLowerCase() === 'pfam')  return 'Pfam'
  if (src.toLowerCase() === 'smart') return 'SMART'
  return src
}

const TYPE_LABELS = {
  IDR:           'Intrinsically Disordered Region',
  LCD:           'Low Complexity Region',
  Domain:        'Domain',
  MoRF:          'MoRF',
  'pLDDT region': 'pLDDT Region',
}

function expandType(type) {
  return TYPE_LABELS[type] ?? type
}

// ─── D3 rendering ────────────────────────────────────────────────────────────
const containerRef = ref(null)
const tooltipRef   = ref(null)
let resizeObserver = null
let currentWidth   = 0

function render(width) {
  if (!containerRef.value || width < 10) return
  currentWidth = width

  const svg = d3.select(containerRef.value).select('svg')
  svg.attr('width', width).attr('height', TRACK_HEIGHT)
  svg.selectAll('*').remove()

  if (!props.sequenceLength) return

  const x = d3.scaleLinear().domain([0, props.sequenceLength]).range([0, width])

  // 1. Background bar — outlined only, visually distinct from data
  svg.append('rect')
    .attr('x', 0).attr('y', BG_Y)
    .attr('width', width).attr('height', BG_H)
    .attr('fill', '#F8FAFC')
    .attr('stroke', '#E2E8F0')
    .attr('stroke-width', 1)
    .attr('rx', 2)

  // 2. IDRs — MobiDB-lite only
  trackIdrs.value.forEach(r => drawRegion(svg, x, r, LAYERS.IDR, null))

  // 3. LCDs — MobiDB-lite-sub only
  trackLcds.value.forEach(r => drawRegion(svg, x, r, LAYERS.LCD, 'Low complexity region'))

  // 4. Domains — all Pfam instances, label only if rendered width > 40px
  domains.value.forEach(r => {
    const px = x(r.start)
    const pw = Math.max(2, x(r.end) - px)
    drawRegion(svg, x, r, LAYERS.DOM, pw > 40 ? r.label : null)
  })

  // 5. MoRFs — top strip
  morfs.value.forEach(r => drawRegion(svg, x, r, LAYERS.MORF, null))

  // pLDDT regions: table only, not in SVG

  // Sequence length label
  svg.append('text')
    .attr('x', width - 2).attr('y', TRACK_HEIGHT - 6)
    .attr('text-anchor', 'end')
    .attr('fill', '#484E59')
    .attr('font-size', '10px')
    .attr('font-family', 'ui-sans-serif, system-ui, sans-serif')
    .text(`${props.sequenceLength} aa`)

  // Invisible hit area for tooltip
  svg.append('rect')
    .attr('width', width).attr('height', TRACK_HEIGHT)
    .attr('fill', 'transparent').attr('cursor', 'crosshair')
    .on('mousemove', (event) => onMouseMove(event, x))
    .on('mouseleave', hideTooltip)
}

function drawRegion(svg, x, region, layer, label) {
  const rx = x(region.start)
  const rw = Math.max(2, x(region.end) - rx)
  const g  = svg.append('g')

  g.append('rect')
    .attr('x', rx).attr('y', layer.y)
    .attr('width', rw).attr('height', layer.h)
    .attr('fill', layer.fill).attr('rx', 2)

  if (label) {
    const fitted = fitLabel(label, rw)
    if (fitted) {
      g.append('text')
        .attr('x', rx + rw / 2).attr('y', layer.y + layer.h / 2)
        .attr('text-anchor', 'middle').attr('dominant-baseline', 'middle')
        .attr('fill', layer.textFill)
        .attr('font-size', '10px').attr('font-weight', '600')
        .attr('font-family', 'ui-sans-serif, system-ui, sans-serif')
        .text(fitted)
    }
  }
}

function onMouseMove(event, x) {
  const [mX] = d3.pointer(event)
  const aa   = Math.round(x.invert(mX))

  const hits = [
    ...trackIdrs.value.filter(r => aa >= r.start && aa <= r.end)
      .map(r => ({ type: 'IDR', range: `${r.start}–${r.end}`, label: null, source: r.source })),
    ...trackLcds.value.filter(r => aa >= r.start && aa <= r.end)
      .map(r => ({ type: 'LCD', range: `${r.start}–${r.end}`, label: 'Low complexity region', source: r.source })),
    ...domains.value.filter(r => aa >= r.start && aa <= r.end)
      .map(r => ({ type: 'Domain', range: `${r.start}–${r.end}`, label: r.label, source: formatSource(r.database) })),
    ...morfs.value.filter(r => aa >= r.start && aa <= r.end)
      .map(r => ({ type: 'MoRF', range: `${r.start}–${r.end}`, label: null, source: r.source })),
  ]

  if (!hits.length) { hideTooltip(); return }

  const tip = tooltipRef.value
  if (!tip) return
  tip.style.display = 'block'
  tip.style.left    = (event.clientX + 14) + 'px'
  tip.style.top     = (event.clientY - 28) + 'px'
  tip.innerHTML     = `
    <div style="color:#94a3b8;font-size:9px;margin-bottom:3px">pos ${aa} aa</div>
    ${hits.map(h => `
      <div>
        <span style="font-weight:600">${h.type}</span>${h.label ? ': ' + h.label : ''}
        <span style="color:#94a3b8"> ${h.range}</span>
        ${h.source ? `<span style="color:#64748b;font-size:9px"> · ${h.source}</span>` : ''}
      </div>
    `).join('')}
  `
}

function hideTooltip() {
  if (tooltipRef.value) tooltipRef.value.style.display = 'none'
}

onMounted(() => {
  if (!containerRef.value) return
  resizeObserver = new ResizeObserver(entries => {
    const w = entries[0].contentRect.width
    if (Math.abs(w - currentWidth) > 2) render(w)
  })
  resizeObserver.observe(containerRef.value)
  render(containerRef.value.clientWidth)
})

onUnmounted(() => {
  resizeObserver?.disconnect()
})

watch(
  () => [props.sequenceLength, props.sequenceFeatures],
  () => render(currentWidth),
  { deep: true }
)

// ─── Feature table ────────────────────────────────────────────────────────────
const TYPE_COLORS = {
  IDR:           '#F5A0A0',
  LCD:           '#FAC775',
  Domain:        '#86C865',
  MoRF:          '#C4B5FD',
  'pLDDT region': '#93C5FD',
}

const featureGroups = computed(() => {
  const groups = []

  // IDR — only MobiDB-lite and AlphaFold-disorder
  if (tableIdrs.value.length) {
    groups.push({
      type: 'IDR',
      color: TYPE_COLORS.IDR,
      items: tableIdrs.value.map(r => ({
        region: `${r.start}–${r.end}`,
        source: r.source ?? '—',
        label:  '—',
      })),
    })
  }

  // LCD — only MobiDB-lite-sub
  if (tableLcds.value.length) {
    groups.push({
      type: 'LCD',
      color: TYPE_COLORS.LCD,
      items: tableLcds.value.map(r => ({
        region: `${r.start}–${r.end}`,
        source: r.source ?? '—',
        label:  'Low complexity region',
      })),
    })
  }

  // Domains — deduplicated by accession, Pfam source capitalized
  if (tableDomainsDeduped.value.length) {
    groups.push({
      type: 'Domain',
      color: TYPE_COLORS.Domain,
      items: tableDomainsDeduped.value.map(r => ({
        region: `${r.start}–${r.end}`,
        source: formatSource(r.database),
        label:  r.accession ? `${r.label} (${r.accession})` : (r.label ?? '—'),
      })),
    })
  }

  // MoRFs
  if (morfs.value.length) {
    groups.push({
      type: 'MoRF',
      color: TYPE_COLORS.MoRF,
      items: morfs.value.map(r => ({
        region: `${r.start}–${r.end}`,
        source: r.source ?? '—',
        label:  r.label ?? '—',
      })),
    })
  }

  // pLDDT — table only (source always AlphaFold2)
  if (plddtRegions.value.length) {
    groups.push({
      type: 'pLDDT region',
      color: TYPE_COLORS['pLDDT region'],
      items: plddtRegions.value.map(r => ({
        region: `${r.start}–${r.end}`,
        source: 'AlphaFold2',
        label:  r.label ?? '—',
      })),
    })
  }

  return groups
})
</script>

<template>
  <div>
    <!-- Stats line -->
    <div v-if="featureStats" class="text-xs text-[#484E59] mb-3">{{ featureStats }}</div>

    <!-- D3 track -->
    <div ref="containerRef" class="w-full relative mb-4">
      <svg style="display:block; overflow:visible"></svg>
    </div>

    <teleport to="body">
      <div
        ref="tooltipRef"
        style="
          display: none;
          position: fixed;
          pointer-events: none;
          z-index: 9999;
          background: #1e293b;
          color: #f1f5f9;
          font-size: 11px;
          font-family: ui-monospace, monospace;
          padding: 6px 10px;
          border-radius: 6px;
          box-shadow: 0 4px 12px rgba(0,0,0,0.25);
          white-space: nowrap;
          line-height: 1.6;
        "
      ></div>
    </teleport>

    <!-- Feature table -->
    <div v-if="!hasFeatures" class="text-sm text-[#484E59]">No sequence features available.</div>
    <table v-else class="w-full text-xs mt-2 border-collapse">
      <template v-for="group in featureGroups" :key="group.type">
        <!-- Group header -->
        <tr>
          <td colspan="4" class="pt-3 pb-1 px-2 bg-slate-50">
            <div class="flex items-center gap-2">
              <span
                class="inline-block w-2.5 h-2.5 rounded-sm flex-shrink-0"
                :style="{ backgroundColor: group.color }"
              ></span>
              <span class="text-[#484E59] font-medium text-[10px]">
                {{ expandType(group.type) }}
              </span>
            </div>
          </td>
        </tr>
        <!-- Feature rows -->
        <tr v-for="(item, i) in group.items" :key="i" class="border-t border-slate-100">
          <td class="py-1 px-2 text-[#484E59]">{{ expandType(group.type) }}</td>
          <td class="py-1 px-2 w-28 font-mono text-gray-700">{{ item.region }}</td>
          <td class="py-1 px-2 w-32 text-[#484E59]">{{ item.source }}</td>
          <td class="py-1 px-2 text-gray-700">{{ item.label }}</td>
        </tr>
      </template>
    </table>
  </div>
</template>
