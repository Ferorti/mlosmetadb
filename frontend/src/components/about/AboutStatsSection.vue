<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import StatBarChart from './StatBarChart.vue'
import StatDonutChart from './StatDonutChart.vue'
import AboutHeadlineStats from './AboutHeadlineStats.vue'
import { LLPS_SOURCES } from '@/data/aboutSources'
import { formatOrganism } from '@/utils/format'

const props = defineProps({
  stats: { type: Object, default: null }
})

const router = useRouter()

const SOURCE_COLORS = Object.fromEntries(LLPS_SOURCES.map(s => [s.name, s.color.text]))

const sourceData = computed(() => {
  if (!props.stats) return []
  const bySource = props.stats.mlo_annotations.unique_proteins_by_source ?? {}
  return Object.entries(bySource)
    .map(([label, value]) => ({ label, value, color: SOURCE_COLORS[label] || '#185FA5' }))
    .sort((a, b) => b.value - a.value)
})

const roleData = computed(() => {
  if (!props.stats) return []
  const r = props.stats.proteins.by_component_role ?? {}
  return [
    { label: 'Driver', value: r.driver ?? 0, color: '#185FA5' },
    { label: 'Component', value: r.component ?? 0, color: '#9CA3AF' },
  ]
})

const ORGANISM_COLORS = ['#185FA5', '#0F6E56', '#854F0B', '#B45309', '#6B21A8']
const ORGANISM_TOP_N = 5

const organismData = computed(() => {
  if (!props.stats) return []
  const sorted = Object.entries(props.stats.proteins.by_organism ?? {})
    .map(([key, value]) => ({ label: formatOrganism(key), key, value }))
    .sort((a, b) => b.value - a.value)

  const top = sorted.slice(0, ORGANISM_TOP_N).map((d, i) => ({ ...d, color: ORGANISM_COLORS[i] }))
  const rest = sorted.slice(ORGANISM_TOP_N)
  const othersValue = rest.reduce((sum, d) => sum + d.value, 0)

  if (othersValue > 0) {
    top.push({ label: 'Others', value: othersValue, color: '#9CA3AF', disabled: true })
  }
  return top
})

function goToRole(label) {
  const role = label === 'Driver' ? 'driver' : 'component'
  router.push({ path: '/results', query: { role } })
}

function goToOrganism(label) {
  router.push({ path: '/results', query: { organism: label } })
}
</script>

<template>
  <section id="stats" class="scroll-mt-28">
    <h2 class="text-lg font-semibold text-gray-800 mb-3">Data Statistics and Annotations</h2>

    <AboutHeadlineStats :stats="stats" class="mb-6" />

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div class="bg-white border border-gray-200 rounded-lg p-4">
        <div class="text-sm font-semibold text-gray-700 mb-3">Proteins by source database</div>
        <!-- No click-to-navigate here: "PhaSepDB" combines two distinct raw
             source_db tags (PhaseDB + PhasePDB), so it can't map to a single
             /results?source_db=... value -- see about-page design spec §2. -->
        <StatBarChart :data="sourceData" :clickable="false" />
      </div>

      <div class="bg-white border border-gray-200 rounded-lg p-4">
        <div class="text-sm font-semibold text-gray-700 mb-3">Driver vs. Component</div>
        <StatDonutChart :data="roleData" @select="goToRole" />
      </div>

      <div class="bg-white border border-gray-200 rounded-lg p-4">
        <div class="text-sm font-semibold text-gray-700 mb-3">Top organisms</div>
        <StatDonutChart :data="organismData" @select="goToOrganism" />
      </div>
    </div>
  </section>
</template>
