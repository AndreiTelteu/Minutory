<template>
    <AppLayout>
        <div class="mx-auto max-w-6xl px-6 py-8 lg:px-10">
            <div class="mb-6 flex flex-wrap items-center justify-between gap-3">
                <div>
                    <h1 class="text-[20px] font-semibold tracking-tight">Clients</h1>
                    <p class="mt-0.5 text-[13px] text-ink-secondary">Organize meetings by client.</p>
                </div>
                <Link
                    :href="route('clients.create')"
                    class="rounded-md bg-accent-solid px-3 py-1.5 text-[13px] font-medium text-white transition-colors duration-150 hover:bg-accent-solid-hover"
                >
                    Add client
                </Link>
            </div>

            <div class="overflow-hidden rounded-lg border border-border bg-ground-raised">
                <div v-if="clients.length === 0" class="px-5 py-16 text-center">
                    <p class="text-[13px] text-ink-secondary">No clients yet.</p>
                    <Link :href="route('clients.create')" class="mt-1 inline-block text-[13px] font-medium text-accent hover:text-accent-hover">
                        Add your first client
                    </Link>
                </div>

                <div v-else class="overflow-x-auto">
                    <table class="w-full">
                        <thead>
                            <tr class="border-b border-border bg-ground-subtle text-left">
                                <th class="px-5 py-2 text-[11px] font-medium tracking-[0.05em] text-ink-tertiary uppercase">Name</th>
                                <th class="px-5 py-2 text-[11px] font-medium tracking-[0.05em] text-ink-tertiary uppercase">Company</th>
                                <th class="px-5 py-2 text-[11px] font-medium tracking-[0.05em] text-ink-tertiary uppercase">Email</th>
                                <th class="px-5 py-2 text-[11px] font-medium tracking-[0.05em] text-ink-tertiary uppercase">Phone</th>
                                <th class="px-5 py-2 text-[11px] font-medium tracking-[0.05em] text-ink-tertiary uppercase">Meetings</th>
                                <th class="px-5 py-2" />
                            </tr>
                        </thead>
                        <tbody>
                            <tr
                                v-for="client in clients"
                                :key="client.id"
                                class="cursor-pointer border-b border-border transition-colors duration-150 last:border-0 hover:bg-ground-subtle"
                                @click="router.visit(route('clients.show', client.id))"
                            >
                                <td class="px-5 py-2.5 text-[13px] font-medium">{{ client.name }}</td>
                                <td class="px-5 py-2.5 text-[13px] text-ink-secondary">{{ client.company || '—' }}</td>
                                <td class="px-5 py-2.5 text-[13px] text-ink-secondary">{{ client.email || '—' }}</td>
                                <td class="tnum px-5 py-2.5 text-[13px] text-ink-secondary">{{ client.phone || '—' }}</td>
                                <td class="tnum px-5 py-2.5 text-[13px] text-ink-secondary">{{ client.meetings_count }}</td>
                                <td class="px-5 py-2.5 text-right">
                                    <div class="flex items-center justify-end gap-1">
                                        <Link
                                            :href="route('clients.edit', client.id)"
                                            @click.stop
                                            class="rounded p-1 text-ink-tertiary transition-colors duration-150 hover:bg-ground-raised hover:text-ink"
                                            aria-label="Edit client"
                                        >
                                            <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                                                <path
                                                    stroke-linecap="round"
                                                    stroke-linejoin="round"
                                                    d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L6.832 19.82a4.5 4.5 0 01-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 011.13-1.897L16.863 4.487zm0 0L19.5 7.125"
                                                />
                                            </svg>
                                        </Link>
                                        <button
                                            @click.stop="deleteClient(client)"
                                            :disabled="(client.meetings_count ?? 0) > 0"
                                            class="rounded p-1 text-ink-tertiary transition-colors duration-150 hover:bg-red-50 hover:text-red-600 disabled:cursor-not-allowed disabled:opacity-40 dark:hover:bg-red-950/40 dark:hover:text-red-400"
                                            aria-label="Delete client"
                                            :title="(client.meetings_count ?? 0) > 0 ? 'Cannot delete a client with meetings' : 'Delete client'"
                                        >
                                            <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                                                <path
                                                    stroke-linecap="round"
                                                    stroke-linejoin="round"
                                                    d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"
                                                />
                                            </svg>
                                        </button>
                                    </div>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </AppLayout>
</template>

<script setup lang="ts">
import AppLayout from '@/lib/AppLayout.vue';
import type { Client } from '@/types';
import { Link, router } from '@inertiajs/vue3';

interface Props {
    clients: Client[];
}

defineProps<Props>();

const deleteClient = (client: Client) => {
    if ((client.meetings_count ?? 0) > 0) {
        alert('Cannot delete client with existing meetings.');
        return;
    }
    if (confirm(`Are you sure you want to delete ${client.name}?`)) {
        router.delete(route('clients.destroy', client.id));
    }
};
</script>
