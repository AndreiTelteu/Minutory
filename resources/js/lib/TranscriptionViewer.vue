<template>
    <div class="transcription-viewer flex min-h-0 flex-1 flex-col">
        <div class="mb-3 flex shrink-0 items-center justify-between gap-3">
            <h3 class="text-[13px] font-semibold">Transcript</h3>
            <div class="flex items-center gap-3">
                <label class="flex cursor-pointer items-center gap-1.5 text-[12px] text-ink-secondary select-none">
                    <input
                        v-model="autoScroll"
                        type="checkbox"
                        class="h-3.5 w-3.5 rounded border-border-strong accent-accent"
                        @change="onAutoScrollToggle"
                    />
                    Auto-scroll
                </label>
                <span class="tnum text-[12px] text-ink-tertiary">{{ transcriptions.length }} segments</span>
            </div>
        </div>

        <!-- Search -->
        <div class="relative mb-3 shrink-0">
            <input
                v-model="searchQuery"
                type="text"
                placeholder="Search transcript…"
                class="w-full rounded-md border border-border-strong bg-ground-raised py-1.5 pr-3 pl-8 text-[13px] text-ink placeholder:text-ink-tertiary focus:border-accent focus:ring-2 focus:ring-accent/30 focus:outline-none"
            />
            <svg class="absolute top-2 left-2.5 h-4 w-4 text-ink-tertiary" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
            </svg>
        </div>

        <!-- Segments -->
        <div
            ref="transcriptionContainer"
            class="max-h-[70vh] min-h-0 flex-1 overflow-y-auto rounded-lg border border-border bg-ground-subtle"
            @scroll.passive="onContainerScroll"
            @wheel.passive="onManualScrollIntent"
            @touchmove.passive="onManualScrollIntent"
        >
            <div v-if="filteredTranscriptions.length === 0" class="p-8 text-center text-[13px] text-ink-secondary">
                {{ searchQuery ? 'No segments match your search.' : 'No transcription available.' }}
            </div>

            <div v-else class="space-y-0.5 p-1.5">
                <div
                    v-for="transcription in filteredTranscriptions"
                    :key="transcription.id"
                    :ref="(el) => setTranscriptionRef(transcription.id, el)"
                    :class="[
                        'transcription-segment cursor-pointer rounded px-2 py-1.5 leading-snug transition-colors duration-150',
                        isCurrentSegment(transcription) ? 'bg-accent-subtle' : 'hover:bg-ground-raised',
                    ]"
                    @click="onTimestampClick(transcription.start_time)"
                >
                    <span class="text-[12px] font-semibold" :class="isCurrentSegment(transcription) ? 'text-accent' : 'text-ink'">
                        {{ transcription.speaker || 'Unknown Speaker' }}
                    </span>
                    <span class="tnum ml-1.5 text-[11px] text-ink-tertiary" :title="`Jump to ${formatTime(transcription.start_time)}`">
                        {{ formatTime(transcription.start_time) }}
                    </span>
                    <span
                        class="ml-1.5 text-[13px] text-ink-secondary"
                        :class="{ 'text-ink': isCurrentSegment(transcription) }"
                        v-html="highlightSearchTerm(transcription.text)"
                    ></span>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue';

interface Transcription {
    id: number;
    speaker: string | null;
    text: string | null;
    start_time: number;
    end_time: number;
    confidence: number;
}

interface Props {
    transcriptions: Transcription[];
    currentTime: number;
}

