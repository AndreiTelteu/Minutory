<template>
    <Teleport to="body">
        <Transition
            name="slide-down"
            enter-active-class="transition-transform duration-300 ease-out"
            enter-from-class="-translate-y-full"
            enter-to-class="translate-y-0"
            leave-active-class="transition-transform duration-300 ease-in"
            leave-from-class="translate-y-0"
            leave-to-class="-translate-y-full"
        >
            <div v-if="!isOnline" class="fixed top-0 right-0 left-0 z-50 border-b border-red-200 bg-red-50 px-4 py-2 text-center text-[13px] font-medium text-red-700 dark:border-red-900/50 dark:bg-red-950 dark:text-red-300">
                <div class="flex items-center justify-center gap-2">
                    <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
                    </svg>
                    <span>No internet connection. Some features may not work properly.</span>
                </div>
            </div>
        </Transition>

        <Transition
            name="slide-down"
            enter-active-class="transition-all duration-500 ease-out"
            enter-from-class="-translate-y-full opacity-0"
            enter-to-class="translate-y-0 opacity-100"
            leave-active-class="transition-all duration-300 ease-in"
            leave-from-class="translate-y-0 opacity-100"
            leave-to-class="-translate-y-full opacity-0"
        >
            <div v-if="showReconnected" class="fixed top-0 right-0 left-0 z-50 border-b border-green-200 bg-green-50 px-4 py-2 text-center text-[13px] font-medium text-green-700 dark:border-green-900/50 dark:bg-green-950 dark:text-green-300">
                <div class="flex items-center justify-center gap-2">
                    <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <span>Connection restored.</span>
                </div>
            </div>
        </Transition>
    </Teleport>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue';

const isOnline = ref(navigator.onLine);
const showReconnected = ref(false);
let reconnectedTimeout: number | null = null;

const handleOnline = () => {
    isOnline.value = true;
    showReconnected.value = true;

    // Hide reconnected message after 3 seconds
    if (reconnectedTimeout) {
        clearTimeout(reconnectedTimeout);
    }
    reconnectedTimeout = window.setTimeout(() => {
        showReconnected.value = false;
    }, 3000);
};

const handleOffline = () => {
    isOnline.value = false;
    showReconnected.value = false;

    if (reconnectedTimeout) {
        clearTimeout(reconnectedTimeout);
        reconnectedTimeout = null;
    }
};

onMounted(() => {
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
});

onUnmounted(() => {
    window.removeEventListener('online', handleOnline);
    window.removeEventListener('offline', handleOffline);

    if (reconnectedTimeout) {
        clearTimeout(reconnectedTimeout);
    }
});

// Expose online status globally
defineExpose({
    isOnline,
});
</script>
