<template>
    <AppLayout>
        <div class="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
            <!-- Processing Status -->
            <div v-if="meeting.status === 'pending'" class="mb-6 rounded-lg border border-blue-200 bg-blue-50 p-6">
                <div class="flex items-center justify-between">
                    <div>
                        <h3 class="text-lg font-semibold text-blue-900">Meeting Queued for Processing</h3>
                        <p class="text-sm text-blue-700">
                            Estimated processing time: {{ meeting.formatted_estimated_processing_time || 'Calculating...' }}
                        </p>
                    </div>
                    <div class="h-8 w-8 animate-spin rounded-full border-b-2 border-blue-600"></div>
                </div>
            </div>

            <div v-else-if="meeting.status === 'processing'" class="mb-6 rounded-lg border border-yellow-200 bg-yellow-50 p-6">
                <div class="flex items-center justify-between">
                    <div>
                        <h3 class="text-lg font-semibold text-yellow-900">Processing Meeting</h3>
                        <p class="text-sm text-yellow-700">
                            Elapsed: {{ meeting.formatted_elapsed_time || '0:00' }} | Remaining:
                            {{ meeting.formatted_estimated_remaining_time || 'Calculating...' }}
                        </p>
                    </div>
                    <div class="h-8 w-8 animate-spin rounded-full border-b-2 border-yellow-600"></div>
                </div>
            </div>

            <!-- Video Player and Transcription Layout -->
            <div
                v-if="meeting.status === 'completed' && videoUrl && meeting.transcriptions && meeting.transcriptions.length > 0"
                class="grid grid-cols-1 gap-6 lg:grid-cols-2"
            >
                <!-- Video Player Section -->
                <div class="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
                    <!-- Header inside video section -->
                    <div class="mb-6">
                        <Link :href="route('meetings.index')" class="text-sm font-medium text-blue-600 hover:text-blue-700">
                            ← Back to Meetings
                        </Link>
                        <div class="mt-3">
                            <h1 class="text-2xl font-bold text-gray-900">{{ meeting.title }}</h1>
                            <div class="mt-2 flex items-center space-x-4">
                                <p class="text-sm text-gray-600">Client: {{ meeting.client.name }}</p>
                                <MeetingStatusBadge :status="meeting.status" :meeting="meeting" />
                            </div>
                        </div>
                    </div>

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

                    <!-- Navigation controls -->
                    <div class="mt-4 flex items-center justify-between text-sm text-gray-600">
                        <div>
                            <button
                                @click="goToPrevious"
                                :disabled="!transcriptionViewerRef?.hasPrevious"
                                class="rounded bg-gray-200 px-3 py-1 text-gray-700 hover:bg-gray-300 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                                ← Previous
                            </button>
                            <button
                                @click="goToNext"
                                :disabled="!transcriptionViewerRef?.hasNext"
                                class="ml-2 rounded bg-gray-200 px-3 py-1 text-gray-700 hover:bg-gray-300 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                                Next →
                            </button>
                        </div>

                        <div v-if="transcriptionViewerRef && transcriptionViewerRef.currentSegmentIndex >= 0">
                            {{ transcriptionViewerRef.currentSegmentIndex + 1 }} of {{ transcriptionViewerRef.filteredTranscriptions.length }}
                        </div>
                    </div>
                </div>

                <!-- Transcription Section -->
                <div class="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
                    <TranscriptionViewer
                        ref="transcriptionViewerRef"
                        :transcriptions="meeting.transcriptions"
                        :current-time="videoCurrentTime"
                        @timestamp-click="onTranscriptionTimestampClick"
                    />
                </div>
            </div>

            <!-- Single Column Layout for Non-Completed Meetings -->
            <div v-else class="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
                <!-- Header inside video section -->
                <div class="mb-6">
                    <Link :href="route('meetings.index')" class="text-sm font-medium text-blue-600 hover:text-blue-700"> ← Back to Meetings </Link>
                    <div class="mt-3">
                        <h1 class="text-2xl font-bold text-gray-900">{{ meeting.title }}</h1>
                        <div class="mt-2 flex items-center space-x-4">
                            <p class="text-sm text-gray-600">Client: {{ meeting.client.name }}</p>
                            <MeetingStatusBadge :status="meeting.status" :meeting="meeting" />
                        </div>
                    </div>
                </div>

                <div v-if="meeting.status === 'pending'" class="py-12 text-center">
                    <div class="mb-4 text-gray-400">
                        <svg class="mx-auto h-16 w-16" fill="currentColor" viewBox="0 0 20 20">
                            <path
                                d="M2 6a2 2 0 012-2h6l2 2h6a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6zM5 8a1 1 0 011-1h1a1 1 0 010 2H6a1 1 0 01-1-1zm6 1a1 1 0 100 2h3a1 1 0 100-2H11z"
                            />
                        </svg>
                    </div>
                    <p class="text-gray-600">Video will be available after processing completes</p>
                </div>

                <div v-else-if="meeting.status === 'processing'" class="py-12 text-center">
                    <div class="mb-4 text-gray-400">
                        <svg class="mx-auto h-16 w-16 animate-pulse" fill="currentColor" viewBox="0 0 20 20">
                            <path
                                d="M2 6a2 2 0 012-2h6l2 2h6a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6zM5 8a1 1 0 011-1h1a1 1 0 010 2H6a1 1 0 01-1-1zm6 1a1 1 0 100 2h3a1 1 0 100-2H11z"
                            />
                        </svg>
                    </div>
                    <p class="text-gray-600">Processing video...</p>
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

                    <!-- Navigation controls for single column layout -->
                    <div
                        v-if="meeting.transcriptions && meeting.transcriptions.length > 0"
                        class="flex items-center justify-between text-sm text-gray-600"
                    >
                        <div>
                            <button
                                @click="goToPrevious"
                                :disabled="!transcriptionViewerRef?.hasPrevious"
                                class="rounded bg-gray-200 px-3 py-1 text-gray-700 hover:bg-gray-300 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                                ← Previous
                            </button>
                            <button
                                @click="goToNext"
                                :disabled="!transcriptionViewerRef?.hasNext"
                                class="ml-2 rounded bg-gray-200 px-3 py-1 text-gray-700 hover:bg-gray-300 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                                Next →
                            </button>
                        </div>

                        <div v-if="transcriptionViewerRef && transcriptionViewerRef.currentSegmentIndex >= 0">
                            {{ transcriptionViewerRef.currentSegmentIndex + 1 }} of {{ transcriptionViewerRef.filteredTranscriptions.length }}
                        </div>
                    </div>

                    <!-- Show message if no transcriptions -->
                    <div v-if="!meeting.transcriptions || meeting.transcriptions.length === 0" class="py-8 text-center text-gray-500">
                        <p>No transcription available for this meeting.</p>
                    </div>
                </div>

                <div v-else class="py-12 text-center">
                    <div class="mb-4 text-red-400">
                        <svg class="mx-auto h-16 w-16" fill="currentColor" viewBox="0 0 20 20">
                            <path
                                fill-rule="evenodd"
                                d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
                                clip-rule="evenodd"
                            />
                        </svg>
                    </div>
                    <p class="text-gray-600">Video not available</p>
                </div>
            </div>

            <!-- Full-width Transcription for Single Column Layout -->
            <div
                v-if="meeting.status === 'completed' && meeting.transcriptions && meeting.transcriptions.length > 0 && (!videoUrl || !isLargeScreen)"
                class="mt-6 rounded-lg border border-gray-200 bg-white p-6 shadow-sm"
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
import MeetingStatusBadge from '@/lib/MeetingStatusBadge.vue';
import TranscriptionViewer from '@/lib/TranscriptionViewer.vue';
import VideoPlayer from '@/lib/VideoPlayer.vue';
import { Link } from '@inertiajs/vue3';
import { computed, onMounted, onUnmounted, ref } from 'vue';

