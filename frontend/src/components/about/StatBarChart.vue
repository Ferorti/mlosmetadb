<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as d3 from 'd3'

const props = defineProps({
  data: { type: Array, required: true }, // [{ label, value, color }]
  valueLabel: { type: String, default: 'proteins' },
})

const containerRef = ref(null)
const tooltipRef = ref(null)
let resizeObserver = null
let currentWidth = 0

const BAR_HEIGHT = 22
const BAR_GAP = 10
const LABEL_WIDTH = 110
const VALUE_PADDING = 44

function showTooltip(event, d) {
  const tip = tooltipRef.value
  if (!tip) return
  tip.style.display = 'block'
  tip.style.left = (event.clientX + 14) + 'px'
  tip.style.top = (event.clientY - 28) + 'px'
  tip.textContent = `${d.label}: ${d.value.toLocaleString()} ${props.valueLabel}`
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

  const height = props.data.length * (BAR_HEIGHT + BAR_GAP)
  svg.attr('width', width).attr('height', height)
  svg.selectAll('*').remove()

  const chartWidth = Math.max(10, width - LABEL_WIDTH - VALUE_PADDING)
  const maxValue = d3.max(props.data, d => d.value) || 1
  const x = d3.scaleLinear().domain([0, maxValue]).range([0, chartWidth])

  const rows = svg.selectAll('g.row')
    .data(props.data)
    .enter()
    .append('g')
    .attr('class', 'row')
    .attr('transform', (d, i) => `translate(0, ${i * (BAR_HEIGHT + BAR_GAP)})`)
    .on('mousemove', showTooltip)
    .on('mouseleave', hideTooltip)

  // Full-width transparent hit area so the tooltip also triggers over the gap
  // between the label and the bar, not only over the drawn marks themselves.
  rows.append('rect')
    .attr('x', 0).attr('y', 0)
    .attr('width', width).attr('height', BAR_HEIGHT)
    .attr('fill', 'transparent')

  rows.append('text')
    .attr('x', LABEL_WIDTH - 8)
    .attr('y', BAR_HEIGHT / 2)
    .attr('text-anchor', 'end')
    .attr('dominant-baseline', 'middle')
    .attr('font-size', '12px')
    .attr('fill', '#484E59')
    .text(d => d.label)

  rows.append('rect')
    .attr('x', LABEL_WIDTH)
    .attr('y', 0)
    .attr('height', BAR_HEIGHT)
    .attr('width', d => x(d.value))
    .attr('rx', 3)
    .attr('fill', d => d.color || '#185FA5')

  rows.append('text')
    .attr('x', d => LABEL_WIDTH + x(d.value) + 8)
    .attr('y', BAR_HEIGHT / 2)
    .attr('dominant-baseline', 'middle')
    .attr('font-size', '12px')
    .attr('font-weight', '600')
    .attr('fill', '#1B3D6F')
    .text(d => d.value.toLocaleString())
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
  <div ref="containerRef" class="w-full">
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
</template>
