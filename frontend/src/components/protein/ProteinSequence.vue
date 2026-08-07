<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'

/**
 * Monospace sequence block, linked to the feature track / table / structure.
 *
 * Deliberately renders no per-residue DOM node: monospace character width is
 * constant, so mouse x converts to a residue index arithmetically and feature
 * regions are painted as absolutely-positioned overlays. Titin (34350 aa) is
 * ~290 line elements this way instead of 34350 spans.
 *
 * The letters stay in normal flow (only the overlays are absolute) so that
 * selecting and copying the sequence still works.
 */

const props = defineProps({
  sequence:   { type: String, required: true },
  spans:      { type: Array,  default: () => [] },   // from useProteinFeatures().featureSpans
  hoveredId:  { type: String, default: null },
  pinnedId:   { type: String, default: null },
  residuePos: { type: Number, default: null },
})

const emit = defineEmits(['hover-residue'])

const BLOCK = 10                    // residues per visual block
const LINE_H = 20                   // px, must match the leading-[20px] class below
const GUTTER_GAP = 12               // px between the line number and the letters
const WIDTH_TIERS = [120, 60, 30]   // largest that fits wins
const COLLAPSE_THRESHOLD = 1500     // aa
const COLLAPSED_LINES = 5

const containerRef = ref(null)
const linesRef     = ref(null)
const probeRef     = ref(null)

const charW    = ref(7.2)   // measured on mount; this is only a first-paint guess
const availW   = ref(0)
const expanded = ref(false)

const seqLength = computed(() => props.sequence.length)

const numberW = computed(() => String(seqLength.value).length * charW.value)
const gutterW = computed(() => numberW.value + GUTTER_GAP)

const perLine = computed(() => {
  const usable = availW.value - gutterW.value - numberW.value - GUTTER_GAP
  if (usable <= 0) return WIDTH_TIERS[WIDTH_TIERS.length - 1]
  const fits = n => (n + Math.floor((n - 1) / BLOCK)) * charW.value <= usable
  return WIDTH_TIERS.find(fits) ?? WIDTH_TIERS[WIDTH_TIERS.length - 1]
})

const allLines = computed(() => {
  const out = []
  const n = perLine.value
  for (let i = 0; i < seqLength.value; i += n) {
    const text = props.sequence.slice(i, i + n)
    out.push({
      start: i + 1,                       // 1-based residue of the first character
      end:   i + text.length,
      // Space-separated blocks of 10, which is what the column arithmetic assumes
      text:  text.match(/.{1,10}/g)?.join(' ') ?? text,
    })
  }
  return out
})

const collapsible = computed(() => seqLength.value > COLLAPSE_THRESHOLD)
const lines = computed(() =>
  collapsible.value && !expanded.value ? allLines.value.slice(0, COLLAPSED_LINES) : allLines.value
)

// ─── Column arithmetic ───────────────────────────────────────────────────────
// A line is rendered as blocks of 10 joined by a single space, so the character
// cell of the i-th residue in a line is i + floor(i / 10).
function cellOf(localIndex) {
  return localIndex + Math.floor(localIndex / BLOCK)
}

function residueFromCell(cell) {
  const block  = Math.floor(cell / (BLOCK + 1))
  const offset = Math.min(cell % (BLOCK + 1), BLOCK - 1)   // the gap snaps left
  return block * BLOCK + offset
}

// ─── Overlays ────────────────────────────────────────────────────────────────
const activeSpans = computed(() => {
  const ids = new Set()
  if (props.hoveredId) ids.add(props.hoveredId)
  if (props.pinnedId)  ids.add(props.pinnedId)
  return ids.size ? props.spans.filter(s => ids.has(s.featureId)) : []
})

/** Per-line overlay rectangles for whichever features are hovered or pinned. */
function overlaysFor(line) {
  const out = []
  for (const span of activeSpans.value) {
    const from = Math.max(span.start, line.start)
    const to   = Math.min(span.end, line.end)
    if (from > to) continue
    const a = cellOf(from - line.start)
    const b = cellOf(to - line.start)
    out.push({
      key:    `${span.featureId}:${span.start}:${line.start}`,
      left:   gutterW.value + a * charW.value,
      width:  (b - a + 1) * charW.value,
      color:  span.color,
      pinned: span.featureId === props.pinnedId,
    })
  }
  return out
}

