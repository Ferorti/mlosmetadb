<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getStats } from '@/api/stats'
import StatBar from '@/components/ui/StatBar.vue'
import RoleCards from '@/components/browse/RoleCards.vue'
import MloBadges from '@/components/browse/MloBadges.vue'
import OrganismGrid from '@/components/browse/OrganismGrid.vue'
import SearchBox from '@/components/search/SearchBox.vue'
const router = useRouter()
const stats = ref(null)

onMounted(async () => {
  const res = await getStats()
  stats.value = res.data
})

function handleSearch({ q, field, role, mode }) {
  if (!q) return
  const query = { q }
  if (field && field !== 'all') query.field = field
  if (role)  query.role = role
  if (mode)  query.mode = mode
  router.push({ path: '/results', query })
}

function searchExample(term) {
  router.push({ path: '/results', query: { q: term, mode: 'fuzzy' } })
}
</script>

<template>
  <div class="bg-white">

    <!-- Hero + Search -->
    <section class="bg-gradient-to-b from-slate-100 to-white pt-8 pb-10 text-center">
      <div class="max-w-4xl mx-auto px-6">

        <div class="flex justify-center items-end gap-1.5 mb-4">
          <span class="w-4 h-4 rounded-full bg-[#4A9EDB]"></span>
          <span class="w-[22px] h-[22px] rounded-full bg-[#5BBF8E]"></span>
          <span class="w-3.5 h-3.5 rounded-full bg-[#3B7DD8]"></span>
        </div>

        <h1 class="text-3xl font-bold text-[#1B3D6F] tracking-tight">
          MLOsMetaDB
        </h1>
        <p class="text-gray-500 text-sm max-w-2xl mx-auto mt-2 leading-relaxed">
          A meta-database of proteins associated with membraneless organelles
          involved in liquid-liquid phase separation.
          Integrates <span class="font-medium text-gray-600">PhaseDB, DrLLPS, PhasePro, LLPSDB</span>
          and <span class="font-medium text-gray-600">CD-CODE</span>.
        </p>

        <div class="mt-6 max-w-3xl mx-auto w-full px-4">
          <SearchBox
            :show-search-options="true"
            :initial-query="''"
            :initial-field="'all'"
            @search="handleSearch"
          />
        </div>

        <div class="mt-2 text-xs text-gray-400">
          Examples:
          <button class="text-[#2B6CB0] hover:underline text-xs mx-1" @click="searchExample('FUS')">FUS</button>·
          <button class="text-[#2B6CB0] hover:underline text-xs mx-1" @click="searchExample('P35637')">P35637</button>·
          <button class="text-[#2B6CB0] hover:underline text-xs mx-1" @click="searchExample('Paraspeckle')">Paraspeckle</button>
        </div>

      </div>
    </section>

    <!-- StatBar — flush below hero -->
    <section class="max-w-4xl mx-auto px-6 py-4">
      <StatBar :stats="stats" />
    </section>

    <div class="border-t border-gray-100 mx-6 my-8"></div>

    <!-- Browse by role -->
    <section class="max-w-4xl mx-auto px-6 pb-10">
      <h2 class="text-base font-semibold text-[#1B3D6F] border-l-[3px] border-[#2B7CD8] pl-3 mb-4">
        Browse by component role
      </h2>
      <RoleCards :stats="stats" />
    </section>

    <div class="border-t border-gray-100 mx-6 my-8"></div>

    <!-- Browse by MLO -->
    <section class="max-w-4xl mx-auto px-6 pb-10">
      <h2 class="text-base font-semibold text-[#1B3D6F] border-l-[3px] border-[#2B7CD8] pl-3 mb-4">
        Browse by membraneless organelle
      </h2>
      <MloBadges />
    </section>

    <div class="border-t border-gray-100 mx-6 my-8"></div>

    <!-- Browse by organism -->
    <section class="max-w-4xl mx-auto px-6 pb-10">
      <h2 class="text-base font-semibold text-[#1B3D6F] border-l-[3px] border-[#2B7CD8] pl-3 mb-4">
        Browse by organism
      </h2>
      <OrganismGrid :stats="stats" />
    </section>

    <!-- Advanced search link -->
    <section class="max-w-4xl mx-auto px-6 pb-12 text-center">
      <RouterLink
        to="/results"
        class="text-sm text-[#2B6CB0] font-medium hover:underline transition-colors"
      >
        Need complex queries? Try the Advanced Search →
      </RouterLink>
    </section>

  </div>
</template>
