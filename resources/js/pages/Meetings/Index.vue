<template>
    <AppLayout>
        <div class="mx-auto max-w-6xl px-6 py-8 lg:px-10">
            <div class="mb-6 flex flex-wrap items-center justify-between gap-3">
                <div class="flex items-center gap-3">
                    <h1 class="text-[20px] font-semibold tracking-tight">Meetings</h1>
                    <span class="flex items-center gap-1.5 text-[12px] text-ink-tertiary">
                        <span class="h-1.5 w-1.5 animate-pulse rounded-full bg-green-500" />
                        Live
                    </span>
                </div>
                <Link
                    :href="route('meetings.create')"
                    class="rounded-md bg-accent-solid px-3 py-1.5 text-[13px] font-medium text-white transition-colors duration-150 hover:bg-accent-solid-hover"
                >
                    Upload meeting
                </Link>
            </div>

            <!-- Filter toolbar -->
            <form @submit.prevent="applyFilters" class="mb-4 flex flex-wrap items-end gap-2">
                <select
                    v-model="filterForm.client_id"
                    data-testid="client-filter"
                    aria-label="Filter by client"
                    class="rounded-md border border-border-strong bg-ground-raised px-2.5 py-1.5 text-[13px] text-ink focus:border-accent focus:ring-2 focus:ring-accent/30 focus:outline-none"
                    @change="applyFilters"
                >
                    <option value="">All clients</option>
                    <option v-for="client in clients" :key="client.id" :value="client.id">{{ client.name }}</option>
                </select>

                <select
                    v-model="filterForm.status"
                    data-testid="status-filter"
                    aria-label="Filter by status"
                    class="rounded-md border border-border-strong bg-ground-raised px-2.5 py-1.5 text-[13px] text-ink focus:border-accent focus:ring-2 focus:ring-accent/30 focus:outline-none"
                    @change="applyFilters"
                >
                    <option value="">All statuses</option>
                    <option value="pending">Pending</option>
                    <option value="processing">Processing</option>
                    <option value="completed">Completed</option>
                    <option value="failed">Failed</option>
                </select>

                <input
                    v-model="filterForm.date_from"
                    type="date"
                    data-testid="date-from"
                    aria-label="From date"
                    class="rounded-md border border-border-strong bg-ground-raised px-2.5 py-1.5 text-[13px] text-ink focus:border-accent focus:ring-2 focus:ring-accent/30 focus:outline-none"
                    @change="applyFilters"
                />
                <input
                    v-model="filterForm.date_to"
                    type="date"
                    data-testid="date-to"
                    aria-label="To date"
                    class="rounded-md border border-border-strong bg-ground-raised px-2.5 py-1.5 text-[13px] text-ink focus:border-accent focus:ring-2 focus:ring-accent/30 focus:outline-none"
                    @change="applyFilters"
                />

                <button
                    v-if="hasActiveFilters"
                    type="button"
                    @click="clearFilters"
                    class="rounded-md px-2.5 py-1.5 text-[13px] font-medium text-ink-secondary transition-colors duration-150 hover:bg-ground-subtle hover:text-ink"
                >
                    Clear
                </button>
            </form>

            <!-- Meetings table -->
            <div class="overflow-hidden rounded-lg border border-border bg-ground-raised">
                <div v-if="realtimeMeetings.length === 0" class="px-5 py-16 text-center">
                    <p class="text-[13px] text-ink-secondary">No meetings found.</p>
                    <Link :href="route('meetings.create')" class="mt-1 inline-block text-[13px] font-medium text-accent hover:text-accent-hover">
                        Upload your first meeting
                    </Link>
                </div>

                <div v-else class="overflow-x-auto">
                    <table class="w-full">
                        <thead>
                            <tr class="border-b border-border bg-ground-subtle text-left">
                                <th v-for="col in columns" :key="col.key" class="px-5 py-2" :class="col.headerClass">
                                    <button
                                        v-if="col.sortable"
                                        @click="setSort(col.key)"
                                        class="inline-flex items-center gap-1 text-[11px] font-medium tracking-[0.05em] text-ink-tertiary uppercase transition-colors hover:text-ink"
                                    >
                                        {{ col.label }}
                                        <span v-if="filterForm.sort === col.key" class="text-ink">{{
                                            filterForm.direction === 'asc' ? '↑' : '↓'
                                        }}</span>
                                    </button>
                                    <span v-else class="text-[11px] font-medium tracking-[0.05em] text-ink-tertiary uppercase">{{ col.label }}</span>
                                </th>
                                <th class="px-5 py-2" />
                            </tr>
                        </thead>
                        <tbody>
                            <tr
                                v-for="meeting in realtimeMeetings"
                                :key="meeting.id"
                                class="cursor-pointer border-b border-border transition-colors duration-150 last:border-0 hover:bg-ground-subtle"
                                @click="router.visit(route('meetings.show', meeting.id))"
                            >
                                <td class="px-5 py-2.5 text-[13px] font-medium">{{ meeting.title }}</td>
                                <td class="px-5 py-2.5 text-[13px] text-ink-secondary">{{ meeting.client.name }}</td>
                                <td class="w-56 px-5 py-2.5">
                                    <div class="space-y-1.5">
                                        <MeetingStatusBadge :status="meeting.status" :meeting="meeting" />
                                        <MeetingProgressIndicator
                                            v-if="meeting.status === 'pending' || meeting.status === 'processing' || meeting.status === 'failed'"
                                            :meeting="meeting"
                                        />
                                    </div>
                                </td>
                                <td class="tnum px-5 py-2.5 text-[13px] whitespace-nowrap text-ink-secondary" :title="meetingTimeTitle(meeting)">
                                    {{ formatDate(meeting.meeting_at ?? meeting.uploaded_at) }}
                                </td>
                                <td class="tnum px-5 py-2.5 text-[13px] whitespace-nowrap text-ink-secondary">
                                    {{ formatDuration(meeting.duration) }}
                                </td>
                                <td class="px-5 py-2.5 text-right">
                                    <button
                                        @click.stop="deleteMeeting(meeting)"
                                        class="rounded p-1 text-ink-tertiary transition-colors duration-150 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950/40 dark:hover:text-red-400"
                                        aria-label="Delete meeting"
                                    >
                                        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                                            <path
                                                stroke-linecap="round"
                                                stroke-linejoin="round"
                                                d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"
                                            />
                                        </svg>
                                    </button>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>

                <!-- Pagination -->
                <div v-if="meetings.links.length > 3" class="flex items-center justify-between border-t border-border px-5 py-2.5">
                    <span class="tnum text-[12px] text-ink-tertiary">{{ meetings.from }}–{{ meetings.to }} of {{ meetings.total }}</span>
                    <div class="flex gap-0.5">
                        <Link
                            v-for="link in meetings.links"
                            :key="link.label"
                            :href="link.url || '#'"
                            :class="[
                                'rounded-md px-2 py-1 text-[12px] font-medium transition-colors duration-150',
                                link.active
                                    ? 'bg-accent-subtle text-accent'
                                    : link.url
                                      ? 'text-ink-secondary hover:bg-ground-subtle hover:text-ink'
                                      : 'pointer-events-none text-ink-tertiary opacity-50',
                            ]"
                            v-html="link.label"
                        />
                    </div>
                </div>
            </div>
        </div>
    </AppLayout>
