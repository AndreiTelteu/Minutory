<template>
  <div class="min-h-screen bg-gray-50 py-8">
    <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
      <div class="mb-8">
        <Link :href="route('clients.index')" class="text-sm font-medium text-indigo-600 hover:text-indigo-500">
        ← Back to Clients
        </Link>
      </div>

      <!-- Client Header -->
      <div class="bg-white shadow sm:rounded-lg">
        <div class="px-4 py-6 sm:p-8">
          <div class="sm:flex sm:items-center sm:justify-between">
            <div>
              <h1 class="text-2xl font-semibold leading-6 text-gray-900">{{ client.name }}</h1>
              <div class="mt-2 space-y-1">
                <p v-if="client.company" class="text-sm text-gray-600">
                  <span class="font-medium">Company:</span> {{ client.company }}
                </p>
                <p v-if="client.email" class="text-sm text-gray-600">
                  <span class="font-medium">Email:</span>
                  <a :href="`mailto:${client.email}`" class="text-indigo-600 hover:text-indigo-500">
                    {{ client.email }}
                  </a>
                </p>
                <p v-if="client.phone" class="text-sm text-gray-600">
                  <span class="font-medium">Phone:</span>
                  <a :href="`tel:${client.phone}`" class="text-indigo-600 hover:text-indigo-500">
                    {{ client.phone }}
                  </a>
                </p>
              </div>
            </div>
            <div class="mt-4 sm:ml-16 sm:mt-0 sm:flex-none">
              <Link :href="route('clients.edit', client.id)"
                class="block rounded-md bg-indigo-600 px-3 py-2 text-center text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600">
              Edit Client
              </Link>
            </div>
          </div>
        </div>
      </div>

      <!-- Meetings Section -->
      <div class="mt-8">
        <div class="sm:flex sm:items-center">
          <div class="sm:flex-auto">
            <h2 class="text-lg font-semibold leading-6 text-gray-900">Meetings</h2>
            <p class="mt-2 text-sm text-gray-700">
              All meetings associated with {{ client.name }}.
            </p>
          </div>
          <div class="mt-4 sm:ml-16 sm:mt-0 sm:flex-none">
            <!-- Future: Add meeting creation button -->
            <button type="button"
              class="block rounded-md bg-gray-300 px-3 py-2 text-center text-sm font-semibold text-gray-500 cursor-not-allowed"
              disabled>
              Add Meeting (Coming Soon)
            </button>
          </div>
        </div>

        <div class="mt-6 bg-white shadow sm:rounded-lg">
          <div v-if="client.meetings && client.meetings.length > 0" class="overflow-hidden">
            <table class="min-w-full divide-y divide-gray-300">
              <thead class="bg-gray-50">
                <tr>
                  <th scope="col" class="py-3.5 pl-4 pr-3 text-left text-sm font-semibold text-gray-900 sm:pl-6">
                    Title
                  </th>
                  <th scope="col" class="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">
                    Status
                  </th>
                  <th scope="col" class="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">
                    Duration
                  </th>
                  <th scope="col" class="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">
                    Uploaded
                  </th>
                  <th scope="col" class="relative py-3.5 pl-3 pr-4 sm:pr-6">
                    <span class="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-200 bg-white">
                <tr v-for="meeting in client.meetings" :key="meeting.id">
                  <td class="whitespace-nowrap py-4 pl-4 pr-3 text-sm font-medium text-gray-900 sm:pl-6">
                    {{ meeting.title }}
                  </td>
                  <td class="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                    <span class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium"
                      :class="getStatusBadgeClass(meeting.status)">
                      {{ meeting.status }}
                    </span>
                  </td>
                  <td class="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                    {{ formatDuration(meeting.duration) }}
                  </td>
                  <td class="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                    {{ formatDate(meeting.uploaded_at) }}
                  </td>
                  <td class="relative whitespace-nowrap py-4 pl-3 pr-4 text-right text-sm font-medium sm:pr-6">
                    <!-- Future: Add meeting view link -->
                    <span class="text-gray-400">View (Coming Soon)</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else class="px-6 py-14 text-center text-sm text-gray-500">
            <div class="flex flex-col items-center">
              <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"
                aria-hidden="true">
                <path vector-effect="non-scaling-stroke" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
              <h3 class="mt-2 text-sm font-semibold text-gray-900">No meetings</h3>
              <p class="mt-1 text-sm text-gray-500">This client doesn't have any meetings yet.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Link } from '@inertiajs/vue3'
import type { Client } from '@/types'

interface Props {
  client: Client
}

defineProps<Props>()

const getStatusBadgeClass = (status: string) => {
  switch (status) {
    case 'completed':
      return 'bg-green-100 text-green-800'
    case 'processing':
      return 'bg-yellow-100 text-yellow-800'
    case 'failed':
      return 'bg-red-100 text-red-800'
    case 'pending':
    default:
      return 'bg-gray-100 text-gray-800'
  }
}

const formatDuration = (duration: number | null) => {
  if (!duration) return '-'
  const minutes = Math.floor(duration / 60)
  const seconds = duration % 60
  return `${minutes}:${seconds.toString().padStart(2, '0')}`
}

const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}
</script>