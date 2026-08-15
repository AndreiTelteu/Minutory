<template>
    <AppLayout>
        <Head :title="`${meeting.title} - ${meeting.client.name}`" />
        <div class="px-6 py-8 lg:px-10">
            <!-- Header -->
            <div class="mb-6">
                <Link
                    :href="route('meetings.index')"
                    class="inline-flex items-center gap-1 text-[13px] font-medium text-ink-secondary transition-colors duration-150 hover:text-ink"
                >
                    <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
                    </svg>
                    Meetings
                </Link>
                <div class="mt-2 flex flex-wrap items-center gap-3">
                    <h1 class="text-[20px] font-semibold tracking-tight">{{ meeting.title }}</h1>
                    <MeetingStatusBadge :status="meeting.status" :meeting="meeting" />
                    <button
                        v-if="meeting.status === 'completed' && meeting.transcriptions?.length"
                        class="rounded-md border border-border-strong px-2.5 py-1 text-[12px] font-medium text-ink-secondary transition-colors duration-150 hover:bg-ground-subtle hover:text-ink"
                        @click="speakerEditorOpen = !speakerEditorOpen"
                    >
                        {{ speakerEditorOpen ? 'Hide speakers' : 'Edit speakers' }}
                    </button>
                </div>
                <Link :href="route('clients.show', meeting.client.id)" class="mt-1 inline-block text-[13px] text-ink-secondary hover:text-accent">
                    {{ meeting.client.name }}
                </Link>
                <div class="tnum mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[12px] text-ink-tertiary">
                    <span>Language {{ meeting.language === 'en' ? 'English' : 'Română' }}</span>
                    <span>Meeting time {{ formatDateTime(meeting.meeting_at) }}</span>
                    <span>Uploaded {{ formatDateTime(meeting.uploaded_at) }}</span>
                </div>
            </div>

            <!-- Processing status -->
            <div
                v-if="meeting.status === 'pending' || meeting.status === 'processing'"
                class="mb-6 flex items-center justify-between rounded-lg border border-border bg-ground-raised px-5 py-4"
            >
                <div>
                    <h3 class="text-[13px] font-semibold">
                        {{ meeting.status === 'pending' ? 'Queued for processing' : 'Processing meeting' }}
                    </h3>
                    <p class="tnum mt-0.5 text-[12px] text-ink-secondary">
                        <template v-if="meeting.status === 'pending'">
                            Estimated time: {{ meeting.formatted_estimated_processing_time || 'Calculating…' }}
                        </template>
                        <template v-else>
                            Elapsed {{ meeting.formatted_elapsed_time || '0:00' }} · Remaining
                            {{ meeting.formatted_estimated_remaining_time || 'Calculating…' }}
                        </template>
                    </p>
                </div>
                <div class="h-5 w-5 animate-spin rounded-full border-2 border-border-strong border-t-accent" />
            </div>

            <!-- Video + transcript -->
            <div
                v-if="meeting.status === 'completed' && videoUrl && meeting.transcriptions && meeting.transcriptions.length > 0"
                class="grid grid-cols-1 gap-6 xl:grid-cols-5"
            >
                <section class="rounded-lg border border-border bg-ground-raised p-5 xl:col-span-3">
                    <VideoPlayer
                        ref="videoPlayerRef"
                        :video-url="videoUrl"
                        :current-time="videoCurrentTime"
                        @time-update="onVideoTimeUpdate"
                        @duration-change="onVideoDurationChange"
                        @play="onVideoPlay"
                        @pause="onVideoPause"
                        @error="onVideoError"
                    />

                    <div class="mt-4 flex items-center justify-between">
                        <div class="flex gap-1.5">
                            <button
                                @click="goToPrevious"
                                :disabled="!meeting.transcriptions?.length"
                                class="rounded-md border border-border-strong px-2.5 py-1 text-[12px] font-medium text-ink-secondary transition-colors duration-150 hover:bg-ground-subtle hover:text-ink disabled:cursor-not-allowed disabled:opacity-40"
                            >
                                ← Prev
                            </button>
                            <button
                                @click="goToNext"
                                :disabled="!meeting.transcriptions?.length"
                                class="rounded-md border border-border-strong px-2.5 py-1 text-[12px] font-medium text-ink-secondary transition-colors duration-150 hover:bg-ground-subtle hover:text-ink disabled:cursor-not-allowed disabled:opacity-40"
                            >
                                Next →
                            </button>
                        </div>
                        <span
                            v-if="transcriptionViewerRef && transcriptionViewerRef.currentSegmentIndex >= 0"
                            class="tnum text-[12px] text-ink-tertiary"
                        >
                            {{ transcriptionViewerRef.currentSegmentIndex + 1 }} / {{ transcriptionViewerRef.filteredTranscriptions.length }}
                        </span>
                    </div>
                    <SpeakerEditorModal
                        :open="speakerEditorOpen"
                        :meeting-id="meeting.id"
                        :client-name="meeting.client.name"
                        :people="meeting.client.persons || []"
                        :transcriptions="meeting.transcriptions || []"
                        @close="speakerEditorOpen = false"
                        @seek="onTranscriptionTimestampClick"
                    />
                </section>

                <section class="flex flex-col rounded-lg border border-border bg-ground-raised p-5 xl:col-span-2">
                    <TranscriptionViewer
                        ref="transcriptionViewerRef"
                        :transcriptions="meeting.transcriptions"
                        :current-time="videoCurrentTime"
                        @timestamp-click="onTranscriptionTimestampClick"
                    />
                </section>
            </div>

            <!-- Non-completed states -->
            <div v-else class="rounded-lg border border-border bg-ground-raised p-5">
                <div v-if="meeting.status === 'pending' || meeting.status === 'processing'" class="py-16 text-center">
                    <svg class="mx-auto h-10 w-10 text-ink-tertiary" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                        <path
                            stroke-linecap="round"
                            stroke-linejoin="round"
                            d="M15.75 10.5l4.72-4.72a.75.75 0 011.28.53v11.38a.75.75 0 01-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 002.25-2.25v-9a2.25 2.25 0 00-2.25-2.25h-9A2.25 2.25 0 002.25 7.5v9a2.25 2.25 0 002.25 2.25z"
                        />
                    </svg>
                    <p class="mt-3 text-[13px] text-ink-secondary">
                        {{ meeting.status === 'pending' ? 'Video will be available after processing completes' : 'Processing video…' }}
                    </p>
                </div>

                <div v-else-if="meeting.status === 'completed' && videoUrl" class="space-y-4">
                    <VideoPlayer
                        ref="videoPlayerRef"
                        :video-url="videoUrl"
                        :current-time="videoCurrentTime"
                        @time-update="onVideoTimeUpdate"
                        @duration-change="onVideoDurationChange"
                        @play="onVideoPlay"
                        @pause="onVideoPause"
                        @error="onVideoError"
                    />
                    <div
                        v-if="!meeting.transcriptions || meeting.transcriptions.length === 0"
                        class="py-8 text-center text-[13px] text-ink-secondary"
                    >
                        No transcription available for this meeting.
                    </div>
                </div>

                <div v-else class="py-16 text-center">
                    <svg
                        class="mx-auto h-10 w-10 text-red-500 dark:text-red-400"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="1.5"
                        viewBox="0 0 24 24"
                    >
                        <path
                            stroke-linecap="round"
                            stroke-linejoin="round"
                            d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
                        />
                    </svg>
                    <p class="mt-3 text-[13px] text-ink-secondary">Video not available</p>
                </div>
            </div>

            <!-- Full-width transcript for small screens / no video -->
            <div
                v-if="meeting.status === 'completed' && meeting.transcriptions && meeting.transcriptions.length > 0 && (!videoUrl || !isLargeScreen)"
                class="mt-6 rounded-lg border border-border bg-ground-raised p-5"
            >
                <TranscriptionViewer
                    ref="transcriptionViewerRef"
                    :transcriptions="meeting.transcriptions"
                    :current-time="videoCurrentTime"
                    @timestamp-click="onTranscriptionTimestampClick"
                />
            </div>
        </div>

    </AppLayout>
