<template>
    <section v-if="open" class="mt-6 rounded-lg border border-border bg-ground-raised p-5">
        <header class="mb-4">
            <h2 class="text-[15px] font-semibold">Speakers</h2>
            <p class="mt-0.5 text-[12px] text-ink-secondary">Match detected labels to people for {{ clientName }}.</p>
        </header>

        <div class="overflow-x-auto">
            <table class="w-full min-w-[620px] text-left">
                <thead class="text-[11px] font-medium tracking-[0.05em] text-ink-tertiary uppercase">
                    <tr class="border-b border-border">
                        <th class="pb-2 pr-4">Detected label</th>
                        <th class="pb-2 pr-4">Segments</th>
                        <th class="pb-2">Person</th>
                    </tr>
                </thead>
                <tbody>
                    <template v-for="row in rows" :key="row.key">
                    <tr class="border-b border-border last:border-0">
                        <td class="py-3 pr-4 align-center text-[13px] font-medium">{{ row.label }}</td>
                        <td class="py-3 pr-4 align-center">
                            <div class="flex max-w-md flex-row flex-nowrap items-center gap-1 overflow-hidden">
                                <button
                                    v-for="segment in row.segments.slice(0, 10)"
                                    :key="segment.id"
                                    class="tnum shrink-0 rounded border border-border-strong px-2 py-0.5 text-[11px] text-ink-secondary transition-colors duration-150 hover:bg-ground-subtle hover:text-ink"
                                    @click="emit('seek', segment.start_time)"
                                >
                                    {{ formatTime(segment.start_time) }}
                                </button>
                                <span v-if="row.segments.length > 10" class="tnum shrink-0 px-1.5 py-0.5 text-[11px] font-medium text-ink-tertiary">
                                    +{{ row.segments.length - 10 }}
                                </span>
                            </div>
                        </td>
                        <td class="py-2 align-center">
                            <div class="relative max-w-sm">
                                <input
                                    v-model="queries[row.key]"
                                    class="w-full rounded-md border border-border-strong bg-ground-raised px-2.5 py-1.5 text-[13px] focus:border-accent focus:ring-2 focus:ring-accent/30 focus:outline-none"
                                    :placeholder="selectedPerson(row)?.name || 'Leave unassigned'"
                                    @focus="activeRow = row.key"
                                    @blur="closeOptions(row.key)"
                                    @input="clearSelection(row)"
                                />
                                <div v-if="activeRow === row.key" class="absolute z-10 mt-1 w-full overflow-hidden rounded-md border border-border bg-ground-raised shadow-lg">
                                    <button
                                        v-for="person in matchingPeople(row)"
                                        :key="person.id"
                                        class="block w-full px-3 py-2 text-left text-[13px] hover:bg-ground-subtle"
                                        @mousedown.prevent="selectPerson(row, person)"
                                    >
                                        <span class="font-medium">{{ person.name }}</span>
                                        <span v-if="person.email" class="ml-1 text-ink-tertiary">{{ person.email }}</span>
                                    </button>
                                    <button
                                        v-if="canCreate(row)"
                                        class="block w-full border-t border-border px-3 py-2 text-left text-[13px] font-medium text-accent hover:bg-ground-subtle"
                                        @mousedown.prevent="openCreate(row)"
                                    >
                                        Create “{{ queries[row.key].trim() }}”
                                    </button>
                                </div>
                            </div>
                        </td>
                    </tr>
                    <tr v-if="createRow?.key === row.key" class="border-b border-border last:border-0">
                        <td colspan="3" class="py-3">
                            <form class="flex flex-wrap items-end gap-3" @submit.prevent="createPerson">
                                <div class="min-w-48 flex-1">
                                    <label class="block text-[12px] font-medium text-ink-secondary">New person</label>
                                    <input v-model="newPerson.name" class="mt-1 w-full rounded-md border border-border-strong bg-ground-raised px-2.5 py-1.5 text-[13px] focus:border-accent focus:outline-none" />
                                </div>
                                <div class="min-w-48 flex-1">
                                    <label class="block text-[12px] font-medium text-ink-secondary">Email <span class="font-normal text-ink-tertiary">optional</span></label>
                                    <input v-model="newPerson.email" type="email" class="mt-1 w-full rounded-md border border-border-strong bg-ground-raised px-2.5 py-1.5 text-[13px] focus:border-accent focus:outline-none" />
                                </div>
                                <button type="button" class="rounded-md border border-border-strong px-3 py-1.5 text-[13px] font-medium text-ink-secondary hover:bg-ground-subtle" @click="createRow = null">Cancel</button>
                                <button type="submit" class="rounded-md bg-accent-solid px-3 py-1.5 text-[13px] font-medium text-white hover:bg-accent-solid-hover disabled:opacity-50" :disabled="creating || !newPerson.name.trim()">
                                    {{ creating ? 'Creating…' : 'Create person' }}
                                </button>
                            </form>
                            <p v-if="createError" class="mt-2 text-[12px] text-red-600">{{ createError }}</p>
                        </td>
                    </tr>
                    </template>
                </tbody>
            </table>
        </div>

        <footer class="mt-4 flex justify-end gap-2">
            <button class="rounded-md border border-border-strong px-3 py-1.5 text-[13px] font-medium text-ink-secondary hover:bg-ground-subtle" @click="emit('close')">
                Cancel
            </button>
            <button class="rounded-md bg-accent-solid px-3 py-1.5 text-[13px] font-medium text-white hover:bg-accent-solid-hover disabled:opacity-50" :disabled="saving" @click="save">
                {{ saving ? 'Saving…' : 'Save speakers' }}
            </button>
        </footer>
    </section>
