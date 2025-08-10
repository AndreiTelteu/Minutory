<template>
    <AppLayout>
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
            <div class="mb-8">
                <Link :href="route('meetings.index')" class="text-blue-600 hover:text-blue-700 font-medium">
                ← Back to Meetings
                </Link>
                <div class="flex justify-between items-start mt-4">
                    <div>
                        <h1 class="text-3xl font-bold text-gray-900">{{ meeting.title }}</h1>
                        <div class="flex items-center space-x-4 mt-2">
                            <p class="text-gray-600">
                                Client: {{ meeting.client.name }}
                            </p>
                            <MeetingStatusBadge :status="meeting.status" />
                        </div>
                    </div>
                </div>
            </div>

            <!-- Video Player -->
            <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
                <h2 class="text-lg font-semibold text-gray-900 mb-4">Video</h2>

                <div v-if="meeting.status === 'pending'" class="text-center py-12">
                    <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
                    <p class="text-gray-600">Meeting is queued for processing...</p>
                </div>

                <div v-else-if="videoUrl" class="space-y-4">
                    <video controls class="w-full rounded-lg" :src="videoUrl">
                        Your browser does not support the video tag.
                    </video>
                </div>

                <div v-else class="text-center py-12">
                    <p class="text-gray-600">Video not available</p>
                </div>
            </div>
        </div>
    </AppLayout>
</template>

<script setup lang="ts">
import { Link } from '@inertiajs/vue3'
import AppLayout from '@/lib/AppLayout.vue'
import MeetingStatusBadge from '@/lib/MeetingStatusBadge.vue'

interface Client {
    id: number
    name: string
}

interface Meeting {
    id: number
    title: string
    client: Client
    status: 'pending' | 'processing' | 'completed' | 'failed'
    uploaded_at: string
    duration: number | null
}

interface Props {
    meeting: Meeting
    videoUrl: string | null
}

defineProps<Props>()
</script>