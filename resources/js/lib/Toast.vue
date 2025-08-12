<template>
  <Teleport to="body">
    <div class="fixed top-4 right-4 z-50 space-y-2">
      <TransitionGroup
        name="toast"
        tag="div"
        class="space-y-2"
      >
        <div
          v-for="toast in toasts"
          :key="toast.id"
          :class="[
            'max-w-sm w-full bg-white shadow-lg rounded-lg pointer-events-auto ring-1 ring-black ring-opacity-5 overflow-hidden',
            toast.type === 'success' && 'border-l-4 border-green-400',
            toast.type === 'error' && 'border-l-4 border-red-400',
            toast.type === 'warning' && 'border-l-4 border-yellow-400',
            toast.type === 'info' && 'border-l-4 border-blue-400'
          ]"
        >
          <div class="p-4">
            <div class="flex items-start">
              <div class="flex-shrink-0">
                <!-- Success Icon -->
                <svg
                  v-if="toast.type === 'success'"
                  class="h-5 w-5 text-green-400"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fill-rule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                    clip-rule="evenodd"
                  />
                </svg>
                
                <!-- Error Icon -->
                <svg
                  v-else-if="toast.type === 'error'"
                  class="h-5 w-5 text-red-400"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fill-rule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                    clip-rule="evenodd"
                  />
                </svg>
                
                <!-- Warning Icon -->
                <svg
                  v-else-if="toast.type === 'warning'"
                  class="h-5 w-5 text-yellow-400"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fill-rule="evenodd"
                    d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                    clip-rule="evenodd"
                  />
                </svg>
                
                <!-- Info Icon -->
                <svg
                  v-else
                  class="h-5 w-5 text-blue-400"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fill-rule="evenodd"
                    d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
                    clip-rule="evenodd"
                  />
                </svg>
              </div>
              
              <div class="ml-3 w-0 flex-1">
                <p
                  :class="[
                    'text-sm font-medium',
                    toast.type === 'success' && 'text-green-800',
                    toast.type === 'error' && 'text-red-800',
                    toast.type === 'warning' && 'text-yellow-800',
                    toast.type === 'info' && 'text-blue-800'
                  ]"
                >
                  {{ toast.title }}
                </p>
                <p
                  v-if="toast.message"
                  :class="[
                    'mt-1 text-sm',
                    toast.type === 'success' && 'text-green-700',
                    toast.type === 'error' && 'text-red-700',
                    toast.type === 'warning' && 'text-yellow-700',
                    toast.type === 'info' && 'text-blue-700'
                  ]"
                >
                  {{ toast.message }}
                </p>
                
                <!-- Action buttons -->
                <div v-if="toast.actions && toast.actions.length > 0" class="mt-3 flex space-x-2">
                  <button
                    v-for="action in toast.actions"
                    :key="action.label"
                    @click="action.handler"
                    :class="[
                      'text-sm font-medium rounded-md px-3 py-1 transition-colors',
                      action.primary
                        ? 'bg-blue-600 text-white hover:bg-blue-700'
                        : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                    ]"
                  >
                    {{ action.label }}
                  </button>
                </div>
              </div>
              
              <div class="ml-4 flex-shrink-0 flex">
                <button
                  @click="removeToast(toast.id)"
                  class="bg-white rounded-md inline-flex text-gray-400 hover:text-gray-500 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                >
                  <span class="sr-only">Close</span>
                  <svg class="h-5 w-5" fill="currentColor" viewBox="0 0 20 20">
                    <path
                      fill-rule="evenodd"
                      d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                      clip-rule="evenodd"
                    />
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'

export interface ToastAction {
  label: string
  handler: () => void
  primary?: boolean
}

export interface Toast {
  id: string
  type: 'success' | 'error' | 'warning' | 'info'
  title: string
  message?: string
  duration?: number
  actions?: ToastAction[]
}

const toasts = ref<Toast[]>([])

const addToast = (toast: Omit<Toast, 'id'>) => {
  const id = Math.random().toString(36).substr(2, 9)
  const newToast = { ...toast, id }
  
  toasts.value.push(newToast)
  
  // Auto remove after duration
  if (toast.duration !== 0) {
    setTimeout(() => {
      removeToast(id)
    }, toast.duration || 5000)
  }
  
  return id
}

const removeToast = (id: string) => {
  const index = toasts.value.findIndex(t => t.id === id)
  if (index > -1) {
    toasts.value.splice(index, 1)
  }
}

const clearAll = () => {
  toasts.value = []
}

// Global toast methods
const showSuccess = (title: string, message?: string, options?: Partial<Toast>) => {
  return addToast({ type: 'success', title, message, ...options })
}

const showError = (title: string, message?: string, options?: Partial<Toast>) => {
  return addToast({ type: 'error', title, message, ...options })
}

const showWarning = (title: string, message?: string, options?: Partial<Toast>) => {
  return addToast({ type: 'warning', title, message, ...options })
}

const showInfo = (title: string, message?: string, options?: Partial<Toast>) => {
  return addToast({ type: 'info', title, message, ...options })
}

// Expose methods globally
onMounted(() => {
  window.toast = {
    success: showSuccess,
    error: showError,
    warning: showWarning,
    info: showInfo,
    remove: removeToast,
    clear: clearAll
  }
})

defineExpose({
  addToast,
  removeToast,
  clearAll,
  showSuccess,
  showError,
  showWarning,
  showInfo
})
</script>

<style scoped>
.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}

.toast-enter-from {
  opacity: 0;
  transform: translateX(100%);
}

.toast-leave-to {
  opacity: 0;
  transform: translateX(100%);
}

.toast-move {
  transition: transform 0.3s ease;
}
</style>