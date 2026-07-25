<template>
    <AppLayout>
        <div class="mx-auto max-w-2xl px-6 py-8 lg:px-10">
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
                <h1 class="mt-2 text-[20px] font-semibold tracking-tight">Upload meeting</h1>
                <p class="mt-0.5 text-[13px] text-ink-secondary">Upload a video to transcribe and add to your archive.</p>
            </div>

            <form @submit.prevent="submit" enctype="multipart/form-data" class="space-y-5 rounded-lg border border-border bg-ground-raised p-6">
                <!-- Title -->
                <div>
                    <label for="title" class="mb-1.5 block text-[13px] font-medium">Title</label>
                    <input
                        id="title"
                        :value="suggestionState.title.value"
                        @input="handleTitleInput"
                        type="text"
                        required
                        placeholder="e.g. Q3 planning review"
                        class="w-full rounded-md border bg-ground-raised px-3 py-2 text-[13px] text-ink placeholder:text-ink-tertiary focus:ring-2 focus:outline-none"
                        :class="
                            errors.title ? 'border-red-400 focus:ring-red-400/30' : 'border-border-strong focus:border-accent focus:ring-accent/30'
                        "
                    />
                    <p v-if="errors.title" class="mt-1 text-[12px] text-red-600 dark:text-red-400">{{ errors.title }}</p>
                </div>

                <!-- Meeting date and time -->
                <div>
                    <label for="meeting_at" class="mb-1.5 block text-[13px] font-medium">
                        Meeting date and time <span class="font-normal text-ink-tertiary">(optional)</span>
                    </label>
                    <input
                        id="meeting_at"
                        :value="suggestionState.localDateTime.value"
                        @input="handleMeetingAtInput"
                        type="datetime-local"
                        step="1"
                        class="tnum w-full rounded-md border bg-ground-raised px-3 py-2 text-[13px] text-ink [color-scheme:light] focus:ring-2 focus:outline-none dark:[color-scheme:dark]"
                        :class="
                            errors.meeting_at
                                ? 'border-red-400 focus:ring-red-400/30'
                                : 'border-border-strong focus:border-accent focus:ring-accent/30'
                        "
                    />
                    <p v-if="errors.meeting_at" class="mt-1 text-[12px] text-red-600 dark:text-red-400">{{ errors.meeting_at }}</p>
                    <p v-else class="mt-1 text-[12px] text-ink-tertiary">Suggested from a timestamp at the start of the filename when available.</p>
                </div>

                <!-- Client -->
                <div>
                    <label for="client_id" class="mb-1.5 block text-[13px] font-medium">Client</label>
                    <select
                        id="client_id"
                        v-model="rememberedState.clientId"
                        required
                        class="w-full rounded-md border bg-ground-raised px-3 py-2 text-[13px] text-ink focus:ring-2 focus:outline-none"
                        :class="
                            errors.client_id
                                ? 'border-red-400 focus:ring-red-400/30'
                                : 'border-border-strong focus:border-accent focus:ring-accent/30'
                        "
                    >
                        <option value="">Select a client</option>
                        <option v-for="client in clients" :key="client.id" :value="String(client.id)">{{ client.name }}</option>
                    </select>
                    <p v-if="errors.client_id" class="mt-1 text-[12px] text-red-600 dark:text-red-400">{{ errors.client_id }}</p>
                    <p class="mt-1 text-[12px] text-ink-tertiary">
                        Don't see your client?
                        <Link :href="route('clients.create')" class="font-medium text-accent hover:text-accent-hover">Create one</Link>
                    </p>
                </div>

                <!-- Video -->
                <div>
                    <label class="mb-1.5 block text-[13px] font-medium">Video</label>

                    <div
                        @drop="handleDrop"
                        @dragover.prevent
                        @dragenter.prevent
                        @dragleave="handleDragLeave"
                        :class="[
                            'rounded-lg border-2 border-dashed px-6 py-10 text-center transition-colors duration-150',
                            isDragOver
                                ? 'border-accent bg-accent-subtle'
                                : errors.video
                                  ? 'border-red-400 bg-red-50 dark:bg-red-950/20'
                                  : 'border-border-strong hover:border-ink-tertiary',
                        ]"
                    >
                        <div v-if="!form.video">
                            <svg class="mx-auto h-8 w-8 text-ink-tertiary" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                                <path
                                    stroke-linecap="round"
                                    stroke-linejoin="round"
                                    d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
                                />
                            </svg>
                            <p class="mt-3 text-[13px] text-ink-secondary">
                                Drop your video here, or
                                <label for="video" class="cursor-pointer font-medium text-accent hover:text-accent-hover">browse</label>
                            </p>
                            <p class="mt-1 text-[12px] text-ink-tertiary">MP4, MOV, AVI, WebM · up to 500 MB</p>
                        </div>

                        <div v-else>
                            <svg
                                class="mx-auto h-8 w-8 text-green-600 dark:text-green-400"
                                fill="none"
                                stroke="currentColor"
                                stroke-width="1.5"
                                viewBox="0 0 24 24"
                            >
                                <path
                                    stroke-linecap="round"
                                    stroke-linejoin="round"
                                    d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                                />
                            </svg>
                            <p class="mt-3 text-[13px] font-medium">{{ form.video.name }}</p>
                            <p class="tnum mt-0.5 text-[12px] text-ink-tertiary">{{ formatFileSize(form.video.size) }}</p>
                            <button
                                type="button"
                                @click="removeFile"
                                class="mt-2 text-[12px] font-medium text-red-600 transition-colors hover:text-red-700 dark:text-red-400"
                            >
                                Remove
                            </button>
                        </div>
                    </div>

                    <input
                        id="video"
                        ref="fileInput"
                        type="file"
                        accept=".mp4,.mov,.avi,.webm,video/mp4,video/quicktime,video/x-msvideo,video/webm"
                        @change="handleFileSelect"
                        class="hidden"
                    />

                    <div
                        v-if="errors.video"
                        class="mt-2 flex items-start gap-2 rounded-md border border-red-200 bg-red-50 p-3 dark:border-red-900/50 dark:bg-red-950/30"
                    >
                        <svg
                            class="mt-0.5 h-4 w-4 shrink-0 text-red-600 dark:text-red-400"
                            fill="none"
                            stroke="currentColor"
                            stroke-width="1.5"
                            viewBox="0 0 24 24"
                        >
                            <path
                                stroke-linecap="round"
                                stroke-linejoin="round"
                                d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
                            />
                        </svg>
                        <p class="text-[12px] text-red-700 dark:text-red-300">{{ errors.video }}</p>
                    </div>

                    <!-- Upload progress -->
                    <div v-if="uploadProgress !== null" class="mt-3">
                        <div class="mb-1.5 flex justify-between text-[12px] text-ink-secondary">
                            <span>Uploading…</span>
                            <span class="tnum">{{ uploadProgress }}%</span>
                        </div>
                        <div class="h-1.5 w-full overflow-hidden rounded-full bg-ground-subtle">
                            <div
                                class="h-full rounded-full bg-accent transition-[width] duration-300 ease-out"
                                :style="{ width: uploadProgress + '%' }"
                            />
                        </div>
                        <p class="mt-1 text-[12px] text-ink-tertiary">Don't close this page while uploading.</p>
                    </div>

                    <!-- Upload error recovery -->
                    <div v-if="uploadError" class="mt-3 rounded-md border border-red-200 bg-red-50 p-3 dark:border-red-900/50 dark:bg-red-950/30">
                        <p class="text-[13px] font-medium text-red-700 dark:text-red-300">Upload failed</p>
                        <p class="mt-0.5 text-[12px] text-red-600 dark:text-red-400">{{ uploadError }}</p>
                        <div class="mt-2 flex gap-2">
                            <button
                                @click="retryUpload"
                                class="rounded-md border border-red-300 px-2.5 py-1 text-[12px] font-medium text-red-700 transition-colors hover:bg-red-100 dark:border-red-800 dark:text-red-300 dark:hover:bg-red-950/50"
                            >
                                Try again
                            </button>
                            <button
                                @click="clearUploadError"
                                class="px-2.5 py-1 text-[12px] font-medium text-red-600 hover:text-red-700 dark:text-red-400"
                            >
                                Choose different file
                            </button>
                        </div>
                    </div>
                </div>

                <!-- Actions -->
                <div class="flex justify-end gap-2 border-t border-border pt-5">
                    <Link
                        :href="route('meetings.index')"
                        class="rounded-md border border-border-strong px-3 py-1.5 text-[13px] font-medium text-ink transition-colors duration-150 hover:bg-ground-subtle"
                    >
                        Cancel
                    </Link>
                    <button
                        type="submit"
                        :disabled="processing || !suggestionState.title.value || !rememberedState.clientId || !form.video"
                        class="rounded-md bg-accent-solid px-4 py-1.5 text-[13px] font-medium text-white transition-colors duration-150 hover:bg-accent-solid-hover disabled:cursor-not-allowed disabled:opacity-50"
                    >
                        {{ processing ? 'Uploading…' : 'Upload meeting' }}
                    </button>
                </div>
            </form>
        </div>
    </AppLayout>
