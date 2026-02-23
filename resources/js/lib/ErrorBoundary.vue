<template>
    <div v-if="hasError" class="flex min-h-screen items-center justify-center bg-gray-50">
        <div class="w-full max-w-md rounded-lg bg-white p-6 text-center shadow-lg">
            <div class="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-red-100">
                <svg class="h-8 w-8 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        stroke-width="2"
                        d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z"
                    />
                </svg>
            </div>

            <h2 class="mb-2 text-xl font-semibold text-gray-900">Something went wrong</h2>
            <p class="mb-6 text-gray-600">
                We encountered an unexpected error. Please try refreshing the page or contact support if the problem persists.
            </p>

            <div class="space-y-3">
                <button @click="retry" class="w-full rounded-md bg-blue-600 px-4 py-2 text-white transition-colors hover:bg-blue-700">
                    Try Again
                </button>

                <button @click="goHome" class="w-full rounded-md bg-gray-100 px-4 py-2 text-gray-700 transition-colors hover:bg-gray-200">
                    Go to Dashboard
                </button>
            </div>

            <details v-if="errorDetails" class="mt-6 text-left">
                <summary class="cursor-pointer text-sm text-gray-500 hover:text-gray-700">Technical Details</summary>
                <pre class="mt-2 max-h-32 overflow-auto rounded bg-gray-100 p-3 text-xs">{{ errorDetails }}</pre>
            </details>
        </div>
    </div>

    <slot v-else />
</template>

<script setup lang="ts">
import { router } from '@inertiajs/vue3';
import { onErrorCaptured, ref } from 'vue';

const hasError = ref(false);
const errorDetails = ref<string>('');

onErrorCaptured((error: Error) => {
    hasError.value = true;
    errorDetails.value = error.stack || error.message;
    console.error('Error caught by ErrorBoundary:', error);
    return false; // Prevent error from propagating
});

const retry = () => {
    hasError.value = false;
    errorDetails.value = '';
    window.location.reload();
};

const goHome = () => {
    router.visit('/');
};
</script>
