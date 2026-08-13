<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { searchOrganisms, buildExportUrl, getProteins } from '@/api/proteins'
import { getUnificationStats } from '@/api/unification'
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

// ── Download form (moved here from the retired /download page) ───────────────
const MODEL_ORGANISMS = [
  'Homo sapiens',
  'Mus musculus',
  'Arabidopsis thaliana',
  'Caenorhabditis elegans',
  'Saccharomyces cerevisiae',
  'Xenopus laevis',
  'Bos taurus',
  'Drosophila melanogaster',
  'Rattus norvegicus',
]

const organism = ref('')
const organismEditing = ref(false)
const orgSearch = ref('')
const orgSearchResults = ref([])
const role = ref('')
const fields = ref('full')
const format = ref('tsv')

const matchCount = ref(null)
const countLoading = ref(false)

const showAllOrganismsOption = computed(() => {
  const q = orgSearch.value.trim().toLowerCase()
  return !q || 'all organisms'.includes(q)
})

const filteredModelOrganisms = computed(() => {
  const q = orgSearch.value.trim().toLowerCase()
  if (!q) return MODEL_ORGANISMS
  return MODEL_ORGANISMS.filter(name => name.toLowerCase().includes(q))
})

async function onOrganismSearch() {
  if (orgSearch.value.length < 3) {
    orgSearchResults.value = []
    return
  }
  try {
    const res = await searchOrganisms(orgSearch.value)
    orgSearchResults.value = res.data.results ?? []
  } catch {
    orgSearchResults.value = []
  }
}

function openOrganismEditor() {
  organismEditing.value = true
}

function closeOrganismEditor() {
  organismEditing.value = false
  orgSearch.value = ''
  orgSearchResults.value = []
}

function selectOrganism(name) {
  organism.value = name
  closeOrganismEditor()
}

function selectAllOrganisms() {
  organism.value = ''
  closeOrganismEditor()
}

async function refreshCount() {
  countLoading.value = true
  try {
    const params = { per_page: 1 }
    if (organism.value) params.organism = organism.value
    if (role.value) params.role = role.value
    const res = await getProteins(params)
    matchCount.value = res.data.total
  } catch {
    matchCount.value = null
  } finally {
    countLoading.value = false
  }
}

watch([organism, role], refreshCount, { immediate: true })

const downloadUrl = computed(() => buildExportUrl({
  organism: organism.value || null,
  role: role.value || null,
  fields: fields.value,
  format: format.value,
}))