interface Emits {
    (e: 'timestampClick', time: number): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const transcriptionContainer = ref<HTMLElement | null>(null);
const transcriptionRefs = ref<Map<number, HTMLElement>>(new Map());
const searchQuery = ref('');
const currentSegmentIndex = ref(-1);
const autoScroll = ref(true);

let programmaticScroll = false;
let programmaticScrollTimer: ReturnType<typeof setTimeout> | null = null;

const filteredTranscriptions = computed(() => {
    if (!searchQuery.value.trim()) {
        return props.transcriptions;
    }
    const query = searchQuery.value.toLowerCase();
    return props.transcriptions.filter((t) => (t.text ?? '').toLowerCase().includes(query) || (t.speaker ?? '').toLowerCase().includes(query));
});

const currentSegment = computed(() => {
    return props.transcriptions.find((t) => props.currentTime >= t.start_time && props.currentTime <= t.end_time);
});

const isCurrentSegment = (transcription: Transcription): boolean => {
    return currentSegment.value?.id === transcription.id;
};

const hasPrevious = computed(() => currentSegmentIndex.value > 0);
const hasNext = computed(() => currentSegmentIndex.value < filteredTranscriptions.value.length - 1);

const setTranscriptionRef = (id: number, el: any) => {
    if (el) {
        transcriptionRefs.value.set(id, el);
    } else {
        transcriptionRefs.value.delete(id);
    }
};

const onTimestampClick = (time: number | string) => {
    const timestamp = Number(time);
    if (Number.isFinite(timestamp)) {
        emit('timestampClick', timestamp);
    }
};

const scrollToCurrentSegment = async () => {
    if (!currentSegment.value || !transcriptionContainer.value) return;
    await nextTick();
    const element = transcriptionRefs.value.get(currentSegment.value.id);
    if (element) {
        markProgrammaticScroll();
        element.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
};

const markProgrammaticScroll = () => {
    programmaticScroll = true;
    if (programmaticScrollTimer) clearTimeout(programmaticScrollTimer);
    programmaticScrollTimer = setTimeout(() => {
        programmaticScroll = false;
    }, 600);
};

const onContainerScroll = () => {
    if (programmaticScroll) return;
    if (autoScroll.value) autoScroll.value = false;
};

const onManualScrollIntent = () => {
    programmaticScroll = false;
    if (programmaticScrollTimer) clearTimeout(programmaticScrollTimer);
    if (autoScroll.value) autoScroll.value = false;
};

const onAutoScrollToggle = () => {
    if (autoScroll.value) {
        scrollToCurrentSegment();
    }
};

const navigateToSegment = (index: number): number | null => {
    const transcription = filteredTranscriptions.value[index];
    if (!transcription) return null;

    currentSegmentIndex.value = index;
    onTimestampClick(transcription.start_time);
    if (autoScroll.value) {
        scrollToCurrentSegment();
    }

    return transcription.start_time;
};

const scrollToPrevious = (): number | null => {
    const currentIndex = currentSegmentIndex.value;
    const index = currentIndex > 0 ? currentIndex - 1 : 0;
    return navigateToSegment(index);
};

const scrollToNext = (): number | null => {
    const currentIndex = currentSegmentIndex.value;
    const index = currentIndex >= 0 ? Math.min(currentIndex + 1, filteredTranscriptions.value.length - 1) : 0;
    return navigateToSegment(index);
};

const formatTime = (seconds: number): string => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const remainingSeconds = Math.floor(seconds % 60);
    if (hours > 0) {
        return `${hours}:${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`;
    }
    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
};

const highlightSearchTerm = (text: string | null): string => {
    const normalizedText = text ?? '';
    if (!searchQuery.value.trim()) return normalizedText;
    const query = searchQuery.value.trim().replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const regex = new RegExp(`(${query})`, 'gi');
    return normalizedText.replace(regex, '<mark>$1</mark>');
};

watch(currentSegment, (newSegment) => {
    if (newSegment) {
        const index = filteredTranscriptions.value.findIndex((t) => t.id === newSegment.id);
        currentSegmentIndex.value = index;
        if (autoScroll.value) {
            scrollToCurrentSegment();
        }
    }
});

watch(searchQuery, () => {
    currentSegmentIndex.value = -1;
});

defineExpose({
    scrollToPrevious,
    scrollToNext,
    hasPrevious,
    hasNext,
    currentSegmentIndex,
    filteredTranscriptions,
});
</script>

<style scoped>
.transcription-segment {
    scroll-margin-top: 1rem;
}

:deep(mark) {
    background-color: rgb(254 240 138);
    color: #18181b;
    padding: 0 0.125rem;
    border-radius: 0.25rem;
}

.dark :deep(mark) {
    background-color: rgb(133 77 14);
    color: #ededec;
}
</style>
