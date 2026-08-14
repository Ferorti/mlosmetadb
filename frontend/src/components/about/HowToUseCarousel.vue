<script setup>
import { ref } from 'vue'

const SLIDES = [
  {
    title: 'Search & Results',
    bullets: [
      "Use the search bar on the Home page to look up a gene name, UniProt ID, or organism.",
      'The Results page lists matching proteins with pagination and sortable columns.',
      'Use the filter sidebar to narrow by organism, LLPS role, MLO, or source database.',
      "Click any row to open that protein's full detail page.",
    ],
    image: '/about/how-to-1.png',
  },
  {
    title: 'Protein page & MLOs',
    bullets: [
      'The Overview tab shows the AlphaFold structure and sequence feature track (IDRs, domains).',
      'The MLO Annotations tab lists every membraneless organelle this protein is linked to, with its role per source database.',
      'The Interactions tab shows protein-protein interaction partners.',
      'Browse by MLO from the MLOs page to see every protein linked to a given organelle.',
    ],
    image: '/about/how-to-2.png',
  },
  {
    title: 'Download & API',
    bullets: [
      'The Download page lets you export a filtered slice of the dataset as TSV or JSON.',
      'Filter by organism, role, and source database before exporting.',
      'The API page documents the public REST endpoints for programmatic access.',
      'Full interactive API reference is available at /docs (Swagger UI).',
    ],
    image: '/about/how-to-3.png',
  },
]

const activeSlide = ref(0)
const mountedSlides = ref(new Set([0]))

function goTo(i) {
  activeSlide.value = i
  mountedSlides.value.add(i)
}

function next() {
  goTo((activeSlide.value + 1) % SLIDES.length)
}

function prev() {
  goTo((activeSlide.value - 1 + SLIDES.length) % SLIDES.length)
}

function onImageError(event) {
  event.target.style.display = 'none'
  event.target.nextElementSibling.style.display = 'flex'
}
</script>

<template>
  <section id="how-to-use" class="scroll-mt-28 mt-10">
    <h2 class="text-lg font-semibold text-gray-800 mb-3">How to Use</h2>

    <div class="bg-white border border-gray-200 rounded-lg p-4">
      <div class="relative md:h-[420px]">
        <div
          v-for="(slide, i) in SLIDES"
          v-show="activeSlide === i"
          :key="slide.title"
        >
          <template v-if="mountedSlides.has(i)">
            <h3 class="text-base font-semibold text-gray-800 mb-3">{{ slide.title }}</h3>
            <div class="flex flex-col md:flex-row gap-6">
              <ul class="order-2 md:order-none flex-1 space-y-2 text-sm text-gray-600 list-disc list-inside">
                <li v-for="(b, bi) in slide.bullets" :key="bi">{{ b }}</li>
              </ul>
              <div class="order-1 md:order-none w-full md:w-[420px] md:flex-shrink-0">
                <div class="aspect-video rounded border border-gray-200 overflow-hidden relative">
                  <img
                    :src="slide.image"
                    :alt="slide.title"
                    class="w-full h-full object-contain bg-gray-50"
                    @error="onImageError"
                  />
                  <div
                    class="absolute inset-0 border-2 border-dashed border-gray-300 bg-gray-50 hidden items-center justify-center text-xs text-gray-400"
                  >
                    Screenshot pending
                  </div>
                </div>
              </div>
            </div>
          </template>
        </div>
      </div>

      <div class="flex items-center justify-center gap-4 mt-4 pt-3 border-t border-gray-100">
        <button @click="prev" class="text-gray-400 hover:text-[#185FA5]" aria-label="Previous slide">‹</button>
        <div class="flex gap-2">
          <button
            v-for="(slide, i) in SLIDES"
            :key="slide.title"
            class="w-2 h-2 rounded-full"
            :class="activeSlide === i ? 'bg-[#185FA5]' : 'bg-gray-300'"
            @click="goTo(i)"
            :aria-label="`Go to slide ${i + 1}`"
          ></button>
        </div>
        <button @click="next" class="text-gray-400 hover:text-[#185FA5]" aria-label="Next slide">›</button>
      </div>
    </div>
  </section>
</template>
