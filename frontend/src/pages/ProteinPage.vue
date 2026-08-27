<script setup>
import { reactive, nextTick, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useProtein } from '@/composables/useProtein.js'
import LoadingSpinner from '@/components/ui/LoadingSpinner.vue'
import ProteinHeader from '@/components/protein/ProteinHeader.vue'
import ProteinMLOs from '@/components/protein/ProteinMLOs.vue'
import ProteinOverview from '@/components/protein/ProteinOverview.vue'
import ProteinPPI from '@/components/protein/ProteinPPI.vue'

const route = useRoute()
const { protein, loading, error, fetchProtein } = useProtein()

const TABS = [
  { id: 'overview',      label: 'Overview' },
  { id: 'mlos',          label: 'Membraneless Organelles' },
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
    <div v-else-if="error === 'not_found'" class="py-24 text-center text-sm text-ink3">
      Protein not found.
      <RouterLink to="/" class="ml-2 text-brand hover:underline">← Back to home</RouterLink>
    </div>

    <!-- Generic error -->
    <div v-else-if="error" class="py-24 text-center text-sm text-ink3">
      Could not load protein data.
    </div>

    <!-- Protein data -->
    <template v-else-if="protein">

      <!-- Header with blue background -->
      <div class="bg-surface border-b border-border">
        <div class="max-w-6xl mx-auto px-6">
          <ProteinHeader :protein="protein" />
        </div>
      </div>

      <!-- Section nav + content -->
      <div class="max-w-6xl mx-auto px-6 pb-6">

      <!-- Nav: click jumps to a section like a tab, or just scroll past all of them -->
      <div class="sticky top-14 z-10 bg-surface border-b border-border mb-6">
        <nav class="flex gap-7">
          <a
            v-for="tab in TABS"
            :key="tab.id"
            :href="`#${tab.id}`"
            class="pt-2 pb-2 text-[14px] font-medium tracking-[-0.005em] text-ink3 border-b-2 border-transparent hover:text-ink transition-colors"
          >
            {{ tab.label }}
          </a>
        </nav>
      </div>

      <!-- Overview -->
      <div id="overview" class="scroll-mt-28">
        <ProteinOverview :protein="protein" />
      </div>

      <!-- Membraneless Organelles -->
      <div id="mlos" class="scroll-mt-28 mt-10">
        <div class="text-lg font-semibold text-gray-800 mb-4">
          Membraneless organelles associated with {{ protein.gene_name || protein.uniprot_id }}
        </div>
        <ProteinMLOs
          v-if="mountedSections.has('mlos')"
          :mlo-annotations="protein.mlo_annotations ?? []"
          :uniprot-id="protein.uniprot_id"
        />
      </div>

      <!-- Interactions -->
      <div id="interactions" class="scroll-mt-28 mt-10">
        <div class="text-lg font-semibold text-gray-800 mb-4">
          {{ protein.gene_name || protein.uniprot_id }} protein interaction network in MLOsMetaDB
        </div>
        <ProteinPPI v-if="mountedSections.has('interactions')" :protein="protein" />
      </div>

      </div><!-- end nav+content -->
    </template>
  </div>
</template>
