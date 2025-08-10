<template>
  <div class="transcription-viewer">
    <div class="mb-4 flex justify-between items-center">
      <h3 class="text-lg font-semibold text-gray-900">Transcription</h3>
      <div class="text-sm text-gray-500">
        {{ transcriptions.length }} segments
      </div>
    </div>

    <!-- Search functionality -->
    <div class="mb-4">
      <div class="relative">
        <input v-model="searchQuery" type="text" placeholder="Search transcription..."
          class="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent">
        <svg class="absolute left-3 top-2.5 h-5 w-5 text-gray-400" fill="none" stroke="currentColor"
          viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
      </div>
    </div>

    <!-- Transcription content -->
    <div ref="transcriptionContainer" class="max-h-96 overflow-y-auto border border-gray-200 rounded-lg bg-gray-50">
      <div v-if="filteredTranscriptions.length === 0" class="p-6 text-center text-gray-500">
        <div v-if="searchQuery">
          No transcription segments match your search.
        </div>
        <div v-else>
          No transcription available.
        </div>
      </div>

      <div v-else class="space-y-1 p-4">
        <div v-for="transcription in filteredTranscriptions" :key="transcription.id"
          :ref="el => setTranscriptionRef(transcription.id, el)" :class="[
            'transcription-segment p-3 rounded-lg cursor-pointer transition-all duration-200',
            {
              'bg-blue-100 border-l-4 border-blue-500 shadow-sm': isCurrentSegment(transcription),
              'bg-white hover:bg-gray-100 border-l-4 border-transparent': !isCurrentSegment(transcription),
              'ring-2 ring-yellow-300': isSearchHighlighted(transcription)
            }
          ]" @click="onTimestampClick(transcription.start_time)">
          <div class="flex items-start justify-between mb-2">
            <div class="flex items-center space-x-2">
              <span class="font-medium text-gray-900 text-sm">
                {{ transcription.speaker || 'Unknown Speaker' }}
              </span>
              <span class="text-xs px-2 py-1 bg-gray-200 text-gray-600 rounded-full hover:bg-blue-200 transition-colors"
                :title="`Click to jump to ${formatTime(transcription.start_time)}`">
                {{ formatTime(transcription.start_time) }}
              </span>
            </div>
            <div class="text-xs text-gray-500">
              {{ formatDuration(transcription.end_time - transcription.start_time) }}
            </div>
          </div>

          <p class="text-gray-700 leading-relaxed" v-html="highlightSearchTerm(transcription.text)"></p>
        </div>
      </div>
    </div>


  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'

interface Transcription {
  id: number
  speaker: string
  text: string
  start_time: number
  end_time: number
  confidence: number
}

interface Props {
  transcriptions: Transcription[]
  currentTime: number
}

interface Emits {
  (e: 'timestampClick', time: number): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const transcriptionContainer = ref<HTMLElement | null>(null)
const transcriptionRefs = ref<Map<number, HTMLElement>>(new Map())
const searchQuery = ref('')
const currentSegmentIndex = ref(-1)

// Filter transcriptions based on search query
const filteredTranscriptions = computed(() => {
  if (!searchQuery.value.trim()) {
    return props.transcriptions
  }

  const query = searchQuery.value.toLowerCase()
  return props.transcriptions.filter(t =>
    t.text.toLowerCase().includes(query) ||
    t.speaker.toLowerCase().includes(query)
  )
})

// Find current segment based on video time
const currentSegment = computed(() => {
  return props.transcriptions.find(t =>
    props.currentTime >= t.start_time && props.currentTime <= t.end_time
  )
})

// Check if a transcription segment is currently active
const isCurrentSegment = (transcription: Transcription): boolean => {
  return currentSegment.value?.id === transcription.id
}

// Check if a transcription segment matches search
const isSearchHighlighted = (transcription: Transcription): boolean => {
  if (!searchQuery.value.trim()) return false
  const query = searchQuery.value.toLowerCase()
  return transcription.text.toLowerCase().includes(query) ||
    transcription.speaker.toLowerCase().includes(query)
}

// Navigation helpers
const hasPrevious = computed(() => currentSegmentIndex.value > 0)
const hasNext = computed(() => currentSegmentIndex.value < filteredTranscriptions.value.length - 1)

// Set transcription element ref
const setTranscriptionRef = (id: number, el: any) => {
  if (el) {
    transcriptionRefs.value.set(id, el)
  } else {
    transcriptionRefs.value.delete(id)
  }
}

// Handle timestamp click
const onTimestampClick = (time: number) => {
  emit('timestampClick', time)
}

// Scroll to current segment
const scrollToCurrentSegment = async () => {
  if (!currentSegment.value || !transcriptionContainer.value) return

  await nextTick()

  const element = transcriptionRefs.value.get(currentSegment.value.id)
  if (element) {
    element.scrollIntoView({
      behavior: 'smooth',
      block: 'center'
    })
  }
}

// Navigation functions
const scrollToPrevious = () => {
  if (hasPrevious.value) {
    currentSegmentIndex.value--
    const transcription = filteredTranscriptions.value[currentSegmentIndex.value]
    onTimestampClick(transcription.start_time)
  }
}

const scrollToNext = () => {
  if (hasNext.value) {
    currentSegmentIndex.value++
    const transcription = filteredTranscriptions.value[currentSegmentIndex.value]
    onTimestampClick(transcription.start_time)
  }
}

// Format time display
const formatTime = (seconds: number): string => {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const remainingSeconds = Math.floor(seconds % 60)

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`
  }
  return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`
}

// Format duration
const formatDuration = (seconds: number): string => {
  if (seconds < 60) {
    return `${Math.round(seconds)}s`
  }
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = Math.round(seconds % 60)
  return `${minutes}m ${remainingSeconds}s`
}

// Highlight search terms in text
const highlightSearchTerm = (text: string): string => {
  if (!searchQuery.value.trim()) return text

  const query = searchQuery.value.trim()
  const regex = new RegExp(`(${query})`, 'gi')
  return text.replace(regex, '<mark class="bg-yellow-200 px-1 rounded">$1</mark>')
}

// Watch for current segment changes and update index
watch(currentSegment, (newSegment) => {
  if (newSegment) {
    const index = filteredTranscriptions.value.findIndex(t => t.id === newSegment.id)
    currentSegmentIndex.value = index
    scrollToCurrentSegment()
  }
})

// Watch for search query changes and reset index
watch(searchQuery, () => {
  currentSegmentIndex.value = -1
})

// Expose methods and state for parent component
defineExpose({
  scrollToPrevious,
  scrollToNext,
  hasPrevious,
  hasNext,
  currentSegmentIndex,
  filteredTranscriptions
})
</script>

<style scoped>
.transcription-segment {
  scroll-margin-top: 1rem;
}

:deep(mark) {
  background-color: rgb(254 240 138);
  padding: 0.125rem 0.25rem;
  border-radius: 0.25rem;
}
</style>