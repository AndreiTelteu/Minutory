<template>
  <div v-if="!meeting" class="flex items-center space-x-2">
    <!-- Loading State -->
    <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
      <svg class="animate-spin -ml-1 mr-1.5 h-3 w-3" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
      Loading...
    </span>
  </div>
  
  <div v-else class="flex items-center space-x-2">
    <!-- Status Badge -->
    <span
      :class="[
        'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
        statusClasses
      ]"
    >
      <svg
        v-if="showSpinner"
        class="animate-spin -ml-1 mr-1.5 h-3 w-3"
        fill="none"
        viewBox="0 0 24 24"
      >
        <circle
          class="opacity-25"
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          stroke-width="4"
        ></circle>
        <path
          class="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
        ></path>
      </svg>
      
      <svg
        v-else-if="statusIcon"
        class="-ml-0.5 mr-1.5 h-3 w-3"
        :class="iconClasses"
        fill="currentColor"
        viewBox="0 0 20 20"
      >
        <path :d="statusIcon" />
      </svg>
      
      {{ statusText }}
    </span>

    <!-- Error Details Button -->
    <button
      v-if="meeting && meeting.status === 'failed' && meeting.error_message"
      @click="showErrorDetails = !showErrorDetails"
      class="text-red-600 hover:text-red-800 transition-colors"
      title="Show error details"
    >
      <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
        />
      </svg>
    </button>

    <!-- Retry Button -->
    <button
      v-if="meeting && meeting.status === 'failed' && canRetry"
      @click="$emit('retry')"
      :disabled="isRetrying"
      class="text-blue-600 hover:text-blue-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      title="Retry processing"
    >
      <svg
        class="h-4 w-4"
        :class="{ 'animate-spin': isRetrying }"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
        />
      </svg>
    </button>
  </div>

  <!-- Error Details Modal/Dropdown -->
  <Transition
    name="slide-down"
    enter-active-class="transition-all duration-200 ease-out"
    enter-from-class="opacity-0 -translate-y-2"
    enter-to-class="opacity-100 translate-y-0"
    leave-active-class="transition-all duration-150 ease-in"
    leave-from-class="opacity-100 translate-y-0"
    leave-to-class="opacity-0 -translate-y-2"
  >
    <div
      v-if="showErrorDetails && meeting && meeting.status === 'failed'"
      class="mt-3 p-4 bg-red-50 border border-red-200 rounded-md"
    >
      <div class="flex items-start">
        <svg class="h-5 w-5 text-red-400 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
          <path
            fill-rule="evenodd"
            d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
            clip-rule="evenodd"
          />
        </svg>
        <div class="ml-3 flex-1">
          <h4 class="text-sm font-medium text-red-800">Processing Failed</h4>
          <p class="text-sm text-red-700 mt-1">{{ meeting.error_message }}</p>
          
          <div class="mt-3 flex space-x-3">
            <button
              v-if="canRetry"
              @click="$emit('retry')"
              :disabled="isRetrying"
              class="text-sm bg-red-100 text-red-800 px-3 py-1 rounded-md hover:bg-red-200 disabled:opacity-50 transition-colors"
            >
              {{ isRetrying ? 'Retrying...' : 'Try Again' }}
            </button>
            
            <button
              @click="showTechnicalDetails = !showTechnicalDetails"
              class="text-sm text-red-600 hover:text-red-800 transition-colors"
            >
              {{ showTechnicalDetails ? 'Hide' : 'Show' }} Technical Details
            </button>
          </div>
          
          <details v-if="showTechnicalDetails && meeting.technical_error" class="mt-3">
            <summary class="cursor-pointer text-sm text-red-600 hover:text-red-800">
              Technical Error Details
            </summary>
            <pre class="mt-2 text-xs bg-red-100 p-3 rounded overflow-auto max-h-32 text-red-800">{{ meeting.technical_error }}</pre>
          </details>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

interface Meeting {
  id: number
  status: 'pending' | 'processing' | 'completed' | 'failed'
  processing_progress?: number
  queue_progress?: number
  formatted_elapsed_time?: string
  formatted_estimated_remaining_time?: string
  error_message?: string
  technical_error?: string
}

interface Props {
  meeting?: Meeting | null
  showProgress?: boolean
  canRetry?: boolean
  isRetrying?: boolean
}

interface Emits {
  (e: 'retry'): void
}

const props = withDefaults(defineProps<Props>(), {
  showProgress: true,
  canRetry: true,
  isRetrying: false
})

defineEmits<Emits>()

const showErrorDetails = ref(false)
const showTechnicalDetails = ref(false)

const statusClasses = computed(() => {
  if (!props.meeting) return 'bg-gray-100 text-gray-800'
  
  switch (props.meeting.status) {
    case 'pending':
      return 'bg-yellow-100 text-yellow-800'
    case 'processing':
      return 'bg-blue-100 text-blue-800'
    case 'completed':
      return 'bg-green-100 text-green-800'
    case 'failed':
      return 'bg-red-100 text-red-800'
    default:
      return 'bg-gray-100 text-gray-800'
  }
})

const iconClasses = computed(() => {
  if (!props.meeting) return 'text-gray-600'
  
  switch (props.meeting.status) {
    case 'pending':
      return 'text-yellow-600'
    case 'processing':
      return 'text-blue-600'
    case 'completed':
      return 'text-green-600'
    case 'failed':
      return 'text-red-600'
    default:
      return 'text-gray-600'
  }
})

const statusIcon = computed(() => {
  if (!props.meeting) return null
  
  switch (props.meeting.status) {
    case 'pending':
      return 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z' // Clock icon
    case 'completed':
      return 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z' // Check circle
    case 'failed':
      return 'M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z' // X circle
    default:
      return null
  }
})

const showSpinner = computed(() => {
  if (!props.meeting) return props.isRetrying
  return props.meeting.status === 'processing' || props.isRetrying
})

const statusText = computed(() => {
  if (!props.meeting) return 'Loading...'
  
  switch (props.meeting.status) {
    case 'pending':
      return 'Pending'
    case 'processing':
      return 'Processing'
    case 'completed':
      return 'Completed'
    case 'failed':
      return 'Failed'
    default:
      return 'Unknown'
  }
})

const progressPercentage = computed(() => {
  if (!props.meeting) return null
  
  if (props.meeting.status === 'pending' && props.meeting.queue_progress !== undefined) {
    return props.meeting.queue_progress
  }
  if (props.meeting.status === 'processing' && props.meeting.processing_progress !== undefined) {
    return props.meeting.processing_progress
  }
  return null
})

const timeInfo = computed(() => {
  if (!props.meeting || props.meeting.status !== 'processing') return null
  
  const elapsed = props.meeting.formatted_elapsed_time
  const remaining = props.meeting.formatted_estimated_remaining_time
  if (elapsed && remaining) {
    return `${elapsed} elapsed, ~${remaining} remaining`
  } else if (elapsed) {
    return `${elapsed} elapsed`
  }
  return null
})
</script>