</template>

<script setup lang="ts">
import { router } from '@inertiajs/vue3';
import { computed, reactive, ref, watch } from 'vue';

interface Person { id: number; name: string; email: string | null }
interface Segment { id: number; detected_speaker: string | null; speaker: string | null; start_time: number; person_id?: number | null }
interface Row { key: string; label: string; segments: Segment[] }

const props = defineProps<{ open: boolean; meetingId: number; clientName: string; people: Person[]; transcriptions: Segment[] }>();
const emit = defineEmits<{ close: []; seek: [time: number] }>();
const people = ref<Person[]>([]);
const activeRow = ref<string | null>(null);
const queries = reactive<Record<string, string>>({});
const selectedPersonIds = reactive<Record<string, number | null>>({});
const saving = ref(false);
const createRow = ref<Row | null>(null);
const newPerson = reactive({ name: '', email: '' });
const creating = ref(false);
const createError = ref('');

const rows = computed<Row[]>(() => {
    const grouped = new Map<string, Segment[]>();
    props.transcriptions.forEach((segment) => {
        const key = segment.detected_speaker?.trim() || '__unknown__';
        grouped.set(key, [...(grouped.get(key) ?? []), segment]);
    });

    return [...grouped.entries()].map(([key, segments]) => ({
        key,
        label: key === '__unknown__' ? 'Unknown Speaker' : key,
        segments,
    }));
});

watch(() => [props.open, props.people, props.transcriptions] as const, () => {
    people.value = [...props.people];
    rows.value.forEach((row) => {
        const personId = row.segments.find((segment) => segment.person_id)?.person_id ?? null;
        selectedPersonIds[row.key] = personId;
        queries[row.key] = personId ? (people.value.find((person) => person.id === personId)?.name ?? '') : '';
    });
}, { immediate: true, deep: true });

const selectedPerson = (row: Row) => people.value.find((person) => person.id === selectedPersonIds[row.key]);
const matchingPeople = (row: Row) => {
    const query = (queries[row.key] ?? '').trim().toLowerCase();
    return people.value.filter((person) => !query || person.name.toLowerCase().includes(query)).slice(0, 6);
};
const clearSelection = (row: Row) => { selectedPersonIds[row.key] = null; };
const closeOptions = (key: string) => window.setTimeout(() => { if (activeRow.value === key) activeRow.value = null; }, 150);
const selectPerson = (row: Row, person: Person) => { selectedPersonIds[row.key] = person.id; queries[row.key] = person.name; activeRow.value = null; };
const canCreate = (row: Row) => {
    const name = (queries[row.key] ?? '').trim();
    return name.length > 0 && !people.value.some((person) => person.name.toLowerCase() === name.toLowerCase());
};
const openCreate = (row: Row) => { createRow.value = row; newPerson.name = queries[row.key].trim(); newPerson.email = ''; createError.value = ''; activeRow.value = null; };
const formatTime = (seconds: number) => `${Math.floor(seconds / 60)}:${Math.floor(seconds % 60).toString().padStart(2, '0')}`;

const createPerson = async () => {
    if (!createRow.value) return;
    creating.value = true;
    createError.value = '';

    try {
        const response = await fetch(route('meetings.people.store', props.meetingId), {
            method: 'POST',
            headers: {
                Accept: 'application/json',
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRF-TOKEN': document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')?.content ?? '',
            },
            body: JSON.stringify({ name: newPerson.name.trim(), email: newPerson.email.trim() || null }),
        });
        const body = await response.json();
        if (!response.ok) throw new Error(body.message ?? 'Could not create the person.');

        people.value.push(body.person);
        selectPerson(createRow.value, body.person);
        createRow.value = null;
    } catch (error) {
        createError.value = error instanceof Error ? error.message : 'Could not create the person.';
    } finally {
        creating.value = false;
    }
};

const save = () => {
    saving.value = true;
    router.put(route('meetings.speakers.update', props.meetingId), {
        assignments: rows.value.map((row) => ({
            speaker: row.key === '__unknown__' ? null : row.key,
            person_id: selectedPersonIds[row.key],
        })),
    }, {
        preserveScroll: true,
        onSuccess: () => emit('close'),
        onFinish: () => { saving.value = false; },
    });
};
</script>
