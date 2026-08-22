<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { getMlo } from '@/api/mlos'
import LoadingSpinner from '@/components/ui/LoadingSpinner.vue'

const route = useRoute()
const detail = ref(null)
const loading = ref(true)
const error = ref(false)

async function load(mlo) {
  loading.value = true
  error.value = false
  try {
    const res = await getMlo(mlo)
    detail.value = res.data
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

watch(() => route.params.mlo, (mlo) => { if (mlo) load(mlo) }, { immediate: true })
</script>

<template>
  <div class="max-w-[1080px] mx-auto px-8 py-10">
    <LoadingSpinner v-if="loading" />
    <div v-else-if="error" class="py-24 text-center text-sm text-ink3">
      MLO not found.
    </div>
  </div>
</template>
