<template>
  <div class="max-w-6xl mx-auto px-6 py-8">
    <!-- Page header -->
    <div class="mb-6">
      <h1 class="text-2xl font-semibold text-gray-800">Membraneless Organelles</h1>
      <p class="text-sm text-gray-600 mt-1">Browse all MLOs curated in the database</p>
    </div>

    <!-- Filter bar -->
    <div class="bg-white border border-gray-200 rounded-lg px-4 py-3 mb-4 flex flex-wrap items-center gap-x-4 gap-y-2">
      <!-- Text search -->
      <div class="flex items-center gap-2 min-w-[180px]">
        <i class="ti ti-search text-gray-400 text-sm"></i>
        <input
          v-model="textFilter"
          type="text"
          placeholder="Search organelles…"
          class="text-sm text-gray-800 placeholder-gray-400 border-none outline-none w-full"
        />
      </div>

      <div class="w-px h-5 bg-gray-200 hidden sm:block"></div>

      <!-- Category dropdown -->
      <select
        v-model="categoryFilter"
        class="text-sm text-gray-700 border border-gray-200 rounded px-2 py-1 bg-white focus:outline-none focus:border-[#185FA5]"
      >
        <option value="">All categories</option>
        <option v-for="cat in categories" :key="cat" :value="cat">{{ formatCategory(cat) }}</option>
      </select>

      <div class="w-px h-5 bg-gray-200 hidden sm:block"></div>

      <!-- Source DB toggle chips -->
      <div class="flex items-center gap-1.5 flex-wrap">
        <span class="text-xs text-gray-500">Source:</span>
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

      <div class="w-px h-5 bg-gray-200 hidden sm:block"></div>

      <!-- Organism placeholder -->
      <select
        disabled
        class="text-sm text-gray-400 border border-gray-200 rounded px-2 py-1 bg-gray-50 cursor-not-allowed"
      >
        <option>Organism — coming soon</option>
      </select>

      <div class="w-px h-5 bg-gray-200 hidden sm:block"></div>

      <!-- Sort control -->
      <select
        v-model="sortBy"
        class="text-sm text-gray-700 border border-gray-200 rounded px-2 py-1 bg-white focus:outline-none focus:border-[#185FA5]"
      >
        <option value="drivers">Most drivers</option>
        <option value="alphabetical">Alphabetical</option>
        <option value="protein_count">Most proteins</option>
      </select>

      <!-- Count display -->
      <div class="ml-auto text-xs text-gray-500 whitespace-nowrap">
        Showing
        <span class="font-medium text-gray-700">{{ filtered.length }}</span>
        of
        <span class="font-medium text-gray-700">{{ totalCount }}</span>
        MLOs
      </div>
    </div>

    <!-- Loading -->
    <LoadingSpinner v-if="loading" />

    <!-- Error -->
    <div v-else-if="error" class="text-center py-16 text-sm text-red-500">
      Failed to load MLOs. Please try again.
    </div>

    <!-- Empty state -->
    <div v-else-if="filtered.length === 0" class="text-center py-16 text-sm text-gray-500">
      No organelles match your filters. Try removing some filters.
    </div>

    <!-- MLO list -->
    <div v-else class="bg-white border border-gray-200 rounded-lg overflow-hidden">
      <div
        v-for="mlo in filtered"
        :key="mlo.unified_mlo"
        class="px-5 py-4 border-b border-gray-100 last:border-b-0 hover:bg-slate-50 cursor-pointer transition-colors"
        @click="navigateToMlo(mlo.unified_mlo)"
      >
        <!-- Line 1: name + category badge -->
        <div class="flex items-start justify-between gap-4">
          <span class="text-[16px] font-medium text-gray-800">{{ formatMlo(mlo.unified_mlo) }}</span>
          <span
            v-if="mlo.category"
            class="shrink-0 text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200"
          >
            {{ formatCategory(mlo.category) }}
          </span>
        </div>

        <!-- Line 2: protein · driver counts -->
        <div class="mt-1 text-sm text-gray-600">
          {{ formatCount(mlo.protein_count) }} proteins ·
          <span class="text-[#185FA5]">{{ formatCount(mlo.driver_count) }} drivers</span>
        </div>

        <!-- Line 3: source DBs -->
        <div v-if="mlo.sources && mlo.sources.length" class="mt-0.5 text-xs text-gray-400">
          {{ mlo.sources.join(' · ') }}
        </div>

        <!-- Line 4: truncated definition + expand toggle -->
        <div class="mt-1.5 flex items-start justify-between gap-3">
          <p
            v-if="!expandedRows.has(mlo.unified_mlo) && firstDefinition(mlo)"
            class="text-sm text-gray-600 flex-1 leading-snug"
          >
            {{ truncate(firstDefinition(mlo), 120) }}
          </p>
          <div v-else-if="!expandedRows.has(mlo.unified_mlo)" class="flex-1"></div>

          <button
            v-if="mlo.definitions && mlo.definitions.length"
            @click.stop="toggleExpand(mlo.unified_mlo)"
            class="shrink-0 flex items-center gap-0.5 text-xs text-[#185FA5] hover:text-blue-700 mt-0.5"
          >
            <i :class="expandedRows.has(mlo.unified_mlo) ? 'ti ti-chevron-up' : 'ti ti-chevron-down'"></i>
            {{ expandedRows.has(mlo.unified_mlo) ? 'collapse' : 'expand' }}
          </button>
        </div>

        <!-- Expanded definitions -->
        <div
          v-if="expandedRows.has(mlo.unified_mlo)"
          class="mt-3 pt-3 border-t border-gray-100 space-y-3"
          @click.stop
        >
          <div v-for="def in mlo.definitions" :key="def.source_db">
            <div class="flex items-baseline gap-2 mb-0.5">
              <span class="text-[10px] font-semibold uppercase tracking-wider text-gray-400">{{ def.source_db }}</span>
              <span v-if="def.source_name" class="text-xs text-gray-500 italic">{{ def.source_name }}</span>
            </div>
            <p v-if="def.definition" class="text-sm text-gray-700 leading-snug">{{ def.definition }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getMlos } from '@/api/mlos.js'
