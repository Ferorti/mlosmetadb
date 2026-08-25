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
// Sized for the full-width band. IDR and Domain fill the background band at
// the same height; LCD nests inside IDR, both centered on CENTER_Y. MoRF
// keeps its own thin height and sits above the band as a separate strip
// (its y is pinned to stay clear of the band top, not derived from it), so
// LCD/MoRF still need their own vertical bounds for hit-testing.
const TRACK_HEIGHT = 66
const CENTER_Y = 40
const BG_Y = CENTER_Y - 15         // 25 -- matches IDR/Domain's h/2 below
const BG_H = 30

const LAYERS = {
  IDR:    { y: CENTER_Y - 15, h: 30, textFill: '#3F1710' },
  LCD:    { y: CENTER_Y - 9,  h: 18, textFill: '#ffffff' },
  Domain: { y: CENTER_Y - 15, h: 30, textFill: '#ffffff' },
  MoRF:   { y: CENTER_Y - 25, h: 7,  textFill: '#3B2A52' },
}

const LABEL_SIZE  = 12
const LINE_HEIGHT = 13
const MIN_CHARS = 3

// Truncates `str` to the longest prefix (plus an ellipsis) that measures
// <= avail px, using `node`'s actual rendered width -- a character-count
// estimate under/overshoots depending on how wide the glyphs in that word
// actually are, which is what produced overflowing and mid-word-truncated
// labels before this measured the real SVG text length.
function truncateToWidth(node, str, avail) {
  node.textContent = str
  if (node.getComputedTextLength() <= avail) return str
  let lo = 0, hi = str.length
  while (lo < hi) {
    const mid = Math.ceil((lo + hi) / 2)
    node.textContent = str.slice(0, mid) + '…'
    if (node.getComputedTextLength() <= avail) lo = mid
    else hi = mid - 1
  }
  return lo >= MIN_CHARS ? str.slice(0, lo) + '…' : null
}

// Greedily fits whole words onto the first line; a single word wider than
// `avail` on its own is hard-broken by character instead of overflowing.
function fitFirstLine(node, label, avail) {
  const words = label.split(' ')
  let line = ''
  let i = 0
  for (; i < words.length; i++) {
    const attempt = line ? `${line} ${words[i]}` : words[i]
    node.textContent = attempt
    if (node.getComputedTextLength() <= avail) {
      line = attempt
    } else {
      if (!line) { line = truncateToWidth(node, words[i], avail) ?? ''; i++ }
      break
    }
  }
  return { line, rest: words.slice(i).join(' ') }
}

// Splits a label into up to two lines that fit `avail` px width, measured
// against the real font metrics via `node` (a live, attached SVG <text>).
// The second line is ellipsis-truncated if it still doesn't fit.
function wrapLabel(node, label, avail) {
  if (!label) return []
  node.textContent = label
  if (node.getComputedTextLength() <= avail) return [label]
  const { line: line1, rest } = fitFirstLine(node, label, avail)
  if (!line1) return []
  if (!rest) return [line1]
  const line2 = truncateToWidth(node, rest, avail)
  return line2 ? [line1, line2] : [line1]
}

// Only domains and LCDs carry an in-track label, and only when the rect is
// wide enough for a domain's.
function spanLabel(span, widthPx) {
  if (span.type === 'Domain' && widthPx <= 40) return null
  if (span.type === 'Domain' || span.type === 'LCD') return span.label
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
    .attr('fill', '#F7F9FC')
    .attr('stroke', '#DFE4EC')
    .attr('stroke-width', 1)
    .attr('rx', 2)

  // Hidden text node used only to measure real glyph widths for wrapLabel()
  // -- removed once every span has been laid out.
  const measureNode = svg.append('text')
    .attr('font-size', `${LABEL_SIZE}px`).attr('font-weight', '600')
    .attr('font-family', 'ui-sans-serif, system-ui, sans-serif')
    .attr('visibility', 'hidden')
    .node()

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

    const lines = wrapLabel(measureNode, spanLabel(span, rw), Math.max(0, rw - 8))
    if (lines.length) {
      const cy = layer.y + layer.h / 2
      const startY = lines.length === 1 ? cy : cy - LINE_HEIGHT / 2
      const text = g.append('text')
        .attr('text-anchor', 'middle')
        .attr('fill', layer.textFill)
        .attr('font-size', `${LABEL_SIZE}px`).attr('font-weight', '600')
        .attr('font-family', 'ui-sans-serif, system-ui, sans-serif')
        .attr('pointer-events', 'none')
      lines.forEach((line, i) => {
        text.append('tspan')
          .attr('x', rx + rw / 2).attr('y', startY + i * LINE_HEIGHT)
          .attr('dominant-baseline', 'middle')
          .text(line)
      })
    }
  }

  measureNode.remove()

  // Residue marker, hidden until the sequence reports a position
  svg.append('line')
    .attr('class', 'residue-marker')
    .attr('y1', 4).attr('y2', TRACK_HEIGHT - 16)
    .attr('stroke', '#1560A8').attr('stroke-width', 1)
    .attr('pointer-events', 'none')
    .style('display', 'none')

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
      rect.attr('stroke', '#1560A8')
    } else if (props.hoveredId && id === props.hoveredId) {
      rect.attr('stroke', '#16181C')
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
