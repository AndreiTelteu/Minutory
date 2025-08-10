<template>
  <div class="min-h-screen bg-gray-50 py-8">
    <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
      <div class="sm:flex sm:items-center">
        <div class="sm:flex-auto">
          <h1 class="text-2xl font-semibold leading-6 text-gray-900">Clients</h1>
          <p class="mt-2 text-sm text-gray-700">
            Manage your clients and organize meetings by client accounts.
          </p>
        </div>
        <div class="mt-4 sm:ml-16 sm:mt-0 sm:flex-none">
          <Link :href="route('clients.create')"
            class="block rounded-md bg-indigo-600 px-3 py-2 text-center text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600">
          Add Client
          </Link>
        </div>
      </div>

      <!-- Success/Error Messages -->
      <div v-if="$page.props.flash?.success" class="mt-4 rounded-md bg-green-50 p-4">
        <div class="flex">
          <div class="ml-3">
            <p class="text-sm font-medium text-green-800">
              {{ $page.props.flash.success }}
            </p>
          </div>
        </div>
      </div>

      <div v-if="$page.props.flash?.error" class="mt-4 rounded-md bg-red-50 p-4">
        <div class="flex">
          <div class="ml-3">
            <p class="text-sm font-medium text-red-800">
              {{ $page.props.flash.error }}
            </p>
          </div>
        </div>
      </div>

      <!-- Clients Table -->
      <div class="mt-8 flow-root">
        <div class="-mx-4 -my-2 overflow-x-auto sm:-mx-6 lg:-mx-8">
          <div class="inline-block min-w-full py-2 align-middle sm:px-6 lg:px-8">
            <div class="overflow-hidden shadow ring-1 ring-black ring-opacity-5 sm:rounded-lg">
              <table class="min-w-full divide-y divide-gray-300">
                <thead class="bg-gray-50">
                  <tr>
                    <th scope="col" class="py-3.5 pl-4 pr-3 text-left text-sm font-semibold text-gray-900 sm:pl-6">
                      Name
                    </th>
                    <th scope="col" class="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">
                      Company
                    </th>
                    <th scope="col" class="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">
                      Email
                    </th>
                    <th scope="col" class="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">
                      Phone
                    </th>
                    <th scope="col" class="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">
                      Meetings
                    </th>
                    <th scope="col" class="relative py-3.5 pl-3 pr-4 sm:pr-6">
                      <span class="sr-only">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-gray-200 bg-white">
                  <tr v-for="client in clients" :key="client.id">
                    <td class="whitespace-nowrap py-4 pl-4 pr-3 text-sm font-medium text-gray-900 sm:pl-6">
                      <Link :href="route('clients.show', client.id)" class="text-indigo-600 hover:text-indigo-900">
                      {{ client.name }}
                      </Link>
                    </td>
                    <td class="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                      {{ client.company || '-' }}
                    </td>
                    <td class="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                      {{ client.email || '-' }}
                    </td>
                    <td class="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                      {{ client.phone || '-' }}
                    </td>
                    <td class="whitespace-nowrap px-3 py-4 text-sm text-gray-500">
                      <span
                        class="inline-flex items-center rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-800">
                        {{ client.meetings_count }} meetings
                      </span>
                    </td>
                    <td class="relative whitespace-nowrap py-4 pl-3 pr-4 text-right text-sm font-medium sm:pr-6">
                      <Link :href="route('clients.edit', client.id)" class="text-indigo-600 hover:text-indigo-900 mr-4">
                      Edit
                      </Link>
                      <button @click="deleteClient(client)" class="text-red-600 hover:text-red-900"
                        :disabled="client.meetings_count > 0"
                        :class="{ 'opacity-50 cursor-not-allowed': client.meetings_count > 0 }">
                        Delete
                      </button>
                    </td>
                  </tr>
                  <tr v-if="clients.length === 0">
                    <td colspan="6" class="px-6 py-14 text-center text-sm text-gray-500">
                      <div class="flex flex-col items-center">
                        <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24"
                          stroke="currentColor" aria-hidden="true">
                          <path vector-effect="non-scaling-stroke" stroke-linecap="round" stroke-linejoin="round"
                            stroke-width="2"
                            d="M9 13h6m-3-3v6m-9 1V7a2 2 0 012-2h6l2 2h6a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
                        </svg>
                        <h3 class="mt-2 text-sm font-semibold text-gray-900">No clients</h3>
                        <p class="mt-1 text-sm text-gray-500">Get started by creating a new client.</p>
                        <div class="mt-6">
                          <Link :href="route('clients.create')"
                            class="inline-flex items-center rounded-md bg-indigo-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600">
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
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Link, router } from '@inertiajs/vue3'
import type { Client } from '@/types'

interface Props {
  clients: Client[]
}

defineProps<Props>()

const deleteClient = (client: Client) => {
  if (client.meetings_count && client.meetings_count > 0) {
    alert('Cannot delete client with existing meetings.')
    return
  }

  if (confirm(`Are you sure you want to delete ${client.name}?`)) {
    router.delete(route('clients.destroy', client.id))
  }
}
</script>