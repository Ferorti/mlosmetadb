<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import * as d3 from 'd3'
import { formatSource } from '@/composables/useProteinFeatures.js'

const props = defineProps({
  spans:          { type: Array,  required: true },   // from useProteinFeatures().featureSpans
  sequenceLength: { type: Number, required: true },
  hoveredId:      { type: String, default: null },
  pinnedId:       { type: String, default: null },
  residuePos:     { type: Number, default: null },    // vertical marker, driven by sequence hover
})

const emit = defineEmits(['hover', 'select'])

// ─── SVG geometry — all layers share a single centerY ────────────────────────
// Sized for the full-width band. The layers are nested rather than stacked, so
// their heights have to stay ordered Domain > IDR > LCD or an inner one hides:
// LCD sits inside IDR, and both sit inside the domain bar.
const TRACK_HEIGHT = 88
const CENTER_Y = 40
const BG_Y = CENTER_Y - 11         // 29
const BG_H = 22

const LAYERS = {
  IDR:    { y: CENTER_Y - 10, h: 20, textFill: '#7F1D1D' },
  LCD:    { y: CENTER_Y - 6,  h: 12, textFill: '#7C2D12' },
  Domain: { y: CENTER_Y - 14, h: 28, textFill: '#ffffff' },
  MoRF:   { y: CENTER_Y - 21, h: 7,  textFill: '#6B21A8' },
}

const LABEL_SIZE = 12
// Truncation budget for the in-track labels. Keep it proportional to
// LABEL_SIZE — undersizing it lets labels overflow their rectangle.
const CHAR_W = LABEL_SIZE * 0.65
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

// Only domains carry an in-track label, and only when the rect is wide enough.
function spanLabel(span, widthPx) {
  if (span.type === 'Domain' && widthPx > 40) return span.label
  if (span.type === 'LCD') return 'Low complexity region'
  return null
}

// ─── D3 rendering ────────────────────────────────────────────────────────────
const containerRef = ref(null)
const tooltipRef   = ref(null)
let resizeObserver = null
let currentWidth   = 0
let xScale         = null

function render(width) {
  if (!containerRef.value || width < 10) return
  currentWidth = width

  const svg = d3.select(containerRef.value).select('svg')
  svg.attr('width', width).attr('height', TRACK_HEIGHT)
  svg.selectAll('*').remove()

  if (!props.sequenceLength) return

  const x = d3.scaleLinear().domain([0, props.sequenceLength]).range([0, width])
  xScale = x

  // Background bar — outlined only, visually distinct from data
  svg.append('rect')
    .attr('x', 0).attr('y', BG_Y)
    .attr('width', width).attr('height', BG_H)
    .attr('fill', '#F8FAFC')
    .attr('stroke', '#E2E8F0')
    .attr('stroke-width', 1)
    .attr('rx', 2)

  // Feature spans — props.spans is already in paint order
  const regions = svg.append('g').attr('class', 'regions')
  for (const span of props.spans) {
    const layer = LAYERS[span.type]
    if (!layer) continue
    const rx = x(span.start)
    const rw = Math.max(2, x(span.end) - rx)
    const g = regions.append('g')
      .attr('class', 'region')
      .attr('data-feature-id', span.featureId)

    g.append('rect')
      .attr('x', rx).attr('y', layer.y)
      .attr('width', rw).attr('height', layer.h)
      .attr('fill', span.color).attr('rx', 2)
      .attr('stroke', 'none')
      .attr('stroke-width', 2)

    const fitted = fitLabel(spanLabel(span, rw), rw)
    if (fitted) {
      g.append('text')
        .attr('x', rx + rw / 2).attr('y', layer.y + layer.h / 2)
        .attr('text-anchor', 'middle').attr('dominant-baseline', 'middle')
        .attr('fill', layer.textFill)
        .attr('font-size', `${LABEL_SIZE}px`).attr('font-weight', '600')
        .attr('font-family', 'ui-sans-serif, system-ui, sans-serif')
        .attr('pointer-events', 'none')
        .text(fitted)
    }
  }

  // Residue marker, hidden until the sequence reports a position
  svg.append('line')
    .attr('class', 'residue-marker')
    .attr('y1', 4).attr('y2', TRACK_HEIGHT - 16)
    .attr('stroke', '#185FA5').attr('stroke-width', 1)
    .attr('pointer-events', 'none')
    .style('display', 'none')

  // Sequence length label
  svg.append('text')
    .attr('x', width - 2).attr('y', TRACK_HEIGHT - 6)
    .attr('text-anchor', 'end')
    .attr('fill', '#484E59')
    .attr('font-size', '11px')
    .attr('font-family', 'ui-sans-serif, system-ui, sans-serif')
    .text(`${props.sequenceLength} aa`)

  // One transparent hit area for the whole track: overlapping spans are resolved
  // by paint order (topmost wins), which per-rect hit areas cannot do.
  svg.append('rect')
    .attr('width', width).attr('height', TRACK_HEIGHT)
    .attr('fill', 'transparent').attr('cursor', 'pointer')
    .on('mousemove', onMouseMove)
    .on('mouseleave', onMouseLeave)
    .on('click', onClick)

  applyActive()
  applyMarker()
}