</template>

<script setup lang="ts">
import AppLayout from '@/lib/AppLayout.vue';
import { formatBrowserDateTime } from '@/lib/browserDateTime';
import MeetingStatusBadge from '@/lib/MeetingStatusBadge.vue';
import SpeakerEditorModal from '@/lib/SpeakerEditorModal.vue';
import TranscriptionViewer from '@/lib/TranscriptionViewer.vue';
import VideoPlayer from '@/lib/VideoPlayer.vue';
import { Head, Link } from '@inertiajs/vue3';
import { computed, onMounted, onUnmounted, ref } from 'vue';

interface Person {
    id: number;
    name: string;
    email: string | null;
}

interface Client {
    id: number;
    name: string;
    persons?: Person[];
}

interface Transcription {
    id: number;
    detected_speaker: string | null;
    person_id: number | null;
    speaker: string | null;
    text: string;
    start_time: number;
    end_time: number;
    confidence: number;
}

interface Meeting {
    id: number;
    title: string;
    client: Client;
    status: 'pending' | 'processing' | 'completed' | 'failed';
    meeting_at: string | null;
    uploaded_at: string | null;
    duration?: number;
    language: 'ro' | 'en';
    estimated_processing_time?: number;
    queue_progress?: number;
    processing_progress?: number;
    formatted_estimated_processing_time?: string;
    formatted_elapsed_time?: string;
    formatted_estimated_remaining_time?: string;
    transcriptions?: Transcription[];
}