</template>

<script setup lang="ts">
import AppLayout from '@/lib/AppLayout.vue';
import { localDateTimeToOffsetIso, parseMeetingFilename } from '@/lib/meetingFilename';
import {
    applyMeetingFilenameSuggestion,
    clearAutomaticMeetingSuggestions,
    createRememberableMeetingCreateState,
    markSuggestedFieldEdited,
    resetMeetingSuggestionState,
    type RememberableMeetingCreateState,
} from '@/lib/meetingSuggestionState';
import { Link, router, useRemember } from '@inertiajs/vue3';
import { onMounted, onUnmounted, reactive, ref } from 'vue';

interface Client {
    id: number;
    name: string;
}

interface Props {
    clients: Client[];
    errors: Record<string, string>;
}

defineProps<Props>();

const fileInput = ref<HTMLInputElement>();
const isDragOver = ref(false);
const uploadProgress = ref<number | null>(null);
const processing = ref(false);
const uploadError = ref<string>('');
const retryCount = ref(0);
const maxRetries = 3;

const rememberedState = useRemember(
    reactive(createRememberableMeetingCreateState()),
    'Meetings/Create:meeting-metadata:v1',
) as RememberableMeetingCreateState;
const suggestionState = rememberedState.suggestionState;
const form = reactive({
    video: null as File | null,
});