/** Every span covering a residue, regardless of where it is drawn vertically. */
function spansAt(aa) {
  return props.spans.filter(s => aa >= s.start && aa <= s.end)
}

/**
 * The span actually under the cursor. Horizontal position alone is not enough:
 * the MoRF strip and the domain bar routinely cover the same residues at
 * different heights, and an x-only test would make the strip drawn on top
 * unreachable for every residue it spans.
 */
function hitAt(aa, my) {
  const hits = spansAt(aa).filter(s => {
    const layer = LAYERS[s.type]
    return layer && my >= layer.y && my <= layer.y + layer.h
  })
  return hits.length ? hits[hits.length - 1] : null   // props.spans is in paint order
}

function pointFromEvent(event) {
  if (!xScale) return null
  const [mX, mY] = d3.pointer(event)
  return {
    aa: Math.max(1, Math.min(props.sequenceLength, Math.round(xScale.invert(mX)))),
    y: mY,
  }
}

function onMouseMove(event) {
  const p = pointFromEvent(event)
  if (!p) return
  const top = hitAt(p.aa, p.y)
  emit('hover', top ? top.featureId : null)

  // The tooltip still lists everything at that residue, including layers the
  // cursor is not over — that is the informative part.
  const hits = spansAt(p.aa)
  if (!hits.length) { hideTooltip(); return }
  showTooltip(event, p.aa, hits)
}

function onMouseLeave() {
  emit('hover', null)
  hideTooltip()
}

function onClick(event) {
  const p = pointFromEvent(event)
  if (!p) return
  const top = hitAt(p.aa, p.y)
  emit('select', top ? top.featureId : null)
}

// ─── Active-state styling, applied without re-rendering the whole track ──────
function applyActive() {
  if (!containerRef.value) return
  d3.select(containerRef.value).selectAll('g.region').each(function () {
    const id = this.getAttribute('data-feature-id')
    const rect = d3.select(this).select('rect')
    if (props.pinnedId && id === props.pinnedId) {
      rect.attr('stroke', '#185FA5')
    } else if (props.hoveredId && id === props.hoveredId) {
      rect.attr('stroke', '#1e293b')
    } else {
      rect.attr('stroke', 'none')
    }
  })
}

function applyMarker() {
  if (!containerRef.value || !xScale) return
  const line = d3.select(containerRef.value).select('line.residue-marker')
  if (line.empty()) return
  if (props.residuePos == null) {
    line.style('display', 'none')
    return
  }
  const px = xScale(props.residuePos)
  line.attr('x1', px).attr('x2', px).style('display', null)
}

// ─── Tooltip ─────────────────────────────────────────────────────────────────
function showTooltip(event, aa, hits) {
  const tip = tooltipRef.value
  if (!tip) return
  tip.style.display = 'block'
  tip.style.left    = (event.clientX + 14) + 'px'
  tip.style.top     = (event.clientY - 28) + 'px'
  tip.innerHTML     = `
    <div style="color:#94a3b8;font-size:9px;margin-bottom:3px">pos ${aa} aa</div>
    ${hits.map(h => `
      <div>
        <span style="font-weight:600">${h.type}</span>${h.label && h.label !== h.type ? ': ' + h.label : ''}
        <span style="color:#94a3b8"> ${h.start}–${h.end}</span>
        ${h.source ? `<span style="color:#64748b;font-size:9px"> · ${formatSource(h.source)}</span>` : ''}
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
  hideTooltip()
})

watch(() => [props.spans, props.sequenceLength], () => render(currentWidth), { deep: true })
watch(() => [props.hoveredId, props.pinnedId], applyActive)
watch(() => props.residuePos, applyMarker)
</script>

<template>
  <div ref="containerRef" class="w-full relative">
    <svg style="display:block; overflow:visible"></svg>

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
  </div>
</template>
