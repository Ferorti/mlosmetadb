<script setup>
import { ref, watch, onMounted, onUnmounted, computed } from 'vue'
import * as d3 from 'd3'
import { formatCount } from '@/utils/format'

const props = defineProps({
  combos:  { type: Array,  required: true },  // f2_protein_source_combos
  summary: { type: Object, required: true },
})

const TOP_N = 12
// Fixed row order for the dot matrix -- matches the report's own reference figure.
const SOURCE_ROWS = ['CDCODE', 'DrLLPS', 'PhaSepDB', 'LLPSDB', 'PhasePro']

const sortedCombos = computed(() => [...props.combos].sort((a, b) => b.n_proteins - a.n_proteins))
const displayCombos = computed(() => sortedCombos.value.slice(0, TOP_N))
const omittedCount = computed(() => sortedCombos.value.length - displayCombos.value.length)
const omittedProteins = computed(() =>
  sortedCombos.value.slice(TOP_N).reduce((sum, c) => sum + c.n_proteins, 0)
)
const pctMultiSource = computed(() => {
  if (!props.summary.n_proteins) return 0
  return Math.round((props.summary.proteins_multi_source / props.summary.n_proteins) * 100)
})

const containerRef = ref(null)
const tooltipRef = ref(null)
let resizeObserver = null
let currentWidth = 0

function showTooltip(event, combo) {
  const tip = tooltipRef.value
  if (!tip) return
  tip.style.display = 'block'
  tip.style.left = (event.clientX + 14) + 'px'
  tip.style.top = (event.clientY - 28) + 'px'
  tip.innerHTML = `<div style="font-weight:600">${combo.sources.join(' + ')}</div><div>${combo.n_proteins.toLocaleString()} proteins</div>`
}

function hideTooltip() {
  if (tooltipRef.value) tooltipRef.value.style.display = 'none'
}

function render(width) {
  if (!containerRef.value || width < 10) return
  currentWidth = width

  const rows = displayCombos.value
  const labelW = 90
  const plotW = Math.max(20, width - labelW - 10)
  const barAreaH = 210
  const barBottomY = barAreaH - 20
  // Dot-matrix rows kept tight (18px) rather than the more generous spacing a
  // default UpSet layout would use -- "hacerlo menos alto" per user feedback.
  const rowH = 18
  const matrixTopPad = 12
  const matrixH = SOURCE_ROWS.length * rowH
  const height = barAreaH + matrixTopPad + matrixH + 8

  const svg = d3.select(containerRef.value).select('svg')
  svg.attr('width', width).attr('height', height)
  svg.selectAll('*').remove()

  const x = d3.scaleBand().domain(rows.map((_, i) => i)).range([0, plotW]).padding(0.35)
  const maxVal = d3.max(rows, r => r.n_proteins) || 1
  const y = d3.scaleLinear().domain([0, maxVal]).range([barBottomY, 10])

  const plot = svg.append('g').attr('transform', `translate(${labelW + 10}, 0)`)

  // Y-axis, gridlines only (no axis line) -- matches the reference figure's
  // light horizontal guides rather than a heavy boxed axis.
  plot.append('g')
    .call(d3.axisLeft(y).ticks(5).tickSize(-plotW).tickFormat(d3.format(',')))
    .call(g => g.selectAll('.tick line').attr('stroke', '#eef0f2'))
    .call(g => g.select('.domain').remove())
    .selectAll('text').attr('font-size', 9).attr('fill', '#9ca3af')

  // Bars
  rows.forEach((row, i) => {
    const bx = x(i)
    const bw = x.bandwidth()
    const isMulti = row.n_sources >= 2
    const by = y(row.n_proteins)
    const bh = Math.max(1, barBottomY - by)
    plot.append('rect')
      .attr('x', bx).attr('y', by).attr('width', bw).attr('height', bh)
      .attr('rx', 2)
      .attr('fill', isMulti ? '#eb6834' : '#9ca3af')
      .style('cursor', 'default')
      .on('mousemove', (event) => showTooltip(event, row))
      .on('mouseleave', hideTooltip)
    plot.append('text')
      .attr('x', bx + bw / 2).attr('y', by - 4)
      .attr('font-size', 9).attr('text-anchor', 'middle').attr('fill', '#374151')
      .text(row.n_proteins.toLocaleString())
  })

  // Dot matrix
  const matrixTop = barAreaH + matrixTopPad
  const activeR = 5
  const inactiveR = 2.5

  SOURCE_ROWS.forEach((src, ri) => {
    svg.append('text')
      .attr('x', labelW).attr('y', matrixTop + ri * rowH + rowH / 2 + 3)
      .attr('font-size', 9).attr('text-anchor', 'end').attr('fill', '#6b7280')
      .text(src)
  })

  rows.forEach((row, i) => {
    const cx = labelW + 10 + x(i) + x.bandwidth() / 2
    const activeRis = SOURCE_ROWS
      .map((src, ri) => ({ ri, active: row.sources.includes(src) }))
      .filter(r => r.active)
      .map(r => r.ri)

    if (activeRis.length > 1) {
      const yTop = matrixTop + activeRis[0] * rowH + rowH / 2
      const yBot = matrixTop + activeRis[activeRis.length - 1] * rowH + rowH / 2
      svg.append('line')
        .attr('x1', cx).attr('x2', cx).attr('y1', yTop).attr('y2', yBot)
        .attr('stroke', '#374151').attr('stroke-width', 1.5)
    }

    SOURCE_ROWS.forEach((src, ri) => {
      const active = row.sources.includes(src)
      svg.append('circle')
        .attr('cx', cx).attr('cy', matrixTop + ri * rowH + rowH / 2)
        .attr('r', active ? activeR : inactiveR)
        .attr('fill', active ? '#374151' : '#e5e7eb')
        .style('cursor', 'default')
        .on('mousemove', (event) => showTooltip(event, row))
        .on('mouseleave', hideTooltip)
    })
  })
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
  hideTooltip()
})

watch(displayCombos, () => render(currentWidth), { deep: true })
</script>

<template>
  <section id="protein-overlap">
    <h2 class="text-lg font-semibold text-gray-800 mb-1">Protein overlap</h2>
    <p class="text-sm text-gray-600 mb-4">
      {{ formatCount(summary.proteins_multi_source) }} proteins ({{ pctMultiSource }}%)
      are reported by two or more sources; {{ formatCount(summary.proteins_single_source) }}
      by a single one. Overlap is not redundancy to be discarded, it is corroboration,
      and it is quantified here.
    </p>
    <div ref="containerRef" class="w-full">
      <svg style="display:block"></svg>
    </div>
    <p class="text-xs text-gray-500 mt-2">
      Top {{ displayCombos.length }} source combinations by protein count
      ({{ omittedCount }} smaller combinations, {{ formatCount(omittedProteins) }} proteins total, are omitted).
      Orange bars are multi-source combinations, gray is single-source.
    </p>

    <teleport to="body">
      <div
        ref="tooltipRef"
        style="display:none;position:fixed;pointer-events:none;z-index:9999;background:#1e293b;color:#f1f5f9;font-size:11px;padding:5px 8px;border-radius:6px;box-shadow:0 4px 12px rgba(0,0,0,0.25);white-space:nowrap;line-height:1.5;"
      ></div>
    </teleport>
  </section>
</template>
