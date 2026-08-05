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
  baseline: { y: 16, color: '#e2e8f0', width: 1.5 },
  IDR:    { color: '#f4d3d3', h: 10, y: 12, textColor: '#7F1D1D' },
  LCD:    { color: '#FAC775', h: 18, y: 8,  textColor: '#7C2D12' },
  DOMAIN: { color: '#acc7ff', h: 18, y: 8,  textColor: '#ffffff' },
  LLPS:   { color: '#60A5FA', h: 4,  y: 30 },
}

const COMPACT = {
  height:   20,
  baseline: { y: 10, color: '#e2e8f0', width: 1.5 },
  IDR:    { color: '#f4d3d3', h: 7,  y: 6, textColor: '#7F1D1D' },
  LCD:    { color: '#FAC775', h: 7, y: 4, textColor: '#7C2D12' },
  DOMAIN: { color: '#bed1f9', h: 7, y: 6, textColor: '#ffffff' },
}

const CHAR_WIDTH = 6.5
const MIN_CHARS  = 4

function fitLabel(label, availableWidth) {
  if (!label) return null
  const fullWidth = label.length * CHAR_WIDTH + 8
  if (fullWidth <= availableWidth) return label

  for (let len = label.length - 1; len >= MIN_CHARS; len--) {
    const truncated  = label.slice(0, len) + '…'
    const truncWidth = truncated.length * CHAR_WIDTH + 8
    if (truncWidth <= availableWidth) return truncated
  }

  return null
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

  // IDR regions (bottom layer) — never show labels
  props.idrRegions.forEach(r => drawRegion(svg, x, r, t.IDR, null))

  // LCD regions — disabled for now, data not yet populated
  // props.lcdRegions.forEach(r => drawRegion(svg, x, r, t.LCD, r.label ?? 'LCD'))

  // Domain regions — labels only in full mode
  props.domains.forEach(r => drawRegion(svg, x, r, t.DOMAIN, props.compact ? null : r.label))

  // LLPS — disabled until data is available
  // props.llpsRegions.forEach(r => { ... })

  // Invisible hit area for tooltip
  svg.append('rect')
    .attr('width', width).attr('height', height)
    .attr('fill', 'transparent').attr('cursor', 'crosshair')
    .on('mousemove', (event) => onMouseMove(event, x))
    .on('mouseleave', hideTooltip)
}

function drawRegion(svg, x, region, style, label) {
  const rx = x(region.start)
  const rw = Math.max(2, x(region.end) - rx)
  const g  = svg.append('g')

  g.append('rect')
    .attr('x', rx).attr('y', style.y)
    .attr('width', rw).attr('height', style.h)
    .attr('fill', style.color).attr('rx', 3)

  if (label) {
    const fitted = fitLabel(label, rw)
    if (fitted) {
      g.append('text')
        .attr('x', rx + rw / 2).attr('y', style.y + style.h / 2)
        .attr('text-anchor', 'middle').attr('dominant-baseline', 'middle')
        .attr('fill', style.textColor)
        .attr('font-size', '10.5px').attr('font-weight', '600')
        .attr('font-family', 'ui-sans-serif, system-ui, sans-serif')
        .text(fitted)
    }
  }
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
