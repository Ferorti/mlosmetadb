<script setup>
import { ref, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { getMlo } from '@/api/mlos'
import { formatMlo, formatCount } from '@/utils/format'
import {
  spatialLocationLabel, spatialLocationNote, isSpatialLocationProvisional,
  taxonomicScopeLabel, taxonomicScopeNote, isTaxonomicScopeThin,
  physiologicalStateLabel, cellTypeContextLabel,
} from '@/utils/mloAxes'
import RoleBadge from '@/components/ui/RoleBadge.vue'
import LoadingSpinner from '@/components/ui/LoadingSpinner.vue'

const route = useRoute()
const detail = ref(null)
const loading = ref(true)
const error = ref(false)
const roleFilter = ref('all')   // 'all' | 'driver' | 'component'

async function load(mlo) {
  loading.value = true
  error.value = false
  try {
    const res = await getMlo(mlo, roleFilter.value === 'all' ? {} : { role: roleFilter.value })
    detail.value = res.data
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

watch(() => route.params.mlo, (mlo) => { if (mlo) load(mlo) }, { immediate: true })
watch(roleFilter, () => load(route.params.mlo))

const MATRIX_SOURCES = ['CDCODE', 'DrLLPS', 'LLPSDB', 'PhasePro', 'PhaSepDB']

const headerStats = computed(() => {
  if (!detail.value) return []
  const s = detail.value.stats
  const sourceCount = Object.keys(s.by_source ?? {}).length
  return [
    { value: formatCount(s.total_proteins), label: 'PROTEINS' },
    { value: formatCount(s.by_role?.driver ?? 0), label: 'LLPS DRIVERS' },
    { value: sourceCount, label: 'SOURCES' },
  ]
})

// 3 real buckets (driver/regulator/component) -- NOT 4, see spec §5.3.
// component already absorbs NULL-role rows server-side
// (mlo_queries.py::get_mlo_stats()'s CASE `else` branch).
const roleRows = computed(() => {
  if (!detail.value) return []
  const by = detail.value.stats.by_role ?? {}
  const max = Math.max(1, ...Object.values(by))
  const ROLE_META = {
    driver:    { label: 'LLPS Drivers',    color: '#1560A8', description: 'Proteins with direct experimental evidence of driving liquid-liquid phase separation and/or MLO formation. Annotated as driver or scaffold in at least one source database.' },
    component: { label: 'MLO Components',  color: '#4E5762', description: 'Proteins associated with membraneless organelles without direct evidence of driving phase separation. Includes clients and proteins whose role no source determined.' },
    regulator: { label: 'MLO Regulators',  color: '#854F0B', description: 'Proteins a curator annotated as regulating an organelle rather than driving or residing in it. Curator-assigned in at least one source database.' },
  }
  return Object.entries(ROLE_META)
    .filter(([key]) => by[key] != null)
    .map(([key, meta]) => ({ ...meta, count: by[key], pct: Math.round((by[key] / max) * 100) }))
})

const termRows = computed(() => (detail.value?.definitions ?? []).map(d => ({
  source: d.source_db, term: d.source_name ?? d.definition ?? '—',
})))

const proteinRows = computed(() => (detail.value?.proteins?.items ?? []).map(p => ({
  uniprot_id: p.uniprot_id, gene_name: p.gene_name, organism: p.organism,
  role: p.unified_role, disorder: p.disorder_mobidb_lite_dc,
  sources: p.sources ?? [],
})))
</script>

<template>
  <div v-if="loading" class="max-w-[1080px] mx-auto px-8 py-16"><LoadingSpinner /></div>
  <div v-else-if="error" class="max-w-[1080px] mx-auto px-8 py-24 text-center text-sm text-ink3">
    MLO not found.
  </div>

  <template v-else-if="detail">
    <div class="bg-surface border-b border-border">
      <div class="max-w-[1080px] mx-auto px-8 pt-8 pb-9">
        <div class="font-mono text-[11.5px] text-ink3 mb-4">
          <RouterLink to="/mlos" class="text-brand hover:underline">MLOs</RouterLink>
          / {{ spatialLocationLabel(detail.spatial_location) }} / {{ formatMlo(detail.unified_mlo) }}
        </div>

        <div class="flex justify-between items-start gap-11 flex-wrap">
          <div>
            <h1 class="font-display font-bold text-[42px] leading-none tracking-[-0.035em] text-ink">{{ formatMlo(detail.unified_mlo) }}</h1>
            <div class="mt-4 font-mono text-xs text-ink3 flex gap-4 flex-wrap items-center">
              <span :title="spatialLocationNote(detail) || undefined" class="flex items-center gap-1.5"
                    :class="isSpatialLocationProvisional(detail) ? 'text-[#854F0B]' : ''">
                {{ spatialLocationLabel(detail.spatial_location) }}
                <span v-if="isSpatialLocationProvisional(detail)">· provisional</span>
              </span>
              <span v-if="detail.physiological_state">{{ physiologicalStateLabel(detail.physiological_state) }}</span>
              <span v-if="detail.cell_type_context">{{ cellTypeContextLabel(detail.cell_type_context) }}</span>
              <span v-if="detail.taxonomic_scope" :title="taxonomicScopeNote(detail)"
                    :class="isTaxonomicScopeThin(detail) ? 'text-[#854F0B]' : ''">
                {{ taxonomicScopeLabel(detail.taxonomic_scope) }}
                ({{ detail.taxonomic_support_n }}{{ isTaxonomicScopeThin(detail) ? ', thin' : '' }})
              </span>
            </div>
          </div>
          <div class="flex gap-9 flex-shrink-0">
            <div v-for="s in headerStats" :key="s.label">
              <div class="font-display font-semibold text-[28px] leading-none tracking-[-0.02em] text-ink">{{ s.value }}</div>
              <div class="font-mono text-[10.5px] text-ink3 tracking-[0.07em] mt-[7px]">{{ s.label }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <main class="max-w-[1080px] mx-auto px-8 py-11">
      <!-- Source terms mapped here -->
      <section class="mb-[62px]">
        <div class="flex items-baseline gap-3.5 border-b border-border pb-[11px] mb-3">
          <h2 class="text-[17px] font-medium tracking-[-0.01em] text-ink">Source terms mapped here</h2>
          <span class="font-mono text-[11px] text-muted">{{ termRows.length }} strings</span>
        </div>
        <p class="text-[13.5px] text-ink3 max-w-[64ch] mb-5">
          Every string below was collapsed into the unified term
          <em>{{ formatMlo(detail.unified_mlo) }}</em>. The original wording is
          preserved on each annotation, so a mapping decision can always be
          traced back.
        </p>
        <table class="w-full border-collapse">
          <thead>
            <tr>
              <th class="text-left pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 tracking-[0.07em]">SOURCE</th>
              <th class="text-left px-3 pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 tracking-[0.07em]">TERM AS WRITTEN IN THE SOURCE</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(t, i) in termRows" :key="i" class="border-b border-border-soft">
              <td class="py-2.5 pr-3 font-mono text-[11.5px] text-ink3 whitespace-nowrap">{{ t.source }}</td>
              <td class="py-2.5 px-3 text-[13.5px] text-ink">{{ t.term }}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <!-- Roles -->
      <section class="mb-[62px]" v-if="roleRows.length">
        <div class="border-b border-border pb-[11px] mb-5">
          <h2 class="text-[17px] font-medium tracking-[-0.01em] text-ink">Roles</h2>
        </div>
        <div class="flex flex-col gap-3.5">
          <div v-for="r in roleRows" :key="r.label">
            <div class="flex justify-between items-baseline gap-3">
              <span class="text-[13.5px] text-ink">{{ r.label }}</span>
              <span class="font-mono text-xs text-ink">{{ formatCount(r.count) }}</span>
            </div>
            <div class="h-[5px] bg-track rounded-[1px] mt-1.5">
              <div class="h-[5px] rounded-[1px]" :style="{ background: r.color, width: r.pct + '%' }"></div>
            </div>
            <div class="text-[12.5px] text-ink3 mt-1.5">{{ r.description }}</div>
          </div>
        </div>
      </section>

      <!-- Proteins -->
      <section>
        <div class="flex justify-between items-baseline gap-5 border-b border-border pb-[11px] mb-4.5">
          <div class="flex items-baseline gap-3.5">
            <h2 class="text-[17px] font-medium tracking-[-0.01em] text-ink">Proteins</h2>
            <span class="font-mono text-[11px] text-muted">{{ proteinRows.length }} shown of {{ formatCount(detail.stats.total_proteins) }}</span>
          </div>
          <div class="flex gap-2">
            <button
              v-for="opt in [['all','All'],['driver','Drivers'],['component','Components']]"
              :key="opt[0]"
              class="font-mono text-[11.5px] px-3 py-1.5 rounded-[2px]"
              :class="roleFilter === opt[0] ? 'border border-ink bg-ink text-page' : 'border border-border-strong text-ink2'"
              @click="roleFilter = opt[0]"
            >{{ opt[1] }}</button>
          </div>
        </div>
        <table class="w-full border-collapse">
          <thead>
            <tr>
              <th class="text-left pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 tracking-[0.07em]">GENE</th>
              <th class="text-right px-3 pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 tracking-[0.07em] w-[74px]">DISORDER</th>
              <th class="text-center px-3 pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 tracking-[0.07em] w-[96px]">SOURCES</th>
              <th class="text-right pl-3 pb-[9px] border-b border-border-strong font-mono text-[10.5px] font-normal text-ink3 tracking-[0.07em] w-[82px]">ROLE</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in proteinRows" :key="p.uniprot_id" class="border-b border-border-soft">
              <td class="py-2.5 pr-3">
                <RouterLink :to="`/protein/${p.uniprot_id}`" class="text-[14px] font-medium text-ink hover:text-brand">{{ p.gene_name || p.uniprot_id }}</RouterLink>
                <span class="block font-mono text-[10.5px] text-muted mt-0.5">{{ p.uniprot_id }}</span>
              </td>
              <td class="py-2.5 px-3 text-right font-mono text-xs text-ink">{{ p.disorder != null ? Math.round(p.disorder * 100) + '%' : '—' }}</td>
              <td class="py-2.5 px-3">
                <div class="flex gap-1.5 justify-center">
                  <span v-for="src in MATRIX_SOURCES" :key="src" :title="p.sources.includes(src) ? src : `${src}: not annotated`"
                        class="inline-block" :class="p.sources.includes(src) ? 'w-[7px] h-[7px] rounded-full bg-ink' : 'w-[7px] h-px bg-border-strong mt-[3px]'"></span>
                </div>
              </td>
              <td class="py-2.5 pl-3 text-right">
                <RoleBadge v-if="p.role" :role="p.role" />
              </td>
            </tr>
          </tbody>
        </table>
      </section>
    </main>
  </template>
</template>
