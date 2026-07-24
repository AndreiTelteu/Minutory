<template>
    <AppLayout>
        <div class="mx-auto max-w-6xl px-6 py-8 lg:px-10">
            <!-- Header -->
            <div class="mb-8 flex flex-wrap items-center justify-between gap-3">
                <div>
                    <h1 class="text-[20px] font-semibold tracking-tight">Dashboard</h1>
                    <p class="mt-0.5 text-[13px] text-ink-secondary">Overview of your archive.</p>
                </div>
                <div class="flex items-center gap-2">
                    <Link
                        :href="route('ai.chat')"
                        class="rounded-md border border-border-strong px-3 py-1.5 text-[13px] font-medium text-ink transition-colors duration-150 hover:bg-ground-subtle"
                    >
                        Ask AI
                    </Link>
                    <Link
                        :href="route('meetings.create')"
                        class="rounded-md bg-accent-solid px-3 py-1.5 text-[13px] font-medium text-white transition-colors duration-150 hover:bg-accent-solid-hover"
                    >
                        Upload meeting
                    </Link>
                </div>
            </div>

            <!-- Stats strip -->
            <div class="mb-8 flex flex-wrap items-center gap-x-8 gap-y-3 border-y border-border py-4">
                <div v-for="stat in statItems" :key="stat.label" class="flex items-baseline gap-2">
                    <span class="tnum text-[20px] font-semibold tracking-tight" :class="stat.colorClass">{{ stat.value }}</span>
                    <span class="text-[13px] text-ink-secondary">{{ stat.label }}</span>
                </div>
            </div>

            <div class="grid grid-cols-1 gap-6 lg:grid-cols-3">
                <!-- Recent meetings -->
                <section class="overflow-hidden rounded-lg border border-border bg-ground-raised lg:col-span-2">
                    <header class="flex items-center justify-between border-b border-border px-5 py-3">
                        <h2 class="text-[13px] font-semibold">Recent meetings</h2>
                        <Link :href="route('meetings.index')" class="text-[13px] font-medium text-accent hover:text-accent-hover">
                            View all
                        </Link>
                    </header>

                    <div v-if="recentMeetings.length === 0" class="px-5 py-12 text-center">
                        <p class="text-[13px] text-ink-secondary">No meetings yet.</p>
                        <Link :href="route('meetings.create')" class="mt-1 inline-block text-[13px] font-medium text-accent hover:text-accent-hover">
                            Upload your first meeting
                        </Link>
                    </div>

                    <div v-else class="overflow-x-auto">
                    <table class="w-full min-w-[540px]">
                        <thead>
                            <tr class="border-b border-border bg-ground-subtle text-left">
                                <th class="px-5 py-2 text-[11px] font-medium tracking-[0.05em] text-ink-tertiary uppercase">Title</th>
                                <th class="px-5 py-2 text-[11px] font-medium tracking-[0.05em] text-ink-tertiary uppercase">Client</th>
                                <th class="px-5 py-2 text-[11px] font-medium tracking-[0.05em] text-ink-tertiary uppercase">Status</th>
                                <th class="px-5 py-2 text-right text-[11px] font-medium tracking-[0.05em] text-ink-tertiary uppercase">Uploaded</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr
                                v-for="m in recentMeetings"
                                :key="m.id"
                                class="cursor-pointer border-b border-border transition-colors duration-150 last:border-0 hover:bg-ground-subtle"
                                @click="router.visit(route('meetings.show', m.id))"
                            >
                                <td class="px-5 py-2.5 text-[13px] font-medium">{{ m.title }}</td>
                                <td class="px-5 py-2.5 text-[13px] text-ink-secondary">{{ m.client.name }}</td>
                                <td class="px-5 py-2.5"><MeetingStatusBadge :status="m.status" :meeting="m" /></td>
                                <td class="tnum px-5 py-2.5 text-right text-[13px] text-ink-secondary">
                                    {{ formatDate(m.created_at || m.uploaded_at) }}
                                </td>
                            </tr>
                        </tbody>
                    </table>
                    </div>
                </section>

                <!-- Top clients -->
                <section class="overflow-hidden rounded-lg border border-border bg-ground-raised">
                    <header class="border-b border-border px-5 py-3">
                        <h2 class="text-[13px] font-semibold">Top clients</h2>
                    </header>

                    <div v-if="topClients.length === 0" class="px-5 py-12 text-center text-[13px] text-ink-secondary">No clients yet.</div>

                    <ul v-else>
                        <li v-for="c in topClients" :key="c.id">
                            <Link
                                :href="route('clients.show', c.id)"
                                class="flex items-center justify-between border-b border-border px-5 py-2.5 transition-colors duration-150 last:border-0 hover:bg-ground-subtle"
                            >
                                <span class="text-[13px] font-medium">{{ c.name }}</span>
                                <span class="tnum text-[13px] text-ink-secondary">{{ c.meetings_count }} meetings</span>
                            </Link>
                        </li>
                    </ul>
                </section>
            </div>
        </div>
    </AppLayout>
</template>

<script setup lang="ts">
import AppLayout from '@/lib/AppLayout.vue';
import MeetingStatusBadge from '@/lib/MeetingStatusBadge.vue';
import { Link, router } from '@inertiajs/vue3';
import { computed } from 'vue';

interface ClientLite {
    id: number;
    name: string;
    meetings_count?: number;
}

interface ClientRef {
    id: number;
    name: string;
}

interface Meeting {
    id: number;
    title: string;
    status: 'pending' | 'processing' | 'completed' | 'failed';
    uploaded_at: string;
    created_at?: string;
    client: ClientRef;
}

interface Stats {
    total_clients: number;
    total_meetings: number;
    completed_meetings: number;
    processing_meetings: number;
    pending_meetings: number;
    failed_meetings: number;
}

interface Props {
    recentMeetings: Meeting[];
    stats: Stats;
    topClients: ClientLite[];
}

const props = defineProps<Props>();

const recentMeetings = props.recentMeetings || [];
const stats = props.stats || {
    total_clients: 0,
    total_meetings: 0,
    completed_meetings: 0,
    processing_meetings: 0,
    pending_meetings: 0,
    failed_meetings: 0,
};
const topClients = props.topClients || [];

const statItems = computed(() => [
    { label: 'clients', value: stats.total_clients, colorClass: '' },
    { label: 'meetings', value: stats.total_meetings, colorClass: '' },
    { label: 'completed', value: stats.completed_meetings, colorClass: 'text-green-600 dark:text-green-400' },
    { label: 'processing', value: stats.processing_meetings, colorClass: 'text-amber-600 dark:text-amber-400' },
    {
        label: 'pending / failed',
        value: stats.pending_meetings + stats.failed_meetings,
        colorClass: 'text-ink-secondary',
    },
]);

const formatDate = (dateString: string) => {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    });
};
</script>
