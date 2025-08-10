<template>
  <div class="video-player-container">
    <div class="relative bg-black rounded-lg overflow-hidden">
      <video
        ref="videoElement"
        class="w-full h-auto"
        :src="videoUrl"
        @loadedmetadata="onVideoLoaded"
        @timeupdate="onTimeUpdate"
        @play="onPlay"
        @pause="onPause"
        @ended="onEnded"
        @error="onError"
        controls
      >
        Your browser does not support the video tag.
      </video>
      
      <!-- Loading overlay -->
      <div
        v-if="isLoading"
        class="absolute inset-0 flex items-center justify-center bg-black bg-opacity-50"
      >
        <div class="text-white text-center">
          <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-white mx-auto mb-2"></div>
          <p class="text-sm">Loading video...</p>
        </div>
      </div>
      
      <!-- Error overlay -->
      <div
        v-if="hasError"
        class="absolute inset-0 flex items-center justify-center bg-black bg-opacity-75"
      >
        <div class="text-white text-center">
          <svg class="w-12 h-12 mx-auto mb-4 text-red-400" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>
          </svg>
          <p class="text-lg font-medium mb-2">Video Error</p>
          <p class="text-sm text-gray-300">Unable to load video. Please try refreshing the page.</p>
          <button
            @click="retryLoad"
            class="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    </div>
    
    <!-- Video controls info -->
    <div v-if="duration > 0" class="mt-2 text-sm text-gray-600 flex justify-between">
      <span>{{ formatTime(currentTime) }} / {{ formatTime(duration) }}</span>
      <span v-if="isPlaying" class="text-green-600">Playing</span>
      <span v-else class="text-gray-500">Paused</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'

interface Props {
  videoUrl: string
  currentTime?: number
}

interface Emits {
  (e: 'timeUpdate', time: number): void
  (e: 'durationChange', duration: number): void
  (e: 'play'): void
  (e: 'pause'): void
  (e: 'ended'): void
  (e: 'error', error: Event): void
}

const props = withDefaults(defineProps<Props>(), {
  currentTime: 0
})

const emit = defineEmits<Emits>()

const videoElement = ref<HTMLVideoElement | null>(null)
const isLoading = ref(true)
const hasError = ref(false)
const duration = ref(0)
const currentTime = ref(0)
const isPlaying = ref(false)

// Watch for external currentTime changes (from transcription clicks)
watch(() => props.currentTime, (newTime) => {
  if (videoElement.value && Math.abs(videoElement.value.currentTime - newTime) > 1) {
    videoElement.value.currentTime = newTime
  }
})

const onVideoLoaded = () => {
  if (videoElement.value) {
    duration.value = videoElement.value.duration
    isLoading.value = false
    hasError.value = false
    emit('durationChange', duration.value)
  }
}

const onTimeUpdate = () => {
  if (videoElement.value) {
    currentTime.value = videoElement.value.currentTime
    emit('timeUpdate', currentTime.value)
  }
}

const onPlay = () => {
  isPlaying.value = true
  emit('play')
}

const onPause = () => {
  isPlaying.value = false
  emit('pause')
}

const onEnded = () => {
  isPlaying.value = false
  emit('ended')
}

const onError = (error: Event) => {
  isLoading.value = false
  hasError.value = true
  emit('error', error)
}

const retryLoad = () => {
  if (videoElement.value) {
    hasError.value = false
    isLoading.value = true
    videoElement.value.load()
  }
}

const seekTo = (time: number) => {
  if (videoElement.value) {
    videoElement.value.currentTime = time
  }
}

const play = () => {
  if (videoElement.value) {
    videoElement.value.play()
  }
}

const pause = () => {
  if (videoElement.value) {
    videoElement.value.pause()
  }
}

const formatTime = (seconds: number): string => {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const remainingSeconds = Math.floor(seconds % 60)
  
  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`
  }
  return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`
}

// Expose methods for parent component
defineExpose({
  seekTo,
  play,
  pause,
  videoElement
})

onMounted(() => {
  if (videoElement.value) {
    // Set initial time if provided
    if (props.currentTime > 0) {
      videoElement.value.currentTime = props.currentTime
    }
  }
})
</script>