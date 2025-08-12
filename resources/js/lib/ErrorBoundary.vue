<template>
  <div v-if="hasError" class="min-h-screen flex items-center justify-center bg-gray-50">
    <div class="max-w-md w-full bg-white rounded-lg shadow-lg p-6 text-center">
      <div class="w-16 h-16 mx-auto mb-4 bg-red-100 rounded-full flex items-center justify-center">
        <svg class="w-8 h-8 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
        </svg>
      </div>
      
      <h2 class="text-xl font-semibold text-gray-900 mb-2">Something went wrong</h2>
      <p class="text-gray-600 mb-6">
        We encountered an unexpected error. Please try refreshing the page or contact support if the problem persists.
      </p>
      
      <div class="space-y-3">
        <button
          @click="retry"
          class="w-full bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 transition-colors"
        >
          Try Again
        </button>
        
        <button
          @click="goHome"
          class="w-full bg-gray-100 text-gray-700 px-4 py-2 rounded-md hover:bg-gray-200 transition-colors"
        >
          Go to Dashboard
        </button>
      </div>
      
      <details v-if="errorDetails" class="mt-6 text-left">
        <summary class="cursor-pointer text-sm text-gray-500 hover:text-gray-700">
          Technical Details
        </summary>
        <pre class="mt-2 text-xs bg-gray-100 p-3 rounded overflow-auto max-h-32">{{ errorDetails }}</pre>
      </details>
    </div>
  </div>
  
  <slot v-else />
</template>

<script setup lang="ts">
import { ref, onErrorCaptured } from 'vue'
import { router } from '@inertiajs/vue3'

const hasError = ref(false)
const errorDetails = ref<string>('')

onErrorCaptured((error: Error) => {
  hasError.value = true
  errorDetails.value = error.stack || error.message
  console.error('Error caught by ErrorBoundary:', error)
  return false // Prevent error from propagating
})

const retry = () => {
  hasError.value = false
  errorDetails.value = ''
  window.location.reload()
}

const goHome = () => {
  router.visit('/')
}
</script>