</template>

<script setup lang="ts">
import AppLayout from '@/lib/AppLayout.vue';
import { formatBrowserDateTime, resolveBrowserTimeZone } from '@/lib/browserDateTime';
import MeetingProgressIndicator from '@/lib/MeetingProgressIndicator.vue';
import MeetingStatusBadge from '@/lib/MeetingStatusBadge.vue';
import { useRealTimeUpdates } from '@/lib/useRealTimeUpdates';
import { Link, router } from '@inertiajs/vue3';
import { computed, onMounted, reactive, ref, watch } from 'vue';

interface Client {
    id: number;
    name: string;
}

interface Meeting {
    id: number;
    title: string;
    client: Client;
    status: 'pending' | 'processing' | 'completed' | 'failed';
    meeting_at: string | null;
    uploaded_at: string | null;
    duration: number | null;
    elapsed_time?: number;
    estimated_remaining_time?: number;
    processing_progress?: number;
    formatted_elapsed_time?: string;
    formatted_estimated_remaining_time?: string;
    queue_progress?: number;
}

interface PaginatedMeetings {
    data: Meeting[];
    links: Array<{
        url: string | null;
        label: string;
        active: boolean;
    }>;
    from: number;
    to: number;
    total: number;
}

interface Props {
    meetings: PaginatedMeetings;
    clients: Client[];
    filters: {
        client_id?: string;
        status?: string;
        date_from?: string;
        date_to?: string;
        sort?: string;
        direction?: 'asc' | 'desc';
        timezone?: string;
    };
}

