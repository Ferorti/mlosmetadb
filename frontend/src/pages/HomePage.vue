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

// No `field` is emitted any more: a protein search always covers accession,
// gene name and protein name at once. Organelles are not searched here — the
// MLO grid below links straight to ?mlo=<slug>.
function handleSearch({ q, role, mode }) {
  if (!q) return
  const query = { q }
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
    <section class="bg-surface border-b border-border">
      <div class="max-w-[1080px] mx-auto px-8 pt-[70px] pb-9">

        <h1 class="font-display font-bold text-[52px] leading-[1.05] tracking-[-0.035em] text-ink max-w-[15ch]">
          Proteins in membraneless organelles
        </h1>
        <p class="mt-5 text-[17px] leading-relaxed text-ink2 max-w-[56ch]">
          A meta-database of proteins associated with membraneless organelles
          involved in liquid-liquid phase separation. Integrates proteins from
          PhaSepDB, DrLLPS, PhaSePro, LLPSDB and CD-CODE.
        </p>

        <div class="mt-[34px] max-w-[660px]">
          <SearchBox
            :show-search-options="true"
            :initial-query="''"
            @search="handleSearch"
          />
          <div class="flex items-center gap-3 mt-3 font-mono text-[11.5px] text-muted">
            <span>TRY</span>
            <button class="text-brand hover:text-ink hover:underline" @click="searchExample('FUS')">FUS</button>
            <button class="text-brand hover:text-ink hover:underline" @click="searchExample('P35637')">P35637</button>
          </div>
        </div>

      </div>
    </section>

    <!-- StatBar — flush below hero 
    <section class="max-w-4xl mx-auto px-6 py-4">
      <StatBar :stats="stats" />
    </section>
-->
    <div class=" mx-6 my-4"></div>

    <!-- Browse by role -->
    <section class="max-w-4xl mx-auto px-6 pb-5">
      <div class="flex items-baseline gap-3.5 border-b border-border pb-[11px] mb-5">
        <h2 class="font-sans text-[17px] font-medium tracking-[-0.01em] text-ink">Browse by component role</h2>
      </div>
      <p class="text-[13.5px] text-ink3 max-w-[64ch] mb-6">
        You can also reach proteins without naming one: pick the role they play across their annotations.
      </p>
      <RoleCards :stats="stats" />
    </section>

    <!-- Browse by MLO -->
    <section class="max-w-4xl mx-auto px-6 pb-10">
      <h2 class="text-base font-semibold text-[#1B3D6F] border-l-[3px] border-[#2B7CD8] pl-3 mb-1">
        Membraneless organelles (MLOs)
      </h2>
      <p class="text-sm text-gray-600 pl-3 mb-4">
        Or find proteins by the organelle they are associated with. The filter also reads the names
        each source database uses, so “GW-body” finds P body.
      </p>
      <MloBadges />
    </section>


    <!-- Browse by organism -->
    <section class="max-w-4xl mx-auto px-6 pb-10">
      <h2 class="text-base font-semibold text-[#1B3D6F] border-l-[3px] border-[#2B7CD8] pl-3 mb-4">
        Model organisms
      </h2>
      <OrganismGrid :stats="stats" />
    </section>

    <!-- Advanced search link 
    <section class="max-w-4xl mx-auto px-6 pb-12 text-center">
      <RouterLink
        to="/results"
        class="text-sm text-[#2B6CB0] font-medium hover:underline transition-colors"
      >
        Need complex queries? Try the Advanced Search →
      </RouterLink>
    </section>-->

  </div>
</template>