interface Props {
    meeting: Meeting;
    videoUrl: string | null;
}

const props = defineProps<Props>();

const speakerEditorOpen = ref(false);
const videoPlayerRef = ref<InstanceType<typeof VideoPlayer> | null>(null);
const transcriptionViewerRef = ref<InstanceType<typeof TranscriptionViewer> | null>(null);

const videoCurrentTime = ref(0);
const videoDuration = ref(0);
const isVideoPlaying = ref(false);
const pendingSeekTime = ref<number | null>(null);
const timestampsReady = ref(false);

const formatDateTime = (value: string | null) => formatBrowserDateTime(value, timestampsReady.value);

const isLargeScreen = computed(() => {
    if (typeof window === 'undefined') return true;
    return window.innerWidth >= 1280;
});

let statusInterval: ReturnType<typeof setInterval> | null = null;

const onVideoTimeUpdate = (time: number) => {
    videoCurrentTime.value = time;
};

const onVideoDurationChange = (duration: number) => {
    videoDuration.value = duration;
    if (pendingSeekTime.value !== null) {
        onTranscriptionTimestampClick(pendingSeekTime.value);
        pendingSeekTime.value = null;
    }
};

const onVideoPlay = () => {
    isVideoPlaying.value = true;
};

const onVideoPause = () => {
    isVideoPlaying.value = false;
};

const onVideoError = (error: Event) => {
    console.error('Video playback error:', error);
};

const onTranscriptionTimestampClick = (time: number | string) => {
    const timestamp = Number(time);
    if (!Number.isFinite(timestamp)) return;

    if (videoPlayerRef.value) {
        videoPlayerRef.value.seekTo(timestamp);
    }
    transcriptionViewerRef.value?.seekTo(timestamp);
    videoCurrentTime.value = timestamp;
};

const goToPrevious = () => {
    const time = transcriptionViewerRef.value?.scrollToPrevious();
    if (time !== null && time !== undefined) {
        onTranscriptionTimestampClick(time);
    }
};

const goToNext = () => {
    const time = transcriptionViewerRef.value?.scrollToNext();
    if (time !== null && time !== undefined) {
        onTranscriptionTimestampClick(time);
    }
};

const pollStatus = async () => {
    if (props.meeting.status === 'pending' || props.meeting.status === 'processing') {
        try {
            const response = await fetch(`/meetings/${props.meeting.id}/status`);
            const data = await response.json();
            if (data.data.status !== props.meeting.status) {
                window.location.reload();
            }
        } catch (error) {
            console.error('Failed to fetch meeting status:', error);
        }
    }
};

const applyDeepLinkTimestamp = () => {
    try {
        const t = new URLSearchParams(window.location.search).get('t');
        if (t !== null) {
            const seconds = parseFloat(t);
            if (Number.isFinite(seconds) && seconds >= 0) {
                pendingSeekTime.value = seconds;
                onTranscriptionTimestampClick(seconds);
            }
        }
    } catch {
        // ignore
    }
};

onMounted(() => {
    timestampsReady.value = true;

    if (props.meeting.status === 'pending' || props.meeting.status === 'processing') {
        statusInterval = setInterval(pollStatus, 2000);
        pollStatus();
    }

    if (props.meeting.status === 'completed') {
        applyDeepLinkTimestamp();
    }
});

onUnmounted(() => {
    if (statusInterval) {
        clearInterval(statusInterval);
    }
});
</script>
