<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { RouterLink } from 'vue-router'
import * as d3 from 'd3'
import { formatCount } from '@/utils/format'

const props = defineProps({
  stats:   { type: Array,  required: true },  // f1_source_contribution
  summary: { type: Object, required: true },
})

// Fixed per-source_db color, reused across all three metric charts below.
// A bar for CDCODE is the same color in every one of the three panels.
const SOURCE_COLORS = {
  CDCODE: '#2a78d6',
  DrLLPS: '#eb6834',
  LLPSDB: '#1baf7a',
  PhaSepDB: '#eda100',
  PhasePro: '#e87ba4',
}

// One-line context per source so the chart is legible without leaving the
// page. Full descriptions and citations live on the About page instead of
// being duplicated here in full. Kept in sync with HomePage.vue's own
// SOURCE_BLURBS.
const SOURCE_BLURBS = [
  { key: 'CDCODE', name: 'CD-CODE', blurb: 'Crowdsourcing condensate database and encyclopedia.' },
  { key: 'DrLLPS', name: 'DrLLPS', blurb: 'Data resource of liquid-liquid phase separation.' },
  { key: 'LLPSDB', name: 'LLPSDB', blurb: 'Proteins undergoing liquid-liquid phase separation in vitro.' },
  { key: 'PhaSepDB', name: 'PhaSepDB', blurb: 'The comprehensive knowledgebase for protein phase separation and biomolecular condensates.' },
  { key: 'PhasePro', name: 'PhasePro', blurb: 'Comprehensive database of proteins driving liquid-liquid phase separation (LLPS) in living cells.' },
]

const METRICS = [
  { key: 'annotations', label: 'Annotations' },
  { key: 'proteins', label: 'Proteins' },
  { key: 'source_terms', label: 'MLO names' },
]

const annotationsRef = ref(null)
const proteinsRef = ref(null)
const sourceTermsRef = ref(null)
const REF_MAP = { annotations: annotationsRef, proteins: proteinsRef, source_terms: sourceTermsRef }

const tooltipRef = ref(null)
const resizeObservers = {}
const currentWidths = { annotations: 0, proteins: 0, source_terms: 0 }

function showTooltip(event, sourceDb, value) {
  const tip = tooltipRef.value
  if (!tip) return
  tip.style.display = 'block'
  tip.style.left = (event.clientX + 14) + 'px'
  tip.style.top = (event.clientY - 28) + 'px'
  tip.innerHTML = `<div style="font-weight:600">${sourceDb}</div><div>${value.toLocaleString()}</div>`
}

function hideTooltip() {
  if (tooltipRef.value) tooltipRef.value.style.display = 'none'
}

function renderMetric(metricKey, width) {
  const el = REF_MAP[metricKey].value
  if (!el || width < 10) return
  currentWidths[metricKey] = width

  const rows = [...props.stats].sort((a, b) => a.source_db.localeCompare(b.source_db))
  const barH = 22
  const gap = 8
  const labelW = 80
  const height = rows.length * (barH + gap)

  const svg = d3.select(el).select('svg')
  svg.attr('width', width).attr('height', height)
  svg.selectAll('*').remove()

  const maxVal = d3.max(rows, r => r[metricKey]) || 1
  const x = d3.scaleLinear().domain([0, maxVal]).range([0, Math.max(20, width - labelW - 50)])

  rows.forEach((row, i) => {
    const y = i * (barH + gap)
    const w = Math.max(1, x(row[metricKey]))
    svg.append('text').attr('x', 0).attr('y', y + barH - 7).attr('font-size', 10).attr('fill', '#374151').text(row.source_db)
    svg.append('rect')
      .attr('x', labelW).attr('y', y).attr('width', w).attr('height', barH - 4)
      .attr('rx', 3).attr('fill', SOURCE_COLORS[row.source_db] || '#9ca3af')
      .style('cursor', 'default')
      .on('mousemove', (event) => showTooltip(event, row.source_db, row[metricKey]))
      .on('mouseleave', hideTooltip)
    svg.append('text').attr('x', labelW + w + 6).attr('y', y + barH - 7).attr('font-size', 10).attr('fill', '#374151')
      .text(row[metricKey].toLocaleString())
  })
}

function renderAll() {
  METRICS.forEach(m => renderMetric(m.key, REF_MAP[m.key].value?.clientWidth ?? currentWidths[m.key]))
}

onMounted(() => {
  METRICS.forEach(m => {
    const el = REF_MAP[m.key].value
    if (!el) return
    const ro = new ResizeObserver(entries => {
      const w = entries[0].contentRect.width
      if (Math.abs(w - currentWidths[m.key]) > 2) renderMetric(m.key, w)
    })
    ro.observe(el)
    resizeObservers[m.key] = ro
    renderMetric(m.key, el.clientWidth)
  })
})

onUnmounted(() => {
  Object.values(resizeObservers).forEach(ro => ro?.disconnect())
  hideTooltip()
})

watch(() => props.stats, renderAll, { deep: true })
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

    <div class="grid grid-cols-1 sm:grid-cols-5 gap-3 mb-4 text-xs">
      <div v-for="src in SOURCE_BLURBS" :key="src.key">
        <div class="flex items-center gap-1.5">
          <span class="w-2 h-2 rounded-full inline-block" :style="{ backgroundColor: SOURCE_COLORS[src.key] }"></span>
          <span class="font-semibold text-gray-800">{{ src.name }}</span>
        </div>
        <p class="text-gray-500 mt-0.5">{{ src.blurb }}</p>
      </div>
    </div>
    <p class="text-xs text-gray-500 mb-4">
      Full descriptions and citations: <RouterLink to="/about#data-sources" class="text-[#185FA5] hover:underline">About page</RouterLink>.
    </p>

    <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
      <div>
        <p class="text-xs font-medium text-gray-500 mb-1">Annotations</p>
        <div ref="annotationsRef" class="w-full"><svg style="display:block"></svg></div>
      </div>
      <div>
        <p class="text-xs font-medium text-gray-500 mb-1">Proteins</p>
        <div ref="proteinsRef" class="w-full"><svg style="display:block"></svg></div>
      </div>
      <div>
        <p class="text-xs font-medium text-gray-500 mb-1">MLO names</p>
        <div ref="sourceTermsRef" class="w-full"><svg style="display:block"></svg></div>
      </div>
    </div>

    <p class="text-xs text-gray-500 mt-2">
      CD-CODE contributes 0 PMIDs: its evidence is condensate membership, not a per-annotation citation.
    </p>

    <teleport to="body">
      <div
        ref="tooltipRef"
        style="display:none;position:fixed;pointer-events:none;z-index:9999;background:#1e293b;color:#f1f5f9;font-size:11px;padding:5px 8px;border-radius:6px;box-shadow:0 4px 12px rgba(0,0,0,0.25);white-space:nowrap;line-height:1.5;"
      ></div>
    </teleport>
  </section>
</template>
