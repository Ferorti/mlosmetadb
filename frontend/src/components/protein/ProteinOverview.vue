<script setup>
import { ref, computed, watch } from 'vue'
import { useProteinFeatures } from '@/composables/useProteinFeatures.js'
import ProteinFeatureTrack from '@/components/protein/ProteinFeatureTrack.vue'
import ProteinFeatureTable from '@/components/protein/ProteinFeatureTable.vue'
import ProteinSequence from '@/components/protein/ProteinSequence.vue'
import MolStarViewer from '@/components/viewers/MolStarViewer.vue'

/**
 * Overview section: feature track, sequence, structure and feature table, all
 * linked through a single hover/pin state owned here.
 *
 * Hover is transient; pin survives moving the mouse away, which is the only way
 * to rotate the structure while a region stays marked. Mol* renders highlight
 * and selection in different colors natively, so both can be active at once.
 */

const props = defineProps({
  protein: { type: Object, required: true },
})

const { featureSpans, byId, groups, stats, hasFeatures, sequenceLength } = useProteinFeatures(
  () => props.protein.sequence_features,
  () => props.protein.sequence_length,
)

const hoveredId  = ref(null)
const pinnedId   = ref(null)
const residuePos = ref(null)

const molstarRef = ref(null)

const sequence = computed(() => props.protein.sequence ?? null)

function rangesOf(id) {
  return byId.value.get(id)?.ranges ?? []
}

function onHover(id) {
  hoveredId.value = id
  if (id) residuePos.value = null   // a feature under the cursor outranks a residue
}

function onSelect(id) {
  pinnedId.value = (id && id !== pinnedId.value) ? id : null
}

function onHoverResidue(pos) {
  residuePos.value = pos
}

// Structure highlight channel: a hovered feature wins over a hovered residue,
// and clearing both clears the highlight.
watch([hoveredId, residuePos], ([id, pos]) => {
  const viewer = molstarRef.value
  if (!viewer) return
  if (id)             viewer.highlightRanges(rangesOf(id))
  else if (pos != null) viewer.highlightRanges([{ start: pos, end: pos }])
  else                viewer.highlightRanges([])
})

// Structure selection channel, independent of the highlight above.
watch(pinnedId, (id) => {
  molstarRef.value?.selectRanges(id ? rangesOf(id) : [])
})

// A new protein invalidates every feature id.
watch(() => props.protein.uniprot_id, () => {
  hoveredId.value = null
  pinnedId.value = null
  residuePos.value = null
})
</script>

<template>
  <div>
    <!-- Band 1 — feature track, full width -->
    <div v-if="hasFeatures">
      <div class="text-sm font-medium text-gray-700 mb-2">Sequence features</div>
      <ProteinFeatureTrack
        :spans="featureSpans"
        :sequence-length="sequenceLength"
        :hovered-id="hoveredId"
        :pinned-id="pinnedId"
        :residue-pos="residuePos"
        @hover="onHover"
        @select="onSelect"
      />
      <div v-if="stats" class="text-xs text-center text-[#484E59] mt-1">{{ stats }}</div>
    </div>
    <div v-else class="text-sm text-[#484E59]">No sequence features available.</div>

    <!-- Band 2 — sequence, full width -->
    <div v-if="sequence" class="mt-6">
      <div class="flex items-baseline justify-between mb-2">
        <div class="text-sm font-medium text-gray-700">Protein sequence</div>
        <div class="text-xs text-[#484E59]">{{ sequence.length.toLocaleString() }} aa</div>
      </div>
      <div class="rounded border border-slate-200 bg-slate-50/60 px-3 py-2 overflow-x-auto">
        <ProteinSequence
          :sequence="sequence"
          :spans="featureSpans"
          :hovered-id="hoveredId"
          :pinned-id="pinnedId"
          :residue-pos="residuePos"
          @hover-residue="onHoverResidue"
        />
      </div>
    </div>

    <!-- Band 3 — structure and feature table -->
    <div class="flex gap-6 items-start mt-6">
      <div class="w-[520px] flex-shrink-0">
        <div class="text-sm font-medium text-gray-700 mb-2">AlphaFold structure</div>
        <div class="h-[420px] rounded border border-slate-200 overflow-hidden">
          <MolStarViewer ref="molstarRef" :uniprot-id="protein.uniprot_id" />
        </div>
        <a
          :href="`https://alphafold.ebi.ac.uk/entry/${protein.uniprot_id}`"
          target="_blank" rel="noopener"
          class="text-xs text-[#185FA5] mt-1 inline-block hover:underline"
        >View in AlphaFold DB →</a>
      </div>

      <div class="flex-1 min-w-0">
        <div class="text-sm font-medium text-gray-700 mb-2">Features</div>
        <ProteinFeatureTable
          v-if="hasFeatures"
          :groups="groups"
          :hovered-id="hoveredId"
          :pinned-id="pinnedId"
          @hover="onHover"
          @select="onSelect"
        />
        <div v-else class="text-sm text-[#484E59]">No sequence features available.</div>
      </div>
    </div>
  </div>
</template>
