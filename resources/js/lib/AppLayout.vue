<template>
    <ErrorBoundary>
        <div class="flex min-h-screen bg-ground text-ink">
            <!-- Sidebar -->
            <aside
                class="fixed inset-y-0 left-0 z-40 flex w-60 flex-col overflow-hidden border-r border-border bg-ground-subtle whitespace-nowrap transition-[transform,width] duration-200 ease-out lg:translate-x-0"
                :class="[
                    sidebarOpen ? 'translate-x-0' : '-translate-x-full',
                    railMode ? 'group/sidebar lg:w-14 lg:hover:w-60 lg:hover:shadow-[0_8px_24px_rgb(0_0_0/0.12)] lg:dark:hover:shadow-[0_8px_24px_rgb(0_0_0/0.4)]' : '',
                ]"
            >
                <!-- Workspace -->
                <div class="flex h-14 items-center gap-2.5 border-b border-border" :class="railMode ? 'px-4 lg:px-[14px] lg:hover:px-4' : 'px-4'">
                    <div class="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-accent-solid text-[11px] font-bold text-white">M</div>
                    <span v-if="!railMode" class="text-[14px] font-semibold tracking-tight">Minutory</span>
                    <span v-else class="text-[14px] font-semibold tracking-tight lg:hidden lg:group-hover/sidebar:inline">Minutory</span>
                </div>

                <!-- Search -->
                <div class="p-2">
                    <button
                        @click="spotlightRef?.show()"
                        class="flex w-full items-center gap-2.5 rounded-md border border-border bg-ground-raised px-2.5 py-1.5 text-[13px] text-ink-tertiary transition-colors duration-150 hover:border-border-strong hover:text-ink-secondary"
                        :class="railMode ? 'lg:px-[7px] lg:hover:px-2.5' : ''"
                        :title="railMode ? 'Search (⌘K)' : undefined"
                    >
                        <svg class="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
                        </svg>
                        <template v-if="railMode">
                            <span class="flex-1 text-left lg:hidden lg:group-hover/sidebar:inline">Search…</span>
                            <kbd class="rounded border border-border bg-ground-subtle px-1 py-0.5 text-[10px] lg:hidden lg:group-hover/sidebar:inline">⌘K</kbd>
                        </template>
                        <template v-else>
                            <span class="flex-1 text-left">Search…</span>
                            <kbd class="rounded border border-border bg-ground-subtle px-1 py-0.5 text-[10px]">⌘K</kbd>
                        </template>
                    </button>
                </div>

                <!-- Nav -->
                <nav class="space-y-0.5 px-2">
                    <Link
                        v-for="item in navItems"
                        :key="item.label"
                        :href="route(item.route)"
                        :title="railMode ? item.label : undefined"
                        :class="[
                            'flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-[13px] font-medium transition-colors duration-150',
                            item.active($page.component)
                                ? 'bg-accent-subtle text-accent'
                                : 'text-ink-secondary hover:bg-ground-raised hover:text-ink',
                            railMode ? 'lg:px-[7px] lg:hover:px-2.5' : '',
                        ]"
                        @click="sidebarOpen = false"
                    >
                        <component :is="item.icon" class="h-4 w-4 shrink-0" />
                        <span v-if="railMode" class="lg:hidden lg:group-hover/sidebar:inline">{{ item.label }}</span>
                        <template v-else>{{ item.label }}</template>
                    </Link>
                </nav>

                <!-- Recent meetings -->
                <div class="mt-4 flex min-h-0 flex-1 flex-col">
                    <div v-if="!railMode" class="px-4 pb-1 text-[11px] font-medium tracking-[0.05em] text-ink-tertiary uppercase">Recent</div>
                    <div v-else class="px-4 pb-1 text-[11px] font-medium tracking-[0.05em] text-ink-tertiary uppercase lg:hidden lg:group-hover/sidebar:block">Recent</div>
                    <div class="min-h-0 flex-1 space-y-0.5 overflow-y-auto px-2 pb-2">
                        <Link
                            v-for="m in sidebarMeetings"
                            :key="m.id"
                            :href="route('meetings.show', m.id)"
                            :title="railMode ? m.title : undefined"
                            class="flex items-center gap-2 rounded-md px-2.5 py-1.5 text-[13px] text-ink-secondary transition-colors duration-150 hover:bg-ground-raised hover:text-ink"
                            :class="[{ 'bg-ground-raised text-ink': isActiveMeeting(m.id) }, railMode ? 'lg:px-[9px] lg:hover:px-2.5' : '']"
                            @click="sidebarOpen = false"
                        >
                            <span class="h-1.5 w-1.5 shrink-0 rounded-full" :class="statusDotClass(m.status)" />
                            <span v-if="railMode" class="min-w-0 flex-1 truncate lg:hidden lg:group-hover/sidebar:block">{{ m.title }}</span>
                            <span v-else class="min-w-0 flex-1 truncate">{{ m.title }}</span>
                        </Link>
                        <div v-if="sidebarMeetings.length === 0" class="px-2.5 py-1.5 text-[12px] text-ink-tertiary">No meetings yet</div>
                    </div>
                </div>

                <!-- Footer: theme toggle -->
                <div class="border-t border-border p-2">
                    <button
                        @click="toggleTheme"
                        class="flex w-full items-center gap-2.5 rounded-md px-2.5 py-1.5 text-[13px] font-medium text-ink-secondary transition-colors duration-150 hover:bg-ground-raised hover:text-ink"
                        :class="railMode ? 'lg:px-[7px] lg:hover:px-2.5' : ''"
                    >
                        <svg v-if="isDark" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                            <path
                                stroke-linecap="round"
                                stroke-linejoin="round"
                                d="M12 3v2.25m6.364.386l-1.591 1.591M21 12h-2.25m-.386 6.364l-1.591-1.591M12 18.75V21m-4.773-4.227l-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0z"
                            />
                        </svg>
                        <svg v-else class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                            <path
                                stroke-linecap="round"
                                stroke-linejoin="round"
                                d="M21.752 15.002A9.718 9.718 0 0118 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 003 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 009.002-5.998z"
                            />
                        </svg>
                        <span v-if="railMode" class="lg:hidden lg:group-hover/sidebar:inline">{{ isDark ? 'Light mode' : 'Dark mode' }}</span>
                        <template v-else>{{ isDark ? 'Light mode' : 'Dark mode' }}</template>
                    </button>
                </div>
            </aside>

            <!-- Mobile overlay -->
            <div v-if="sidebarOpen" class="fixed inset-0 z-30 bg-black/40 lg:hidden" @click="sidebarOpen = false" />

            <!-- Content -->
            <div class="flex min-w-0 flex-1 flex-col" :class="railMode ? 'lg:pl-14' : ''">
                <!-- Mobile top bar -->
                <div class="flex h-14 items-center gap-3 border-b border-border bg-ground px-4 lg:hidden">
                    <button
                        @click="sidebarOpen = true"
                        class="rounded-md p-1.5 text-ink-secondary transition-colors hover:bg-ground-subtle hover:text-ink"
                        aria-label="Open navigation"
                    >
                        <svg class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
                        </svg>
                    </button>
                    <span class="text-[14px] font-semibold tracking-tight">Minutory</span>
                </div>

                <!-- Flash messages -->
                <div class="pointer-events-none fixed inset-x-0 top-3 z-50 flex flex-col items-center gap-2 px-4">
                    <Transition
                        enter-active-class="transition-all duration-300 ease-out"
                        enter-from-class="-translate-y-2 opacity-0"
                        enter-to-class="translate-y-0 opacity-100"
                        leave-active-class="transition-all duration-200 ease-in"
                        leave-from-class="translate-y-0 opacity-100"
                        leave-to-class="-translate-y-2 opacity-0"
                    >
                        <div
                            v-if="flash?.success"
                            class="pointer-events-auto flex items-center gap-2.5 rounded-lg border border-border bg-ground-raised px-3.5 py-2.5 text-[13px] font-medium shadow-[0_4px_12px_rgb(0_0_0/0.08)] dark:shadow-[0_4px_12px_rgb(0_0_0/0.24)]"
                        >
                            <svg class="h-4 w-4 shrink-0 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            <span>{{ flash.success }}</span>
                            <button @click="clearFlashMessage('success')" class="ml-1 text-ink-tertiary hover:text-ink">
                                <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
                                </svg>
                            </button>
                        </div>
                    </Transition>
                    <Transition
                        enter-active-class="transition-all duration-300 ease-out"
                        enter-from-class="-translate-y-2 opacity-0"
                        enter-to-class="translate-y-0 opacity-100"
                        leave-active-class="transition-all duration-200 ease-in"
                        leave-from-class="translate-y-0 opacity-100"
                        leave-to-class="-translate-y-2 opacity-0"
                    >
                        <div
                            v-if="flash?.error"
                            class="pointer-events-auto flex items-center gap-2.5 rounded-lg border border-border bg-ground-raised px-3.5 py-2.5 text-[13px] font-medium shadow-[0_4px_12px_rgb(0_0_0/0.08)] dark:shadow-[0_4px_12px_rgb(0_0_0/0.24)]"
                        >
                            <svg class="h-4 w-4 shrink-0 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                                <path
                                    stroke-linecap="round"
                                    stroke-linejoin="round"
                                    d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
                                />
                            </svg>
                            <span>{{ flash.error }}</span>
                            <button @click="clearFlashMessage('error')" class="ml-1 text-ink-tertiary hover:text-ink">
                                <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
                                </svg>
                            </button>
                        </div>
                    </Transition>
                </div>

                <!-- Main -->
                <main class="min-w-0 flex-1">
                    <slot />
                </main>
            </div>
        </div>

        <Toast ref="toastComponent" />
        <NetworkStatus />
        <SpotlightSearch ref="spotlightRef" />
    </ErrorBoundary>
