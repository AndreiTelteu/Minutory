<template>
  <AppLayout>
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-3xl font-bold text-gray-900">Clients</h1>
          <p class="mt-2 text-sm text-gray-600">
            Manage your clients and organize meetings by client accounts.
          </p>
        </div>
        <div>
          <Link
            :href="route('clients.create')"
            class="inline-flex items-center bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg font-medium transition-colors"
          >
            Add Client
          </Link>
        </div>
      </div>


      <!-- Clients Table -->
      <div class="mt-8 bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
        <div class="overflow-x-auto">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
              <tr>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Company</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Email</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Phone</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Meetings</th>
                <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
              <tr v-for="client in clients" :key="client.id" class="hover:bg-gray-50">
                <td class="px-6 py-4 whitespace-nowrap">
                  <Link :href="route('clients.show', client.id)" class="text-blue-600 hover:text-blue-800 font-medium">
                    {{ client.name }}
                  </Link>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                  {{ client.company || '-' }}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                  {{ client.email || '-' }}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                  {{ client.phone || '-' }}
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                  <span class="inline-flex items-center rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-800">
                    {{ client.meetings_count }} meetings
                  </span>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                  <Link :href="route('clients.edit', client.id)" class="text-blue-600 hover:text-blue-900 mr-4">
                    Edit
                  </Link>
                  <button
                    @click="deleteClient(client)"
                    class="text-red-600 hover:text-red-900"
                    :disabled="(client.meetings_count ?? 0) > 0"
                    :class="{ 'opacity-50 cursor-not-allowed': (client.meetings_count ?? 0) > 0 }"
                  >
                    Delete
                  </button>
                </td>
              </tr>

              <tr v-if="clients.length === 0">
                <td colspan="6" class="px-6 py-14 text-center text-sm text-gray-500">
                  <div class="flex flex-col items-center">
                    <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                      <path vector-effect="non-scaling-stroke" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                        d="M9 13h6m-3-3v6m-9 1V7a2 2 0 012-2h6l2 2h6a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
                    </svg>
                    <h3 class="mt-2 text-sm font-semibold text-gray-900">No clients</h3>
                    <p class="mt-1 text-sm text-gray-500">Get started by creating a new client.</p>
                    <div class="mt-6">
                      <Link
                        :href="route('clients.create')"
                        class="inline-flex items-center bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg font-medium transition-colors"
                      >
                        Add Client
                      </Link>
                    </div>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { Link, router } from '@inertiajs/vue3'
import AppLayout from '@/lib/AppLayout.vue'
import type { Client } from '@/types'

interface Props {
  clients: Client[]
}

defineProps<Props>()

const deleteClient = (client: Client) => {
  if ((client.meetings_count ?? 0) > 0) {
    alert('Cannot delete client with existing meetings.')
    return
  }

  if (confirm(`Are you sure you want to delete ${client.name}?`)) {
    router.delete(route('clients.destroy', client.id))
  }
}
</script>