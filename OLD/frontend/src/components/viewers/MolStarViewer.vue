<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'

const props = defineProps({
  uniprotId: { type: String, required: true },
})

const containerRef = ref(null)
const loading = ref(true)
const error   = ref(null)

let viewerInstance = null

async function initViewer(uniprotId) {
  if (!window.molstar) {
    error.value   = 'MolStar viewer could not be loaded.'
    loading.value = false
    return
  }
  loading.value = true
  error.value   = null
  try {
    if (viewerInstance) {
      viewerInstance.plugin.dispose()
      viewerInstance = null
    }
    viewerInstance = await window.molstar.Viewer.create(containerRef.value, {
      layoutIsExpanded:          false,
      layoutShowControls:        false,
      layoutShowRemoteState:     false,
      layoutShowSequence:        false,
      layoutShowLog:             false,
      layoutShowLeftPanel:       false,
      viewportShowExpand:        true,
      viewportShowSelectionMode: false,
      viewportShowAnimation:     false,
    })
    await viewerInstance.loadAlphaFoldDb(uniprotId)
  } catch {
    error.value = 'No AlphaFold structure available for this protein.'
  } finally {
    loading.value = false
  }
}

onMounted(() => initViewer(props.uniprotId))
onUnmounted(() => { if (viewerInstance) viewerInstance.plugin.dispose() })
watch(() => props.uniprotId, (id) => initViewer(id))
</script>

<template>
  <div class="relative w-full h-full">
    <div
      v-if="loading"
      class="absolute inset-0 flex items-center justify-center bg-slate-50"
    >
      <span class="text-sm text-[#484E59]">Loading structure…</span>
    </div>
    <div
      v-else-if="error"
      class="absolute inset-0 flex items-center justify-center px-4 text-center bg-slate-50"
    >
      <span class="text-sm text-[#484E59]">{{ error }}</span>
    </div>
    <div ref="containerRef" style="position: relative; width: 100%; height: 100%;"></div>
  </div>
</template>