</template>

<script setup lang="ts">
import { Link, router, usePage } from '@inertiajs/vue3';
import { computed, h, onMounted, onUnmounted, ref } from 'vue';
import ErrorBoundary from './ErrorBoundary.vue';
import NetworkStatus from './NetworkStatus.vue';
import SpotlightSearch from './SpotlightSearch.vue';
import Toast from './Toast.vue';

interface SidebarMeeting {
    id: number;
    title: string;
    status: 'pending' | 'processing' | 'completed' | 'failed';
    client_id: number;
    created_at: string;
}

const sidebarOpen = ref(false);
const isDark = ref(false);
// On meeting detail, the sidebar rests as a slim icon rail and overlays
// content on hover instead of pushing it (avoids video/transcript reflow).
const railMode = computed(() => page.component === 'Meetings/Show');
const toastComponent = ref();
const spotlightRef = ref<InstanceType<typeof SpotlightSearch>>();

const page = usePage<{
    sidebarMeetings?: SidebarMeeting[];
    flash?: {
        success?: string;
        error?: string;
    };
}>();
const sidebarMeetings = computed(() => page.props.sidebarMeetings ?? []);
const flash = computed(() => page.props.flash);

const isActiveMeeting = (id: number) => {
    return page.component.startsWith('Meetings/Show') && (page.props as any).meeting?.id === id;
};

