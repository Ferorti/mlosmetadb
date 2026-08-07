<script setup>
import { LLPS_SOURCES, ANNOTATION_SOURCES } from '@/data/aboutSources'
</script>

<template>
  <section id="data-origin" class="scroll-mt-28 mt-10">
    <h2 class="text-lg font-semibold text-gray-800 mb-3">Data Origin</h2>

    <h3 class="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">LLPS source databases</h3>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
      <div
        v-for="src in LLPS_SOURCES"
        :key="src.key"
        class="bg-white border border-gray-200 rounded-lg p-4"
      >
        <span
          class="text-xs px-2 py-0.5 rounded font-medium inline-block mb-2"
          :style="{ backgroundColor: src.color.bg, color: src.color.text, borderColor: src.color.border, borderStyle: 'solid', borderWidth: '1px' }"
        >{{ src.name }}</span>
        <p class="text-sm text-gray-600 leading-relaxed">{{ src.description }}</p>
        <p class="text-xs text-gray-800 mt-2">
          {{ src.citationText }}
          <a :href="src.citationUrl" target="_blank" rel="noopener" class="text-[#185FA5] hover:underline">{{ src.citationUrl }}</a>
        </p>
      </div>
    </div>

    <h3 class="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">Annotation & enrichment databases</h3>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div
        v-for="src in ANNOTATION_SOURCES"
        :key="src.key"
        class="bg-white border border-gray-200 rounded-lg p-4"
      >
        <span class="text-xs px-2 py-0.5 rounded font-medium inline-block mb-2 bg-gray-100 text-gray-700 border border-gray-200">{{ src.name }}</span>
        <p class="text-sm text-gray-600 leading-relaxed">{{ src.description }}</p>
        <p class="text-xs text-gray-800 mt-2">
          {{ src.citationText }}
          <a :href="src.citationUrl" target="_blank" rel="noopener" class="text-[#185FA5] hover:underline">{{ src.citationUrl }}</a>
        </p>
      </div>
    </div>
  </section>
</template>
