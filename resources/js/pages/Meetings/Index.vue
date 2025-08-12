<template>
  <AppLayout>
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div class="flex justify-between items-center mb-8">
        <div class="flex items-center space-x-4">
          <h1 class="text-3xl font-bold text-gray-900">Meetings</h1>
          <div class="flex items-center space-x-2 text-sm text-gray-500">
            <div class="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
            <span>Live updates active</span>
          </div>
        </div>
        <Link :href="route('meetings.create')"
          class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg font-medium transition-colors">
        Upload Meeting
        </Link>
      </div>

      <!-- Filters -->
      <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
        <h2 class="text-lg font-semibold text-gray-900 mb-4">Filters</h2>
        <form @submit.prevent="applyFilters" class="grid grid-cols-1 md:grid-cols-5 gap-4">
          <div>
            <label for="client_id" class="block text-sm font-medium text-gray-700 mb-1">
              Client
            </label>
            <select id="client_id" v-model="filterForm.client_id" data-testid="client-filter"
              class="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
              <option value="">All Clients</option>
              <option v-for="client in clients" :key="client.id" :value="client.id">
                {{ client.name }}
              </option>
            </select>
          </div>

          <div>
            <label for="status" class="block text-sm font-medium text-gray-700 mb-1">
              Status
            </label>
            <select id="status" v-model="filterForm.status" data-testid="status-filter"
              class="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
              <option value="">All Statuses</option>
              <option value="pending">Pending</option>
              <option value="processing">Processing</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
            </select>
          </div>

          <div>
            <label for="date_from" class="block text-sm font-medium text-gray-700 mb-1">
              From Date
            </label>
            <input id="date_from" v-model="filterForm.date_from" type="date" data-testid="date-from"
              class="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500" />
          </div>

          <div>
            <label for="date_to" class="block text-sm font-medium text-gray-700 mb-1">
              To Date
            </label>
            <input id="date_to" v-model="filterForm.date_to" type="date" data-testid="date-to"
              class="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500" />
          </div>

          <div>
            <label for="sort" class="block text-sm font-medium text-gray-700 mb-1">
              Sort By
            </label>
            <div class="flex gap-2">
              <select id="sort" v-model="filterForm.sort"
                class="flex-1 rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                <option value="uploaded_at">Uploaded Date</option>
                <option value="title">Title</option>
                <option value="client">Client</option>
                <option value="status">Status</option>
                <option value="duration">Duration</option>
              </select>
              <button type="button" @click="toggleDirection"
                :title="`Toggle direction (currently ${filterForm.direction.toUpperCase()})`"
                class="px-3 py-2 rounded-md border text-sm"
                :class="filterForm.direction === 'asc' ? 'border-gray-300 text-gray-700' : 'border-gray-800 text-gray-900'">
                <span v-if="filterForm.direction === 'asc'">↑</span>
                <span v-else>↓</span>
              </button>
            </div>
          </div>

          <div class="md:col-span-5 flex gap-2">
            <button type="submit"
              class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md font-medium transition-colors">
              Apply Filters
            </button>
            <button type="button" @click="clearFilters"
              class="bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded-md font-medium transition-colors">
              Clear
            </button>
          </div>
        </form>
      </div>

      <!-- Meetings List -->
      <div class="bg-white rounded-lg shadow-sm border border-gray-200">
        <div v-if="realtimeMeetings.length === 0" class="p-8 text-center text-gray-500">
          <p class="text-lg">No meetings found.</p>
          <p class="mt-2">
            <Link :href="route('meetings.create')" class="text-blue-600 hover:text-blue-700 font-medium">
            Upload your first meeting
            </Link>
          </p>
        </div>

        <div v-else class="overflow-hidden">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
              <tr>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  <button @click="setSort('title')" class="inline-flex items-center gap-1 hover:text-gray-700">
                    Meeting
                    <span :class="['text-xs', filterForm.sort === 'title' ? 'text-gray-900' : 'text-gray-400']">
                      {{ filterForm.sort === 'title' ? (filterForm.direction === 'asc' ? '↑' : '↓') : '↕' }}
                    </span>
                  </button>
                </th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  <button @click="setSort('client')" class="inline-flex items-center gap-1 hover:text-gray-700">
                    Client
                    <span :class="['text-xs', filterForm.sort === 'client' ? 'text-gray-900' : 'text-gray-400']">
                      {{ filterForm.sort === 'client' ? (filterForm.direction === 'asc' ? '↑' : '↓') : '↕' }}
                    </span>
                  </button>
                </th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-64">
                  Status & Progress
                </th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  <button @click="setSort('uploaded_at')" class="inline-flex items-center gap-1 hover:text-gray-700">
                    Uploaded
                    <span :class="['text-xs', filterForm.sort === 'uploaded_at' ? 'text-gray-900' : 'text-gray-400']">
                      {{ filterForm.sort === 'uploaded_at' ? (filterForm.direction === 'asc' ? '↑' : '↓') : '↕' }}
                    </span>
                  </button>
                </th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  <button @click="setSort('duration')" class="inline-flex items-center gap-1 hover:text-gray-700">
                    Duration
                    <span :class="['text-xs', filterForm.sort === 'duration' ? 'text-gray-900' : 'text-gray-400']">
                      {{ filterForm.sort === 'duration' ? (filterForm.direction === 'asc' ? '↑' : '↓') : '↕' }}
                    </span>
                  </button>
                </th>
                <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
              <tr v-for="meeting in realtimeMeetings" :key="meeting.id" class="hover:bg-gray-50">
                <td class="px-6 py-4 whitespace-nowrap">
                  <div class="text-sm font-medium text-gray-900">{{ meeting.title }}</div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                  <div class="text-sm text-gray-900">{{ meeting.client.name }}</div>
                </td>
                <td class="px-6 py-4">
                  <div class="space-y-2">
                    <MeetingStatusBadge :status="meeting.status" :meeting="meeting" />
                    <MeetingProgressIndicator 
                      v-if="meeting.status === 'pending' || meeting.status === 'processing' || meeting.status === 'failed'"
                      :meeting="meeting" 
                    />
                  </div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {{ formatDate(meeting.uploaded_at) }}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {{ formatDuration(meeting.duration) }}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                  <Link :href="route('meetings.show', meeting.id)" class="text-blue-600 hover:text-blue-900 mr-3">
                  View
                  </Link>
                  <button @click="deleteMeeting(meeting)" class="text-red-600 hover:text-red-900">
                    Delete
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Pagination -->
        <div v-if="meetings.links.length > 3" class="px-6 py-3 border-t border-gray-200">
          <div class="flex justify-between items-center">
            <div class="text-sm text-gray-700">
              Showing {{ meetings.from }} to {{ meetings.to }} of {{ meetings.total }} results
            </div>
            <div class="flex space-x-1">
              <Link v-for="link in meetings.links" :key="link.label" :href="link.url || '#'" :class="[
                'px-3 py-2 text-sm rounded-md',
                link.active
                  ? 'bg-blue-600 text-white'
                  : link.url
                    ? 'text-gray-700 hover:bg-gray-100'
                    : 'text-gray-400 cursor-not-allowed'
              ]" v-html="link.label" />
            </div>
          </div>
        </div>
      </div>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { reactive, watch } from 'vue'