import { formatMlo, formatCount } from '@/utils/format.js'
import LoadingSpinner from '@/components/ui/LoadingSpinner.vue'

const router = useRouter()

const SOURCE_DBS = ['PhaseDB', 'DrLLPS', 'PhasePro', 'LLPSDB', 'CDCODE']

const CATEGORY_LABELS = {
  cytoplasmic_rnp: 'Cytoplasmic RNP',
  nuclear_rnp: 'Nuclear RNP',
  nuclear_body: 'Nuclear body',
  cytoplasmic_membraneless: 'Cytoplasmic',
  in_vitro: 'In vitro',
}

function formatCategory(cat) {
  if (!cat) return ''
  return CATEGORY_LABELS[cat] ?? cat.replace(/_/g, ' ').replace(/^\w/, c => c.toUpperCase())
}

function firstDefinition(mlo) {
  return mlo.definitions?.[0]?.definition ?? ''
}

function truncate(str, n) {
  if (!str) return ''
  return str.length > n ? str.slice(0, n).trimEnd() + '…' : str
}

const mlos = ref([])
const loading = ref(true)
const error = ref(false)
const textFilter = ref('')
const categoryFilter = ref('')
const selectedSources = ref([])
const sortBy = ref('drivers')
const expandedRows = ref(new Set())

function toggleSourceDb(db) {
  const idx = selectedSources.value.indexOf(db)
  if (idx >= 0) {
    selectedSources.value.splice(idx, 1)
  } else {
    selectedSources.value.push(db)
  }
}

function toggleExpand(mloId) {
  const next = new Set(expandedRows.value)
  if (next.has(mloId)) {
    next.delete(mloId)
  } else {
    next.add(mloId)
  }
  expandedRows.value = next
}

function navigateToMlo(unifiedMlo) {
  router.push({ path: '/results', query: { mlo: unifiedMlo } })
}

const categories = computed(() => {
  const cats = new Set()
  mlos.value.forEach(m => { if (m.category) cats.add(m.category) })
  return [...cats].sort()
})

const totalCount = computed(() => mlos.value.length)

const filtered = computed(() => {
  let result = mlos.value

  const q = textFilter.value.trim().toLowerCase()
  if (q) {
    result = result.filter(m => m.unified_mlo.toLowerCase().includes(q))
  }

  if (categoryFilter.value) {
    result = result.filter(m => m.category === categoryFilter.value)
  }

  if (selectedSources.value.length) {
    result = result.filter(m =>
      selectedSources.value.some(db =>
        m.sources && m.sources.some(s => s.toLowerCase() === db.toLowerCase())
      )
    )
  }

  if (sortBy.value === 'alphabetical') {
    return [...result].sort((a, b) => formatMlo(a.unified_mlo).localeCompare(formatMlo(b.unified_mlo)))
  }

  const countKey = sortBy.value === 'protein_count' ? 'protein_count' : 'driver_count'
  return [...result].sort((a, b) => {
    const diff = (b[countKey] ?? 0) - (a[countKey] ?? 0)
    if (diff !== 0) return diff
    return formatMlo(a.unified_mlo).localeCompare(formatMlo(b.unified_mlo))
  })
})

onMounted(async () => {
  try {
    const res = await getMlos()
    mlos.value = res.data.mlos ?? []
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
})
</script>
