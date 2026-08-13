<script setup>
import { ref, watch, onMounted, onUnmounted, computed } from 'vue'
import * as d3 from 'd3'
import { formatCount } from '@/utils/format'

const props = defineProps({
  terms:   { type: Array,  required: true },  // f3_vocab_collapse
  summary: { type: Object, required: true },
})

const BUCKETS = [
  { label: '1', test: n => n === 1 },
  { label: '2', test: n => n === 2 },
  { label: '3', test: n => n === 3 },
  { label: '4-5', test: n => n >= 4 && n <= 5 },
  { label: '6-10', test: n => n >= 6 && n <= 10 },
  { label: '11+', test: n => n >= 11 },
]

const histogram = computed(() => {
  return BUCKETS.map(b => ({
    label: b.label,
    count: props.terms.filter(t => b.test(t.n_source_names)).length,
  }))
})

const topTerms = computed(() => {
  return [...props.terms].sort((a, b) => b.n_source_names - a.n_source_names).slice(0, 10)
})

const containerRef = ref(null)
let resizeObserver = null
let currentWidth = 0

function render(width) {
  if (!containerRef.value || width < 10) return
  currentWidth = width

  const halfW = (width - 24) / 2
  const barH = 18
  const gap = 6
  const histoH = histogram.value.length * (barH + gap)
  const topH = topTerms.value.length * (barH + gap)
  const height = Math.max(histoH, topH) + 20

  const svg = d3.select(containerRef.value).select('svg')
  svg.attr('width', width).attr('height', height)
  svg.selectAll('*').remove()

  // Left: histogram
  const left = svg.append('g')
  left.append('text').attr('x', 0).attr('y', 12).attr('font-size', 11).attr('font-weight', 600).attr('fill', '#374151')
    .text('Source names collapsed per unified term')
  const leftLabelW = Math.min(30, Math.max(18, halfW * 0.1))
  const maxHisto = d3.max(histogram.value, h => h.count) || 1
  const xHisto = d3.scaleLinear().domain([0, maxHisto]).range([0, halfW - leftLabelW - 30])
  histogram.value.forEach((h, i) => {
    const y = 22 + i * (barH + gap)
    left.append('text').attr('x', 0).attr('y', y + barH - 5).attr('font-size', 11).attr('fill', '#374151').text(h.label)
    left.append('rect').attr('x', leftLabelW).attr('y', y).attr('width', Math.max(1, xHisto(h.count))).attr('height', barH)
      .attr('rx', 3).attr('fill', '#2a78d6')
    left.append('text').attr('x', leftLabelW + Math.max(1, xHisto(h.count)) + 6).attr('y', y + barH - 5)
      .attr('font-size', 11).attr('fill', '#374151').text(h.count)
  })

  // Right: top 10 terms
  const right = svg.append('g').attr('transform', `translate(${halfW + 24}, 0)`)
  right.append('text').attr('x', 0).attr('y', 12).attr('font-size', 11).attr('font-weight', 600).attr('fill', '#374151')
    .text('Top 10 terms by source names absorbed')
  const rightLabelW = Math.min(140, Math.max(60, halfW * 0.4))
  const maxTop = d3.max(topTerms.value, t => t.n_source_names) || 1
  const xTop = d3.scaleLinear().domain([0, maxTop]).range([0, halfW - rightLabelW - 40])
  topTerms.value.forEach((t, i) => {
    const y = 22 + i * (barH + gap)
    right.append('text').attr('x', 0).attr('y', y + barH - 5).attr('font-size', 10).attr('fill', '#374151')
      .text(t.unified_mlo.replace(/_/g, ' '))
    right.append('rect').attr('x', rightLabelW).attr('y', y).attr('width', Math.max(1, xTop(t.n_source_names))).attr('height', barH)
      .attr('rx', 3).attr('fill', '#1baf7a')
    right.append('text').attr('x', rightLabelW + Math.max(1, xTop(t.n_source_names)) + 6).attr('y', y + barH - 5)
      .attr('font-size', 10).attr('fill', '#374151').text(t.n_source_names)
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

watch(() => props.terms, () => render(currentWidth), { deep: true })
</script>

<template>
  <section id="mlo-vocabulary">
    <h2 class="text-lg font-semibold text-gray-800 mb-1">MLO vocabulary</h2>
    <p class="text-sm text-gray-600 mb-4">
      {{ formatCount(summary.n_source_entries) }} source entries were mapped onto
      {{ formatCount(summary.n_unified_mlo_terms) }} unified terms
      ({{ summary.collapse_ratio }}× collapse). The full mapping is downloadable below.
    </p>
    <div ref="containerRef" class="w-full">
      <svg style="display:block"></svg>
    </div>
  </section>
</template>
