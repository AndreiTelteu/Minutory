<template>
    <AppLayout>
        <div class="mx-auto max-w-2xl px-6 py-8 lg:px-10">
            <div class="mb-6">
                <Link
                    :href="route('clients.index')"
                    class="inline-flex items-center gap-1 text-[13px] font-medium text-ink-secondary transition-colors duration-150 hover:text-ink"
                >
                    <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
                    </svg>
                    Clients
                </Link>
                <h1 class="mt-2 text-[20px] font-semibold tracking-tight">Add client</h1>
                <p class="mt-0.5 text-[13px] text-ink-secondary">Add a client to organize meetings.</p>
            </div>

            <form @submit.prevent="submit" class="space-y-5 rounded-lg border border-border bg-ground-raised p-6">
                <div class="grid grid-cols-1 gap-5 sm:grid-cols-2">
                    <div class="sm:col-span-2">
                        <label for="name" class="mb-1.5 block text-[13px] font-medium">Name</label>
                        <input
                            id="name"
                            v-model="form.name"
                            type="text"
                            required
                            placeholder="Jane Cooper"
                            class="w-full rounded-md border bg-ground-raised px-3 py-2 text-[13px] text-ink placeholder:text-ink-tertiary focus:ring-2 focus:outline-none"
                            :class="form.errors.name ? 'border-red-400 focus:ring-red-400/30' : 'border-border-strong focus:border-accent focus:ring-accent/30'"
                        />
                        <p v-if="form.errors.name" class="mt-1 text-[12px] text-red-600 dark:text-red-400">{{ form.errors.name }}</p>
                    </div>

                    <div class="sm:col-span-2">
                        <label for="email" class="mb-1.5 block text-[13px] font-medium">Email</label>
                        <input
                            id="email"
                            v-model="form.email"
                            type="email"
                            placeholder="jane@company.com"
                            class="w-full rounded-md border bg-ground-raised px-3 py-2 text-[13px] text-ink placeholder:text-ink-tertiary focus:ring-2 focus:outline-none"
                            :class="form.errors.email ? 'border-red-400 focus:ring-red-400/30' : 'border-border-strong focus:border-accent focus:ring-accent/30'"
                        />
                        <p v-if="form.errors.email" class="mt-1 text-[12px] text-red-600 dark:text-red-400">{{ form.errors.email }}</p>
                    </div>

                    <div>
                        <label for="company" class="mb-1.5 block text-[13px] font-medium">Company</label>
                        <input
                            id="company"
                            v-model="form.company"
                            type="text"
                            placeholder="Acme Corp"
                            class="w-full rounded-md border bg-ground-raised px-3 py-2 text-[13px] text-ink placeholder:text-ink-tertiary focus:ring-2 focus:outline-none"
                            :class="form.errors.company ? 'border-red-400 focus:ring-red-400/30' : 'border-border-strong focus:border-accent focus:ring-accent/30'"
                        />
                        <p v-if="form.errors.company" class="mt-1 text-[12px] text-red-600 dark:text-red-400">{{ form.errors.company }}</p>
                    </div>

                    <div>
                        <label for="phone" class="mb-1.5 block text-[13px] font-medium">Phone</label>
                        <input
                            id="phone"
                            v-model="form.phone"
                            type="tel"
                            placeholder="+1 (555) 000-0000"
                            class="w-full rounded-md border bg-ground-raised px-3 py-2 text-[13px] text-ink placeholder:text-ink-tertiary focus:ring-2 focus:outline-none"
                            :class="form.errors.phone ? 'border-red-400 focus:ring-red-400/30' : 'border-border-strong focus:border-accent focus:ring-accent/30'"
                        />
                        <p v-if="form.errors.phone" class="mt-1 text-[12px] text-red-600 dark:text-red-400">{{ form.errors.phone }}</p>
                    </div>
                </div>

                <div class="flex justify-end gap-2 border-t border-border pt-5">
                    <Link
                        :href="route('clients.index')"
                        class="rounded-md border border-border-strong px-3 py-1.5 text-[13px] font-medium text-ink transition-colors duration-150 hover:bg-ground-subtle"
                    >
                        Cancel
                    </Link>
                    <button
                        type="submit"
                        :disabled="form.processing"
                        class="rounded-md bg-accent-solid px-4 py-1.5 text-[13px] font-medium text-white transition-colors duration-150 hover:bg-accent-solid-hover disabled:cursor-not-allowed disabled:opacity-50"
                    >
                        {{ form.processing ? 'Creating…' : 'Add client' }}
                    </button>
                </div>
            </form>
        </div>
    </AppLayout>
</template>

<script setup lang="ts">
import AppLayout from '@/lib/AppLayout.vue';
import { Link, useForm } from '@inertiajs/vue3';

const form = useForm({
    name: '',
    email: '',
    company: '',
    phone: '',
});

const submit = () => {
    form.post(route('clients.store'));
};
</script>
