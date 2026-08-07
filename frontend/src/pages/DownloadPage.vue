<script setup>
import { ref, computed, watch } from 'vue'
import { searchOrganisms, buildExportUrl, getProteins } from '@/api/proteins'

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
</script>

<template>
  <div class="max-w-6xl mx-auto px-6 py-8">
    <!-- Page header -->
    <div class="mb-6">
      <h1 class="text-2xl font-semibold text-gray-800">Download</h1>
      <p class="text-sm text-gray-600 mt-1">Export a filtered slice of the protein dataset.</p>
    </div>

    <div class="bg-white border border-gray-200 rounded-lg px-4 py-4 space-y-5 max-w-2xl">
      <!-- Organism filter -->
      <div>
        <label class="text-xs font-semibold text-gray-700 uppercase tracking-wide block mb-1.5">Organism</label>

        <!-- Default/closed state: reads like a <select>, defaults to "All organisms" -->
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

        <!-- Editing state: All organisms, then search, then model organisms as quick picks -->
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
  </div>
</template>