const props = defineProps<Props>();
const timestampsReady = ref(false);

const { meetings: realtimeMeetings } = useRealTimeUpdates(props.meetings.data);

onMounted(() => {
    timestampsReady.value = true;
    filterForm.timezone = resolveBrowserTimeZone();
});

watch(
    () => props.meetings.data,
    (newMeetings) => {
        realtimeMeetings.value = [...newMeetings];
    },
);

const filterForm = reactive({
    client_id: props.filters.client_id || '',
    status: props.filters.status || '',
    date_from: props.filters.date_from || '',
    date_to: props.filters.date_to || '',
    sort: props.filters.sort || 'meeting_at',
    direction: (props.filters.direction as 'asc' | 'desc') || 'desc',
    timezone: props.filters.timezone || 'UTC',
});

const columns = [
    { key: 'title', label: 'Meeting', sortable: true, headerClass: '' },
    { key: 'client', label: 'Client', sortable: true, headerClass: '' },
    { key: 'status', label: 'Status', sortable: false, headerClass: '' },
    { key: 'meeting_at', label: 'Meeting time', sortable: true, headerClass: '' },
    { key: 'duration', label: 'Duration', sortable: true, headerClass: '' },
];

const hasActiveFilters = computed(
    () => filterForm.client_id !== '' || filterForm.status !== '' || filterForm.date_from !== '' || filterForm.date_to !== '',
);

const applyFilters = () => {
    filterForm.timezone = resolveBrowserTimeZone();
    router.get(route('meetings.index'), filterForm, {
        preserveState: true,
        preserveScroll: true,
    });
};

const clearFilters = () => {
    filterForm.client_id = '';
    filterForm.status = '';
    filterForm.date_from = '';
    filterForm.date_to = '';
    applyFilters();
};

const deleteMeeting = (meeting: Meeting) => {
    if (confirm(`Are you sure you want to delete "${meeting.title}"? This action cannot be undone.`)) {
        router.delete(route('meetings.destroy', meeting.id), {
            preserveScroll: true,
        });
    }
};

const formatDate = (dateString: string | null) =>
    formatBrowserDateTime(dateString, timestampsReady.value, undefined, {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    });

const meetingTimeTitle = (meeting: Meeting): string => {
    if (meeting.meeting_at && meeting.uploaded_at) {
        return `Uploaded ${formatDate(meeting.uploaded_at)}`;
    }

    if (!meeting.meeting_at && meeting.uploaded_at) {
        return 'Using upload time';
    }

    return 'Meeting time unavailable';
};

const setSort = (column: string) => {
    if (filterForm.sort === column) {
        filterForm.direction = filterForm.direction === 'asc' ? 'desc' : 'asc';
    } else {
        filterForm.sort = column;
        filterForm.direction = column === 'title' || column === 'client' ? 'asc' : 'desc';
    }
    applyFilters();
};

const formatDuration = (duration: number | null) => {
    if (!duration) return '—';
    const hours = Math.floor(duration / 3600);
    const minutes = Math.floor((duration % 3600) / 60);
    const seconds = duration % 60;
    if (hours > 0) return `${hours}h ${minutes}m`;
    if (minutes > 0) return `${minutes}m ${seconds}s`;
    return `${seconds}s`;
};
</script>
