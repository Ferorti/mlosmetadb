<script setup>
import { ref, onMounted } from 'vue'
import { getStats } from '@/api/stats'
import AboutStatsSection from '@/components/about/AboutStatsSection.vue'
import DataSourcesSection from '@/components/about/DataSourcesSection.vue'
import HowToUseCarousel from '@/components/about/HowToUseCarousel.vue'
import CitationsSection from '@/components/about/CitationsSection.vue'

const stats = ref(null)

onMounted(async () => {
  try {
    const res = await getStats()
    stats.value = res.data
  } catch {
    stats.value = null
  }
})

const NAV = [
  { id: 'stats', label: 'Statistics' },
  { id: 'data-sources', label: 'Data Sources' },
  { id: 'how-to-use', label: 'How to Use' },
  { id: 'citations', label: 'Citations' },
]
</script>

<template>
  <div class="max-w-6xl mx-auto px-6 py-8">
    <div class="mb-6">
      <h1 class="text-2xl font-semibold text-gray-800">About MLOsMetaDB</h1>
      <p class="text-sm text-gray-600 mt-1">Statistics, data sources, usage guide, and citations.</p>
    </div>

    <nav class="sticky top-14 z-10 bg-white border-b border-gray-200 mb-8 flex gap-6 text-sm">
      <a
        v-for="item in NAV"
        :key="item.id"
        :href="`#${item.id}`"
        class="py-2 text-[#484E59] hover:text-[#185FA5] border-b-2 border-transparent hover:border-[#185FA5] transition-colors"
      >{{ item.label }}</a>
    </nav>

    <AboutStatsSection :stats="stats" />
    <DataSourcesSection />
    <HowToUseCarousel />
    <CitationsSection />
  </div>
</template>
