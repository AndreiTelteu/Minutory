<template>
    <div class="space-y-1.5">
        <!-- Processing -->
        <div v-if="meeting.status === 'processing'" class="space-y-1.5">
            <div class="flex items-center justify-between text-[12px] text-ink-secondary">
                <span>Processing</span>
                <span v-if="meeting.processing_progress !== null" class="tnum font-medium">{{ Math.round(meeting.processing_progress ?? 0) }}%</span>
            </div>
            <div class="h-1 w-full overflow-hidden rounded-full bg-ground-subtle">
                <div
                    class="h-full rounded-full bg-amber-500 transition-[width] duration-500 ease-out"
                    :style="{ width: `${meeting.processing_progress || 0}%` }"
                />
            </div>
            <div class="tnum flex gap-4 text-[11px] text-ink-tertiary">
                <span v-if="meeting.formatted_elapsed_time">Elapsed {{ meeting.formatted_elapsed_time }}</span>
                <span v-if="meeting.formatted_estimated_remaining_time">Remaining {{ meeting.formatted_estimated_remaining_time }}</span>
            </div>
        </div>

        <!-- Queue -->
        <div v-else-if="meeting.status === 'pending'" class="space-y-1.5">
            <div class="flex items-center justify-between text-[12px] text-ink-secondary">
                <span>In queue</span>
                <span v-if="meeting.queue_progress !== null" class="tnum font-medium">{{ Math.round(meeting.queue_progress ?? 0) }}%</span>
            </div>
            <div class="h-1 w-full overflow-hidden rounded-full bg-ground-subtle">
                <div
                    class="h-full rounded-full bg-zinc-400 transition-[width] duration-500 ease-out"
                    :style="{ width: `${meeting.queue_progress || 0}%` }"
                />
            </div>
            <div v-if="meeting.formatted_estimated_processing_time" class="tnum text-[11px] text-ink-tertiary">
                Est. {{ meeting.formatted_estimated_processing_time }}
            </div>
        </div>

        <!-- Completed -->
        <div v-else-if="meeting.status === 'completed'" class="text-[12px] text-ink-tertiary">
            <span v-if="meeting.formatted_elapsed_time">Processed in {{ meeting.formatted_elapsed_time }}</span>
        </div>

        <!-- Failed -->
        <div v-else-if="meeting.status === 'failed'" class="text-[12px] text-red-600 dark:text-red-400">Please try uploading again</div>
    </div>
</template>

<script setup lang="ts">
interface Meeting {
    id: number;
    status: 'pending' | 'processing' | 'completed' | 'failed';
    elapsed_time?: number | null;
    estimated_remaining_time?: number | null;
    processing_progress?: number | null;
    formatted_elapsed_time?: string | null;
    formatted_estimated_remaining_time?: string | null;
    queue_progress?: number | null;
    formatted_estimated_processing_time?: string | null;
}

defineProps<{ meeting: Meeting }>();
</script>
