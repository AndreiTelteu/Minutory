<template>
    <AppLayout>
        <div class="mx-auto max-w-6xl px-6 py-8 lg:px-10">
            <div class="mb-6">
                <Link
                    :href="route('clients.index')"
                    class="inline-flex items-center gap-1 text-[13px] font-medium text-ink-secondary transition-colors duration-150 hover:text-ink"
                >
                    <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
                    </svg>
                    Clients
                </Link>
            </div>

            <!-- Client header -->
            <div class="mb-8 flex flex-wrap items-start justify-between gap-4">
                <div>
                    <h1 class="text-[20px] font-semibold tracking-tight">{{ client.name }}</h1>
                    <div class="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-[13px] text-ink-secondary">
                        <span v-if="client.company">{{ client.company }}</span>
                        <a v-if="client.email" :href="`mailto:${client.email}`" class="text-accent hover:text-accent-hover">{{ client.email }}</a>
                        <a v-if="client.phone" :href="`tel:${client.phone}`" class="tnum hover:text-ink">{{ client.phone }}</a>
                    </div>
                </div>
                <Link
                    :href="route('clients.edit', client.id)"
                    class="rounded-md border border-border-strong px-3 py-1.5 text-[13px] font-medium text-ink transition-colors duration-150 hover:bg-ground-subtle"
                >
                    Edit client
                </Link>
            </div>

            <!-- Meetings -->
            <div class="mb-4 flex items-center justify-between">
                <h2 class="text-[13px] font-semibold">Meetings</h2>
                <Link
                    :href="route('meetings.create', { client_id: client.id })"
                    class="rounded-md bg-accent-solid px-3 py-1.5 text-[13px] font-medium text-white transition-colors duration-150 hover:bg-accent-solid-hover"
                >
                    Add meeting
                </Link>
            </div>

            <div class="overflow-hidden rounded-lg border border-border bg-ground-raised">
                <div v-if="!client.meetings?.length" class="px-5 py-16 text-center">
                    <p class="text-[13px] text-ink-secondary">This client doesn't have any meetings yet.</p>
                    <Link
                        :href="route('meetings.create', { client_id: client.id })"
                        class="mt-1 inline-block text-[13px] font-medium text-accent hover:text-accent-hover"
                    >
                        Upload a meeting
                    </Link>
                </div>

                <div v-else class="overflow-x-auto">
                <table class="w-full min-w-[540px]">
                    <thead>
                        <tr class="border-b border-border bg-ground-subtle text-left">
                            <th class="px-5 py-2 text-[11px] font-medium tracking-[0.05em] text-ink-tertiary uppercase">Title</th>
                            <th class="px-5 py-2 text-[11px] font-medium tracking-[0.05em] text-ink-tertiary uppercase">Status</th>
                            <th class="px-5 py-2 text-[11px] font-medium tracking-[0.05em] text-ink-tertiary uppercase">Duration</th>
                            <th class="px-5 py-2 text-right text-[11px] font-medium tracking-[0.05em] text-ink-tertiary uppercase">Uploaded</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr
                            v-for="meeting in client.meetings"
                            :key="meeting.id"
                            class="cursor-pointer border-b border-border transition-colors duration-150 last:border-0 hover:bg-ground-subtle"
                            @click="router.visit(route('meetings.show', meeting.id))"
                        >
                            <td class="px-5 py-2.5 text-[13px] font-medium">{{ meeting.title }}</td>
                            <td class="px-5 py-2.5">
                                <span :class="['inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[12px] font-medium', getStatusBadgeClass(meeting.status)]">
                                    <span class="h-1.5 w-1.5 rounded-full bg-current" />
                                    {{ meeting.status }}
                                </span>
                            </td>
                            <td class="tnum px-5 py-2.5 text-[13px] text-ink-secondary">{{ formatDuration(meeting.duration) }}</td>
                            <td class="tnum px-5 py-2.5 text-right text-[13px] text-ink-secondary">{{ formatDate(meeting.uploaded_at) }}</td>
                        </tr>
                    </tbody>
                </table>
                </div>
            </div>
        </div>
    </AppLayout>
</template>

<script setup lang="ts">
import AppLayout from '@/lib/AppLayout.vue';
import type { Client } from '@/types';
import { Link, router } from '@inertiajs/vue3';

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

defineProps<{ client: ClientWithMeetings }>();

const getStatusBadgeClass = (status: string) => {
    switch (status) {
        case 'completed':
            return 'bg-green-500/10 text-green-700 dark:text-green-400';
        case 'processing':
            return 'bg-amber-500/10 text-amber-700 dark:text-amber-400';
        case 'failed':
            return 'bg-red-500/10 text-red-700 dark:text-red-400';
        case 'pending':
        default:
            return 'bg-zinc-500/10 text-zinc-600 dark:text-zinc-400';
    }
};

const formatDuration = (duration: number | null) => {
    if (!duration) return '—';
    const minutes = Math.floor(duration / 60);
    const seconds = duration % 60;
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
};

const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    });
};
</script>
