<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import * as d3 from 'd3'
import { formatCount } from '@/utils/format'

const props = defineProps({
  stats:   { type: Array,  required: true },  // f1_source_contribution
  summary: { type: Object, required: true },
})

const COLORS = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4']
const containerRef = ref(null)
let resizeObserver = null
let currentWidth = 0

const METRICS = [
  { key: 'annotations', label: 'Annotations' },
  { key: 'proteins', label: 'Proteins' },
  { key: 'source_terms', label: 'MLO names in source' },
]

function render(width) {
  if (!containerRef.value || width < 10) return
  currentWidth = width

  const rows = [...props.stats].sort((a, b) => a.source_db.localeCompare(b.source_db))
  const groupH = 90
  const height = rows.length * groupH
  const barH = 18
  const labelW = 90

  const svg = d3.select(containerRef.value).select('svg')
  svg.attr('width', width).attr('height', height)
  svg.selectAll('*').remove()

  const maxVal = d3.max(rows, r => Math.max(r.annotations, r.proteins, r.source_terms)) || 1
  const x = d3.scaleLinear().domain([0, maxVal]).range([0, width - labelW - 60])

  rows.forEach((row, i) => {
    const g = svg.append('g').attr('transform', `translate(0, ${i * groupH + 8})`)
    g.append('text')
      .attr('x', 0).attr('y', 14)
      .attr('font-size', 13).attr('font-weight', 600).attr('fill', '#1f2937')
      .text(row.source_db)

    METRICS.forEach((m, j) => {
      const y = 22 + j * (barH + 6)
      const w = Math.max(1, x(row[m.key]))
      g.append('text')
        .attr('x', 0).attr('y', y + barH - 5)
        .attr('font-size', 10).attr('fill', '#6b7280')
        .text(m.label)
      g.append('rect')
        .attr('x', labelW).attr('y', y)
        .attr('width', w).attr('height', barH)
        .attr('rx', 3)
        .attr('fill', COLORS[i % COLORS.length])
      g.append('text')
        .attr('x', labelW + w + 6).attr('y', y + barH - 5)
        .attr('font-size', 11).attr('fill', '#374151')
        .text(row[m.key].toLocaleString())
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

onUnmounted(() => resizeObserver?.disconnect())

watch(() => props.stats, () => render(currentWidth), { deep: true })
</script>

<template>
  <section id="sources">
    <h2 class="text-lg font-semibold text-gray-800 mb-1">Sources</h2>
    <p class="text-sm text-gray-600 mb-4">
      {{ formatCount(summary.n_annotations) }} annotations,
      {{ formatCount(summary.n_proteins) }} proteins,
      {{ formatCount(summary.n_unified_mlo_terms) }} unified MLO terms.
      Contributions are uneven: CD-CODE and DrLLPS supply most annotations,
      PhasePro and LLPSDB few but with in vitro evidence.
    </p>
    <div ref="containerRef" class="w-full">
      <svg style="display:block"></svg>
    </div>
    <p class="text-xs text-gray-500 mt-2">
      CD-CODE contributes 0 PMIDs — its evidence is condensate membership, not a per-annotation citation.
    </p>
  </section>
</template>
