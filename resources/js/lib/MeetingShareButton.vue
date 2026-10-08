<template>
    <div class="space-y-2" @click.stop>
        <button
            type="button"
            :disabled="generating"
            class="rounded-md border border-border-strong px-2.5 py-1 text-[12px] font-medium text-ink-secondary transition-colors duration-150 hover:bg-ground-subtle hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-wait disabled:opacity-50"
            @click="generateLink"
        >
            {{ generating ? 'Generating…' : 'Generate share link' }}
        </button>
        <div v-if="shareUrl" class="space-y-1">
            <label :for="`share-url-${meetingId}`" class="block text-[12px] text-ink-secondary">Public link · recording and transcript</label>
            <input
                :id="`share-url-${meetingId}`"
                :value="shareUrl"
                readonly
                class="w-full rounded-md border border-border-strong bg-ground-raised px-3 py-1.5 text-[13px] text-ink focus-visible:outline-2 focus-visible:outline-accent"
                @focus="selectLink"
            />
        </div>
        <p v-if="message" role="status" class="text-[12px] text-ink-secondary">{{ message }}</p>
        <p v-if="error" role="alert" class="text-[12px] text-red-600 dark:text-red-400">{{ error }}</p>
    </div>
</template>

<script setup lang="ts">
import axios from 'axios';
import { ref } from 'vue';

const props = defineProps<{ meetingId: number }>();
const generating = ref(false);
const shareUrl = ref('');
const message = ref('');
const error = ref('');

const selectLink = (event: FocusEvent) => (event.target as HTMLInputElement).select();

const generateLink = async () => {
    if (generating.value) return;
    generating.value = true;
    message.value = '';
    error.value = '';

    try {
        const response = await axios.post<{ url: string }>(route('meetings.shares.store', props.meetingId));
        shareUrl.value = response.data.url;
        try {
            await navigator.clipboard.writeText(shareUrl.value);
            message.value = 'New public link copied.';
        } catch {
            message.value = 'New public link ready. Select it to copy.';
        }
    } catch {
        error.value = 'Could not generate a share link. Try again.';
    } finally {
        generating.value = false;
    }
};
</script>
