<script setup>
import { ref, computed } from 'vue'
import { searchOrganisms, buildExportUrl } from '@/api/proteins'

const SOURCE_DBS = ['PhaseDB', 'PhasePDB', 'DrLLPS', 'LLPSDB', 'PhasePro', 'CDCODE']

const organism = ref('')
const orgSearch = ref('')
const orgSearchResults = ref([])
const role = ref('')
const selectedSources = ref([])
const fields = ref('full')
const format = ref('tsv')

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

function selectOrganism(name) {
  organism.value = name
  orgSearch.value = ''
  orgSearchResults.value = []
}

function clearOrganism() {
  organism.value = ''
}

function toggleSourceDb(db) {
  selectedSources.value = selectedSources.value.includes(db)
    ? selectedSources.value.filter(d => d !== db)
    : [...selectedSources.value, db]
}

const downloadUrl = computed(() => buildExportUrl({
  organism: organism.value || null,
  role: role.value || null,
  source_db: selectedSources.value,
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
        <div v-if="organism" class="mb-1.5">
          <span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs bg-[#E6F1FB] border border-[#B5D4F4] text-[#185FA5] font-medium">
            <em>{{ organism }}</em>
            <button @click="clearOrganism" class="opacity-60 hover:opacity-100 transition-opacity" aria-label="Remove organism filter">×</button>
          </span>
        </div>
        <div v-else>
          <input
            v-model="orgSearch"
            type="text"
            placeholder="Search organisms… (e.g. Homo sapiens)"
            class="w-full text-sm border border-gray-200 rounded px-2 py-1.5 focus:outline-none focus:border-[#185FA5]"
            @input="onOrganismSearch"
          />
          <div v-if="orgSearch.length >= 3" class="mt-1">
            <div
              v-for="result in orgSearchResults"
              :key="result.organism"
              class="flex items-center justify-between py-1 cursor-pointer hover:text-[#185FA5] text-sm text-gray-600"
              @click="selectOrganism(result.organism)"
            >
              <span>{{ result.organism }}</span>
              <span class="text-xs text-gray-500">{{ result.protein_count }}</span>
            </div>
            <div v-if="orgSearchResults.length === 0" class="text-xs text-gray-500 py-1">No organisms found.</div>
          </div>
        </div>
      </div>

      <!-- Role filter -->
      <div>
        <label class="text-xs font-semibold text-gray-700 uppercase tracking-wide block mb-1.5">Role</label>
        <select v-model="role" class="text-sm text-gray-700 border border-gray-200 rounded px-2 py-1.5 bg-white focus:outline-none focus:border-[#185FA5]">
          <option value="">All roles</option>
          <option value="driver">Drivers only</option>
          <option value="component">Non-drivers</option>
        </select>
      </div>

      <!-- Source DB filter -->
      <div>
        <label class="text-xs font-semibold text-gray-700 uppercase tracking-wide block mb-1.5">Source database</label>
        <div class="flex items-center gap-1.5 flex-wrap">
          <button
            v-for="db in SOURCE_DBS"
            :key="db"
            @click="toggleSourceDb(db)"
            :class="[
              'text-xs px-2 py-0.5 rounded-full border transition-colors',
              selectedSources.includes(db)
                ? 'bg-[#185FA5] text-white border-[#185FA5]'
                : 'bg-white text-gray-600 border-gray-300 hover:border-[#185FA5] hover:text-[#185FA5]',
            ]"
          >
            {{ db }}
          </button>
        </div>
        <p class="text-xs text-gray-500 mt-1">No selection means all sources.</p>
      </div>

      <!-- Fields -->
      <div>
        <label class="text-xs font-semibold text-gray-700 uppercase tracking-wide block mb-1.5">Fields</label>
        <div class="flex gap-4 text-sm text-gray-700">
          <label class="flex items-center gap-1.5 cursor-pointer">
            <input type="radio" value="basic" v-model="fields" class="accent-[#185FA5]" />
            Basic (identity only)
          </label>
          <label class="flex items-center gap-1.5 cursor-pointer">
            <input type="radio" value="full" v-model="fields" class="accent-[#185FA5]" />
            With annotations
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
      <div class="pt-2">
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
