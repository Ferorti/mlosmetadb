<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as d3 from 'd3'

const props = defineProps({
  data: { type: Array, required: true }, // [{ label, value, color }]
  size: { type: Number, default: 160 },
  valueLabel: { type: String, default: 'proteins' },
  showLegend: { type: Boolean, default: true },
})

const containerRef = ref(null)
const tooltipRef = ref(null)
let resizeObserver = null
let currentWidth = 0

function showTooltip(event, d) {
  const tip = tooltipRef.value
  if (!tip) return
  tip.style.display = 'block'
  tip.style.left = (event.clientX + 14) + 'px'
  tip.style.top = (event.clientY - 28) + 'px'
  tip.textContent = `${d.data.label}: ${d.data.value.toLocaleString()} ${props.valueLabel}`
}

function hideTooltip() {
  if (tooltipRef.value) tooltipRef.value.style.display = 'none'
}

function render(width) {
  if (!containerRef.value || width < 10) return
  currentWidth = width

  const svg = d3.select(containerRef.value).select('svg')

  if (!props.data.length) {
    svg.attr('height', 0)
    svg.selectAll('*').remove()
    return
  }

  const size = Math.min(props.size, width)
  const radius = size / 2
  const innerRadius = radius * 0.6

  svg.attr('width', width).attr('height', size)
  svg.selectAll('*').remove()

  const g = svg.append('g').attr('transform', `translate(${width / 2}, ${size / 2})`)

  const pie = d3.pie().value(d => d.value).sort(null)
  const arc = d3.arc().innerRadius(innerRadius).outerRadius(radius)

  const total = d3.sum(props.data, d => d.value)

  g.selectAll('path')
    .data(pie(props.data))
    .enter()
    .append('path')
    .attr('d', arc)
    .attr('fill', d => d.data.color || '#185FA5')
    .on('mousemove', showTooltip)
    .on('mouseleave', hideTooltip)

  g.append('text')
    .attr('text-anchor', 'middle')
    .attr('dominant-baseline', 'middle')
    .attr('font-size', '20px')
    .attr('font-weight', '700')
    .attr('fill', '#1B3D6F')
    .text(total.toLocaleString())
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

watch(() => props.data, () => render(currentWidth), { deep: true })
</script>

<template>
  <div class="flex flex-col items-center gap-2">
    <div ref="containerRef" class="w-full flex justify-center">
      <svg style="display:block; overflow:visible"></svg>
    </div>
    <div v-if="showLegend" class="flex flex-wrap justify-center gap-x-4 gap-y-1 text-xs">
      <div v-for="d in data" :key="d.label" class="flex items-center gap-1.5">
        <span class="w-2.5 h-2.5 rounded-full inline-block" :style="{ backgroundColor: d.color }"></span>
        <span class="text-gray-600">{{ d.label }} ({{ d.value.toLocaleString() }})</span>
      </div>
    </div>
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
</template>
