<template>
    <AppLayout>
        <div class="mx-auto flex h-[calc(100vh-3.5rem)] max-w-3xl flex-col px-6 lg:h-screen lg:px-10">
            <!-- Header -->
            <div class="shrink-0 pt-8 pb-4">
                <h1 class="text-[20px] font-semibold tracking-tight">AI Assistant</h1>
                <p class="mt-0.5 text-[13px] text-ink-secondary">Ask anything across all your meeting transcripts.</p>
            </div>

            <!-- Messages -->
            <div class="min-h-0 flex-1 space-y-4 overflow-y-auto py-4" ref="messagesContainer">
                <div v-if="messages.length === 0" class="flex h-full flex-col items-center justify-center text-center">
                    <div class="flex h-10 w-10 items-center justify-center rounded-lg bg-accent-subtle">
                        <svg class="h-5 w-5 text-accent" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                            <path
                                stroke-linecap="round"
                                stroke-linejoin="round"
                                d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z"
                            />
                        </svg>
                    </div>
                    <p class="mt-4 text-[14px] font-medium">Ask about your meetings</p>
                    <p class="mt-1 max-w-sm text-[13px] text-ink-secondary">
                        I search across every transcript in your archive and cite the exact moment.
                    </p>
                    <div class="mt-5 flex flex-wrap justify-center gap-2">
                        <button
                            v-for="suggestion in suggestions"
                            :key="suggestion"
                            @click="currentMessage = suggestion"
                            class="rounded-md border border-border-strong px-3 py-1.5 text-[12px] text-ink-secondary transition-colors duration-150 hover:bg-ground-subtle hover:text-ink"
                        >
                            {{ suggestion }}
                        </button>
                    </div>
                </div>

                <div v-for="(message, index) in messages" :key="index" class="flex" :class="message.role === 'user' ? 'justify-end' : 'justify-start'">
                    <div
                        :class="[
                            'max-w-[85%] rounded-lg px-3.5 py-2.5 text-[13px] leading-relaxed',
                            message.role === 'user' ? 'bg-accent-solid text-white' : 'border border-border bg-ground-raised text-ink',
                        ]"
                    >
                        <div class="whitespace-pre-wrap">{{ message.content }}</div>

                        <!-- Search results -->
                        <div v-if="message.searchResults && message.searchResults.length > 0" class="mt-3 space-y-2">
                            <div class="border-t pt-2 text-[12px] font-medium" :class="message.role === 'user' ? 'border-white/20' : 'border-border'">
                                {{ message.searchResults.length }} result{{ message.searchResults.length === 1 ? '' : 's' }}
                            </div>
                            <div
                                v-for="result in message.searchResults"
                                :key="`${result.meeting_id}-${result.timestamp}`"
                                class="rounded-md border border-border bg-ground p-3 text-[12px]"
                            >
                                <div class="mb-1.5 flex items-start justify-between gap-2">
                                    <div class="min-w-0">
                                        <div class="truncate font-medium text-accent">{{ result.meeting_title }}</div>
                                        <div class="text-ink-secondary">{{ result.client_name }} · {{ result.speaker }}</div>
                                    </div>
                                    <span class="tnum shrink-0 text-[11px] text-ink-tertiary">{{ result.formatted_timestamp }}</span>
                                </div>
                                <div class="leading-relaxed text-ink-secondary" v-html="formatSearchResult(result.text)"></div>
                                <a
                                    :href="`/meetings/${result.meeting_id}?t=${result.timestamp}`"
                                    class="mt-2 inline-block text-[11px] font-medium text-accent hover:text-accent-hover"
                                    target="_blank"
                                >
                                    View in meeting →
                                </a>
                            </div>
                        </div>

                        <div v-if="message.timestamp" class="tnum mt-1.5 text-[11px]" :class="message.role === 'user' ? 'text-white/60' : 'text-ink-tertiary'">
                            {{ formatTime(message.timestamp) }}
                        </div>
                    </div>
                </div>

                <div v-if="isLoading" class="flex justify-start">
                    <div class="flex items-center gap-2 rounded-lg border border-border bg-ground-raised px-3.5 py-2.5 text-[13px] text-ink-secondary">
                        <span class="h-3.5 w-3.5 animate-spin rounded-full border-2 border-border-strong border-t-accent" />
                        Thinking…
                    </div>
                </div>
            </div>

            <!-- Input -->
            <div class="shrink-0 border-t border-border py-4">
                <form @submit.prevent="sendMessage" class="flex gap-2">
                    <input
                        v-model="currentMessage"
                        type="text"
                        placeholder="Ask about your meetings…"
                        :disabled="isLoading"
                        class="flex-1 rounded-md border border-border-strong bg-ground-raised px-3 py-2 text-[13px] text-ink placeholder:text-ink-tertiary focus:border-accent focus:ring-2 focus:ring-accent/30 focus:outline-none disabled:opacity-50"
                    />
                    <button
                        type="submit"
                        :disabled="!currentMessage.trim() || isLoading"
                        class="rounded-md bg-accent-solid px-4 py-2 text-[13px] font-medium text-white transition-colors duration-150 hover:bg-accent-solid-hover disabled:cursor-not-allowed disabled:opacity-50"
                    >
                        Send
                    </button>
                </form>
            </div>
        </div>
    </AppLayout>
