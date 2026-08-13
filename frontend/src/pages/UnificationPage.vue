<script setup>
import { ref, onMounted } from 'vue'
import { getUnificationStats } from '@/api/unification'
import LoadingSpinner from '@/components/ui/LoadingSpinner.vue'

const stats = ref(null)
const loading = ref(true)
const unavailable = ref(false)

onMounted(async () => {
  try {
    stats.value = await getUnificationStats()
  } catch (err) {
    if (err.response?.status === 503) {
      unavailable.value = true
    } else {
      throw err
    }
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="max-w-6xl mx-auto px-6 py-8">
    <div class="mb-6">
      <h1 class="text-2xl font-semibold text-gray-800">Data unification</h1>
      <p class="text-sm text-gray-600 mt-1">
        MLOsMetaDB merges five primary resources into a single annotation table.
        This section reports how the merge was done and where the sources diverge.
      </p>
    </div>

    <LoadingSpinner v-if="loading" />

    <div v-else-if="unavailable" class="bg-white border border-gray-200 rounded-lg p-8 text-center text-gray-600">
      This section isn't available yet.
    </div>

    <div v-else class="space-y-10">
      <!-- TASK 2: <SourcesSection :stats="stats.f1_source_contribution" :summary="stats.summary" /> -->
      <!-- TASK 2: <ProteinOverviewSection :combos="stats.f2_protein_source_combos" :summary="stats.summary" /> -->
      <!-- TASK 3: <VocabularySection :terms="stats.f3_vocab_collapse" :summary="stats.summary" /> -->
      <!-- TASK 3: <RoleHarmonisationSection :roles="stats.f4_role_mapping" :summary="stats.summary" /> -->
      <!-- TASK 4: <AgreementSection :by-mlo="stats.f5b_discrepancy_by_mlo" :pmid-overlap="stats.f6_pmid_overlap_sources" :summary="stats.summary" /> -->
      <!-- TASK 5: <DiscrepantPairsTable /> -->
      <!-- TASK 6: <MloTermMappingTable /> -->

      <p class="text-xs text-gray-400 text-right">
        db commit {{ stats.meta.code_commit?.slice(0, 7) }} · built {{ stats.meta.build_date?.slice(0, 10) }}
      </p>
    </div>
  </div>
</template>
