<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useProtein } from '@/composables/useProtein.js'
import LoadingSpinner from '@/components/ui/LoadingSpinner.vue'
import ProteinHeader from '@/components/protein/ProteinHeader.vue'
import ProteinMLOs from '@/components/protein/ProteinMLOs.vue'
import ProteinFeatureTrack from '@/components/protein/ProteinFeatureTrack.vue'
import ProteinPPI from '@/components/protein/ProteinPPI.vue'
import MolStarViewer from '@/components/viewers/MolStarViewer.vue'

const route = useRoute()
const { protein, loading, error, fetchProtein } = useProtein()

const activeTab   = ref('overview')
const mountedTabs = reactive(new Set(['overview']))

function activateTab(tab) {
  activeTab.value = tab
  mountedTabs.add(tab)
}

const TABS = [
  { id: 'overview',      label: 'Overview' },
  { id: 'mlos',          label: 'MLO Annotations' },
  { id: 'interactions',  label: 'Interactions' },
  { id: 'orthologs',     label: 'Orthologs' },
]

onMounted(() => {
  fetchProtein(route.params.id)
})
</script>

<template>
  <div class="max-w-6xl mx-auto px-6 py-6">

    <!-- Loading -->
    <LoadingSpinner v-if="loading" />

    <!-- Not found -->
    <div v-else-if="error === 'not_found'" class="py-24 text-center text-sm text-[#484E59]">
      Protein not found.
      <RouterLink to="/" class="ml-2 text-[#185FA5] hover:underline">← Back to home</RouterLink>
    </div>

    <!-- Generic error -->
    <div v-else-if="error" class="py-24 text-center text-sm text-[#484E59]">
      Could not load protein data.
    </div>

    <!-- Protein data -->
    <template v-else-if="protein">

      <ProteinHeader :protein="protein" />

      <!-- Tab nav -->
      <div class="sticky top-14 z-10 bg-white border-b border-slate-200 mb-6">
        <nav class="flex">
          <button
            v-for="tab in TABS"
            :key="tab.id"
            class="px-4 py-3 text-sm font-medium border-b-2 -mb-px transition-colors"
            :class="activeTab === tab.id
              ? 'border-[#185FA5] text-[#185FA5]'
              : 'border-transparent text-[#484E59] hover:text-[#185FA5]'"
            @click="activateTab(tab.id)"
          >
            {{ tab.label }}
          </button>
        </nav>
      </div>

      <!-- Overview -->
      <div v-if="mountedTabs.has('overview')" v-show="activeTab === 'overview'">
        <div class="flex gap-6 items-start">

          <!-- Left: AlphaFold structure (larger) -->
          <div class="w-[520px] flex-shrink-0">
            <div class="text-sm font-medium text-gray-700 mb-2">AlphaFold Structure</div>
            <div class="h-[420px] rounded border border-slate-200 overflow-hidden">
              <MolStarViewer :uniprot-id="protein.uniprot_id" />
            </div>
            <a
              :href="`https://alphafold.ebi.ac.uk/entry/${protein.uniprot_id}`"
              target="_blank" rel="noopener"
              class="text-xs text-[#185FA5] mt-1 inline-block hover:underline"
            >View in AlphaFold DB →</a>
          </div>

          <!-- Right: Sequence & features -->
          <div class="flex-1 min-w-0">
            <div class="text-sm font-medium text-gray-700 mb-2">Sequence & Features</div>
            <ProteinFeatureTrack
              v-if="protein.sequence_features"
              :sequence-features="protein.sequence_features"
              :sequence-length="protein.sequence_length ?? 0"
            />
            <div v-else class="text-sm text-[#484E59]">No sequence features available.</div>
          </div>

        </div>

        <!-- External resources -->
        <div class="mt-6">
          <div class="text-sm font-medium text-gray-700 mb-2">External resources</div>
          <div class="text-sm">
            <a
              :href="`https://www.uniprot.org/uniprotkb/${protein.uniprot_id}`"
              target="_blank" rel="noopener"
              class="text-[#185FA5] hover:underline"
            >UniProt</a>
            <span class="text-[#484E59]"> · </span>
            <a
              :href="`https://mobidb.org/${protein.uniprot_id}`"
              target="_blank" rel="noopener"
              class="text-[#185FA5] hover:underline"
            >MobiDB</a>
            <span class="text-[#484E59]"> · </span>
            <a
              :href="`https://alphafold.ebi.ac.uk/entry/${protein.uniprot_id}`"
              target="_blank" rel="noopener"
              class="text-[#185FA5] hover:underline"
            >AlphaFold DB</a>
            <span class="text-[#484E59]"> · </span>
            <a
              :href="`https://www.ebi.ac.uk/interpro/protein/UniProt/${protein.uniprot_id}`"
              target="_blank" rel="noopener"
              class="text-[#185FA5] hover:underline"
            >InterPro</a>
          </div>
        </div>
      </div>

      <!-- MLO Annotations -->
      <div v-if="mountedTabs.has('mlos')" v-show="activeTab === 'mlos'">
        <ProteinMLOs
          :mlo-annotations="protein.mlo_annotations ?? []"
          :uniprot-id="protein.uniprot_id"
        />
      </div>

      <!-- Interactions -->
      <div v-if="mountedTabs.has('interactions')" v-show="activeTab === 'interactions'">
        <div class="text-lg font-semibold text-gray-800 mb-4">Protein–Protein Interactions</div>
        <ProteinPPI :protein="protein" />
      </div>

      <!-- Orthologs -->
      <div v-if="mountedTabs.has('orthologs')" v-show="activeTab === 'orthologs'">
        <div class="text-sm text-[#484E59]">
          Ortholog data is not yet available in this version of MLOsMetaDB.
        </div>
      </div>

    </template>
  </div>
</template>
