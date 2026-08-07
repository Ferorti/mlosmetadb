<script setup>
import { LLPS_SOURCES, ANNOTATION_SOURCES } from '@/data/aboutSources'
</script>

<template>
  <section id="data-sources" class="scroll-mt-28 mt-10">
    <h2 class="text-lg font-semibold text-gray-800 mb-1">Data Sources</h2>
    <p class="text-sm text-gray-600 mb-6">
      External databases used by this web server, with a short description and the
      corresponding citation for each resource.
    </p>

    <h3 class="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">LLPS-Specific Databases</h3>
    <div class="space-y-5 mb-8">
      <div v-for="src in LLPS_SOURCES" :key="src.key">
        <p class="text-sm text-gray-800 leading-relaxed">
          <span class="font-semibold">{{ src.name }}</span> — {{ src.description }}
        </p>
        <p class="text-xs text-gray-500 mt-1">
          {{ src.citationText }}
          <a :href="src.citationUrl" target="_blank" rel="noopener" class="text-[#185FA5] hover:underline">{{ src.citationUrl }}</a>
        </p>
      </div>
    </div>

    <h3 class="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">General Databases</h3>
    <!-- Superscript reference numbers below are positional -- they must stay in
         sync with ANNOTATION_SOURCES's array order (UniProt, InterPro, MobiDB,
         BioGRID, OMA), which the numbered list right below renders from. -->
    <p class="text-sm text-gray-800 leading-relaxed mb-3">
      Protein-level annotations layered on top of the core dataset draw on several
      specialized resources: sequence and functional metadata from
      <strong>UniProt</strong><sup>1</sup>, domain and family classification from
      <strong>InterPro</strong><sup>2</sup>, predicted intrinsic disorder from
      <strong>MobiDB</strong><sup>3</sup>, curated protein–protein interaction
      evidence from <strong>BioGRID</strong><sup>4</sup>, and cross-species
      ortholog assignments from <strong>OMA</strong><sup>5</sup>.
    </p>
    <ol class="text-xs text-gray-500 space-y-1 list-decimal list-inside">
      <li v-for="src in ANNOTATION_SOURCES" :key="src.key">
        {{ src.citationText }}
        <a :href="src.citationUrl" target="_blank" rel="noopener" class="text-[#185FA5] hover:underline">{{ src.citationUrl }}</a>
      </li>
    </ol>
  </section>
</template>
