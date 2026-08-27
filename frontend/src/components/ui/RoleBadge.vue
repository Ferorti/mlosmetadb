<script setup>
defineProps({
  role: { type: String, required: true },
})

// Three roles are displayable, and only two of them are `unified_role` values.
// `regulator` is derived from an annotation's raw `source_role` (see
// ProteinMLOs.vue): DrLLPS calls those proteins regulators of the organelle, and
// the project deliberately never wrote 'regulator' into unified_role, because it
// is not a driver/client verdict. Before 2026-08-12 those rows were not served at
// all (R1-ACT-14).
//
// `client` had no entry until now and fell through to the gray badge showing the
// raw string, even though the palette has always assigned it brand-green.
const styles = {
  client:    'bg-[#EEF1EC] text-ink3 border-border',
  regulator: 'bg-[#F6EFE4] text-regulator border-[#E5D3B3]',
}
const labels = {
  driver:    'Driver',
  client:    'MLO Component',
  regulator: 'Regulator',
}
// Only the regulator badge needs explaining: a reader who sees it next to an
// organelle will otherwise assume the protein is inside it.
const titles = {
  regulator: 'Annotated as a regulator of this organelle, not as a resident of it — a curator assignment that applies to the whole protein, not to this compartment specifically',
}
</script>

<template>
  <span
    v-if="role === 'driver'"
    class="text-brand text-[11px] font-medium whitespace-nowrap"
  >
    {{ labels.driver }}
  </span>
  <span
    v-else
    class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium border whitespace-nowrap shrink-0"
    :class="styles[role] ?? 'bg-gray-100 text-gray-500 border-gray-200'"
    :title="titles[role]"
  >
    {{ labels[role] ?? role }}
  </span>
</template>
