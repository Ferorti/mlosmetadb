<script setup>
import { ref, watch, onMounted, onUnmounted, computed } from 'vue'
import * as d3 from 'd3'
import { formatCount } from '@/utils/format'

const props = defineProps({
  byMlo:       { type: Array,  required: true },  // f5b_discrepancy_by_mlo
  pmidOverlap: { type: Array,  required: true },  // f6_pmid_overlap_sources
  summary:     { type: Object, required: true },
})

const CONCORDANT_COLOR = '#1baf7a'
const DISCORDANT_COLOR = '#eb6834'

const pctConcordant = computed(() => {
  if (!props.summary.shared_pairs) return 0
  return Math.round((props.summary.concordant_pairs / props.summary.shared_pairs) * 100)
})
const pctDiscordant = computed(() => 100 - pctConcordant.value)
const pctIndependent = computed(() => {
  if (!props.summary.pairs_pmid_comparable) return 0
  return Math.round((props.summary.pairs_independent_pub / props.summary.pairs_pmid_comparable) * 100)
})

const topMlos = computed(() => [...props.byMlo].sort((a, b) => b.n_discordant - a.n_discordant).slice(0, 15))

const discPatterns = computed(() => {
  return Object.entries(props.summary.disc_patterns ?? {}).sort((a, b) => b[1] - a[1])
})

const containerRef = ref(null)
let resizeObserver = null
let currentWidth = 0

function render(width) {
  if (!containerRef.value || width < 10) return
  currentWidth = width

  const stackH = 40
  const barH = 18
  const gap = 6
  const labelW = 200
  const topH = topMlos.value.length * (barH + gap)
  const height = stackH + 20 + topH + 20

  const svg = d3.select(containerRef.value).select('svg')
  svg.attr('width', width).attr('height', height)
  svg.selectAll('*').remove()

  // F5 left: concordant/discordant stacked bar
  const total = props.summary.shared_pairs || 1
  const xStack = d3.scaleLinear().domain([0, total]).range([0, width])
  const concW = xStack(props.summary.concordant_pairs)
  svg.append('rect').attr('x', 0).attr('y', 0).attr('width', concW).attr('height', 24).attr('fill', CONCORDANT_COLOR)
  svg.append('rect').attr('x', concW).attr('y', 0).attr('width', width - concW).attr('height', 24).attr('fill', DISCORDANT_COLOR)
  svg.append('text').attr('x', 4).attr('y', 40).attr('font-size', 11).attr('fill', '#374151')
    .text(`Concordant: ${formatCount(props.summary.concordant_pairs)} (${pctConcordant.value}%)`)
  svg.append('text').attr('x', width - 4).attr('y', 40).attr('font-size', 11).attr('fill', '#374151').attr('text-anchor', 'end')
    .text(`Discordant: ${formatCount(props.summary.discordant_pairs)} (${pctDiscordant.value}%)`)

  // F5 right: top MLOs by discordant count
  const topY0 = stackH + 20
  svg.append('text').attr('x', 0).attr('y', topY0).attr('font-size', 11).attr('font-weight', 600).attr('fill', '#374151')
    .text('MLOs with the most discordant pairs')
  const maxDisc = d3.max(topMlos.value, m => m.n_discordant) || 1
  const xTop = d3.scaleLinear().domain([0, maxDisc]).range([0, width - labelW - 60])
  topMlos.value.forEach((m, i) => {
    const y = topY0 + 10 + i * (barH + gap)
    svg.append('text').attr('x', 0).attr('y', y + barH - 5).attr('font-size', 10).attr('fill', '#374151')
      .text(m.unified_mlo.replace(/_/g, ' '))
    svg.append('rect').attr('x', labelW).attr('y', y).attr('width', Math.max(1, xTop(m.n_discordant))).attr('height', barH)
      .attr('rx', 3).attr('fill', DISCORDANT_COLOR)
    svg.append('text').attr('x', labelW + Math.max(1, xTop(m.n_discordant)) + 6).attr('y', y + barH - 5)
      .attr('font-size', 10).attr('fill', '#374151').text(m.n_discordant)
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

watch(() => [props.byMlo, props.summary], () => render(currentWidth), { deep: true })
</script>

<template>
  <section id="agreement-discrepancy">
    <h2 class="text-lg font-semibold text-gray-800 mb-1">Agreement &amp; discrepancy</h2>
    <p class="text-sm text-gray-600 mb-4">
      Of {{ formatCount(summary.shared_pairs) }} protein–MLO pairs annotated by more
      than one source, {{ pctConcordant }}% receive the same category from all of
      them and {{ formatCount(summary.discordant_pairs) }} ({{ pctDiscordant }}%) do
      not. Discrepancies concentrate in the best-studied MLOs, where more sources
      have an opinion. All discordant pairs are listed below, with the role each
      source assigns and its evidence type. MLOsMetaDB does not arbitrate: it shows
      both claims.
    </p>
    <div ref="containerRef" class="w-full mb-6">
      <svg style="display:block"></svg>
    </div>

    <div class="flex flex-wrap gap-x-6 gap-y-1 text-xs text-gray-600 mb-6">
      <span v-for="[pattern, count] in discPatterns" :key="pattern">
        {{ pattern.split('|').join(' vs. ') }}: {{ formatCount(count) }}
      </span>
    </div>

    <p class="text-sm text-gray-600 mb-3">
      <strong>Evidence.</strong> {{ formatCount(summary.unique_pmids) }} unique PMIDs
      back the annotations. Where two sources annotate the same protein–MLO pair and
      both cite literature, {{ pctIndependent }}% cite different publications — the
      agreement is mostly independent, not the same paper propagated across
      databases. CD-CODE is excluded from this comparison: it records condensate
      membership without a per-annotation citation. {{ formatCount(summary.pairs_shared_pub) }}
      pairs share at least one publication.
    </p>

    <div class="overflow-x-auto">
      <table class="w-full text-sm border border-gray-200 rounded-lg">
        <thead>
          <tr class="bg-gray-50 text-left text-xs text-gray-500 uppercase tracking-wide">
            <th class="px-3 py-2">Source A</th>
            <th class="px-3 py-2">Source B</th>
            <th class="px-3 py-2 text-right">PMIDs (A)</th>
            <th class="px-3 py-2 text-right">PMIDs (B)</th>
            <th class="px-3 py-2 text-right">Shared</th>
            <th class="px-3 py-2 text-right">Jaccard</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in pmidOverlap" :key="`${row.db_a}-${row.db_b}`" class="border-t border-gray-100">
            <td class="px-3 py-2">{{ row.db_a }}</td>
            <td class="px-3 py-2">{{ row.db_b }}</td>
            <td class="px-3 py-2 text-right">{{ formatCount(row.n_a) }}</td>
            <td class="px-3 py-2 text-right">{{ formatCount(row.n_b) }}</td>
            <td class="px-3 py-2 text-right">{{ formatCount(row.shared) }}</td>
            <td class="px-3 py-2 text-right">{{ row.jaccard }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