onMounted(() => {
    try {
        const params = new URLSearchParams(window.location.search);
        const qClientId = params.get('client_id');
        if (qClientId && rememberedState.clientId === '') {
            rememberedState.clientId = qClientId;
        }
    } catch {
        // ignore
    }
});

const handleFileSelect = (event: Event) => {
    const target = event.target as HTMLInputElement;
    if (target.files && target.files[0]) {
        const file = target.files[0];
        if (validateFile(file)) {
            selectFile(file);
        } else {
            clearSelectedVideo(false);
        }
    }
};

const handleDrop = (event: DragEvent) => {
    event.preventDefault();
    isDragOver.value = false;

    if (event.dataTransfer?.files && event.dataTransfer.files[0]) {
        const file = event.dataTransfer.files[0];
        if (validateFile(file)) {
            selectFile(file);
        } else {
            clearSelectedVideo(false);
        }
    }
};

const selectFile = (file: File) => {
    form.video = file;
    uploadError.value = '';
    applyMeetingFilenameSuggestion(suggestionState, parseMeetingFilename(file.name));
};

const handleTitleInput = (event: Event) => {
    markSuggestedFieldEdited(suggestionState.title, (event.target as HTMLInputElement).value);
};

const handleMeetingAtInput = (event: Event) => {
    markSuggestedFieldEdited(suggestionState.localDateTime, (event.target as HTMLInputElement).value);
};

const handleDragLeave = (event: DragEvent) => {
    if (!(event.currentTarget as Node | null)?.contains(event.relatedTarget as Node)) {
        isDragOver.value = false;
    }
};

const validateFile = (file: File): boolean => {
    const maxSize = 500 * 1024 * 1024;
    const minSize = 1024 * 1024;
    const allowedTypes = ['video/mp4', 'video/quicktime', 'video/x-msvideo', 'video/webm'];

    if (!allowedTypes.includes(file.type)) {
        uploadError.value = 'Please select a valid video file (MP4, MOV, AVI, or WebM)';
        return false;
    }
    if (file.size > maxSize) {
        uploadError.value = 'File size must be less than 500MB';
        return false;
    }
    if (file.size < minSize) {
        uploadError.value = 'File size must be at least 1MB';
        return false;
    }
    return true;
};

