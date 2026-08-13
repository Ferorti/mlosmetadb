<script setup>
import { ref, watch, onMounted, onUnmounted, computed } from 'vue'
import * as d3 from 'd3'

const props = defineProps({
  roles:   { type: Array,  required: true },  // f4_role_mapping
  summary: { type: Object, required: true },
})

const CATEGORY_COLOR = { driver: '#2a78d6', regulator: '#eb6834', component: '#1baf7a' }
const CATEGORY_ORDER = ['driver', 'regulator', 'component']

const grouped = computed(() => {
  return CATEGORY_ORDER.map(cat => ({
    category: cat,
    rows: props.roles.filter(r => r.category === cat).sort((a, b) => b.annotations - a.annotations),
  })).filter(g => g.rows.length)
})

const containerRef = ref(null)
let resizeObserver = null
let currentWidth = 0

function render(width) {
  if (!containerRef.value || width < 10) return
  currentWidth = width

  const barH = 18
  const gap = 6
  const groupGap = 20
  const labelW = Math.min(260, Math.max(100, width * 0.4))
  let y = 10
  const groupYStarts = []
  grouped.value.forEach(g => {
    groupYStarts.push(y)
    y += g.rows.length * (barH + gap) + groupGap
  })
  const height = y

  const svg = d3.select(containerRef.value).select('svg')
  svg.attr('width', width).attr('height', height)
  svg.selectAll('*').remove()

  const maxVal = d3.max(props.roles, r => r.annotations) || 1
  const x = d3.scaleLinear().domain([0, maxVal]).range([0, width - labelW - 60])

  grouped.value.forEach((g, gi) => {
    const gy = groupYStarts[gi]
    svg.append('rect')
      .attr('x', 0).attr('y', gy - 10).attr('width', 8).attr('height', 8)
      .attr('rx', 2)
      .attr('fill', CATEGORY_COLOR[g.category])
    svg.append('text')
      .attr('x', 14).attr('y', gy).attr('font-size', 12).attr('font-weight', 700)
      .attr('fill', '#1f2937')
      .text(g.category)
    g.rows.forEach((row, i) => {
      const ry = gy + 14 + i * (barH + gap)
      const label = `${row.source_db} · ${row.source_role} (${row.evidence_type})`
      svg.append('text').attr('x', 0).attr('y', ry + barH - 5).attr('font-size', 10).attr('fill', '#374151').text(label)
      svg.append('rect').attr('x', labelW).attr('y', ry).attr('width', Math.max(1, x(row.annotations))).attr('height', barH)
        .attr('rx', 3).attr('fill', CATEGORY_COLOR[g.category])
      svg.append('text').attr('x', labelW + Math.max(1, x(row.annotations)) + 6).attr('y', ry + barH - 5)
        .attr('font-size', 10).attr('fill', '#374151').text(row.annotations.toLocaleString())
    })
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

watch(() => props.roles, () => render(currentWidth), { deep: true })
</script>

<template>
  <section id="role-harmonisation">
    <h2 class="text-lg font-semibold text-gray-800 mb-1">Role harmonisation</h2>
    <p class="text-sm text-gray-600 mb-4">
      Sources use {{ roles.length }} source-specific role mappings backed by different
      kinds of evidence, mapped onto three categories: <strong>driver</strong> (drives phase separation),
      <strong>regulator</strong> (modulates it without being a constituent driver),
      <strong>component</strong> (present in the MLO, with no driver or regulator
      evidence assigned by any source). "Component" is used in the restricted sense
      of this third class — drivers and regulators are of course also components of
      the condensate. A "client" label in one source and no role in another often
      reflects each database's curation policy rather than different experimental
      evidence, which is why the third category isn't called "client".
    </p>
    <div ref="containerRef" class="w-full">
      <svg style="display:block"></svg>
    </div>
  </section>
</template>
