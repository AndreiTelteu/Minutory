<template>
    <div ref="playerContainer" class="video-player-container" @mousemove="revealControls" @mouseleave="scheduleControlsHide">
        <div class="video-stage relative overflow-hidden rounded-lg bg-black">
            <video
                ref="videoElement"
                class="block h-auto w-full"
                :src="videoUrl"
                preload="metadata"
                @loadedmetadata="onVideoLoaded"
                @seeking="onSeeking"
                @seeked="onSeeked"
                @waiting="onWaiting"
                @canplay="onCanPlay"
                @timeupdate="onTimeUpdate"
                @durationchange="onDurationChange"
                @play="onPlay"
                @pause="onPause"
                @ended="onEnded"
                @volumechange="onVolumeChange"
                @ratechange="onRateChange"
                @error="onError"
            >
                Your browser does not support the video tag.
            </video>

            <button
                v-if="!isLoading && !hasError"
                type="button"
                class="absolute inset-0 flex items-center justify-center bg-black/10 transition-opacity hover:bg-black/20 focus-visible:outline-2 focus-visible:outline-offset-[-4px] focus-visible:outline-white"
                :aria-label="isPlaying ? 'Pause video' : 'Play video'"
                @click="togglePlay"
            >
                <span
                    class="flex h-16 w-16 items-center justify-center rounded-full bg-black/60 text-white shadow-xl ring-1 ring-white/30 backdrop-blur-sm transition-transform duration-200"
                    :class="isPlaying ? 'scale-75 opacity-0' : 'scale-100 opacity-100 hover:scale-110'"
                >
                    <svg class="ml-1 h-7 w-7" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                        <path d="M8 5.14v13.72L19 12 8 5.14Z" />
                    </svg>
                </span>
            </button>

            <div v-if="isLoading || isBuffering" class="absolute inset-0 flex items-center justify-center bg-black/50">
                <div class="text-center text-white">
                    <div class="mx-auto mb-2 h-8 w-8 animate-spin rounded-full border-2 border-white/30 border-t-white"></div>
                    <p class="text-sm">{{ isLoading ? 'Loading video...' : 'Buffering...' }}</p>
                </div>
            </div>

            <div v-if="hasError" class="absolute inset-0 flex items-center justify-center bg-black/75 p-5">
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
                    <button
                        type="button"
                        @click="retryLoad"
                        class="mt-4 rounded-md bg-accent-solid px-3 py-1.5 text-[13px] font-medium text-white transition-colors hover:bg-accent-solid-hover"
                    >
                        Retry
                    </button>
                </div>
            </div>
        </div>

        <div
            v-if="duration > 0 && !hasError"
            class="video-controls mt-3 rounded-lg border border-border bg-ground-subtle p-3 sm:p-4"
            :class="{ 'video-controls--fullscreen': isFullscreen, 'video-controls--hidden': isFullscreen && !controlsVisible }"
            @mouseenter="revealControls"
            @focusin="revealControls"
        >
            <div class="flex items-center gap-2">
                <span class="tnum w-10 shrink-0 text-right text-[11px] text-ink-tertiary">{{ formatTime(localCurrentTime) }}</span>
                <input
                    :value="localCurrentTime"
                    type="range"
                    min="0"
                    :max="duration"
                    step="0.01"
                    aria-label="Video progress"
                    class="min-w-0 flex-1 accent-accent"
                    @input="onProgressInput"
                    @change="onProgressInput"
                    @pointerup="blurAfterProgressSeek"
                />
                <span class="tnum w-10 shrink-0 text-[11px] text-ink-tertiary">{{ formatTime(duration) }}</span>
            </div>

            <div class="mt-3 flex flex-wrap items-center justify-between gap-3">
                <div class="flex items-center gap-1.5">
                    <button type="button" class="video-control-primary" :aria-label="isPlaying ? 'Pause video' : 'Play video'" @click="togglePlay">
                        <svg v-if="isPlaying" class="h-5 w-5" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                            <path d="M6 5h4v14H6zm8 0h4v14h-4z" />
                        </svg>
                        <svg v-else class="ml-0.5 h-5 w-5" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                            <path d="M8 5.14v13.72L19 12 8 5.14Z" />
                        </svg>
                    </button>
                    <button
                        type="button"
                        class="video-control-button"
                        aria-label="Back 10 seconds"
                        title="Back 10 seconds (Left arrow)"
                        @click="skip(-10)"
                    >
                        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24" aria-hidden="true">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M9 14.5 4.5 10 9 5.5M4.5 10H16a3.5 3.5 0 0 1 3.5 3.5V15" /></svg
                        ><span>10</span>
                    </button>
                    <button
                        type="button"
                        class="video-control-button"
                        aria-label="Forward 10 seconds"
                        title="Forward 10 seconds (Right arrow)"
                        @click="skip(10)"
                    >
                        <span>10</span
                        ><svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24" aria-hidden="true">
                            <path stroke-linecap="round" stroke-linejoin="round" d="m15 14.5 4.5-4.5L15 5.5m4.5 4.5H8A3.5 3.5 0 0 0 4.5 13.5V15" />
                        </svg>
                    </button>

                    <span class="mx-1 hidden h-5 w-px bg-border sm:block" />
                    <button
                        type="button"
                        class="video-control-button"
                        :aria-label="isMuted ? 'Unmute video' : 'Mute video'"
                        title="Mute (M)"
                        @click="toggleMute"
                    >
                        <svg
                            v-if="isMuted || volume === 0"
                            class="h-4 w-4"
                            fill="none"
                            stroke="currentColor"
                            stroke-width="1.8"
                            viewBox="0 0 24 24"
                            aria-hidden="true"
                        >
                            <path stroke-linecap="round" stroke-linejoin="round" d="M11 5 6 9H3v6h3l5 4V5Zm4 4 5 5m0-5-5 5" />
                        </svg>
                        <svg v-else class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24" aria-hidden="true">
                            <path
                                stroke-linecap="round"
                                stroke-linejoin="round"
                                d="M11 5 6 9H3v6h3l5 4V5Zm4.5 3a4 4 0 0 1 0 4m2.5-6.5a7 7 0 0 1 0 9"
                            />
                        </svg>
                    </button>
                    <input
                        v-model.number="volume"
                        type="range"
                        min="0"
                        max="1"
                        step="0.05"
                        aria-label="Volume"
                        class="w-20 accent-accent sm:w-24"
                        @input="setVolume(volume)"
                        @pointerup="blurAfterVolumeAdjust"
                    />
                </div>

                <div class="flex items-center gap-1.5">
                    <button type="button" class="video-control-button" aria-label="Previous playback speed" @click="adjustPlaybackRate(-1)">−</button>
                    <span class="tnum min-w-10 text-center text-[12px] font-semibold text-ink">{{ formatPlaybackRate(playbackRate) }}</span>
                    <button type="button" class="video-control-button" aria-label="Next playback speed" @click="adjustPlaybackRate(1)">+</button>
                    <span class="mx-1 hidden h-5 w-px bg-border sm:block" />
                    <a :href="videoUrl" download class="video-control-button" aria-label="Download video" title="Download video">
                        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24" aria-hidden="true">
                            <path
                                stroke-linecap="round"
                                stroke-linejoin="round"
                                d="M12 3v12m0 0 4-4m-4 4-4-4m-4 4v3.75A2.25 2.25 0 0 0 6.25 21h11.5A2.25 2.25 0 0 0 20 18.75V15"
                            />
                        </svg>
                    </a>
                    <button type="button" class="video-control-button" aria-label="Fullscreen" title="Fullscreen (F)" @click="toggleFullscreen">
                        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24" aria-hidden="true">
                            <path
                                stroke-linecap="round"
                                stroke-linejoin="round"
                                d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"
                            />
                        </svg>
                    </button>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue';

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

