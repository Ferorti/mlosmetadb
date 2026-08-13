<script setup>
import { ref, onMounted } from 'vue'
import { buildExportUrl } from '@/api/proteins'
import { getUnificationStats } from '@/api/unification'
import { formatCount } from '@/utils/format'
import LoadingSpinner from '@/components/ui/LoadingSpinner.vue'
import SourcesSection from '@/components/unification/SourcesSection.vue'
import ProteinOverviewSection from '@/components/unification/ProteinOverviewSection.vue'
import VocabularySection from '@/components/unification/VocabularySection.vue'
import RoleHarmonisationSection from '@/components/unification/RoleHarmonisationSection.vue'
import AgreementSection from '@/components/unification/AgreementSection.vue'
import MloTermMappingTable from '@/components/unification/MloTermMappingTable.vue'
// DiscrepantPairsTable exists at ./DiscrepantPairsTable.vue but is not rendered
// yet -- hidden pending manual review, per explicit request. Do not remove the
// file, just don't import/render it here until that review happens.

// ── Download (simplified to a one-click full-dataset export -- no filters) ───
function fullDatasetUrl(fmt) {
  return buildExportUrl({ fields: 'full', format: fmt })
}

// ── Data sources (moved here from the retired /unification page) ─────────────
const stats = ref(null)
const loading = ref(true)
const unavailable = ref(false)
const error = ref(false)

onMounted(async () => {
  try {
    stats.value = await getUnificationStats()
  } catch (err) {
    if (err.response?.status === 503) {
      unavailable.value = true
    } else {
      error.value = true
    }
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="max-w-6xl mx-auto px-6 py-8">


    <!-- ── Download ──────────────────────────────────────────────────────── -->
    <section class="mb-12">
      <div class="flex items-center justify-between flex-wrap gap-3 mb-1">
        <h2 class="text-lg font-semibold text-gray-800">Download MLOsMetaDB full dataset</h2>
        <div class="flex gap-2">
          <a
            :href="fullDatasetUrl('json')"
            class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-[#185FA5] text-white text-sm font-medium hover:bg-[#0F4A87] transition-colors"
          >
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
            </svg>
            JSON
          </a>
          <a
            :href="fullDatasetUrl('tsv')"
            class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-[#185FA5] text-white text-sm font-medium hover:bg-[#0F4A87] transition-colors"
          >
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
            </svg>
            TSV
          </a>
        </div>
      </div>
      <p class="text-sm text-gray-600 mb-3">Every protein in MLOsMetaDB, with full annotations — no filters applied.</p>

      <div class="flex divide-x divide-gray-200 border border-gray-200 rounded-lg max-w-md text-center">
        <div class="flex-1 px-4 py-2">
          <div class="text-lg font-semibold text-gray-800">{{ stats ? formatCount(stats.summary.n_proteins) : '—' }}</div>
          <div class="text-xs text-gray-500">Proteins</div>
        </div>
        <div class="flex-1 px-4 py-2">
          <div class="text-lg font-semibold text-gray-800">{{ stats ? formatCount(stats.summary.n_annotations) : '—' }}</div>
          <div class="text-xs text-gray-500">Annotations</div>
        </div>
        <div class="flex-1 px-4 py-2">
          <div class="text-lg font-semibold text-gray-800">{{ stats ? formatCount(stats.summary.n_unified_mlo_terms) : '—' }}</div>
          <div class="text-xs text-gray-500">MLOs</div>
        </div>
      </div>
    </section>

    <!-- ── Data sources ──────────────────────────────────────────────────── -->
    <section>
      <h2 class="text-lg font-semibold text-gray-800 mb-1">Data sources</h2>
      <p class="text-sm text-gray-600 mb-4">
        MLOsMetaDB merges five primary resources into a single annotation table.
        This section reports how the merge was done and where the sources diverge.
      </p>

      <LoadingSpinner v-if="loading" />

      <div v-else-if="unavailable" class="bg-white border border-gray-200 rounded-lg p-8 text-center text-gray-600">
        This section isn't available yet.
      </div>

      <div v-else-if="error" class="bg-white border border-gray-200 rounded-lg p-8 text-center text-gray-600">
        Something went wrong loading this section. Try refreshing the page.
      </div>

      <div v-else class="divide-y divide-gray-200">
        <div class="py-6 first:pt-0">
          <SourcesSection :stats="stats.f1_source_contribution" :summary="stats.summary" />
        </div>

        <div class="py-6">
          <ProteinOverviewSection :combos="stats.f2_protein_source_combos" :summary="stats.summary" />
        </div>

        <div class="py-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-1 gap-6">
          <div>
            <VocabularySection :terms="stats.f3_vocab_collapse" :summary="stats.summary" />
          </div>
          <div>
            <RoleHarmonisationSection :roles="stats.f4_role_mapping" :summary="stats.summary" />
          </div>
        </div>

        <div class="py-6">
          <AgreementSection :by-mlo="stats.f5b_discrepancy_by_mlo" :pmid-overlap="stats.f6_pmid_overlap_sources" :summary="stats.summary" />
        </div>

        <div class="py-6">
          <MloTermMappingTable />
        </div>

        <p class="text-xs text-gray-400 text-right pt-4">
          db commit {{ stats.meta.code_commit?.slice(0, 7) }} · built {{ stats.meta.build_date?.slice(0, 10) }}
        </p>
      </div>
    </section>
  </div>
</template>