interface Client {
    id: number;
    name: string;
}

interface Transcription {
    id: number;
    speaker: string;
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
    uploaded_at: string;
    duration?: number;
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

// Video player ref for controlling playback
const videoPlayerRef = ref<InstanceType<typeof VideoPlayer> | null>(null);
const transcriptionViewerRef = ref<InstanceType<typeof TranscriptionViewer> | null>(null);

// Video synchronization state
const videoCurrentTime = ref(0);
const videoDuration = ref(0);
const isVideoPlaying = ref(false);

// Screen size detection for layout
const isLargeScreen = computed(() => {
    if (typeof window === 'undefined') return true;
    return window.innerWidth >= 1024; // lg breakpoint
});

let statusInterval: ReturnType<typeof setInterval> | null = null;

// Video event handlers
const onVideoTimeUpdate = (time: number) => {
    videoCurrentTime.value = time;
};

const onVideoDurationChange = (duration: number) => {
    videoDuration.value = duration;
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

// Transcription event handlers
const onTranscriptionTimestampClick = (time: number) => {
    videoCurrentTime.value = time;
    if (videoPlayerRef.value) {
        videoPlayerRef.value.seekTo(time);
    }
};

// Navigation functions for transcription
const goToPrevious = () => {
    if (transcriptionViewerRef.value) {
        transcriptionViewerRef.value.scrollToPrevious();
    }
};

const goToNext = () => {
    if (transcriptionViewerRef.value) {
        transcriptionViewerRef.value.scrollToNext();
    }
};

// Poll for status updates when meeting is pending or processing
const pollStatus = async () => {
    if (props.meeting.status === 'pending' || props.meeting.status === 'processing') {
        try {
            const response = await fetch(`/meetings/${props.meeting.id}/status`);
            const data = await response.json();

            // Reload page if status changed to completed or failed
            if (data.data.status !== props.meeting.status) {
                console.log('Meeting status changed:', data.data.status, props.meeting.status);
                window.location.reload();
            }
        } catch (error) {
            console.error('Failed to fetch meeting status:', error);
        }
    }
};

onMounted(() => {
    // Start polling for status updates every 2 seconds
    if (props.meeting.status === 'pending' || props.meeting.status === 'processing') {
        statusInterval = setInterval(pollStatus, 2000);
        // Initial poll
        pollStatus();
    }
});

onUnmounted(() => {
    if (statusInterval) {
        clearInterval(statusInterval);
    }
});
</script>