const props = withDefaults(defineProps<Props>(), { currentTime: 0 });
const emit = defineEmits<Emits>();
const videoElement = ref<HTMLVideoElement | null>(null);
const playerContainer = ref<HTMLElement | null>(null);
const isLoading = ref(true);
const isBuffering = ref(false);
const hasError = ref(false);
const duration = ref(0);
const localCurrentTime = ref(0);
const isPlaying = ref(false);
const volume = ref(1);
const isMuted = ref(false);
const playbackRate = ref(1);
const isFullscreen = ref(false);
const controlsVisible = ref(true);
const playbackRates = Array.from({ length: 11 }, (_, index) => 0.5 + index * 0.25);
let controlsHideTimer: ReturnType<typeof setTimeout> | null = null;

const onVideoLoaded = () => {
    if (!videoElement.value) return;
    duration.value = Number.isFinite(videoElement.value.duration) ? videoElement.value.duration : 0;
    localCurrentTime.value = videoElement.value.currentTime;
    volume.value = videoElement.value.volume;
    isMuted.value = videoElement.value.muted;
    playbackRate.value = videoElement.value.playbackRate;
    isLoading.value = false;
    isBuffering.value = false;
    hasError.value = false;
    emit('durationChange', duration.value);
};
const onSeeking = () => {
    isBuffering.value = true;
};
const onSeeked = () => {
    isBuffering.value = false;
};
const onWaiting = () => {
    isBuffering.value = true;
};
const onCanPlay = () => {
    isBuffering.value = false;
};
const onDurationChange = () => {
    if (videoElement.value) duration.value = videoElement.value.duration || 0;
};
const onTimeUpdate = () => {
    if (videoElement.value) {
        localCurrentTime.value = videoElement.value.currentTime;
        emit('timeUpdate', localCurrentTime.value);
    }
};
const onPlay = () => {
    isPlaying.value = true;
    revealControls();
    emit('play');
};
const onPause = () => {
    isPlaying.value = false;
    revealControls();
    emit('pause');
};
const onEnded = () => {
    isPlaying.value = false;
    revealControls();
    emit('ended');
};
const onVolumeChange = () => {
    if (videoElement.value) {
        volume.value = videoElement.value.volume;
        isMuted.value = videoElement.value.muted;
    }
};
const onRateChange = () => {
    if (videoElement.value) playbackRate.value = videoElement.value.playbackRate;
};
const onError = (error: Event) => {
    isLoading.value = false;
    isBuffering.value = false;
    hasError.value = true;
    emit('error', error);
};
const seekTo = (time: number) => {
    if (!videoElement.value || !Number.isFinite(time)) return;
    const targetTime = Math.min(Math.max(time, 0), duration.value || Number.POSITIVE_INFINITY);
    isBuffering.value = true;
    videoElement.value.currentTime = targetTime;
    localCurrentTime.value = targetTime;
    emit('timeUpdate', targetTime);
};
const onProgressInput = (event: Event) => {
    const input = event.target as HTMLInputElement;
    seekTo(Number(input.value));
    revealControls();
};
const blurAfterProgressSeek = (event: PointerEvent) => {
    (event.currentTarget as HTMLInputElement).blur();
};
const blurAfterVolumeAdjust = (event: PointerEvent) => {
    (event.currentTarget as HTMLInputElement).blur();
};
const skip = (seconds: number) => seekTo((videoElement.value?.currentTime ?? 0) + seconds);
const play = async () => {
    await videoElement.value?.play();
};
const pause = () => videoElement.value?.pause();
const togglePlay = () => (isPlaying.value ? pause() : play());
const setVolume = (value: number) => {
    if (videoElement.value) {
        videoElement.value.volume = value;
        videoElement.value.muted = value === 0;
    }
};
const toggleMute = () => {
    if (videoElement.value) videoElement.value.muted = !videoElement.value.muted;
};
const adjustPlaybackRate = (direction: -1 | 1) => {
    const currentIndex = playbackRates.findIndex((rate) => Math.abs(rate - playbackRate.value) < 0.01);
    const baseIndex =
        currentIndex >= 0
            ? currentIndex
            : playbackRates.reduce(
                  (closest, rate, index) =>
                      Math.abs(rate - playbackRate.value) < Math.abs(playbackRates[closest] - playbackRate.value) ? index : closest,
                  0,
              );
    const rate = playbackRates[Math.min(Math.max(baseIndex + direction, 0), playbackRates.length - 1)];
    if (videoElement.value) videoElement.value.playbackRate = rate;
};
const toggleFullscreen = async () => {
    if (!playerContainer.value) return;
    if (document.fullscreenElement) await document.exitFullscreen();
    else await playerContainer.value.requestFullscreen();
};
const clearControlsHideTimer = () => {
    if (controlsHideTimer) clearTimeout(controlsHideTimer);
    controlsHideTimer = null;
};
const scheduleControlsHide = () => {
    clearControlsHideTimer();
    if (!isFullscreen.value || !isPlaying.value) return;
    controlsHideTimer = setTimeout(() => {
        controlsVisible.value = false;
    }, 2200);
};
const revealControls = () => {
    controlsVisible.value = true;
    scheduleControlsHide();
};
const onFullscreenChange = () => {
    isFullscreen.value = document.fullscreenElement === playerContainer.value;
    controlsVisible.value = true;
    if (isFullscreen.value) scheduleControlsHide();
    else clearControlsHideTimer();
};
const retryLoad = () => {
    if (videoElement.value) {
        hasError.value = false;
        isLoading.value = true;
        videoElement.value.load();
    }
};
const formatTime = (seconds: number) => {
    const total = Math.floor(Number.isFinite(seconds) ? seconds : 0);
    const hours = Math.floor(total / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    const remaining = total % 60;
    return hours > 0
        ? `${hours}:${minutes.toString().padStart(2, '0')}:${remaining.toString().padStart(2, '0')}`
        : `${minutes}:${remaining.toString().padStart(2, '0')}`;
};
const formatPlaybackRate = (rate: number) => `${Number(rate.toFixed(2))}x`;
const isTypingTarget = (target: EventTarget | null) => {
    if (!(target instanceof HTMLElement)) return false;
    return (
        target.isContentEditable ||
        ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName) ||
        Boolean(target.closest('[contenteditable="true"], [role="textbox"]'))
    );
};
const onGlobalKeydown = (event: KeyboardEvent) => {
    if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.altKey || isTypingTarget(event.target)) return;
    switch (event.key.toLowerCase()) {
        case ' ':
            event.preventDefault();
            togglePlay();
            break;
        case 'arrowleft':
            event.preventDefault();
            skip(-10);
            break;
        case 'arrowright':
            event.preventDefault();
            skip(10);
            break;
        case 'arrowup':
            event.preventDefault();
            setVolume(Math.min((videoElement.value?.volume ?? volume.value) + 0.05, 1));
            break;
        case 'arrowdown':
            event.preventDefault();
            setVolume(Math.max((videoElement.value?.volume ?? volume.value) - 0.05, 0));
            break;
        case 'm':
            event.preventDefault();
            toggleMute();
            break;
        case 'f':
            event.preventDefault();
            void toggleFullscreen();
            break;
    }
};

