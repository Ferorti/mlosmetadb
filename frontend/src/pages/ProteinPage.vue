<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { getProtein } from '@/api/proteins'

const route   = useRoute()
const protein = ref(null)
const loading = ref(true)
const notFound = ref(false)
const error   = ref(null)

onMounted(async () => {
  try {
    const res = await getProtein(route.params.id)
    protein.value = res.data
  } catch (err) {
    if (err.response?.status === 404) {
      notFound.value = true
    } else {
      error.value = err.message || 'An unexpected error occurred.'
    }
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="max-w-4xl mx-auto px-6 py-8">

    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center py-24 text-sm text-gray-400 animate-pulse">
      Loading protein…
    </div>

    <!-- Not found -->
    <div v-else-if="notFound" class="flex flex-col items-center justify-center py-24 text-center">
      <div class="text-4xl mb-4">🔍</div>
      <p class="text-gray-600 font-medium">Protein not found</p>
      <p class="text-sm text-gray-400 mt-1">
        <span class="font-mono">{{ route.params.id }}</span> is not in the database.
      </p>
      <RouterLink to="/" class="mt-4 text-sm text-[#185FA5] hover:underline">← Back to home</RouterLink>
    </div>

    <!-- Generic error -->
    <div v-else-if="error" class="flex flex-col items-center justify-center py-24 text-center">
      <div class="text-4xl mb-4">⚠️</div>
      <p class="text-sm text-red-600 font-medium">Failed to load protein</p>
      <p class="text-xs text-gray-400 mt-1 max-w-xs">{{ error }}</p>
    </div>

    <!-- Protein data -->
    <template v-else-if="protein">

      <!-- Header -->
      <div class="border-b border-gray-200 pb-6 mb-6">
        <h1 class="text-2xl font-bold text-[#1B3D6F] mb-3 leading-snug">
          {{ protein.protein_name || protein.gene_name || protein.uniprot_id }}
        </h1>
        <div class="flex flex-wrap items-center gap-x-6 gap-y-1.5 text-sm text-gray-700">
          <span class="flex items-center gap-1.5">
            <span class="text-[11px] font-medium text-gray-400 uppercase tracking-wide">UniProt</span>
            <span class="font-mono font-medium">{{ protein.uniprot_id }}</span>
          </span>
          <span v-if="protein.gene_name" class="flex items-center gap-1.5">
            <span class="text-[11px] font-medium text-gray-400 uppercase tracking-wide">Gene</span>
            <span class="font-medium">{{ protein.gene_name }}</span>
          </span>
          <span v-if="protein.organism" class="flex items-center gap-1.5">
            <span class="text-[11px] font-medium text-gray-400 uppercase tracking-wide">Organism</span>
            <span class="italic">{{ protein.organism }}</span>
          </span>
        </div>
      </div>

      <!-- Raw JSON (temporary) -->
      <div>
        <p class="text-[11px] font-semibold text-gray-400 uppercase tracking-wider mb-2">
          Raw API response (temporary)
        </p>
        <pre class="bg-gray-50 border border-gray-200 rounded p-4 text-xs text-gray-700 overflow-x-auto whitespace-pre-wrap">{{ JSON.stringify(protein, null, 2) }}</pre>
      </div>

    </template>

  </div>
</template>
