<script setup>
import { reactive, nextTick, onUnmounted, watch } from 'vue'
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

const TABS = [
  { id: 'overview',      label: 'Overview' },
  { id: 'mlos',          label: 'MLO Annotations' },
  { id: 'interactions',  label: 'Interactions' },
]

// All three sections are always in the page now (nav links just scroll to
// them), but Interactions' force-directed graph is expensive to spin up --
// keep it unmounted until its section actually scrolls into view (or a nav
// click jumps straight to it, which triggers the same intersection), instead
// of paying that cost on every single protein page load like an eager mount
// would.
const mountedSections = reactive(new Set(['overview']))
let sectionObserver = null

function observeSections() {
  sectionObserver?.disconnect()
  sectionObserver = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (entry.isIntersecting) {
        mountedSections.add(entry.target.id)
        sectionObserver.unobserve(entry.target)
      }
    }
  }, { rootMargin: '200px 0px' })

  for (const tab of TABS) {
    const el = document.getElementById(tab.id)
    if (el) sectionObserver.observe(el)
  }
}

onUnmounted(() => sectionObserver?.disconnect())

watch(() => route.params.id, async (id) => {
  if (!id) return
  mountedSections.clear()
  mountedSections.add('overview')
  await fetchProtein(id)
  await nextTick()
  observeSections()
}, { immediate: true })
</script>

<template>
  <div>

    <!-- Loading -->
    <div v-if="loading" class="max-w-6xl mx-auto px-6 py-6">
      <LoadingSpinner />
    </div>

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

      <!-- Header with blue background -->
      <div class="bg-[#EBF3FB] border-b border-[#C8DFF2]">
        <div class="max-w-6xl mx-auto px-6">
          <ProteinHeader :protein="protein" />
        </div>
      </div>

      <!-- Section nav + content -->
      <div class="max-w-6xl mx-auto px-6 pb-6">

      <!-- Nav: click jumps to a section like a tab, or just scroll past all of them -->
      <div class="sticky top-14 z-10 bg-white border-b border-slate-200 mb-6">
        <nav class="flex">
          <a
            v-for="tab in TABS"
            :key="tab.id"
            :href="`#${tab.id}`"
            class="px-4 py-3 text-sm font-medium text-[#484E59] border-b-2 border-transparent hover:text-[#185FA5] hover:border-[#185FA5] transition-colors"
          >
            {{ tab.label }}
          </a>
        </nav>
      </div>

      <!-- Overview -->
      <div id="overview" class="scroll-mt-28">
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
      <div id="mlos" class="scroll-mt-28 mt-10">
        <ProteinMLOs
          v-if="mountedSections.has('mlos')"
          :mlo-annotations="protein.mlo_annotations ?? []"
          :uniprot-id="protein.uniprot_id"
        />
      </div>

      <!-- Interactions -->
      <div id="interactions" class="scroll-mt-28 mt-10">
        <div class="text-lg font-semibold text-gray-800 mb-4">Protein–Protein Interactions</div>
        <ProteinPPI v-if="mountedSections.has('interactions')" :protein="protein" />
      </div>

      </div><!-- end nav+content -->
    </template>
  </div>
</template>