defineExpose({ seekTo, play, pause, skip, togglePlay, videoElement });
onMounted(() => {
    document.addEventListener('keydown', onGlobalKeydown);
    document.addEventListener('fullscreenchange', onFullscreenChange);
});
onBeforeUnmount(() => {
    document.removeEventListener('keydown', onGlobalKeydown);
    document.removeEventListener('fullscreenchange', onFullscreenChange);
    clearControlsHideTimer();
});
</script>

<style scoped>
.video-player-container:fullscreen {
    display: flex;
    align-items: center;
    justify-content: center;
    background: black;
}
.video-player-container:fullscreen .video-stage {
    width: 100%;
    max-height: 100vh;
    border-radius: 0;
}
.video-player-container:fullscreen video {
    max-height: 100vh;
    margin: auto;
    object-fit: contain;
}
.video-controls--fullscreen {
    position: fixed;
    bottom: 2rem;
    left: 50%;
    z-index: 20;
    width: min(56rem, calc(100vw - 2rem));
    margin: 0;
    transform: translateX(-50%);
    border-color: rgb(255 255 255 / 0.18);
    background: rgb(0 0 0 / 0.62);
    color: white;
    backdrop-filter: blur(12px);
    transition:
        opacity 250ms ease,
        transform 250ms ease;
}
.video-controls--fullscreen.video-controls--hidden {
    pointer-events: none;
    opacity: 0;
    transform: translate(-50%, 0.75rem);
}
.video-controls--fullscreen .video-control-button {
    border-color: rgb(255 255 255 / 0.28);
    color: rgb(255 255 255 / 0.8);
}
.video-controls--fullscreen .video-control-button:hover {
    background: rgb(255 255 255 / 0.16);
    color: white;
}
.video-controls--fullscreen :is(.text-ink, .text-ink-secondary, .text-ink-tertiary) {
    color: rgb(255 255 255 / 0.75);
}
.video-control-button {
    display: inline-flex;
    height: 2rem;
    align-items: center;
    justify-content: center;
    gap: 0.25rem;
    border: 1px solid var(--color-border-strong);
    border-radius: 0.375rem;
    padding: 0 0.5rem;
    color: var(--color-ink-secondary);
    font-size: 0.75rem;
    font-weight: 500;
    transition:
        color 150ms,
        background-color 150ms;
}
.video-control-button:hover {
    background: var(--color-ground-raised);
    color: var(--color-ink);
}
.video-control-primary {
    display: inline-flex;
    height: 2.25rem;
    width: 2.25rem;
    align-items: center;
    justify-content: center;
    border-radius: 9999px;
    background: var(--color-accent-solid);
    color: white;
    box-shadow: 0 1px 2px rgb(0 0 0 / 0.1);
    transition:
        transform 150ms,
        background-color 150ms;
}
.video-control-primary:hover {
    transform: scale(1.05);
    background: var(--color-accent-solid-hover);
}
.video-control-button:focus-visible,
.video-control-primary:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
}
</style>