const clearSelectedVideo = (clearError = true) => {
    form.video = null;
    clearAutomaticMeetingSuggestions(suggestionState);
    if (clearError) {
        uploadError.value = '';
    }
    if (fileInput.value) {
        fileInput.value.value = '';
    }
};

const removeFile = () => {
    clearSelectedVideo();
};

const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

const submit = () => {
    if (!form.video || !validateFile(form.video)) return;

    const meetingAt = suggestionState.localDateTime.value ? localDateTimeToOffsetIso(suggestionState.localDateTime.value) : null;
    if (suggestionState.localDateTime.value && !meetingAt) {
        uploadError.value = 'Please enter a valid meeting date and time.';
        return;
    }

    processing.value = true;
    uploadProgress.value = 0;
    uploadError.value = '';

    router.post(
        route('meetings.store'),
        {
            title: suggestionState.title.value,
            client_id: rememberedState.clientId,
            meeting_at: meetingAt,
            video: form.video,
        },
        {
            forceFormData: true,
            onProgress: (progress?: { percentage?: number }) => {
                if (progress?.percentage !== undefined && progress?.percentage !== null) {
                    uploadProgress.value = Math.round(progress.percentage);
                }
            },
            onSuccess: () => {
                processing.value = false;
                uploadProgress.value = null;
                retryCount.value = 0;
                resetMeetingSuggestionState(suggestionState);
                rememberedState.clientId = '';
                if (window.toast) {
                    window.toast.success('Meeting uploaded', 'Your meeting is now being processed.');
                }
            },
            onError: (errors) => {
                processing.value = false;
                uploadProgress.value = null;

                if (errors.video) {
                    uploadError.value = errors.video;
                } else if (errors.title) {
                    uploadError.value = 'Please check the meeting title';
                } else if (errors.client_id) {
                    uploadError.value = 'Please select a client';
                } else if (errors.meeting_at) {
                    uploadError.value = errors.meeting_at;
                } else {
                    uploadError.value = 'Upload failed. Please try again.';
                }

                if (window.toast && retryCount.value < maxRetries) {
                    window.toast.error('Upload failed', uploadError.value, {
                        actions: [{ label: 'Try again', handler: retryUpload, primary: true }],
                    });
                }
            },
            onFinish: () => {
                processing.value = false;
                uploadProgress.value = null;
            },
        },
    );
};

const retryUpload = () => {
    if (retryCount.value < maxRetries) {
        retryCount.value++;
        uploadError.value = '';
        submit();
    } else {
        uploadError.value = 'Maximum retry attempts reached. Please try a different file.';
    }
};

const clearUploadError = () => {
    uploadError.value = '';
    clearSelectedVideo();
};

const handleBeforeUnload = (event: BeforeUnloadEvent) => {
    if (processing.value && uploadProgress.value !== null) {
        event.preventDefault();
        event.returnValue = 'Upload in progress. Are you sure you want to leave?';
        return event.returnValue;
    }
};

const handleGlobalDragEnter = (e: DragEvent) => {
    e.preventDefault();
    isDragOver.value = true;
};

const handleGlobalDragLeave = (e: DragEvent) => {
    e.preventDefault();
    if (!e.relatedTarget) {
        isDragOver.value = false;
    }
};

const handleGlobalDrop = (e: DragEvent) => {
    e.preventDefault();
    isDragOver.value = false;
};

onMounted(() => {
    window.addEventListener('beforeunload', handleBeforeUnload);
    document.addEventListener('dragenter', handleGlobalDragEnter);
    document.addEventListener('dragleave', handleGlobalDragLeave);
    document.addEventListener('drop', handleGlobalDrop);
});

onUnmounted(() => {
    window.removeEventListener('beforeunload', handleBeforeUnload);
    document.removeEventListener('dragenter', handleGlobalDragEnter);
    document.removeEventListener('dragleave', handleGlobalDragLeave);
    document.removeEventListener('drop', handleGlobalDrop);
});
</script>
