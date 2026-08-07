<script setup>
import { ref } from 'vue'
import { checkCitations } from '@/api/proteins'
import { MLOSMETADB_CITATION, RELATED_PUBLICATION_CITATION, LLPS_SOURCES, ANNOTATION_SOURCES } from '@/data/aboutSources'

const idsInput = ref('')
const checking = ref(false)
const checkError = ref(false)
const results = ref(null)

function parseIds(text) {
  return [...new Set(
    text.split(/[\s,]+/).map(s => s.trim()).filter(Boolean)
  )]
}

async function runCheck() {
  const ids = parseIds(idsInput.value)
  if (!ids.length) return
  checking.value = true
  checkError.value = false
  results.value = null
  try {
    const res = await checkCitations(ids)
    results.value = Object.entries(res.data.by_source).sort((a, b) => b[1] - a[1])
  } catch {
    checkError.value = true
  } finally {
    checking.value = false
  }
}
</script>

<template>
  <section id="citations" class="scroll-mt-28 mt-10">
    <h2 class="text-lg font-semibold text-gray-800 mb-3">Citations</h2>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
      <div class="bg-white border border-gray-200 rounded-lg p-4">
        <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Cite MLOsMetaDB</p>
        <p class="text-sm text-gray-800">
          {{ MLOSMETADB_CITATION.authors }} {{ MLOSMETADB_CITATION.title }}
          <em>{{ MLOSMETADB_CITATION.journal }}</em> {{ MLOSMETADB_CITATION.year }}
          <a :href="MLOSMETADB_CITATION.url" target="_blank" rel="noopener" class="text-[#185FA5] hover:underline block mt-1">{{ MLOSMETADB_CITATION.url }}</a>
        </p>
      </div>
      <div class="bg-white border border-gray-200 rounded-lg p-4">
        <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Related Publication</p>
        <p class="text-sm text-gray-800">
          {{ RELATED_PUBLICATION_CITATION.authors }} {{ RELATED_PUBLICATION_CITATION.title }}
          <em>{{ RELATED_PUBLICATION_CITATION.journal }}</em> {{ RELATED_PUBLICATION_CITATION.year }}
          <a :href="RELATED_PUBLICATION_CITATION.url" target="_blank" rel="noopener" class="text-[#185FA5] hover:underline block mt-1">{{ RELATED_PUBLICATION_CITATION.url }}</a>
        </p>
      </div>
    </div>

    <div class="bg-white border border-gray-200 rounded-lg p-4 mb-8">
      <p class="text-sm font-semibold text-gray-700 mb-1">Which database should I cite?</p>
      <p class="text-xs text-gray-600 mb-3">Paste a list of UniProt IDs (comma, space, or newline separated) to see which source databases contributed annotations for them.</p>
      <textarea
        v-model="idsInput"
        rows="4"
        placeholder="P35637, Q9Y2Y0, ..."
        class="w-full text-sm border border-gray-200 rounded px-2 py-1.5 font-mono focus:outline-none focus:border-[#185FA5]"
      ></textarea>
      <div class="flex items-center justify-between mt-2">
        <button
          @click="runCheck"
          :disabled="checking || !idsInput.trim()"
          class="inline-flex items-center px-4 py-2 rounded bg-[#185FA5] text-white text-sm font-medium hover:bg-[#0F4A87] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {{ checking ? 'Checking…' : 'Check' }}
        </button>
        <p v-if="checkError" class="text-xs text-red-600">Could not check citations right now. Try again later.</p>
      </div>

      <div v-if="results" class="flex flex-wrap gap-2 mt-4">
        <span
          v-for="[name, count] in results"
          :key="name"
          class="text-xs px-2 py-1 rounded-full bg-[#EBF3FB] text-[#1B4F8A] border border-[#BFDBFE] font-medium"
        >{{ name }} ({{ count }})</span>
        <span v-if="!results.length" class="text-xs text-gray-500">None of these IDs matched a source database in MLOsMetaDB.</span>
      </div>
    </div>

    <div>
      <p class="text-sm font-semibold text-gray-700 mb-2">Full reference list</p>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-1 text-xs text-gray-600">
        <p v-for="src in [...LLPS_SOURCES, ...ANNOTATION_SOURCES]" :key="src.key">
          <span class="font-medium text-gray-700">{{ src.name }}:</span>
          {{ src.citationText }}
          <a :href="src.citationUrl" target="_blank" rel="noopener" class="text-[#185FA5] hover:underline">{{ src.citationUrl }}</a>
        </p>
      </div>
    </div>
  </section>
</template>
