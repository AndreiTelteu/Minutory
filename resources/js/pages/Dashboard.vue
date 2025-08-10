<template>
  <AppLayout>
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <!-- Header -->
      <div class="flex flex-col md:flex-row md:items-center md:justify-between mb-8 gap-4">
        <div>
          <h1 class="text-3xl font-bold text-gray-900">Dashboard</h1>
          <p class="text-gray-600 mt-1">Overview of your clients and meetings activity.</p>
        </div>
        <div class="flex gap-2">
          <Link :href="route('meetings.create')" class="inline-flex items-center bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg font-medium transition-colors">
            Upload Meeting
          </Link>
          <Link :href="route('clients.index')" class="inline-flex items-center bg-gray-100 hover:bg-gray-200 text-gray-800 px-4 py-2 rounded-lg font-medium transition-colors">
            Manage Clients
          </Link>
          <Link :href="route('ai.chat')" class="inline-flex items-center bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-medium transition-colors">
            Open AI Assistant
          </Link>
        </div>
      </div>

      <!-- Stats -->
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4 mb-8">
        <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <div class="text-sm text-gray-500">Total Clients</div>
          <div class="text-2xl font-semibold text-gray-900 mt-1">{{ stats.total_clients }}</div>
        </div>
        <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <div class="text-sm text-gray-500">Total Meetings</div>
          <div class="text-2xl font-semibold text-gray-900 mt-1">{{ stats.total_meetings }}</div>
        </div>
        <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <div class="text-sm text-gray-500">Completed</div>
          <div class="text-2xl font-semibold text-green-700 mt-1">{{ stats.completed_meetings }}</div>
        </div>
        <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <div class="text-sm text-gray-500">Processing</div>
          <div class="text-2xl font-semibold text-blue-700 mt-1">{{ stats.processing_meetings }}</div>
        </div>
        <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <div class="text-sm text-gray-500">Pending/Failed</div>
          <div class="text-2xl font-semibold text-yellow-700 mt-1">
            {{ stats.pending_meetings + stats.failed_meetings }}
          </div>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- Recent Meetings -->
        <div class="lg:col-span-2 bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
          <div class="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
            <h2 class="text-lg font-semibold text-gray-900">Recent Meetings</h2>
            <Link :href="route('meetings.index')" class="text-sm text-blue-600 hover:text-blue-700 font-medium">
              View all →
            </Link>
          </div>

          <div v-if="recentMeetings.length === 0" class="p-8 text-center text-gray-500">
            <p class="text-lg">No meetings yet.</p>
            <p class="mt-2">
              <Link :href="route('meetings.create')" class="text-blue-600 hover:text-blue-700 font-medium">
                Upload your first meeting
              </Link>
            </p>
          </div>

          <div v-else class="overflow-x-auto">
            <table class="min-w-full divide-y divide-gray-200">
              <thead class="bg-gray-50">
                <tr>
                  <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Title</th>
                  <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Client</th>
                  <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                  <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Uploaded</th>
                  <th class="px-6 py-3" />
                </tr>
              </thead>
              <tbody class="bg-white divide-y divide-gray-200">
                <tr v-for="m in recentMeetings" :key="m.id" class="hover:bg-gray-50">
                  <td class="px-6 py-4 whitespace-nowrap">
                    <div class="text-sm font-medium text-gray-900">{{ m.title }}</div>
                  </td>
                  <td class="px-6 py-4 whitespace-nowrap">
                    <div class="text-sm text-gray-900">{{ m.client.name }}</div>
                  </td>
                  <td class="px-6 py-4 whitespace-nowrap">
                    <MeetingStatusBadge :status="m.status" />
                  </td>
                  <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {{ formatDate(m.created_at || m.uploaded_at) }}
                  </td>
                  <td class="px-6 py-4 whitespace-nowrap text-right text-sm">
                    <Link :href="route('meetings.show', m.id)" class="text-blue-600 hover:text-blue-900">
                      Open
                    </Link>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Top Clients -->
        <div class="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
          <div class="px-6 py-4 border-b border-gray-200">
            <h2 class="text-lg font-semibold text-gray-900">Top Clients</h2>
            <p class="text-sm text-gray-500">By number of meetings</p>
          </div>

          <div v-if="topClients.length === 0" class="p-8 text-center text-gray-500">
            No clients yet.
          </div>

          <ul v-else class="divide-y divide-gray-200">
            <li v-for="c in topClients" :key="c.id" class="px-6 py-4 flex items-center justify-between">
              <div>
                <div class="font-medium text-gray-900">{{ c.name }}</div>
                <div class="text-sm text-gray-500">{{ c.meetings_count }} meetings</div>
              </div>
              <Link :href="route('clients.show', c.id)" class="text-blue-600 hover:text-blue-800 text-sm font-medium">
                View
              </Link>
            </li>
          </ul>
        </div>
      </div>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { Link } from '@inertiajs/vue3'
import AppLayout from '@/lib/AppLayout.vue'
import MeetingStatusBadge from '@/lib/MeetingStatusBadge.vue'

interface ClientLite {
  id: number
  name: string
  meetings_count?: number
}

interface ClientRef {
  id: number
  name: string
}

interface Meeting {
  id: number
  title: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  uploaded_at: string
  created_at?: string
  client: ClientRef
}

interface Stats {
  total_clients: number
  total_meetings: number
  completed_meetings: number
  processing_meetings: number
  pending_meetings: number
  failed_meetings: number
}

interface Props {
  recentMeetings: Meeting[]
  stats: Stats
  topClients: ClientLite[]
}

const props = defineProps<Props>()

const recentMeetings = props.recentMeetings || []
const stats = props.stats || {
  total_clients: 0,
  total_meetings: 0,
  completed_meetings: 0,
  processing_meetings: 0,
  pending_meetings: 0,
  failed_meetings: 0
}
const topClients = props.topClients || []

const formatDate = (dateString: string) => {
  if (!dateString) return '-'
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}
</script>