function download() {
  window.location.href = downloadUrl.value
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
    <div class="mb-8">
      <h1 class="text-2xl font-semibold text-gray-800">Data</h1>
      <p class="text-sm text-gray-600 mt-1">Download the dataset, and see how it was assembled from five source databases.</p>
    </div>

    <!-- ── Download ──────────────────────────────────────────────────────── -->
    <section class="mb-12">
      <h2 class="text-lg font-semibold text-gray-800 mb-1">Download</h2>
      <p class="text-sm text-gray-600 mb-4">Export a filtered slice of the protein dataset.</p>

      <div class="bg-white border border-gray-200 rounded-lg px-4 py-4 space-y-5 max-w-2xl">
        <!-- Organism filter -->
        <div>
          <label class="text-xs font-semibold text-gray-700 uppercase tracking-wide block mb-1.5">Organism</label>

          <button
            v-if="!organismEditing"
            @click="openOrganismEditor"
            class="w-full flex items-center justify-between text-sm border border-gray-200 rounded px-2 py-1.5 bg-white hover:border-[#185FA5] transition-colors text-left"
          >
            <span :class="organism ? 'text-gray-800' : 'text-gray-500'">{{ organism || 'All organisms' }}</span>
            <svg class="w-3.5 h-3.5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          <div v-else class="border border-gray-200 rounded">
            <div class="px-2.5 pt-1.5 pb-1">
              <input
                v-model="orgSearch"
                type="text"
                placeholder="Search organisms…"
                class="w-full text-sm border border-gray-200 rounded px-2 py-1 focus:outline-none focus:border-[#185FA5]"
                @input="onOrganismSearch"
                autofocus
              />
            </div>
            <div class="max-h-64 overflow-y-auto pb-1">
              <div
                v-if="showAllOrganismsOption"
                class="px-2.5 py-1.5 cursor-pointer hover:bg-[#EBF3FB] text-sm font-medium text-gray-700"
                @click="selectAllOrganisms"
              >
                All organisms
              </div>

              <template v-if="filteredModelOrganisms.length">
                <div class="px-2.5 pt-1.5 pb-1 text-[10px] font-semibold text-gray-400 uppercase tracking-wide border-t border-gray-100 mt-1">
                  Model organisms
                </div>
                <div
                  v-for="name in filteredModelOrganisms"
                  :key="name"
                  class="px-2.5 py-1.5 cursor-pointer hover:bg-[#EBF3FB] text-sm text-gray-600"
                  @click="selectOrganism(name)"
                >
                  <em>{{ name }}</em>
                </div>
              </template>

              <template v-if="orgSearch.length >= 3">
                <div
                  v-for="result in orgSearchResults"
                  :key="result.organism"
                  class="flex items-center justify-between px-2.5 py-1.5 cursor-pointer hover:bg-[#EBF3FB] text-sm text-gray-600"
                  @click="selectOrganism(result.organism)"
                >
                  <span>{{ result.organism }}</span>
                  <span class="text-xs text-gray-500">{{ result.protein_count }}</span>
                </div>
                <div v-if="orgSearchResults.length === 0" class="text-xs text-gray-500 px-2.5 py-1">No organisms found.</div>
              </template>
            </div>
            <div class="border-t border-gray-100 px-2.5 py-1 text-right">
              <button @click="closeOrganismEditor" class="text-xs text-gray-500 hover:text-gray-700">Close</button>
            </div>
          </div>
        </div>

        <!-- Role filter -->
        <div>
          <label class="text-xs font-semibold text-gray-700 uppercase tracking-wide block mb-1.5">LLPS role</label>
          <select v-model="role" class="text-sm text-gray-700 border border-gray-200 rounded px-2 py-1.5 bg-white focus:outline-none focus:border-[#185FA5]">
            <option value="">All roles</option>
            <option value="driver">Drivers only</option>
            <option value="component">Non-drivers</option>
          </select>
        </div>

        <!-- Fields -->
        <div>
          <label class="text-xs font-semibold text-gray-700 uppercase tracking-wide block mb-1.5">Fields</label>
          <div class="flex gap-4 text-sm text-gray-700">
            <label class="flex items-center gap-1.5 cursor-pointer">
              <input type="radio" value="basic" v-model="fields" class="accent-[#185FA5]" />
              Standard (identity, MLOs, LLPS role, source)
            </label>
            <label class="flex items-center gap-1.5 cursor-pointer">
              <input type="radio" value="full" v-model="fields" class="accent-[#185FA5]" />
              Extended annotations (+ IDRs, domains, LCRs)
            </label>
          </div>
        </div>

        <!-- Format -->
        <div>
          <label class="text-xs font-semibold text-gray-700 uppercase tracking-wide block mb-1.5">Format</label>
          <div class="flex gap-4 text-sm text-gray-700">
            <label class="flex items-center gap-1.5 cursor-pointer">
              <input type="radio" value="tsv" v-model="format" class="accent-[#185FA5]" />
              TSV
            </label>
            <label class="flex items-center gap-1.5 cursor-pointer">
              <input type="radio" value="json" v-model="format" class="accent-[#185FA5]" />
              JSON
            </label>
          </div>
        </div>

        <!-- Download button -->
        <div class="pt-2 flex items-center justify-end gap-3">
          <p class="text-xs text-gray-500">
            <span v-if="countLoading">Counting…</span>
            <span v-else-if="matchCount != null">{{ matchCount.toLocaleString() }} proteins match these filters</span>
          </p>
          <button
            @click="download"
            class="inline-flex items-center px-4 py-2 rounded bg-[#185FA5] text-white text-sm font-medium hover:bg-[#0F4A87] transition-colors"
          >
            Download
          </button>
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

      <div v-else class="space-y-6">
        <div class="bg-white border border-gray-200 rounded-lg p-4">
          <SourcesSection :stats="stats.f1_source_contribution" :summary="stats.summary" />
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <div class="bg-white border border-gray-200 rounded-lg p-4">
            <ProteinOverviewSection :combos="stats.f2_protein_source_combos" :summary="stats.summary" />
          </div>
          <div class="bg-white border border-gray-200 rounded-lg p-4">
            <VocabularySection :terms="stats.f3_vocab_collapse" :summary="stats.summary" />
          </div>
          <div class="bg-white border border-gray-200 rounded-lg p-4">
            <RoleHarmonisationSection :roles="stats.f4_role_mapping" :summary="stats.summary" />
          </div>
        </div>

        <div class="bg-white border border-gray-200 rounded-lg p-4">
          <AgreementSection :by-mlo="stats.f5b_discrepancy_by_mlo" :pmid-overlap="stats.f6_pmid_overlap_sources" :summary="stats.summary" />
        </div>

        <div class="bg-white border border-gray-200 rounded-lg p-4">
          <MloTermMappingTable />
        </div>

        <p class="text-xs text-gray-400 text-right">
          db commit {{ stats.meta.code_commit?.slice(0, 7) }} · built {{ stats.meta.build_date?.slice(0, 10) }}
        </p>
      </div>
    </section>
  </div>
</template>
