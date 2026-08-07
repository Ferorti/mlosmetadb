<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'

const props = defineProps({
  uniprotId: { type: String, required: true },
})

const containerRef = ref(null)
const loading = ref(true)
const error   = ref(null)
const ready   = ref(false)   // a structure is loaded and interactive

let viewerInstance = null

async function initViewer(uniprotId) {
  if (!window.molstar) {
    error.value   = 'MolStar viewer could not be loaded.'
    loading.value = false
    return
  }
  loading.value = true
  error.value   = null
  ready.value   = false
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
    ready.value = true
  } catch {
    error.value = 'No AlphaFold structure available for this protein.'
  } finally {
    loading.value = false
  }
}

onMounted(() => initViewer(props.uniprotId))
onUnmounted(() => { if (viewerInstance) viewerInstance.plugin.dispose() })
watch(() => props.uniprotId, (id) => initViewer(id))

// ─── Exposed API for linked views ────────────────────────────────────────────
// Thin wrappers over Viewer.structureInteractivity(), which resolves an MVS
// component schema to a Loci and dispatches to the interactivity managers.
// AlphaFold models number residues 1..N in UniProt coordinates (label_seq_id ==
// auth_seq_id == UniProt position, single chain), so feature coordinates map
// across with no conversion.
//
// Every method is a no-op when the structure never loaded (no WebGL, no
// AlphaFold entry, older Mol* bundle), so callers never have to check.

function canInteract() {
  return ready.value
    && viewerInstance
    && typeof viewerInstance.structureInteractivity === 'function'
}

function toElements(ranges) {
  return ranges.map(r => ({ beg_label_seq_id: r.start, end_label_seq_id: r.end }))
}

function apply(action, ranges) {
  if (!canInteract()) return
  try {
    viewerInstance.structureInteractivity({
      // Omitting `elements` is how structureInteractivity clears the given action.
      elements: ranges?.length ? toElements(ranges) : undefined,
      action,
    })
  } catch {
    // Structure not in the state tree yet, or disposed mid-flight.
  }
}

defineExpose({
  /** Transient highlight over one or more residue ranges. Empty array clears. */
  highlightRanges: (ranges = []) => apply('highlight', ranges),
  /** Persistent selection, rendered in Mol*'s selection color. Empty array clears. */
  selectRanges:    (ranges = []) => apply('select', ranges),
  /** Drops both the highlight and the selection. */
  clearAll:        () => apply(['highlight', 'select'], []),
})
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
