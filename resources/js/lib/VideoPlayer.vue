<template>
    <div class="video-player-container">
        <div class="relative overflow-hidden rounded-lg bg-black">
            <video
                ref="videoElement"
                class="h-auto w-full"
                :src="videoUrl"
                @loadedmetadata="onVideoLoaded"
                @timeupdate="onTimeUpdate"
                @play="onPlay"
                @pause="onPause"
                @ended="onEnded"
                @error="onError"
                controls
            >
                Your browser does not support the video tag.
            </video>

            <!-- Loading overlay -->
            <div v-if="isLoading" class="bg-opacity-50 absolute inset-0 flex items-center justify-center bg-black">
                <div class="text-center text-white">
                    <div class="mx-auto mb-2 h-8 w-8 animate-spin rounded-full border-b-2 border-white"></div>
                    <p class="text-sm">Loading video...</p>
                </div>
            </div>

            <!-- Error overlay -->
            <div v-if="hasError" class="bg-opacity-75 absolute inset-0 flex items-center justify-center bg-black">
                <div class="text-center text-white">
                    <svg class="mx-auto mb-3 h-10 w-10 text-red-400" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                        <path
                            stroke-linecap="round"
                            stroke-linejoin="round"
                            d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
                        />
                    </svg>
                    <p class="mb-1 text-[14px] font-medium">Video error</p>
                    <p class="text-[13px] text-gray-300">Unable to load video. Please try refreshing the page.</p>
                    <button @click="retryLoad" class="mt-4 rounded-md bg-accent-solid px-3 py-1.5 text-[13px] font-medium text-white transition-colors hover:bg-accent-solid-hover">
                        Retry
                    </button>
                </div>
            </div>
        </div>

        <!-- Video controls info -->
        <div v-if="duration > 0" class="tnum mt-2 flex justify-between text-[12px] text-ink-secondary">
            <span>{{ formatTime(currentTime) }} / {{ formatTime(duration) }}</span>
            <span v-if="isPlaying" class="text-green-600 dark:text-green-400">Playing</span>
            <span v-else class="text-ink-tertiary">Paused</span>
        </div>
    </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue';

interface Props {
    videoUrl: string;
    currentTime?: number;
}

interface Emits {
    (e: 'timeUpdate', time: number): void;
    (e: 'durationChange', duration: number): void;
    (e: 'play'): void;
    (e: 'pause'): void;
    (e: 'ended'): void;
    (e: 'error', error: Event): void;
}

const props = withDefaults(defineProps<Props>(), {
    currentTime: 0,
});

const emit = defineEmits<Emits>();

const videoElement = ref<HTMLVideoElement | null>(null);
const isLoading = ref(true);
const hasError = ref(false);
const duration = ref(0);
const localCurrentTime = ref(0);
const isPlaying = ref(false);

// Watch for external currentTime changes (from transcription clicks)
watch(
    () => props.currentTime,
    (newTime) => {
        if (videoElement.value && Math.abs(videoElement.value.currentTime - newTime) > 1) {
            videoElement.value.currentTime = newTime;
        }
    },
);

const onVideoLoaded = () => {
    if (videoElement.value) {
        duration.value = videoElement.value.duration;
        isLoading.value = false;
        hasError.value = false;
        emit('durationChange', duration.value);
    }
};

const onTimeUpdate = () => {
    if (videoElement.value) {
        localCurrentTime.value = videoElement.value.currentTime;
        emit('timeUpdate', localCurrentTime.value);
    }
};

const onPlay = () => {
    isPlaying.value = true;
    emit('play');
};

const onPause = () => {
    isPlaying.value = false;
    emit('pause');
};

const onEnded = () => {
    isPlaying.value = false;
    emit('ended');
};

const onError = (error: Event) => {
    isLoading.value = false;
    hasError.value = true;

    // Log detailed error information
    const videoError = videoElement.value?.error;
    if (videoError) {
        console.error('Video error:', {
            code: videoError.code,
            message: videoError.message,
            url: props.videoUrl,
        });

        // Show user-friendly error toast
        if (window.toast) {
            let errorMessage = 'Unable to load video';
            let suggestions = ['Try refreshing the page', 'Check your internet connection'];

            switch (videoError.code) {
                case MediaError.MEDIA_ERR_ABORTED:
                    errorMessage = 'Video loading was aborted';
                    suggestions = ['Try refreshing the page', 'Check if the video file exists'];
                    break;
                case MediaError.MEDIA_ERR_NETWORK:
                    errorMessage = 'Network error while loading video';
                    suggestions = ['Check your internet connection', 'Try again in a few moments'];
                    break;
                case MediaError.MEDIA_ERR_DECODE:
                    errorMessage = 'Video format not supported or corrupted';
                    suggestions = ['The video file may be corrupted', 'Contact support for assistance'];
                    break;
                case MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED:
                    errorMessage = 'Video format not supported';
                    suggestions = ['The video format is not supported by your browser', 'Try a different browser'];
                    break;
            }

            window.toast.error(errorMessage, suggestions.join(' • '), {
                actions: [
                    {
                        label: 'Retry',
                        handler: retryLoad,
                        primary: true,
                    },
                ],
            });
        }
    }

    emit('error', error);
};

const retryLoad = () => {
    if (videoElement.value) {
        hasError.value = false;
        isLoading.value = true;

        // Clear any existing error state
        videoElement.value.removeAttribute('src');
        videoElement.value.load();

        // Set source again after a brief delay
        setTimeout(() => {
            if (videoElement.value) {
                videoElement.value.src = props.videoUrl;
                videoElement.value.load();
            }
        }, 100);
    }
};

const seekTo = (time: number) => {
    if (videoElement.value) {
        videoElement.value.currentTime = time;
    }
};

const play = () => {
    if (videoElement.value) {
        videoElement.value.play();
    }
};

const pause = () => {
    if (videoElement.value) {
        videoElement.value.pause();
    }
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

// Expose methods for parent component
defineExpose({
    seekTo,
    play,
    pause,
    videoElement,
});

onMounted(() => {
    if (videoElement.value) {
        // Set initial time if provided
        if (props.currentTime > 0) {
            videoElement.value.currentTime = props.currentTime;
        }
    }
});
</script>
