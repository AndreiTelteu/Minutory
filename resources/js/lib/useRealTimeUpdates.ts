import { ref, onMounted, onUnmounted } from 'vue'
import axios from 'axios'

interface Meeting {
  id: number
  status: 'pending' | 'processing' | 'completed' | 'failed'
  elapsed_time?: number | null
  estimated_remaining_time?: number | null
  processing_progress?: number | null
  formatted_elapsed_time?: string | null
  formatted_estimated_remaining_time?: string | null
  queue_progress?: number | null
}

export function useRealTimeUpdates(meetings: Meeting[]) {
  const updatedMeetings = ref<Meeting[]>([...meetings])
  let intervalId: number | null = null

  const updateMeetingStatuses = async () => {
    // Only update meetings that are pending or processing
    const activeMeetings = updatedMeetings.value.filter(
      meeting => meeting.status === 'pending' || meeting.status === 'processing'
    )

    if (activeMeetings.length === 0) {
      return
    }

    try {
      // Update each active meeting
      const updatePromises = activeMeetings.map(async (meeting) => {
        try {
          const response = await axios.get(`/meetings/${meeting.id}/status`)
          const updatedData = response.data

          // Find and update the meeting in our array
          const index = updatedMeetings.value.findIndex(m => m.id === meeting.id)
          if (index !== -1) {
            updatedMeetings.value[index] = {
              ...updatedMeetings.value[index],
              ...updatedData
            }
          }
        } catch (error) {
          console.error(`Failed to update status for meeting ${meeting.id}:`, error)
        }
      })

      await Promise.all(updatePromises)
    } catch (error) {
      console.error('Failed to update meeting statuses:', error)
    }
  }

  const startUpdates = () => {
    // Update immediately
    updateMeetingStatuses()
    
    // Then update every 2 seconds
    intervalId = window.setInterval(updateMeetingStatuses, 2000)
  }

  const stopUpdates = () => {
    if (intervalId) {
      clearInterval(intervalId)
      intervalId = null
    }
  }

  onMounted(() => {
    startUpdates()
  })

  onUnmounted(() => {
    stopUpdates()
  })

  return {
    meetings: updatedMeetings,
    startUpdates,
    stopUpdates,
    updateMeetingStatuses
  }
}