import { Link, router } from '@inertiajs/vue3'
import AppLayout from '@/lib/AppLayout.vue'
import MeetingStatusBadge from '@/lib/MeetingStatusBadge.vue'
import MeetingProgressIndicator from '@/lib/MeetingProgressIndicator.vue'
import { useRealTimeUpdates } from '@/lib/useRealTimeUpdates'


interface Client {
  id: number
  name: string
}

interface Meeting {
  id: number
  title: string
  client: Client
  status: 'pending' | 'processing' | 'completed' | 'failed'
  uploaded_at: string
  duration: number | null
  elapsed_time?: number | null
  estimated_remaining_time?: number | null
  processing_progress?: number | null
  formatted_elapsed_time?: string | null
  formatted_estimated_remaining_time?: string | null
  queue_progress?: number | null
}

interface PaginatedMeetings {
  data: Meeting[]
  links: Array<{
    url: string | null
    label: string
    active: boolean
  }>
  from: number
  to: number
  total: number
}

interface Props {
  meetings: PaginatedMeetings
  clients: Client[]
  filters: {
    client_id?: string
    status?: string
    date_from?: string
    date_to?: string
    sort?: string
    direction?: 'asc' | 'desc'
  }
}

const props = defineProps<Props>()

// Use real-time updates for meetings
const { meetings: realtimeMeetings } = useRealTimeUpdates(props.meetings.data)

// Keep real-time list in sync when Inertia updates props (e.g., after applying filters/sorting)
watch(
  () => props.meetings.data,
  (newMeetings) => {
    // Replace array to respect new server-sorted/filtered results
    realtimeMeetings.value = [...newMeetings]
  }
)

const filterForm = reactive({
  client_id: props.filters.client_id || '',
  status: props.filters.status || '',
  date_from: props.filters.date_from || '',
  date_to: props.filters.date_to || '',
  sort: props.filters.sort || 'uploaded_at',
  direction: (props.filters.direction as 'asc' | 'desc') || 'desc'
})

const applyFilters = () => {
  router.get(route('meetings.index'), filterForm, {
    preserveState: true,
    preserveScroll: true
  })
}

const clearFilters = () => {
  filterForm.client_id = ''
  filterForm.status = ''
  filterForm.date_from = ''
  filterForm.date_to = ''
  filterForm.sort = 'uploaded_at'
  filterForm.direction = 'desc'
  applyFilters()
}

const deleteMeeting = (meeting: Meeting) => {
  if (confirm(`Are you sure you want to delete "${meeting.title}"? This action cannot be undone.`)) {
    router.delete(route('meetings.destroy', meeting.id), {
      preserveScroll: true
    })
  }
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

const setSort = (column: string) => {
  if (filterForm.sort === column) {
    filterForm.direction = filterForm.direction === 'asc' ? 'desc' : 'asc'
  } else {
    filterForm.sort = column
    filterForm.direction = column === 'title' || column === 'client' ? 'asc' : 'desc'
  }
  applyFilters()
}

const toggleDirection = () => {
  filterForm.direction = filterForm.direction === 'asc' ? 'desc' : 'asc'
  applyFilters()
}

const formatDuration = (duration: number | null) => {
  if (!duration) return 'Unknown'

  const hours = Math.floor(duration / 3600)
  const minutes = Math.floor((duration % 3600) / 60)
  const seconds = duration % 60

  if (hours > 0) {
    return `${hours}h ${minutes}m ${seconds}s`
  } else if (minutes > 0) {
    return `${minutes}m ${seconds}s`
  } else {
    return `${seconds}s`
  }
}
</script>