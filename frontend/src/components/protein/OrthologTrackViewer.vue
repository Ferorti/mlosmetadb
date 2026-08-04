<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as d3 from 'd3'

/**
 * Multi-protein normalized sequence feature viewer for ortholog comparison.
 * Each track is scaled independently to fill the same pixel width,
 * so feature positions are comparable as fractions of total length.
 *
 * Props:
 *   tracks: Array of {
 *     id: String,
 *     organism: String,
 *     geneLabel: String,
 *     length: Number,
 *     idrs: [{start, end}],
 *     lcds: [{start, end}],
 *     domains: [{start, end, label, accession}],
 *     morfs: [{start, end}],
 *     isReference: Boolean,
 *   }
 */
const props = defineProps({
  tracks: { type: Array, required: true },
})

// ── Layout constants ───────────────────────────────────────────────────────────
const LABEL_W  = 152
const ROW_H    = 32
const ROW_GAP  = 6
const HEADER_H = 22

const CENTER_Y = ROW_H / 2

// Feature layers (y, h relative to each row's top edge)
const LAYER = {
  IDR:  { y: CENTER_Y - 7,  h: 14, fill: '#F5A0A0' },
  LCD:  { y: CENTER_Y - 3,  h:  6, fill: '#FAC775' },
  DOM:  { y: CENTER_Y - 9,  h: 18, fill: '#86C865', textFill: '#fff' },
  MORF: { y: 0,             h:  4, fill: '#C4B5FD' },
}

const BG_Y = CENTER_Y - 7
const BG_H = 14

const CHAR_W   = 5.5
const MIN_CHARS = 3

const ORGANISM_ABBREV = {
  'Homo sapiens':             'H. sapiens',
  'Mus musculus':             'M. musculus',
  'Danio rerio':              'D. rerio',
  'Drosophila melanogaster':  'D. melanogaster',
  'Caenorhabditis elegans':   'C. elegans',
  'Saccharomyces cerevisiae': 'S. cerevisiae',
  'Arabidopsis thaliana':     'A. thaliana',
  'Dictyostelium discoideum': 'D. discoideum',
  'Escherichia coli K-12':    'E. coli K-12',
}

function abbrev(org) {
  return ORGANISM_ABBREV[org] ?? org ?? '—'
}

function fitLabel(label, avail) {
  if (!label) return null
  if (label.length * CHAR_W + 6 <= avail) return label
  for (let len = label.length - 1; len >= MIN_CHARS; len--) {
    const t = label.slice(0, len) + '…'
    if (t.length * CHAR_W + 6 <= avail) return t
  }
  return null
}

// ── D3 rendering ───────────────────────────────────────────────────────────────
const containerRef = ref(null)
const tooltipRef   = ref(null)
let resizeObserver = null
let currentWidth   = 0

function totalH() {
  return HEADER_H + props.tracks.length * (ROW_H + ROW_GAP)
}

function render(width) {
  if (!containerRef.value || width < 10 || !props.tracks.length) return
  currentWidth = width

  const svg = d3.select(containerRef.value).select('svg')
  svg.attr('width', width).attr('height', totalH())
  svg.selectAll('*').remove()

  const trackW = Math.max(10, width - LABEL_W)

  // ── Legend ────────────────────────────────────────────────────────────────
  const legend = [
    { label: 'IDR',    fill: '#F5A0A0' },
    { label: 'LCD',    fill: '#FAC775' },
    { label: 'Domain', fill: '#86C865' },
    { label: 'MoRF',   fill: '#C4B5FD' },
  ]
  let lx = LABEL_W
  legend.forEach(item => {
    svg.append('rect')
      .attr('x', lx).attr('y', HEADER_H - 13)
      .attr('width', 8).attr('height', 8)
      .attr('fill', item.fill).attr('rx', 1)
    svg.append('text')
      .attr('x', lx + 11).attr('y', HEADER_H - 6)
      .attr('fill', '#484E59').attr('font-size', '9px')
      .attr('font-family', 'ui-sans-serif, system-ui, sans-serif')
      .text(item.label)
    lx += item.label.length * 5.8 + 20
  })

  // ── Rows ──────────────────────────────────────────────────────────────────
  props.tracks.forEach((track, i) => {
    const rowY = HEADER_H + i * (ROW_H + ROW_GAP)
    const g = svg.append('g').attr('transform', `translate(0, ${rowY})`)

    // Reference highlight
    if (track.isReference) {
      g.append('rect')
        .attr('x', 0).attr('y', 0)
        .attr('width', width).attr('height', ROW_H)
        .attr('fill', '#EBF3FB').attr('rx', 2)
    }

    // ── Label area ──────────────────────────────────────────────────────────
    // organism (italic)
    g.append('text')
      .attr('x', LABEL_W - 10).attr('y', CENTER_Y - 4)
      .attr('text-anchor', 'end').attr('dominant-baseline', 'middle')
      .attr('fill', track.isReference ? '#185FA5' : '#484E59')
      .attr('font-size', '9px').attr('font-style', 'italic')
      .attr('font-family', 'ui-sans-serif, system-ui, sans-serif')
      .text(abbrev(track.organism))

    // gene / id
    g.append('text')
      .attr('x', LABEL_W - 10).attr('y', CENTER_Y + 7)
      .attr('text-anchor', 'end').attr('dominant-baseline', 'middle')
      .attr('fill', track.isReference ? '#185FA5' : '#1f2937')
      .attr('font-size', '10px')
      .attr('font-weight', track.isReference ? '700' : '600')
      .attr('font-family', 'ui-monospace, monospace')
      .text(track.geneLabel)

    // ── Track area ──────────────────────────────────────────────────────────
    const tg = g.append('g').attr('transform', `translate(${LABEL_W}, 0)`)

    if (!track.length) {
      // no data
      tg.append('text')
        .attr('x', trackW / 2).attr('y', CENTER_Y)
        .attr('text-anchor', 'middle').attr('dominant-baseline', 'middle')
        .attr('fill', '#cbd5e1').attr('font-size', '9px')
        .attr('font-family', 'ui-sans-serif, system-ui, sans-serif')
        .text('no data')
      return
    }

    const x = d3.scaleLinear().domain([0, track.length]).range([0, trackW])

    // background bar
    tg.append('rect')
      .attr('x', 0).attr('y', BG_Y)
      .attr('width', trackW).attr('height', BG_H)
      .attr('fill', '#F8FAFC').attr('stroke', '#E2E8F0')
      .attr('stroke-width', 0.5).attr('rx', 2)

    // IDRs
    track.idrs.forEach(r => drawFeat(tg, x, r, LAYER.IDR, null))

    // LCDs
    track.lcds.forEach(r => drawFeat(tg, x, r, LAYER.LCD, null))

    // Domains
    track.domains.forEach(r => {
      const pw = Math.max(2, x(r.end) - x(r.start))
      drawFeat(tg, x, r, LAYER.DOM, pw > 36 ? r.label : null)
    })

    // MoRFs
    track.morfs.forEach(r => drawFeat(tg, x, r, LAYER.MORF, null))

    // length label
    tg.append('text')
      .attr('x', trackW - 2).attr('y', ROW_H - 3)
      .attr('text-anchor', 'end')
      .attr('fill', '#94a3b8').attr('font-size', '8px')
      .attr('font-family', 'ui-sans-serif, system-ui, sans-serif')
      .text(`${track.length} aa`)

    // invisible hit area for tooltip
    tg.append('rect')
      .attr('x', 0).attr('y', 0)
      .attr('width', trackW).attr('height', ROW_H)
      .attr('fill', 'transparent').attr('cursor', 'crosshair')
      .on('mousemove', (event) => showTooltip(event, x, track))
      .on('mouseleave', hideTooltip)
  })
}

