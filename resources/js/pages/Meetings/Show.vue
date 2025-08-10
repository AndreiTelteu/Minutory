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

            <!-- Processing Status -->
            <div v-if="meeting.status === 'pending'" class="bg-blue-50 border border-blue-200 rounded-lg p-6 mb-6">
                <div class="flex items-center justify-between mb-4">
                    <div>
                        <h3 class="text-lg font-semibold text-blue-900">Meeting Queued for Processing</h3>
                        <p class="text-blue-700 text-sm">
                            Estimated processing time: {{ meeting.formatted_estimated_processing_time || 'Calculating...' }}
                        </p>
                    </div>
                    <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                </div>
                
                <!-- Queue Progress Bar -->
                <div class="w-full bg-blue-200 rounded-full h-2 mb-2">
                    <div 
                        class="bg-blue-600 h-2 rounded-full transition-all duration-300 ease-out"
                        :style="{ width: `${currentQueueProgress}%` }"
                    ></div>
                </div>
                <p class="text-blue-600 text-xs">
                    Queue progress: {{ Math.round(currentQueueProgress) }}%
                </p>
            </div>

            <div v-else-if="meeting.status === 'processing'" class="bg-yellow-50 border border-yellow-200 rounded-lg p-6 mb-6">
                <div class="flex items-center justify-between mb-4">
                    <div>
                        <h3 class="text-lg font-semibold text-yellow-900">Processing Meeting</h3>
                        <p class="text-yellow-700 text-sm">
                            Elapsed: {{ meeting.formatted_elapsed_time || '0:00' }} | 
                            Remaining: {{ meeting.formatted_estimated_remaining_time || 'Calculating...' }}
                        </p>
                    </div>
                    <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-yellow-600"></div>
                </div>
                
                <!-- Processing Progress Bar -->
                <div class="w-full bg-yellow-200 rounded-full h-2 mb-2">
                    <div 
                        class="bg-yellow-600 h-2 rounded-full transition-all duration-300 ease-out"
                        :style="{ width: `${meeting.processing_progress || 0}%` }"
                    ></div>
                </div>
                <p class="text-yellow-600 text-xs">
                    Processing progress: {{ Math.round(meeting.processing_progress || 0) }}%
                </p>
            </div>

            <!-- Video Player -->
            <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
                <h2 class="text-lg font-semibold text-gray-900 mb-4">Video</h2>

                <div v-if="meeting.status === 'pending'" class="text-center py-12">
                    <div class="text-gray-400 mb-4">
                        <svg class="w-16 h-16 mx-auto" fill="currentColor" viewBox="0 0 20 20">
                            <path d="M2 6a2 2 0 012-2h6l2 2h6a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6zM5 8a1 1 0 011-1h1a1 1 0 010 2H6a1 1 0 01-1-1zm6 1a1 1 0 100 2h3a1 1 0 100-2H11z"/>
                        </svg>
                    </div>
                    <p class="text-gray-600">Video will be available after processing completes</p>
                </div>

                <div v-else-if="meeting.status === 'processing'" class="text-center py-12">
                    <div class="text-gray-400 mb-4">
                        <svg class="w-16 h-16 mx-auto animate-pulse" fill="currentColor" viewBox="0 0 20 20">
                            <path d="M2 6a2 2 0 012-2h6l2 2h6a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6zM5 8a1 1 0 011-1h1a1 1 0 010 2H6a1 1 0 01-1-1zm6 1a1 1 0 100 2h3a1 1 0 100-2H11z"/>
                        </svg>
                    </div>
                    <p class="text-gray-600">Processing video...</p>
                </div>

                <div v-else-if="videoUrl" class="space-y-4">
                    <video controls class="w-full rounded-lg" :src="videoUrl">
                        Your browser does not support the video tag.
                    </video>
                </div>

                <div v-else class="text-center py-12">
                    <div class="text-red-400 mb-4">
                        <svg class="w-16 h-16 mx-auto" fill="currentColor" viewBox="0 0 20 20">
                            <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>
                        </svg>
                    </div>
                    <p class="text-gray-600">Video not available</p>
                </div>
            </div>

            <!-- Transcription Section (only show if completed) -->
            <div v-if="meeting.status === 'completed' && meeting.transcriptions && meeting.transcriptions.length > 0" 
                 class="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mt-6">
                <h2 class="text-lg font-semibold text-gray-900 mb-4">Transcription</h2>
                <div class="space-y-4">
                    <div v-for="transcription in meeting.transcriptions" :key="transcription.id" 
                         class="border-l-4 border-blue-500 pl-4 py-2">
                        <div class="flex items-center justify-between mb-1">
                            <span class="font-medium text-gray-900">{{ transcription.speaker }}</span>
                            <span class="text-sm text-gray-500">
                                {{ formatTime(transcription.start_time) }} - {{ formatTime(transcription.end_time) }}
                            </span>
                        </div>
                        <p class="text-gray-700">{{ transcription.text }}</p>
                    </div>
                </div>
            </div>
        </div>
    </AppLayout>
</template>

<script setup lang="ts">
import { Link } from '@inertiajs/vue3'
import { ref, onMounted, onUnmounted } from 'vue'
import AppLayout from '@/lib/AppLayout.vue'
import MeetingStatusBadge from '@/lib/MeetingStatusBadge.vue'

interface Client {
    id: number
    name: string
}

interface Transcription {
    id: number
    speaker: string
    text: string
    start_time: number
    end_time: number
    confidence: number
}

interface Meeting {
    id: number
    title: string
    client: Client
    status: 'pending' | 'processing' | 'completed' | 'failed'
    uploaded_at: string
    duration: number | null
    estimated_processing_time: number | null
    queue_progress: number | null
    processing_progress: number | null
    formatted_estimated_processing_time: string | null
    formatted_elapsed_time: string | null
    formatted_estimated_remaining_time: string | null
    transcriptions?: Transcription[]
}

interface Props {
    meeting: Meeting
    videoUrl: string | null
}

const props = defineProps<Props>()

// Reactive queue progress for smooth animation
const currentQueueProgress = ref(props.meeting.queue_progress || 0)
let statusInterval: NodeJS.Timeout | null = null

// Format time in seconds to MM:SS format
const formatTime = (seconds: number): string => {
    const minutes = Math.floor(seconds / 60)
    const remainingSeconds = Math.floor(seconds % 60)
    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`
}

// Poll for status updates when meeting is pending or processing
const pollStatus = async () => {
    if (props.meeting.status === 'pending' || props.meeting.status === 'processing') {
        try {
            const response = await fetch(`/meetings/${props.meeting.id}/status`)
            const data = await response.json()
            
            // Update queue progress for pending meetings
            if (props.meeting.status === 'pending' && data.queue_progress !== null) {
                currentQueueProgress.value = data.queue_progress
            }
            
            // Reload page if status changed to completed or failed
            if (data.status !== props.meeting.status) {
                window.location.reload()
            }
        } catch (error) {
            console.error('Failed to fetch meeting status:', error)
        }
    }
}

onMounted(() => {
    // Start polling for status updates every 2 seconds
    if (props.meeting.status === 'pending' || props.meeting.status === 'processing') {
        statusInterval = setInterval(pollStatus, 2000)
        // Initial poll
        pollStatus()
    }
})

onUnmounted(() => {
    if (statusInterval) {
        clearInterval(statusInterval)
    }
})
</script>