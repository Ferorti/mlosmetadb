<script setup>
import { ref, watch, onMounted, onUnmounted, computed } from 'vue'
import * as d3 from 'd3'
import { formatCount } from '@/utils/format'

const props = defineProps({
  combos:  { type: Array,  required: true },  // f2_protein_source_combos
  summary: { type: Object, required: true },
})

const TOP_N = 12
const displayCombos = computed(() => {
  const sorted = [...props.combos].sort((a, b) => b.n_proteins - a.n_proteins)
  if (sorted.length <= TOP_N) return sorted
  const top = sorted.slice(0, TOP_N)
  const otherCount = sorted.slice(TOP_N).reduce((sum, c) => sum + c.n_proteins, 0)
  return [...top, { combo_label: 'other', n_proteins: otherCount, n_sources: null }]
})

const pctMultiSource = computed(() => {
  if (!props.summary.n_proteins) return 0
  return Math.round((props.summary.proteins_multi_source / props.summary.n_proteins) * 100)
})

const containerRef = ref(null)
const tooltipRef = ref(null)
let resizeObserver = null
let currentWidth = 0

function showTooltip(event, label, value) {
  const tip = tooltipRef.value
  if (!tip) return
  tip.style.display = 'block'
  tip.style.left = (event.clientX + 14) + 'px'
  tip.style.top = (event.clientY - 28) + 'px'
  tip.innerHTML = `<div style="font-weight:600">${label}</div><div>${value.toLocaleString()} proteins</div>`
}

function hideTooltip() {
  if (tooltipRef.value) tooltipRef.value.style.display = 'none'
}

function render(width) {
  if (!containerRef.value || width < 10) return
  currentWidth = width

  const rows = displayCombos.value
  const barH = 20
  const gap = 6
  const labelW = 220
  const height = rows.length * (barH + gap)

  const svg = d3.select(containerRef.value).select('svg')
  svg.attr('width', width).attr('height', height)
  svg.selectAll('*').remove()

  const maxVal = d3.max(rows, r => r.n_proteins) || 1
  const x = d3.scaleLinear().domain([0, maxVal]).range([0, width - labelW - 60])

  rows.forEach((row, i) => {
    const y = i * (barH + gap)
    const isMulti = row.n_sources == null || row.n_sources >= 2
    svg.append('text')
      .attr('x', 0).attr('y', y + barH - 5)
      .attr('font-size', 11).attr('fill', '#374151')
      .text(row.combo_label)
    svg.append('rect')
      .attr('x', labelW).attr('y', y)
      .attr('width', Math.max(1, x(row.n_proteins))).attr('height', barH)
      .attr('rx', 3)
      .attr('fill', isMulti ? '#eb6834' : '#9ca3af')
      .style('cursor', 'default')
      .on('mousemove', (event) => showTooltip(event, row.combo_label, row.n_proteins))
      .on('mouseleave', hideTooltip)
    svg.append('text')
      .attr('x', labelW + Math.max(1, x(row.n_proteins)) + 6).attr('y', y + barH - 5)
      .attr('font-size', 11).attr('fill', '#374151')
      .text(row.n_proteins.toLocaleString())
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
      by a single one. Overlap is not redundancy to be discarded — it is corroboration,
      and it is quantified here.
    </p>
    <div ref="containerRef" class="w-full">
      <svg style="display:block"></svg>
    </div>
    <p class="text-xs text-gray-500 mt-2">
      Top 12 source combinations by protein count; the remaining combinations are summed into "other".
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
