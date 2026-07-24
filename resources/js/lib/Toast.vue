<template>
    <Teleport to="body">
        <div class="fixed inset-x-4 top-4 z-50 sm:left-auto sm:right-4">
            <TransitionGroup name="toast" tag="div" class="space-y-2">
                <div
                    v-for="toast in toasts"
                    :key="toast.id"
                    class="pointer-events-auto w-full max-w-sm rounded-lg border border-border bg-ground-raised shadow-[0_4px_12px_rgb(0_0_0/0.08)] dark:shadow-[0_4px_12px_rgb(0_0_0/0.24)]"
                >
                    <div class="flex items-start gap-2.5 p-3.5">
                        <svg v-if="toast.type === 'success'" class="mt-0.5 h-4 w-4 shrink-0 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        <svg v-else-if="toast.type === 'error'" class="mt-0.5 h-4 w-4 shrink-0 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
                        </svg>
                        <svg v-else-if="toast.type === 'warning'" class="mt-0.5 h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
                        </svg>
                        <svg v-else class="mt-0.5 h-4 w-4 shrink-0 text-accent" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z" />
                        </svg>

                        <div class="min-w-0 flex-1">
                            <p class="text-[13px] font-medium text-ink">{{ toast.title }}</p>
                            <p v-if="toast.message" class="mt-0.5 text-[12px] text-ink-secondary">{{ toast.message }}</p>

                            <div v-if="toast.actions && toast.actions.length > 0" class="mt-2.5 flex gap-2">
                                <button
                                    v-for="action in toast.actions"
                                    :key="action.label"
                                    @click="action.handler"
                                    :class="[
                                        'rounded-md px-2.5 py-1 text-[12px] font-medium transition-colors duration-150',
                                        action.primary
                                            ? 'bg-accent-solid text-white hover:bg-accent-solid-hover'
                                            : 'border border-border-strong text-ink hover:bg-ground-subtle',
                                    ]"
                                >
                                    {{ action.label }}
                                </button>
                            </div>
                        </div>

                        <button @click="removeToast(toast.id)" class="shrink-0 rounded p-0.5 text-ink-tertiary transition-colors hover:text-ink" aria-label="Close">
                            <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
                            </svg>
                        </button>
                    </div>
                </div>
            </TransitionGroup>
        </div>
    </Teleport>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';

export interface ToastAction {
    label: string;
    handler: () => void;
    primary?: boolean;
}

export interface Toast {
    id: string;
    type: 'success' | 'error' | 'warning' | 'info';
    title: string;
    message?: string;
    duration?: number;
    actions?: ToastAction[];
}

const toasts = ref<Toast[]>([]);

const addToast = (toast: Omit<Toast, 'id'>) => {
    const id = Math.random().toString(36).substr(2, 9);
    const newToast = { ...toast, id };

    toasts.value.push(newToast);

    if (toast.duration !== 0) {
        setTimeout(() => {
            removeToast(id);
        }, toast.duration || 5000);
    }

    return id;
};

const removeToast = (id: string) => {
    const index = toasts.value.findIndex((t) => t.id === id);
    if (index > -1) {
        toasts.value.splice(index, 1);
    }
};

const clearAll = () => {
    toasts.value = [];
};

const showSuccess = (title: string, message?: string, options?: Partial<Toast>) => {
    return addToast({ type: 'success', title, message, ...options });
};

const showError = (title: string, message?: string, options?: Partial<Toast>) => {
    return addToast({ type: 'error', title, message, ...options });
};

const showWarning = (title: string, message?: string, options?: Partial<Toast>) => {
    return addToast({ type: 'warning', title, message, ...options });
};

const showInfo = (title: string, message?: string, options?: Partial<Toast>) => {
    return addToast({ type: 'info', title, message, ...options });
};

onMounted(() => {
    window.toast = {
        success: showSuccess,
        error: showError,
        warning: showWarning,
        info: showInfo,
        remove: removeToast,
        clear: clearAll,
    };
});

defineExpose({
    addToast,
    removeToast,
    clearAll,
    showSuccess,
    showError,
    showWarning,
    showInfo,
});
</script>

<style scoped>
.toast-enter-active,
.toast-leave-active {
    transition: all 0.25s ease-out;
}

.toast-enter-from {
    opacity: 0;
    transform: translateX(1rem);
}

.toast-leave-to {
    opacity: 0;
    transform: translateX(1rem);
}

.toast-move {
    transition: transform 0.25s ease-out;
}
</style>
