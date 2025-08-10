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
            <div @drop="handleDrop" @dragover.prevent @dragenter.prevent :class="[
              'border-2 border-dashed rounded-lg p-8 text-center transition-colors',
              isDragOver
                ? 'border-blue-400 bg-blue-50'
                : errors.video
                  ? 'border-red-300 bg-red-50'
                  : 'border-gray-300 hover:border-gray-400'
            ]">
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
                    class="mt-2 text-red-600 hover:text-red-700 text-sm font-medium">
                    Remove file
                  </button>
                </div>
              </div>
            </div>

            <input id="video" ref="fileInput" type="file"
              accept=".mp4,.mov,.avi,.webm,video/mp4,video/quicktime,video/x-msvideo,video/webm"
              @change="handleFileSelect" class="hidden" />

            <p v-if="errors.video" class="mt-2 text-sm text-red-600">
              {{ errors.video }}
            </p>

            <!-- Upload Progress -->
            <div v-if="uploadProgress !== null" class="mt-4">
              <div class="flex justify-between text-sm text-gray-600 mb-1">
                <span>Uploading...</span>
                <span>{{ uploadProgress }}%</span>
              </div>
              <div class="w-full bg-gray-200 rounded-full h-2">
                <div class="bg-blue-600 h-2 rounded-full transition-all duration-300"
                  :style="{ width: uploadProgress + '%' }"></div>
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
import { ref, reactive } from 'vue'
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

const form = reactive({
  title: '',
  client_id: '',
  video: null as File | null
})

const handleFileSelect = (event: Event) => {
  const target = event.target as HTMLInputElement
  if (target.files && target.files[0]) {
    form.video = target.files[0]
  }
}

const handleDrop = (event: DragEvent) => {
  event.preventDefault()
  isDragOver.value = false

  if (event.dataTransfer?.files && event.dataTransfer.files[0]) {
    form.video = event.dataTransfer.files[0]
  }
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
  if (!form.video) return

  processing.value = true
  uploadProgress.value = 0

  const formData = new FormData()
  formData.append('title', form.title)
  formData.append('client_id', form.client_id)
  formData.append('video', form.video)

  router.post(route('meetings.store'), formData, {
    onProgress: (progress) => {
      if (progress.percentage) {
        uploadProgress.value = Math.round(progress.percentage)
      }
    },
    onSuccess: () => {
      processing.value = false
      uploadProgress.value = null
    },
    onError: () => {
      processing.value = false
      uploadProgress.value = null
    },
    onFinish: () => {
      processing.value = false
      uploadProgress.value = null
    }
  })
}

// Drag and drop event handlers
document.addEventListener('dragenter', (e) => {
  e.preventDefault()
  isDragOver.value = true
})

document.addEventListener('dragleave', (e) => {
  e.preventDefault()
  if (!e.relatedTarget) {
    isDragOver.value = false
  }
})

document.addEventListener('drop', (e) => {
  e.preventDefault()
  isDragOver.value = false
})
</script>