</template>

<script setup lang="ts">
import AppLayout from '@/lib/AppLayout.vue';
import { usePage } from '@inertiajs/vue3';
import { nextTick, ref } from 'vue';

interface Message {
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
    searchResults?: SearchResult[];
}

interface SearchResult {
    meeting_id: number;
    meeting_title: string;
    client_name: string;
    speaker: string;
    text: string;
    timestamp: number;
    formatted_timestamp: string;
    confidence: number;
    meeting_url: string;
}

const suggestions = ['Find mentions of budget', 'What was said about the timeline?', 'Search for marketing discussions'];

const messages = ref<Message[]>([]);
const currentMessage = ref('');
const isLoading = ref(false);
const messagesContainer = ref<HTMLElement>();
const page = usePage<{ csrf_token: string }>();

const sendMessage = async () => {
    if (!currentMessage.value.trim() || isLoading.value) return;

    const userMessage: Message = {
        role: 'user',
        content: currentMessage.value,
        timestamp: new Date(),
    };

    messages.value.push(userMessage);
    const messageToSend = currentMessage.value;
    currentMessage.value = '';
    isLoading.value = true;

    await scrollToBottom();

    let retryCount = 0;
    const maxRetries = 3;

    const attemptSend = async (): Promise<void> => {
        try {
            if (!navigator.onLine) {
                throw new Error('No internet connection');
            }

            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 30000);

            const response = await fetch('/ai/chat', {
                method: 'POST',
                credentials: 'same-origin',
                signal: controller.signal,
                headers: {
                    'Content-Type': 'application/json',
                    Accept: 'application/json',
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRF-TOKEN': page.props.csrf_token,
                },
                body: JSON.stringify({
                    message: messageToSend,
                    conversation_history: messages.value.slice(0, -1).map((msg) => ({
                        role: msg.role,
                        content: msg.content,
                    })),
                }),
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                if (response.status === 429) {
                    throw new Error('Too many requests. Please wait a moment and try again.');
                } else if (response.status >= 500) {
                    throw new Error('Server error. Please try again in a few moments.');
                } else if (response.status === 401) {
                    throw new Error('Your session has expired. Please refresh the page.');
                } else {
                    throw new Error(`Request failed with status ${response.status}`);
                }
            }

            const data = await response.json();

            if (data.success) {
                const assistantMessage: Message = {
                    role: 'assistant',
                    content: data.response,
                    timestamp: new Date(),
                };

                if (data.tool_calls && data.tool_calls.length > 0) {
                    const searchToolCall = data.tool_calls.find((call: any) => call.name === 'search_meetings');
                    if (searchToolCall && searchToolCall.result && searchToolCall.result.results) {
                        assistantMessage.searchResults = searchToolCall.result.results;
                    }
                }

                messages.value.push(assistantMessage);
            } else {
                throw new Error(data.error || 'AI service returned an error');
            }
        } catch (error: any) {
            console.error('Chat error:', error);

            if (error.name === 'AbortError') {
                throw new Error('Request timed out. Please try again.');
            }

            if (error.message === 'No internet connection') {
                throw new Error('No internet connection. Please check your network and try again.');
            }

            if (
                retryCount < maxRetries &&
                (error.name === 'NetworkError' || error.message.includes('fetch') || error.message.includes('Server error'))
            ) {
                retryCount++;
                await new Promise((resolve) => setTimeout(resolve, 1000 * retryCount));
                return attemptSend();
            }

            const errorMessage = error.message || 'Sorry, I encountered an error. Please try again.';

            messages.value.push({
                role: 'assistant',
                content: errorMessage,
                timestamp: new Date(),
            });

            if (window.toast) {
                window.toast.error('Chat error', errorMessage, {
                    actions:
                        retryCount < maxRetries
                            ? [
                                  {
                                      label: 'Retry',
                                      handler: () => {
                                          messages.value.pop();
                                          currentMessage.value = messageToSend;
                                          sendMessage();
                                      },
                                      primary: true,
                                  },
                              ]
                            : undefined,
                });
            }
        }
    };

    try {
        await attemptSend();
    } finally {
        isLoading.value = false;
        await scrollToBottom();
    }
};

const scrollToBottom = async () => {
    await nextTick();
    if (messagesContainer.value) {
        messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
    }
};

const formatTime = (date: Date) => {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
};

const formatSearchResult = (text: string) => {
    return text.replace(/\*\*(.*?)\*\*/g, '<mark>$1</mark>');
};
</script>

<style scoped>
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
