<template>
  <div class="space-y-2">
    <!-- Processing Progress -->
    <div v-if="meeting.status === 'processing'" class="space-y-2">
      <div class="flex justify-between items-center text-xs text-gray-600">
        <span>Processing Video</span>
        <span v-if="meeting.processing_progress !== null" class="font-medium">
          {{ Math.round(meeting.processing_progress) }}%
        </span>
      </div>
      
      <div class="w-full bg-gray-200 rounded-full h-2">
        <div 
          class="bg-blue-600 h-2 rounded-full transition-all duration-500 ease-out"
          :style="{ width: `${meeting.processing_progress || 0}%` }"
        ></div>
      </div>
      
      <div class="grid grid-cols-2 gap-4 text-xs text-gray-500">
        <div v-if="meeting.formatted_elapsed_time" class="flex justify-between">
          <span>Elapsed:</span>
          <span class="font-mono text-gray-700">{{ meeting.formatted_elapsed_time }}</span>
        </div>
        <div v-if="meeting.formatted_estimated_remaining_time" class="flex justify-between">
          <span>Remaining:</span>
          <span class="font-mono text-gray-700">{{ meeting.formatted_estimated_remaining_time }}</span>
        </div>
      </div>
    </div>

    <!-- Queue Progress -->
    <div v-else-if="meeting.status === 'pending'" class="space-y-2">
      <div class="flex justify-between items-center text-xs text-gray-600">
        <span>In Queue</span>
        <span v-if="meeting.queue_progress !== null" class="font-medium">
          {{ Math.round(meeting.queue_progress) }}%
        </span>
      </div>
      
      <div class="w-full bg-gray-200 rounded-full h-2">
        <div 
          class="bg-yellow-500 h-2 rounded-full transition-all duration-500 ease-out"
          :style="{ width: `${meeting.queue_progress || 0}%` }"
        ></div>
      </div>
      
      <div class="text-xs text-gray-500">
        <div v-if="meeting.formatted_estimated_processing_time" class="flex justify-between">
          <span>Est. processing time:</span>
          <span class="font-mono text-gray-700">{{ meeting.formatted_estimated_processing_time }}</span>
        </div>
      </div>
    </div>

    <!-- Completed State -->
    <div v-else-if="meeting.status === 'completed'" class="space-y-1">
      <div class="flex items-center text-xs text-green-600">
        <svg class="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
          <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
        </svg>
        <span>Transcription Complete</span>
      </div>
      <div v-if="meeting.formatted_elapsed_time" class="text-xs text-gray-500">
        Processing took {{ meeting.formatted_elapsed_time }}
      </div>
    </div>

    <!-- Failed State -->
    <div v-else-if="meeting.status === 'failed'" class="space-y-1">
      <div class="flex items-center text-xs text-red-600">
        <svg class="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
          <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
        </svg>
        <span>Processing Failed</span>
      </div>
      <div class="text-xs text-gray-500">
        Please try uploading again
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
interface Meeting {
  id: number
  status: 'pending' | 'processing' | 'completed' | 'failed'
  elapsed_time?: number | null
  estimated_remaining_time?: number | null
  processing_progress?: number | null
  formatted_elapsed_time?: string | null
  formatted_estimated_remaining_time?: string | null
  queue_progress?: number | null
  formatted_estimated_processing_time?: string | null
}

interface Props {
  meeting: Meeting
}

defineProps<Props>()
</script>