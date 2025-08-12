<template>
  <AppLayout>
    <div class="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div class="mb-8">
        <Link :href="route('meetings.index')" class="text-blue-600 hover:text-blue-700 font-medium">
        ← Back to Meetings
        </Link>
        <h1 class="text-3xl font-bold text-gray-900 mt-4">Upload Meeting</h1>
        <p class="text-gray-600 mt-2">
          Upload a meeting video to automatically transcribe and analyze the content.
        </p>
      </div>

      <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <form @submit.prevent="submit" enctype="multipart/form-data">
          <!-- Meeting Title -->
          <div class="mb-6">
            <label for="title" class="block text-sm font-medium text-gray-700 mb-2">
              Meeting Title *
            </label>
            <input id="title" v-model="form.title" type="text" required
              class="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
              :class="{ 'border-red-300': errors.title }" placeholder="Enter a descriptive title for this meeting" />
            <p v-if="errors.title" class="mt-1 text-sm text-red-600">
              {{ errors.title }}
            </p>
          </div>

          <!-- Client Selection -->
          <div class="mb-6">
            <label for="client_id" class="block text-sm font-medium text-gray-700 mb-2">
              Client *
            </label>
            <select id="client_id" v-model="form.client_id" required
              class="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
              :class="{ 'border-red-300': errors.client_id }">
              <option value="">Select a client</option>
              <option v-for="client in clients" :key="client.id" :value="client.id">
                {{ client.name }}
              </option>
            </select>
            <p v-if="errors.client_id" class="mt-1 text-sm text-red-600">
              {{ errors.client_id }}
            </p>
            <p class="mt-1 text-sm text-gray-500">
              Don't see your client?
              <Link :href="route('clients.create')" class="text-blue-600 hover:text-blue-700 font-medium">
              Create a new client
              </Link>
            </p>
          </div>

          <!-- Video Upload -->
          <div class="mb-6">
            <label for="video" class="block text-sm font-medium text-gray-700 mb-2">
              Meeting Video *
            </label>

            <!-- File Drop Zone -->
            <div 
              @drop="handleDrop" 
              @dragover.prevent 
              @dragenter.prevent 
              @dragleave="handleDragLeave"
              :class="[
                'border-2 border-dashed rounded-lg p-8 text-center transition-all duration-200',
                isDragOver
                  ? 'border-blue-400 bg-blue-50 scale-105'
                  : errors.video
                    ? 'border-red-300 bg-red-50'
                    : 'border-gray-300 hover:border-gray-400 hover:bg-gray-50'
              ]"
            >
              <div v-if="!form.video" class="space-y-4">
                <svg class="mx-auto h-12 w-12 text-gray-400" stroke="currentColor" fill="none" viewBox="0 0 48 48">
                  <path
                    d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02"
                    stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
                </svg>
                <div>
                  <p class="text-lg font-medium text-gray-900">
                    Drop your video file here, or
                    <label for="video" class="text-blue-600 hover:text-blue-700 cursor-pointer font-medium">
                      browse
                    </label>
                  </p>
                  <p class="text-sm text-gray-500 mt-2">
                    Supports MP4, MOV, AVI, WebM up to 500MB
                  </p>
                </div>
              </div>

              <!-- Selected File Display -->
              <div v-else class="space-y-4">
                <svg class="mx-auto h-12 w-12 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <div>
                  <p class="text-lg font-medium text-gray-900">{{ form.video.name }}</p>
                  <p class="text-sm text-gray-500">{{ formatFileSize(form.video.size) }}</p>
                  <button type="button" @click="removeFile"
                    class="mt-2 text-red-600 hover:text-red-700 text-sm font-medium transition-colors">
                    Remove file
                  </button>
                </div>
              </div>
            </div>

            <input id="video" ref="fileInput" type="file"
              accept=".mp4,.mov,.avi,.webm,video/mp4,video/quicktime,video/x-msvideo,video/webm"
              @change="handleFileSelect" class="hidden" />

            <!-- File validation info -->
            <div class="mt-2 text-xs text-gray-500 space-y-1">
              <p>• Maximum file size: 500MB</p>
              <p>• Supported formats: MP4, MOV, AVI, WebM</p>
              <p>• Minimum file size: 1MB</p>
            </div>

            <!-- Error message -->
            <div v-if="errors.video" class="mt-2 p-3 bg-red-50 border border-red-200 rounded-md">
              <div class="flex">
                <svg class="h-5 w-5 text-red-400 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
                </svg>
                <div class="ml-3">
                  <p class="text-sm text-red-700 font-medium">Upload Error</p>
                  <p class="text-sm text-red-600 mt-1">{{ errors.video }}</p>
                </div>
              </div>
            </div>

            <!-- Upload Progress -->
            <div v-if="uploadProgress !== null" class="mt-4">
              <div class="flex justify-between text-sm text-gray-600 mb-2">
                <span class="font-medium">Uploading...</span>
                <span>{{ uploadProgress }}%</span>
              </div>
              <div class="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
                <div 
                  class="bg-gradient-to-r from-blue-500 to-blue-600 h-3 rounded-full transition-all duration-300 ease-out"
                  :style="{ width: uploadProgress + '%' }"
                ></div>
              </div>
              <p class="text-xs text-gray-500 mt-1">
                Please don't close this page while uploading...
              </p>
            </div>

            <!-- Upload Error Recovery -->
            <div v-if="uploadError" class="mt-4 p-4 bg-red-50 border border-red-200 rounded-md">
              <div class="flex items-start">
                <svg class="h-5 w-5 text-red-400 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
                </svg>
                <div class="ml-3 flex-1">
                  <h4 class="text-sm font-medium text-red-800">Upload Failed</h4>
                  <p class="text-sm text-red-700 mt-1">{{ uploadError }}</p>
                  <div class="mt-3 flex space-x-3">
                    <button
                      @click="retryUpload"
                      class="text-sm bg-red-100 text-red-800 px-3 py-1 rounded-md hover:bg-red-200 transition-colors"
                    >
                      Try Again
                    </button>
                    <button
                      @click="clearUploadError"
                      class="text-sm text-red-600 hover:text-red-800 transition-colors"
                    >
                      Choose Different File
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Submit Button -->
          <div class="flex justify-end space-x-4">
            <Link :href="route('meetings.index')"
              class="px-4 py-2 text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md font-medium transition-colors">
            Cancel
            </Link>
            <button type="submit" :disabled="processing || !form.title || !form.client_id || !form.video"
              class="px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed text-white rounded-md font-medium transition-colors">
              {{ processing ? 'Uploading...' : 'Upload Meeting' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { Link, router } from '@inertiajs/vue3'
import AppLayout from '@/lib/AppLayout.vue'

interface Client {
  id: number
  name: string
}

interface Props {
  clients: Client[]
  errors: Record<string, string>
}

const props = defineProps<Props>()

const fileInput = ref<HTMLInputElement>()
const isDragOver = ref(false)
const uploadProgress = ref<number | null>(null)
const processing = ref(false)
const uploadError = ref<string>('')
const retryCount = ref(0)
const maxRetries = 3

const form = reactive({
  title: '',
  client_id: '',
  video: null as File | null
})

// Preselect client when navigating from a Client page (e.g. Clients/Show → "Add Meeting")
onMounted(() => {
  try {
    const params = new URLSearchParams(window.location.search)
    const qClientId = params.get('client_id')
    if (qClientId) {
      form.client_id = qClientId
    }
  } catch {
    // ignore if not in browser
  }
})

const handleFileSelect = (event: Event) => {
  const target = event.target as HTMLInputElement
  if (target.files && target.files[0]) {
    const file = target.files[0]
    if (validateFile(file)) {
      form.video = file
      uploadError.value = ''
    }
  }
}

const handleDrop = (event: DragEvent) => {
  event.preventDefault()
  isDragOver.value = false

  if (event.dataTransfer?.files && event.dataTransfer.files[0]) {
    const file = event.dataTransfer.files[0]
    if (validateFile(file)) {
      form.video = file
      uploadError.value = ''
    }
  }
}

const handleDragLeave = (event: DragEvent) => {
  // Only set isDragOver to false if we're leaving the drop zone entirely
  if (!event.currentTarget?.contains(event.relatedTarget as Node)) {
    isDragOver.value = false
  }
}

const validateFile = (file: File): boolean => {
  const maxSize = 500 * 1024 * 1024 // 500MB
  const minSize = 1024 * 1024 // 1MB
  const allowedTypes = ['video/mp4', 'video/quicktime', 'video/x-msvideo', 'video/webm']
  
  if (!allowedTypes.includes(file.type)) {
    uploadError.value = 'Please select a valid video file (MP4, MOV, AVI, or WebM)'
    return false
  }
  
  if (file.size > maxSize) {
    uploadError.value = 'File size must be less than 500MB'
    return false
  }
  
  if (file.size < minSize) {
    uploadError.value = 'File size must be at least 1MB'
    return false
  }
  
  return true
}

const removeFile = () => {
  form.video = null
  if (fileInput.value) {
    fileInput.value.value = ''
  }
}

const formatFileSize = (bytes: number) => {
  if (bytes === 0) return '0 Bytes'

  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))

  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

const submit = () => {
  if (!form.video || !validateFile(form.video)) return

  processing.value = true
  uploadProgress.value = 0
  uploadError.value = ''

  const formData = new FormData()
  formData.append('title', form.title)
  formData.append('client_id', form.client_id)
  formData.append('video', form.video)

  router.post(route('meetings.store'), formData, {
    onProgress: (progress?: { percentage?: number }) => {
      if (progress?.percentage !== undefined && progress?.percentage !== null) {
        uploadProgress.value = Math.round(progress.percentage)
      }
    },
    onSuccess: () => {
      processing.value = false
      uploadProgress.value = null
      retryCount.value = 0
      
      // Show success toast
      if (window.toast) {
        window.toast.success(
          'Meeting uploaded successfully!',
          'Your meeting is now being processed and will be ready for review shortly.'
        )
      }
    },
    onError: (errors) => {
      processing.value = false
      uploadProgress.value = null
      
      // Handle specific error types
      if (errors.video) {
        uploadError.value = errors.video
      } else if (errors.title) {
        uploadError.value = 'Please check the meeting title'
      } else if (errors.client_id) {
        uploadError.value = 'Please select a client'
      } else {
        uploadError.value = 'Upload failed. Please try again.'
      }
      
      // Show error toast with retry option
      if (window.toast && retryCount.value < maxRetries) {
        window.toast.error(
          'Upload Failed',
          uploadError.value,
          {
            actions: [
              {
                label: 'Try Again',
                handler: retryUpload,
                primary: true
              }
            ]
          }
        )
      }
    },
    onFinish: () => {
      processing.value = false
      uploadProgress.value = null
    }
  })
}

const retryUpload = () => {
  if (retryCount.value < maxRetries) {
    retryCount.value++
    uploadError.value = ''
    submit()
  } else {
    uploadError.value = 'Maximum retry attempts reached. Please try a different file or contact support.'
  }
}

const clearUploadError = () => {
  uploadError.value = ''
  form.video = null
  if (fileInput.value) {
    fileInput.value.value = ''
  }
}

// Prevent accidental navigation during upload
const handleBeforeUnload = (event: BeforeUnloadEvent) => {
  if (processing.value && uploadProgress.value !== null) {
    event.preventDefault()
    event.returnValue = 'Upload in progress. Are you sure you want to leave?'
    return event.returnValue
  }
}

// Drag and drop event handlers
const handleGlobalDragEnter = (e: DragEvent) => {
  e.preventDefault()
  isDragOver.value = true
}

const handleGlobalDragLeave = (e: DragEvent) => {
  e.preventDefault()
  if (!e.relatedTarget) {
    isDragOver.value = false
  }
}

const handleGlobalDrop = (e: DragEvent) => {
  e.preventDefault()
  isDragOver.value = false
}

onMounted(() => {
  window.addEventListener('beforeunload', handleBeforeUnload)
  document.addEventListener('dragenter', handleGlobalDragEnter)
  document.addEventListener('dragleave', handleGlobalDragLeave)
  document.addEventListener('drop', handleGlobalDrop)
})

onUnmounted(() => {
  window.removeEventListener('beforeunload', handleBeforeUnload)
  document.removeEventListener('dragenter', handleGlobalDragEnter)
  document.removeEventListener('dragleave', handleGlobalDragLeave)
  document.removeEventListener('drop', handleGlobalDrop)
})
</script>