function drawFeat(g, x, region, layer, label) {
  const rx = x(region.start)
  const rw = Math.max(2, x(region.end) - rx)
  const fg = g.append('g')

  fg.append('rect')
    .attr('x', rx).attr('y', layer.y)
    .attr('width', rw).attr('height', layer.h)
    .attr('fill', layer.fill).attr('rx', 1)

  if (label && layer.textFill) {
    const fitted = fitLabel(label, rw)
    if (fitted) {
      fg.append('text')
        .attr('x', rx + rw / 2).attr('y', layer.y + layer.h / 2)
        .attr('text-anchor', 'middle').attr('dominant-baseline', 'middle')
        .attr('fill', layer.textFill)
        .attr('font-size', '9px').attr('font-weight', '600')
        .attr('font-family', 'ui-sans-serif, system-ui, sans-serif')
        .text(fitted)
    }
  }
}

function showTooltip(event, x, track) {
  const [mX] = d3.pointer(event)
  const aa = Math.round(x.invert(mX))

  const hits = [
    ...track.idrs.filter(r => aa >= r.start && aa <= r.end)
      .map(r => ({ type: 'IDR', range: `${r.start}–${r.end}`, label: null })),
    ...track.lcds.filter(r => aa >= r.start && aa <= r.end)
      .map(r => ({ type: 'LCD', range: `${r.start}–${r.end}`, label: null })),
    ...track.domains.filter(r => aa >= r.start && aa <= r.end)
      .map(r => ({ type: 'Domain', range: `${r.start}–${r.end}`, label: r.label })),
    ...track.morfs.filter(r => aa >= r.start && aa <= r.end)
      .map(r => ({ type: 'MoRF', range: `${r.start}–${r.end}`, label: null })),
  ]

  const tip = tooltipRef.value
  if (!tip) return
  tip.style.display = 'block'
  tip.style.left = (event.clientX + 14) + 'px'
  tip.style.top  = (event.clientY - 28) + 'px'
  tip.innerHTML = `
    <div style="color:#94a3b8;font-size:9px;margin-bottom:3px">
      <em>${abbrev(track.organism)}</em> &nbsp;pos ${aa} aa
    </div>
    ${hits.length
      ? hits.map(h => `
          <div>
            <span style="font-weight:600">${h.type}</span>${h.label ? ': ' + h.label : ''}
            <span style="color:#94a3b8"> ${h.range}</span>
          </div>`).join('')
      : '<div style="color:#64748b;font-size:9px">—</div>'
    }
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

watch(() => props.tracks, () => render(currentWidth), { deep: true })
</script>

<template>
  <div ref="containerRef" class="w-full">
    <svg style="display: block; overflow: visible;"></svg>
  </div>

  <teleport to="body">
    <div
      ref="tooltipRef"
      style="
        display: none; position: fixed; pointer-events: none; z-index: 9999;
        background: #1e293b; color: #f1f5f9; font-size: 11px;
        font-family: ui-monospace, monospace;
        padding: 6px 10px; border-radius: 6px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.25);
        white-space: nowrap; line-height: 1.6;
      "
    ></div>
  </teleport>
</template>
