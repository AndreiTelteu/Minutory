<template>
  <div class="min-h-screen bg-gray-50 py-8">
    <div class="mx-auto max-w-2xl px-4 sm:px-6 lg:px-8">
      <div class="mb-8">
        <Link :href="route('clients.index')" class="text-sm font-medium text-indigo-600 hover:text-indigo-500">
        ← Back to Clients
        </Link>
        <h1 class="mt-2 text-2xl font-semibold leading-6 text-gray-900">Create New Client</h1>
        <p class="mt-2 text-sm text-gray-700">
          Add a new client to organize your meetings and track engagement.
        </p>
      </div>

      <div class="bg-white shadow sm:rounded-lg">
        <form @submit.prevent="submit" class="px-4 py-6 sm:p-8">
          <div class="grid grid-cols-1 gap-y-6 sm:grid-cols-2 sm:gap-x-8">
            <!-- Name -->
            <div class="sm:col-span-2">
              <label for="name" class="block text-sm font-medium leading-6 text-gray-900">
                Name <span class="text-red-500">*</span>
              </label>
              <div class="mt-2">
                <input id="name" v-model="form.name" type="text" required
                  class="block w-full rounded-md border-0 py-1.5 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:text-sm sm:leading-6"
                  :class="{ 'ring-red-500 focus:ring-red-500': form.errors.name }" />
                <p v-if="form.errors.name" class="mt-2 text-sm text-red-600">
                  {{ form.errors.name }}
                </p>
              </div>
            </div>

            <!-- Email -->
            <div class="sm:col-span-2">
              <label for="email" class="block text-sm font-medium leading-6 text-gray-900">
                Email
              </label>
              <div class="mt-2">
                <input id="email" v-model="form.email" type="email"
                  class="block w-full rounded-md border-0 py-1.5 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:text-sm sm:leading-6"
                  :class="{ 'ring-red-500 focus:ring-red-500': form.errors.email }" />
                <p v-if="form.errors.email" class="mt-2 text-sm text-red-600">
                  {{ form.errors.email }}
                </p>
              </div>
            </div>

            <!-- Company -->
            <div>
              <label for="company" class="block text-sm font-medium leading-6 text-gray-900">
                Company
              </label>
              <div class="mt-2">
                <input id="company" v-model="form.company" type="text"
                  class="block w-full rounded-md border-0 py-1.5 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:text-sm sm:leading-6"
                  :class="{ 'ring-red-500 focus:ring-red-500': form.errors.company }" />
                <p v-if="form.errors.company" class="mt-2 text-sm text-red-600">
                  {{ form.errors.company }}
                </p>
              </div>
            </div>

            <!-- Phone -->
            <div>
              <label for="phone" class="block text-sm font-medium leading-6 text-gray-900">
                Phone
              </label>
              <div class="mt-2">
                <input id="phone" v-model="form.phone" type="tel"
                  class="block w-full rounded-md border-0 py-1.5 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:text-sm sm:leading-6"
                  :class="{ 'ring-red-500 focus:ring-red-500': form.errors.phone }" />
                <p v-if="form.errors.phone" class="mt-2 text-sm text-red-600">
                  {{ form.errors.phone }}
                </p>
              </div>
            </div>
          </div>

          <div class="mt-8 flex justify-end gap-x-3">
            <Link :href="route('clients.index')"
              class="rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50">
            Cancel
            </Link>
            <button type="submit" :disabled="form.processing"
              class="rounded-md bg-indigo-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600 disabled:opacity-50">
              <span v-if="form.processing">Creating...</span>
              <span v-else>Create Client</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Link, useForm } from '@inertiajs/vue3'

const form = useForm({
  name: '',
  email: '',
  company: '',
  phone: '',
})

const submit = () => {
  form.post(route('clients.store'))
}
</script>