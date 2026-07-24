<template>
    <div v-if="!meeting" class="flex items-center">
        <span class="inline-flex items-center gap-1.5 rounded-full bg-ground-subtle px-2 py-0.5 text-[12px] font-medium text-ink-secondary">
            <span class="h-3 w-3 animate-spin rounded-full border-2 border-border-strong border-t-ink-secondary" />
            Loading…
        </span>
    </div>

    <div v-else class="flex items-center gap-1.5">
        <span :class="['inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[12px] font-medium', statusClasses]">
            <span v-if="showSpinner" class="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent opacity-70" />
            <span v-else class="h-1.5 w-1.5 rounded-full bg-current" />
            {{ statusText }}
        </span>

        <button
            v-if="meeting.status === 'failed' && meeting.error_message"
            @click.stop="showErrorDetails = !showErrorDetails"
            class="rounded p-0.5 text-red-600 transition-colors hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
            title="Show error details"
        >
            <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z"
                />
            </svg>
        </button>

        <button
            v-if="meeting.status === 'failed' && canRetry"
            @click.stop="$emit('retry')"
            :disabled="isRetrying"
            class="rounded p-0.5 text-accent transition-colors hover:text-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
            title="Retry processing"
        >
            <svg class="h-3.5 w-3.5" :class="{ 'animate-spin': isRetrying }" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99"
                />
            </svg>
        </button>
    </div>

    <Transition
        enter-active-class="transition-all duration-200 ease-out"
        enter-from-class="opacity-0 -translate-y-1"
        enter-to-class="opacity-100 translate-y-0"
        leave-active-class="transition-all duration-150 ease-in"
        leave-from-class="opacity-100 translate-y-0"
        leave-to-class="opacity-0 -translate-y-1"
    >
        <div
            v-if="showErrorDetails && meeting && meeting.status === 'failed'"
            class="mt-2 rounded-md border border-red-200 bg-red-50 p-3 dark:border-red-900/50 dark:bg-red-950/30"
        >
            <p class="text-[13px] font-medium text-red-700 dark:text-red-300">Processing failed</p>
            <p class="mt-0.5 text-[12px] text-red-600 dark:text-red-400">{{ meeting.error_message }}</p>

            <div class="mt-2 flex gap-2">
                <button
                    v-if="canRetry"
                    @click="$emit('retry')"
                    :disabled="isRetrying"
                    class="rounded-md border border-red-300 px-2.5 py-1 text-[12px] font-medium text-red-700 transition-colors hover:bg-red-100 disabled:opacity-50 dark:border-red-800 dark:text-red-300 dark:hover:bg-red-950/50"
                >
                    {{ isRetrying ? 'Retrying…' : 'Try again' }}
                </button>
                <button
                    v-if="meeting.technical_error"
                    @click="showTechnicalDetails = !showTechnicalDetails"
                    class="px-2.5 py-1 text-[12px] font-medium text-red-600 hover:text-red-700 dark:text-red-400"
                >
                    {{ showTechnicalDetails ? 'Hide' : 'Show' }} technical details
                </button>
            </div>

            <pre
                v-if="showTechnicalDetails && meeting.technical_error"
                class="mt-2 max-h-32 overflow-auto rounded bg-red-100 p-2.5 text-[11px] text-red-800 dark:bg-red-950/50 dark:text-red-300"
            >{{ meeting.technical_error }}</pre>
        </div>
    </Transition>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';

interface Meeting {
    id: number;
    status: 'pending' | 'processing' | 'completed' | 'failed';
    processing_progress?: number;
    queue_progress?: number;
    formatted_elapsed_time?: string;
    formatted_estimated_remaining_time?: string;
    error_message?: string;
    technical_error?: string;
}

interface Props {
    meeting?: Meeting | null;
    showProgress?: boolean;
    canRetry?: boolean;
    isRetrying?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
    showProgress: true,
    canRetry: true,
    isRetrying: false,
});

defineEmits<{ (e: 'retry'): void }>();

const showErrorDetails = ref(false);
const showTechnicalDetails = ref(false);

const statusClasses = computed(() => {
    if (!props.meeting) return 'bg-ground-subtle text-ink-secondary';
    switch (props.meeting.status) {
        case 'pending':
            return 'bg-zinc-500/10 text-zinc-600 dark:text-zinc-400';
        case 'processing':
            return 'bg-amber-500/10 text-amber-700 dark:text-amber-400';
        case 'completed':
            return 'bg-green-500/10 text-green-700 dark:text-green-400';
        case 'failed':
            return 'bg-red-500/10 text-red-700 dark:text-red-400';
        default:
            return 'bg-ground-subtle text-ink-secondary';
    }
});

const showSpinner = computed(() => {
    if (!props.meeting) return props.isRetrying;
    return props.meeting.status === 'processing' || props.isRetrying;
});

const statusText = computed(() => {
    if (!props.meeting) return 'Loading…';
    switch (props.meeting.status) {
        case 'pending':
            return 'Pending';
        case 'processing':
            return 'Processing';
        case 'completed':
            return 'Completed';
        case 'failed':
            return 'Failed';
        default:
            return 'Unknown';
    }
});
</script>
