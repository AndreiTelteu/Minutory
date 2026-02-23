<template>
    <AppLayout>
        <div class="mx-auto max-w-2xl px-4 py-8 sm:px-6 lg:px-8">
            <div class="mb-8">
                <Link :href="route('clients.index')" class="font-medium text-blue-600 hover:text-blue-700"> ← Back to Clients </Link>
                <h1 class="mt-4 text-3xl font-bold text-gray-900">Edit Client</h1>
                <p class="mt-2 text-gray-600">Update client information and contact details.</p>
            </div>

            <div class="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
                <form @submit.prevent="submit">
                    <div class="grid grid-cols-1 gap-y-6 sm:grid-cols-2 sm:gap-x-6">
                        <!-- Name -->
                        <div class="sm:col-span-2">
                            <label for="name" class="mb-1 block text-sm font-medium text-gray-700"> Name <span class="text-red-500">*</span> </label>
                            <input
                                id="name"
                                v-model="form.name"
                                type="text"
                                required
                                class="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                                :class="{ 'border-red-300': form.errors.name }"
                            />
                            <p v-if="form.errors.name" class="mt-1 text-sm text-red-600">
                                {{ form.errors.name }}
                            </p>
                        </div>

                        <!-- Email -->
                        <div class="sm:col-span-2">
                            <label for="email" class="mb-1 block text-sm font-medium text-gray-700"> Email </label>
                            <input
                                id="email"
                                v-model="form.email"
                                type="email"
                                class="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                                :class="{ 'border-red-300': form.errors.email }"
                            />
                            <p v-if="form.errors.email" class="mt-1 text-sm text-red-600">
                                {{ form.errors.email }}
                            </p>
                        </div>

                        <!-- Company -->
                        <div>
                            <label for="company" class="mb-1 block text-sm font-medium text-gray-700"> Company </label>
                            <input
                                id="company"
                                v-model="form.company"
                                type="text"
                                class="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                                :class="{ 'border-red-300': form.errors.company }"
                            />
                            <p v-if="form.errors.company" class="mt-1 text-sm text-red-600">
                                {{ form.errors.company }}
                            </p>
                        </div>

                        <!-- Phone -->
                        <div>
                            <label for="phone" class="mb-1 block text-sm font-medium text-gray-700"> Phone </label>
                            <input
                                id="phone"
                                v-model="form.phone"
                                type="tel"
                                class="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                                :class="{ 'border-red-300': form.errors.phone }"
                            />
                            <p v-if="form.errors.phone" class="mt-1 text-sm text-red-600">
                                {{ form.errors.phone }}
                            </p>
                        </div>
                    </div>

                    <div class="mt-8 flex justify-end gap-3">
                        <Link
                            :href="route('clients.index')"
                            class="rounded-md bg-gray-100 px-4 py-2 font-medium text-gray-700 transition-colors hover:bg-gray-200"
                        >
                            Cancel
                        </Link>
                        <button
                            type="submit"
                            :disabled="form.processing"
                            class="rounded-md bg-blue-600 px-6 py-2 font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-gray-400"
                        >
                            <span v-if="form.processing">Updating...</span>
                            <span v-else>Update Client</span>
                        </button>
                    </div>
                </form>
            </div>
        </div>
    </AppLayout>
</template>

<script setup lang="ts">
import AppLayout from '@/lib/AppLayout.vue';
import type { Client } from '@/types';
import { Link, useForm } from '@inertiajs/vue3';

interface Props {
    client: Client;
}

const props = defineProps<Props>();

const form = useForm({
    name: props.client.name,
    email: props.client.email || '',
    company: props.client.company || '',
    phone: props.client.phone || '',
});

const submit = () => {
    form.put(route('clients.update', props.client.id));
};
</script>
