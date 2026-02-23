<template>
    <AppLayout>
        <div class="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
            <!-- Back -->
            <div class="mb-6">
                <Link :href="route('clients.index')" class="text-sm font-medium text-blue-600 hover:text-blue-700"> ← Back to Clients </Link>
            </div>

            <!-- Client Header -->
            <div class="rounded-lg border border-gray-200 bg-white shadow-sm">
                <div class="px-6 py-6">
                    <div class="sm:flex sm:items-center sm:justify-between">
                        <div>
                            <h1 class="text-2xl font-bold text-gray-900">{{ client.name }}</h1>
                            <div class="mt-2 space-y-1">
                                <p v-if="client.company" class="text-sm text-gray-600">
                                    <span class="font-medium">Company:</span> {{ client.company }}
                                </p>
                                <p v-if="client.email" class="text-sm text-gray-600">
                                    <span class="font-medium">Email:</span>
                                    <a :href="`mailto:${client.email}`" class="text-blue-600 hover:text-blue-700">
                                        {{ client.email }}
                                    </a>
                                </p>
                                <p v-if="client.phone" class="text-sm text-gray-600">
                                    <span class="font-medium">Phone:</span>
                                    <a :href="`tel:${client.phone}`" class="text-blue-600 hover:text-blue-700">
                                        {{ client.phone }}
                                    </a>
                                </p>
                            </div>
                        </div>
                        <div class="mt-4 flex gap-2 sm:mt-0">
                            <Link
                                :href="route('clients.edit', client.id)"
                                class="inline-flex items-center rounded-md bg-gray-100 px-3 py-2 text-sm font-medium text-gray-800 transition-colors hover:bg-gray-200"
                            >
                                Edit Client
                            </Link>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Meetings Section -->
            <div class="mt-8">
                <div class="flex items-center justify-between">
                    <div>
                        <h2 class="text-lg font-semibold text-gray-900">Meetings</h2>
                        <p class="mt-1 text-sm text-gray-600">All meetings associated with {{ client.name }}.</p>
                    </div>
                    <div>
                        <Link
                            :href="route('meetings.create', { client_id: client.id })"
                            class="inline-flex items-center rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
                        >
                            Add Meeting
                        </Link>
                    </div>
                </div>

                <div class="mt-4 rounded-lg border border-gray-200 bg-white shadow-sm">
                    <div v-if="client.meetings?.length" class="overflow-hidden">
                        <table class="min-w-full divide-y divide-gray-200">
                            <thead class="bg-gray-50">
                                <tr>
                                    <th class="px-6 py-3 text-left text-xs font-medium tracking-wider text-gray-500 uppercase">Title</th>
                                    <th class="px-6 py-3 text-left text-xs font-medium tracking-wider text-gray-500 uppercase">Status</th>
                                    <th class="px-6 py-3 text-left text-xs font-medium tracking-wider text-gray-500 uppercase">Duration</th>
                                    <th class="px-6 py-3 text-left text-xs font-medium tracking-wider text-gray-500 uppercase">Uploaded</th>
                                    <th class="px-6 py-3 text-right text-xs font-medium tracking-wider text-gray-500 uppercase">Actions</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-gray-200 bg-white">
                                <tr v-for="meeting in client.meetings || []" :key="meeting.id" class="hover:bg-gray-50">
                                    <td class="px-6 py-4 text-sm font-medium whitespace-nowrap text-gray-900">
                                        {{ meeting.title }}
                                    </td>
                                    <td class="px-6 py-4 text-sm whitespace-nowrap">
                                        <span
                                            class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium"
                                            :class="getStatusBadgeClass(meeting.status)"
                                        >
                                            {{ meeting.status }}
                                        </span>
                                    </td>
                                    <td class="px-6 py-4 text-sm whitespace-nowrap text-gray-700">
                                        {{ formatDuration(meeting.duration) }}
                                    </td>
                                    <td class="px-6 py-4 text-sm whitespace-nowrap text-gray-700">
                                        {{ formatDate(meeting.uploaded_at) }}
                                    </td>
                                    <td class="px-6 py-4 text-right text-sm font-medium whitespace-nowrap">
                                        <Link :href="route('meetings.show', meeting.id)" class="text-blue-600 hover:text-blue-900"> View </Link>
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </div>

                    <div v-else class="px-6 py-14 text-center text-sm text-gray-500">
                        <div class="flex flex-col items-center">
                            <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                                <path
                                    vector-effect="non-scaling-stroke"
                                    stroke-linecap="round"
                                    stroke-linejoin="round"
                                    stroke-width="2"
                                    d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"
                                />
                            </svg>
                            <h3 class="mt-2 text-sm font-semibold text-gray-900">No meetings</h3>
                            <p class="mt-1 text-sm text-gray-500">This client doesn't have any meetings yet.</p>
                            <div class="mt-6">
                                <Link
                                    :href="route('meetings.create', { client_id: client.id })"
                                    class="inline-flex items-center rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
                                >
                                    Add Meeting
                                </Link>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </AppLayout>
</template>

<script setup lang="ts">
import AppLayout from '@/lib/AppLayout.vue';
import type { Client } from '@/types';
import { Link } from '@inertiajs/vue3';

type MeetingLite = {
    id: number;
    title: string;
    status: 'pending' | 'processing' | 'completed' | 'failed';
    uploaded_at: string;
    duration: number | null;
};

type ClientWithMeetings = Client & {
    meetings?: MeetingLite[];
};

interface Props {
    client: ClientWithMeetings;
}

defineProps<Props>();

const getStatusBadgeClass = (status: string) => {
    switch (status) {
        case 'completed':
            return 'bg-green-100 text-green-800';
        case 'processing':
            return 'bg-yellow-100 text-yellow-800';
        case 'failed':
            return 'bg-red-100 text-red-800';
        case 'pending':
        default:
            return 'bg-gray-100 text-gray-800';
    }
};

const formatDuration = (duration: number | null) => {
    if (!duration) return '-';
    const minutes = Math.floor(duration / 60);
    const seconds = duration % 60;
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
};

const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    });
};
</script>
