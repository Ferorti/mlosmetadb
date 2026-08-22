<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as d3 from 'd3'

const props = defineProps({
  sequenceLength: { type: Number, required: true },
  idrRegions:     { type: Array, default: () => [] },
  lcdRegions:     { type: Array, default: () => [] },
  domains:        { type: Array, default: () => [] },
  llpsRegions:    { type: Array, default: () => [] },
  compact:        { type: Boolean, default: false },
})

// ─── Visual constants ────────────────────────────────────────────────────────
const TRACK = {
  height:   34,
  baseline: { y: 16, color: '#DFE4EC', width: 1.5 },
  IDR:    { color: '#B8362B', h: 10, y: 12 },
  LCD:    { color: '#98A2B3', h: 18, y: 8 },
  DOMAIN: { color: '#2C7A6B', h: 18, y: 8 },
  LLPS:   { color: '#60A5FA', h: 4,  y: 30 },
}

const COMPACT = {
  height:   20,
  baseline: { y: 10, color: '#DFE4EC', width: 1.5 },
  IDR:    { color: '#B8362B', h: 7, y: 6 },
  LCD:    { color: '#98A2B3', h: 7, y: 4 },
  DOMAIN: { color: '#2C7A6B', h: 7, y: 6 },
}

const containerRef = ref(null)
const tooltipRef   = ref(null)
let resizeObserver = null
let currentWidth   = 0

function render(width) {
  if (!containerRef.value || width < 10) return
  currentWidth = width

  const t      = props.compact ? COMPACT : TRACK
  const height = t.height

  const svg = d3.select(containerRef.value).select('svg')
  svg.attr('width', width).attr('height', height)
  svg.selectAll('*').remove()

  const x = d3.scaleLinear().domain([0, props.sequenceLength]).range([0, width])

  // Baseline
  svg.append('line')
    .attr('x1', 0).attr('x2', width)
    .attr('y1', t.baseline.y).attr('y2', t.baseline.y)
    .attr('stroke', t.baseline.color)
    .attr('stroke-width', t.baseline.width)

  // IDR regions (bottom layer)
  props.idrRegions.forEach(r => drawRegion(svg, x, r, t.IDR))

  // LCD regions — disabled for now, data not yet populated
  // props.lcdRegions.forEach(r => drawRegion(svg, x, r, t.LCD))

  // Domain regions
  props.domains.forEach(r => drawRegion(svg, x, r, t.DOMAIN))

  // LLPS — disabled until data is available
  // props.llpsRegions.forEach(r => { ... })

  // Invisible hit area for tooltip
  svg.append('rect')
    .attr('width', width).attr('height', height)
    .attr('fill', 'transparent').attr('cursor', 'crosshair')
    .on('mousemove', (event) => onMouseMove(event, x))
    .on('mouseleave', hideTooltip)
}

function drawRegion(svg, x, region, style) {
  const rx = x(region.start)
  const rw = Math.max(2, x(region.end) - rx)
  const g  = svg.append('g')

  g.append('rect')
    .attr('x', rx).attr('y', style.y)
    .attr('width', rw).attr('height', style.h)
    .attr('fill', style.color).attr('rx', 3)

  // No in-bar text label -- see Task 2's rationale (LCD's fill fails
  // WCAG AA for overlaid text). Name/range is still available on hover
  // via the tooltip built in onMouseMove().
}

function onMouseMove(event, x) {
  const [mX] = d3.pointer(event)
  const aa   = Math.round(x.invert(mX))
  const hits = [
    ...props.idrRegions.filter(r => aa >= r.start && aa <= r.end)
      .map(r => ({ name: 'IDR', range: `${r.start}–${r.end}` })),
    ...props.lcdRegions.filter(r => aa >= r.start && aa <= r.end)
      .map(r => ({ name: r.label ?? 'LCD', range: `${r.start}–${r.end}` })),
    ...props.domains.filter(r => aa >= r.start && aa <= r.end)
      .map(r => ({ name: r.label, range: `${r.start}–${r.end}` })),
  ]

  if (!hits.length) { hideTooltip(); return }

  const tip = tooltipRef.value
  if (!tip) return
  tip.style.display = 'block'
  tip.style.left    = (event.clientX + 14) + 'px'
  tip.style.top     = (event.clientY - 28) + 'px'
  tip.innerHTML     = `
    <div style="color:#94a3b8;font-size:9px;margin-bottom:3px">pos ${aa} aa</div>
    ${hits.map(h =>
      `<div><span style="font-weight:600">${h.name}</span>: ${h.range}</div>`
    ).join('')}
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
  () => [props.sequenceLength, props.idrRegions, props.lcdRegions, props.domains, props.compact],
  () => render(currentWidth),
  { deep: true }
)
</script>

<template>
  <div ref="containerRef" class="w-full relative">
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
