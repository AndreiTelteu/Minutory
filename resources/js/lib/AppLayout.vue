<template>
    <ErrorBoundary>
        <div class="min-h-screen bg-gray-50">
            <!-- Navigation -->
            <nav class="border-b border-gray-200 bg-white shadow-sm">
                <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
                    <div class="flex h-16 justify-between">
                        <div class="flex items-center space-x-8">
                            <!-- Logo -->
                            <Link :href="route('home')" class="flex items-center">
                                <h1 class="text-xl font-bold text-gray-900">MeetingAI</h1>
                            </Link>

                            <!-- Navigation Links -->
                            <div class="hidden space-x-6 md:flex">
                                <Link
                                    :href="route('home')"
                                    :class="[
                                        'rounded-md px-3 py-2 text-sm font-medium transition-colors',
                                        $page.component === 'Dashboard'
                                            ? 'bg-blue-100 text-blue-700'
                                            : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900',
                                    ]"
                                >
                                    Dashboard
                                </Link>
                                <Link
                                    :href="route('clients.index')"
                                    :class="[
                                        'rounded-md px-3 py-2 text-sm font-medium transition-colors',
                                        $page.component.startsWith('Clients/')
                                            ? 'bg-blue-100 text-blue-700'
                                            : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900',
                                    ]"
                                >
                                    Clients
                                </Link>
                                <Link
                                    :href="route('meetings.index')"
                                    :class="[
                                        'rounded-md px-3 py-2 text-sm font-medium transition-colors',
                                        $page.component.startsWith('Meetings/')
                                            ? 'bg-blue-100 text-blue-700'
                                            : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900',
                                    ]"
                                >
                                    Meetings
                                </Link>
                                <Link
                                    :href="route('ai.chat')"
                                    :class="[
                                        'rounded-md px-3 py-2 text-sm font-medium transition-colors',
                                        $page.component.startsWith('AI/')
                                            ? 'bg-blue-100 text-blue-700'
                                            : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900',
                                    ]"
                                >
                                    AI Assistant
                                </Link>
                            </div>
                        </div>

                        <!-- Mobile menu button -->
                        <div class="flex items-center md:hidden">
                            <button
                                @click="mobileMenuOpen = !mobileMenuOpen"
                                class="text-gray-600 hover:text-gray-900 focus:text-gray-900 focus:outline-none"
                            >
                                <svg class="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path
                                        v-if="!mobileMenuOpen"
                                        stroke-linecap="round"
                                        stroke-linejoin="round"
                                        stroke-width="2"
                                        d="M4 6h16M4 12h16M4 18h16"
                                    />
                                    <path v-else stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                                </svg>
                            </button>
                        </div>
                    </div>

                    <!-- Mobile menu -->
                    <div v-if="mobileMenuOpen" class="border-t border-gray-200 py-4 md:hidden">
                        <div class="space-y-2">
                            <Link
                                :href="route('home')"
                                :class="[
                                    'block rounded-md px-3 py-2 text-sm font-medium transition-colors',
                                    $page.component === 'Dashboard'
                                        ? 'bg-blue-100 text-blue-700'
                                        : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900',
                                ]"
                            >
                                Dashboard
                            </Link>
                            <Link
                                :href="route('clients.index')"
                                :class="[
                                    'block rounded-md px-3 py-2 text-sm font-medium transition-colors',
                                    $page.component.startsWith('Clients/')
                                        ? 'bg-blue-100 text-blue-700'
                                        : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900',
                                ]"
                            >
                                Clients
                            </Link>
                            <Link
                                :href="route('meetings.index')"
                                :class="[
                                    'block rounded-md px-3 py-2 text-sm font-medium transition-colors',
                                    $page.component.startsWith('Meetings/')
                                        ? 'bg-blue-100 text-blue-700'
                                        : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900',
                                ]"
                            >
                                Meetings
                            </Link>
                            <Link
                                :href="route('ai.chat')"
                                :class="[
                                    'block rounded-md px-3 py-2 text-sm font-medium transition-colors',
                                    $page.component.startsWith('AI/')
                                        ? 'bg-blue-100 text-blue-700'
                                        : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900',
                                ]"
                            >
                                AI Assistant
                            </Link>
                        </div>
                    </div>
                </div>
            </nav>

            <!-- Enhanced Flash Messages -->
            <Transition
                name="slide-down"
                enter-active-class="transition-all duration-300 ease-out"
                enter-from-class="-translate-y-full opacity-0"
                enter-to-class="translate-y-0 opacity-100"
                leave-active-class="transition-all duration-300 ease-in"
                leave-from-class="translate-y-0 opacity-100"
                leave-to-class="-translate-y-full opacity-0"
            >
                <div v-if="$page.props.flash?.success" class="mb-6 border-l-4 border-green-400 bg-green-50 p-4">
                    <div class="flex items-start justify-between">
                        <div class="flex">
                            <div class="flex-shrink-0">
                                <svg class="h-5 w-5 text-green-400" fill="currentColor" viewBox="0 0 20 20">
                                    <path
                                        fill-rule="evenodd"
                                        d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                                        clip-rule="evenodd"
                                    />
                                </svg>
                            </div>
                            <div class="ml-3">
                                <p class="text-sm text-green-700">{{ $page.props.flash.success }}</p>
                            </div>
                        </div>
                        <button @click="clearFlashMessage('success')" class="text-green-400 transition-colors hover:text-green-600">
                            <svg class="h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
                                <path
                                    fill-rule="evenodd"
                                    d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                                    clip-rule="evenodd"
                                />
                            </svg>
                        </button>
                    </div>
                </div>
            </Transition>

            <Transition
                name="slide-down"
                enter-active-class="transition-all duration-300 ease-out"
                enter-from-class="-translate-y-full opacity-0"
                enter-to-class="translate-y-0 opacity-100"
                leave-active-class="transition-all duration-300 ease-in"
                leave-from-class="translate-y-0 opacity-100"
                leave-to-class="-translate-y-full opacity-0"
            >
                <div v-if="$page.props.flash?.error" class="mb-6 border-l-4 border-red-400 bg-red-50 p-4">
                    <div class="flex items-start justify-between">
                        <div class="flex">
                            <div class="flex-shrink-0">
                                <svg class="h-5 w-5 text-red-400" fill="currentColor" viewBox="0 0 20 20">
                                    <path
                                        fill-rule="evenodd"
                                        d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                                        clip-rule="evenodd"
                                    />
                                </svg>
                            </div>
                            <div class="ml-3">
                                <p class="text-sm text-red-700">{{ $page.props.flash.error }}</p>
                            </div>
                        </div>
                        <button @click="clearFlashMessage('error')" class="text-red-400 transition-colors hover:text-red-600">
                            <svg class="h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
                                <path
                                    fill-rule="evenodd"
                                    d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                                    clip-rule="evenodd"
                                />
                            </svg>
                        </button>
                    </div>
                </div>
            </Transition>

            <!-- Main Content -->
            <main>
                <slot />
            </main>
        </div>

        <!-- Global Components -->
        <Toast ref="toastComponent" />
        <NetworkStatus />
    </ErrorBoundary>
</template>

<script setup lang="ts">
import { Link, router } from '@inertiajs/vue3';
import { ref } from 'vue';
import ErrorBoundary from './ErrorBoundary.vue';
import NetworkStatus from './NetworkStatus.vue';
import Toast from './Toast.vue';

const mobileMenuOpen = ref(false);
const toastComponent = ref();

const clearFlashMessage = (_type: 'success' | 'error') => {
    router.reload({ only: [] });
};
</script>