/** Only one residue can be hovered, so this resolves to at most one box. */
const residueBox = computed(() => {
  const pos = props.residuePos
  if (pos == null) return null
  const line = lines.value.find(l => pos >= l.start && pos <= l.end)
  if (!line) return null
  return {
    lineStart: line.start,
    left:      gutterW.value + cellOf(pos - line.start) * charW.value,
    width:     charW.value,
  }
})

// ─── Hover ───────────────────────────────────────────────────────────────────
// One listener for the whole block, coalesced to one emit per animation frame
// and only when the residue index actually changes.
let rafId = null
let pendingPos = null
let lastEmitted = null

function flush() {
  rafId = null
  if (pendingPos !== lastEmitted) {
    lastEmitted = pendingPos
    emit('hover-residue', pendingPos)
  }
}

function queue(pos) {
  pendingPos = pos
  if (rafId == null) rafId = requestAnimationFrame(flush)
}

function onMouseMove(event) {
  const el = linesRef.value
  if (!el) return
  const rect = el.getBoundingClientRect()
  const row  = Math.floor((event.clientY - rect.top) / LINE_H)
  const line = lines.value[row]
  if (!line) { queue(null); return }

  const cell = Math.floor((event.clientX - rect.left - gutterW.value) / charW.value)
  if (cell < 0) { queue(null); return }

  const pos = line.start + residueFromCell(cell)
  queue(pos <= line.end ? pos : null)
}

function onMouseLeave() {
  queue(null)
}

// ─── Measurement ─────────────────────────────────────────────────────────────
let resizeObserver = null

function measure() {
  if (probeRef.value) {
    const w = probeRef.value.getBoundingClientRect().width
    if (w > 0) charW.value = w / 100
  }
  if (containerRef.value) availW.value = containerRef.value.clientWidth
}

onMounted(async () => {
  await nextTick()
  measure()
  if (containerRef.value) {
    resizeObserver = new ResizeObserver(measure)
    resizeObserver.observe(containerRef.value)
  }
})

onUnmounted(() => {
  resizeObserver?.disconnect()
  if (rafId != null) cancelAnimationFrame(rafId)
})
</script>

<template>
  <div ref="containerRef" class="w-full">
    <!-- Width probe: same font as the lines. h-0 + overflow-hidden keeps it from
         contributing height or scroll width while staying measurable. -->
    <div class="h-0 overflow-hidden" aria-hidden="true">
      <span
        ref="probeRef"
        class="inline-block whitespace-pre font-mono text-[12px] leading-[20px]"
      >MMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMM</span>
    </div>

    <div
      ref="linesRef"
      class="font-mono text-[12px] leading-[20px] cursor-crosshair"
      @mousemove="onMouseMove"
      @mouseleave="onMouseLeave"
    >
      <div
        v-for="line in lines"
        :key="line.start"
        class="relative flex"
        style="height: 20px"
      >
        <!-- Feature overlays, behind the letters -->
        <div
          v-for="ov in overlaysFor(line)"
          :key="ov.key"
          class="absolute top-0 h-5 rounded-[2px] pointer-events-none z-0"
          :style="{
            left:  `${ov.left}px`,
            width: `${ov.width}px`,
            backgroundColor: ov.color,
            opacity: ov.pinned ? 0.9 : 0.55,
            boxShadow: ov.pinned ? 'inset 0 0 0 1px #185FA5' : 'none',
          }"
        ></div>

        <!-- Single hovered residue -->
        <div
          v-if="residueBox && residueBox.lineStart === line.start"
          class="absolute top-0 h-5 rounded-[2px] pointer-events-none z-0"
          :style="{
            left:  `${residueBox.left}px`,
            width: `${residueBox.width}px`,
            boxShadow: 'inset 0 0 0 1px #185FA5',
          }"
        ></div>

        <span
          class="relative z-10 text-right text-[#484E59] tabular-nums flex-shrink-0 select-none"
          :style="{ width: `${numberW}px`, marginRight: `${GUTTER_GAP}px` }"
        >{{ line.start }}</span>

        <span class="relative z-10 whitespace-pre text-gray-800">{{ line.text }}</span>

        <span
          class="relative z-10 text-[#484E59] tabular-nums flex-shrink-0 select-none"
          :style="{ marginLeft: `${GUTTER_GAP}px` }"
        >{{ line.end }}</span>
      </div>
    </div>

    <button
      v-if="collapsible"
      class="mt-2 text-xs text-[#185FA5] hover:underline"
      @click="expanded = !expanded"
    >
      {{ expanded
        ? 'Collapse sequence'
        : `Show full sequence (${seqLength.toLocaleString()} aa)` }}
    </button>
  </div>
</template>
