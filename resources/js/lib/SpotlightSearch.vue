<template>
    <Teleport to="body">
        <Transition
            enter-active-class="transition-all duration-150 ease-out"
            enter-from-class="opacity-0"
            enter-to-class="opacity-100"
            leave-active-class="transition-all duration-100 ease-in"
            leave-from-class="opacity-100"
            leave-to-class="opacity-0"
        >
            <div v-if="open" class="fixed inset-0 z-[60] flex items-start justify-center px-4 pt-[15vh]" @mousedown.self="close">
                <div class="absolute inset-0 bg-black/40" @mousedown="close" />

                <div
                    class="relative w-full max-w-lg overflow-hidden rounded-lg border border-border bg-ground-raised shadow-[0_16px_48px_rgb(0_0_0/0.16)] dark:shadow-[0_16px_48px_rgb(0_0_0/0.5)]"
                    role="dialog"
                    aria-label="Search"
                >
                    <!-- Input -->
                    <div class="flex items-center gap-2.5 border-b border-border px-4">
                        <svg class="h-4 w-4 shrink-0 text-ink-tertiary" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
                        </svg>
                        <input
                            ref="inputRef"
                            v-model="query"
                            type="text"
                            placeholder="Search meetings and clients…"
                            class="w-full bg-transparent py-3 text-[14px] text-ink placeholder:text-ink-tertiary focus:outline-none"
                            @keydown.down.prevent="move(1)"
                            @keydown.up.prevent="move(-1)"
                            @keydown.enter.prevent="selectActive"
                            @keydown.esc="close"
                        />
                        <kbd class="shrink-0 rounded border border-border bg-ground-subtle px-1.5 py-0.5 text-[11px] text-ink-tertiary">esc</kbd>
                    </div>

                    <!-- Results -->
                    <div class="max-h-[50vh] overflow-y-auto p-1.5">
                        <div v-if="query.trim() && !isLoading && flatResults.length === 0" class="px-3 py-8 text-center text-[13px] text-ink-secondary">
                            No results for "{{ query }}"
                        </div>

                        <div v-else-if="!query.trim()" class="px-3 py-8 text-center text-[13px] text-ink-tertiary">
                            Type to search across meetings and clients.
                        </div>

                        <template v-else>
                            <div v-if="groupedResults.meetings.length > 0">
                                <div class="px-3 pt-2 pb-1 text-[11px] font-medium tracking-[0.05em] text-ink-tertiary uppercase">Meetings</div>
                                <button
                                    v-for="item in groupedResults.meetings"
                                    :key="item.key"
                                    @click="go(item)"
                                    @mousemove="activeIndex = item.flatIndex"
                                    :class="[
                                        'flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-left transition-colors duration-100',
                                        activeIndex === item.flatIndex ? 'bg-accent-subtle' : '',
                                    ]"
                                >
                                    <span class="h-1.5 w-1.5 shrink-0 rounded-full" :class="statusDotClass(item.status)" />
                                    <span class="min-w-0 flex-1 truncate text-[13px] font-medium" :class="activeIndex === item.flatIndex ? 'text-accent' : 'text-ink'">
                                        {{ item.title }}
                                    </span>
                                    <span class="shrink-0 text-[12px] text-ink-tertiary">{{ item.subtitle }}</span>
                                </button>
                            </div>

                            <div v-if="groupedResults.clients.length > 0">
                                <div class="px-3 pt-2 pb-1 text-[11px] font-medium tracking-[0.05em] text-ink-tertiary uppercase">Clients</div>
                                <button
                                    v-for="item in groupedResults.clients"
                                    :key="item.key"
                                    @click="go(item)"
                                    @mousemove="activeIndex = item.flatIndex"
                                    :class="[
                                        'flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-left transition-colors duration-100',
                                        activeIndex === item.flatIndex ? 'bg-accent-subtle' : '',
                                    ]"
                                >
                                    <svg class="h-3.5 w-3.5 shrink-0 text-ink-tertiary" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                                        <path
                                            stroke-linecap="round"
                                            stroke-linejoin="round"
                                            d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z"
                                        />
                                    </svg>
                                    <span class="min-w-0 flex-1 truncate text-[13px] font-medium" :class="activeIndex === item.flatIndex ? 'text-accent' : 'text-ink'">
                                        {{ item.title }}
                                    </span>
                                    <span class="shrink-0 text-[12px] text-ink-tertiary">{{ item.subtitle }}</span>
                                </button>
                            </div>
                        </template>
                    </div>
                </div>
            </div>
        </Transition>
    </Teleport>
