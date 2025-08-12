<template>
  <Teleport to="body">
    <Transition
      name="slide-down"
      enter-active-class="transition-transform duration-300 ease-out"
      enter-from-class="-translate-y-full"
      enter-to-class="translate-y-0"
      leave-active-class="transition-transform duration-300 ease-in"
      leave-from-class="translate-y-0"
      leave-to-class="-translate-y-full"
    >
      <div
        v-if="!isOnline"
        class="fixed top-0 left-0 right-0 z-50 bg-red-600 text-white px-4 py-2 text-center text-sm font-medium"
      >
        <div class="flex items-center justify-center space-x-2">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                  d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span>No internet connection. Some features may not work properly.</span>
        </div>
      </div>
    </Transition>
    
    <Transition
      name="slide-down"
      enter-active-class="transition-all duration-500 ease-out"
      enter-from-class="-translate-y-full opacity-0"
      enter-to-class="translate-y-0 opacity-100"
      leave-active-class="transition-all duration-300 ease-in"
      leave-from-class="translate-y-0 opacity-100"
      leave-to-class="-translate-y-full opacity-0"
    >
      <div
        v-if="showReconnected"
        class="fixed top-0 left-0 right-0 z-50 bg-green-600 text-white px-4 py-2 text-center text-sm font-medium"
      >
        <div class="flex items-center justify-center space-x-2">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                  d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span>Connection restored!</span>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

const isOnline = ref(navigator.onLine)
const showReconnected = ref(false)
let reconnectedTimeout: number | null = null

const handleOnline = () => {
  isOnline.value = true
  showReconnected.value = true
  
  // Hide reconnected message after 3 seconds
  if (reconnectedTimeout) {
    clearTimeout(reconnectedTimeout)
  }
  reconnectedTimeout = window.setTimeout(() => {
    showReconnected.value = false
  }, 3000)
}

const handleOffline = () => {
  isOnline.value = false
  showReconnected.value = false
  
  if (reconnectedTimeout) {
    clearTimeout(reconnectedTimeout)
    reconnectedTimeout = null
  }
}

onMounted(() => {
  window.addEventListener('online', handleOnline)
  window.addEventListener('offline', handleOffline)
})

onUnmounted(() => {
  window.removeEventListener('online', handleOnline)
  window.removeEventListener('offline', handleOffline)
  
  if (reconnectedTimeout) {
    clearTimeout(reconnectedTimeout)
  }
})

// Expose online status globally
defineExpose({
  isOnline
})
</script>