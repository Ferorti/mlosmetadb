<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as d3 from 'd3'

const props = defineProps({
  data: { type: Array, required: true }, // [{ label, value, color }]
})
const emit = defineEmits(['select'])

const containerRef = ref(null)
let resizeObserver = null
let currentWidth = 0

const BAR_HEIGHT = 22
const BAR_GAP = 10
const LABEL_WIDTH = 110
const VALUE_PADDING = 44

function render(width) {
  if (!containerRef.value || width < 10 || !props.data.length) return
  currentWidth = width

  const height = props.data.length * (BAR_HEIGHT + BAR_GAP)
  const svg = d3.select(containerRef.value).select('svg')
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
    .style('cursor', 'pointer')
    .on('click', (event, d) => emit('select', d.label))

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
})

watch(() => props.data, () => render(currentWidth), { deep: true })
</script>

<template>
  <div ref="containerRef" class="w-full">
    <svg style="display:block; overflow:visible"></svg>
  </div>
</template>