</template>

<script setup lang="ts">
import { router } from '@inertiajs/vue3';
import { computed, nextTick, ref, watch } from 'vue';

interface ResultItem {
    key: string;
    title: string;
    subtitle: string;
    url: string;
    status?: string;
    flatIndex: number;
}

const open = ref(false);
const query = ref('');
const isLoading = ref(false);
const activeIndex = ref(0);
const inputRef = ref<HTMLInputElement>();

const clients = ref<Array<{ id: number; name: string; company: string | null }>>([]);
const meetings = ref<Array<{ id: number; title: string; status: string; client: { id: number; name: string } | null }>>([]);

let debounceTimer: ReturnType<typeof setTimeout> | null = null;
let abortController: AbortController | null = null;

const groupedResults = computed(() => {
    let i = 0;
    const meetingItems: ResultItem[] = meetings.value.map((m) => ({
        key: `meeting-${m.id}`,
        title: m.title,
        subtitle: m.client?.name || '',
        url: `/meetings/${m.id}`,
        status: m.status,
        flatIndex: i++,
    }));
    const clientItems: ResultItem[] = clients.value.map((c) => ({
        key: `client-${c.id}`,
        title: c.name,
        subtitle: c.company || '',
        url: `/clients/${c.id}`,
        flatIndex: i++,
    }));
    return { meetings: meetingItems, clients: clientItems };
});

const flatResults = computed(() => [...groupedResults.value.meetings, ...groupedResults.value.clients]);

const statusDotClass = (status?: string) => {
    switch (status) {
        case 'completed':
            return 'bg-green-500';
        case 'processing':
            return 'bg-amber-500';
        case 'failed':
            return 'bg-red-500';
        default:
            return 'bg-zinc-400';
    }
};

const search = async () => {
    const q = query.value.trim();
    if (!q) {
        clients.value = [];
        meetings.value = [];
        return;
    }

    abortController?.abort();
    abortController = new AbortController();
    isLoading.value = true;

    try {
        const response = await fetch(`/search?q=${encodeURIComponent(q)}`, {
            headers: { Accept: 'application/json' },
            signal: abortController.signal,
        });
        if (response.ok) {
            const data = await response.json();
            clients.value = data.clients;
            meetings.value = data.meetings;
        }
    } catch {
        // aborted or network error — keep previous results
    } finally {
        isLoading.value = false;
    }
};

watch(query, () => {
    activeIndex.value = 0;
    if (debounceTimer) clearTimeout(debounceTimer);
    debounceTimer = setTimeout(search, 180);
});

const move = (delta: number) => {
    const count = flatResults.value.length;
    if (count === 0) return;
    activeIndex.value = (activeIndex.value + delta + count) % count;
};

const go = (item: ResultItem) => {
    close();
    router.visit(item.url);
};

const selectActive = () => {
    const item = flatResults.value[activeIndex.value];
    if (item) go(item);
};

const show = async () => {
    open.value = true;
    query.value = '';
    clients.value = [];
    meetings.value = [];
    activeIndex.value = 0;
    await nextTick();
    inputRef.value?.focus();
};

const close = () => {
    open.value = false;
    abortController?.abort();
};

defineExpose({ show, close });
</script>