const statusDotClass = (status: string) => {
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

const onGlobalKeydown = (e: KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        spotlightRef.value?.show();
    }
};

onMounted(() => {
    isDark.value = document.documentElement.classList.contains('dark');
    window.addEventListener('keydown', onGlobalKeydown);
});

onUnmounted(() => {
    window.removeEventListener('keydown', onGlobalKeydown);
});

const toggleTheme = () => {
    isDark.value = !isDark.value;
    document.documentElement.classList.toggle('dark', isDark.value);
    localStorage.setItem('minutory-theme', isDark.value ? 'dark' : 'light');
};

const clearFlashMessage = (_type: 'success' | 'error') => {
    router.reload({ only: [] });
};

const icon = (paths: string) =>
    h(
        'svg',
        { fill: 'none', stroke: 'currentColor', 'stroke-width': '1.5', viewBox: '0 0 24 24' },
        paths.split('|').map((d) => h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', d })),
    );

const navItems = [
    {
        label: 'Dashboard',
        route: 'home',
        active: (c: string) => c === 'Dashboard',
        icon: icon(
            'M2.25 12l8.954-8.955c.44-.439 1.152-.439 1.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75',
        ),
    },
    {
        label: 'Meetings',
        route: 'meetings.index',
        active: (c: string) => c.startsWith('Meetings/'),
        icon: icon(
            'M15.75 10.5l4.72-4.72a.75.75 0 011.28.53v11.38a.75.75 0 01-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 002.25-2.25v-9a2.25 2.25 0 00-2.25-2.25h-9A2.25 2.25 0 002.25 7.5v9a2.25 2.25 0 002.25 2.25z',
        ),
    },
    {
        label: 'Clients',
        route: 'clients.index',
        active: (c: string) => c.startsWith('Clients/'),
        icon: icon(
            'M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z',
        ),
    },
    {
        label: 'AI Assistant',
        route: 'ai.chat',
        active: (c: string) => c.startsWith('AI/'),
        icon: icon(
            'M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z',
        ),
    },
];
</script>
