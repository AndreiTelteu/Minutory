import { shallowRef, onMounted, onUnmounted } from 'vue'
import axios from 'axios'

interface BaseMeeting {
  id: number
  status: 'pending' | 'processing' | 'completed' | 'failed'
  elapsed_time?: number | null
  estimated_remaining_time?: number | null
  processing_progress?: number | null
  formatted_elapsed_time?: string | null
  formatted_estimated_remaining_time?: string | null
  queue_progress?: number | null
}

/**
 * Generic real-time updates composable that preserves extra fields on meeting objects.
 */
export function useRealTimeUpdates<T extends BaseMeeting>(meetings: T[]) {
  const updatedMeetings = shallowRef<T[]>([...meetings])
  let intervalId: number | null = null

  const updateMeetingStatuses = async () => {
    // Only update meetings that are pending or processing
    const activeMeetings = updatedMeetings.value.filter(
      (meeting) => meeting.status === 'pending' || meeting.status === 'processing'
    )

    if (activeMeetings.length === 0) {
      return
    }

    try {
      // Update each active meeting
      const updatePromises = activeMeetings.map(async (meeting) => {
        try {
          const response = await axios.get(`/meetings/${meeting.id}/status`)
          const updatedData = response.data as Partial<T>

          // Find and update the meeting in our array
          const index = updatedMeetings.value.findIndex((m) => m.id === meeting.id)
          if (index !== -1) {
            // Preserve existing fields while merging updated status data
            updatedMeetings.value[index] = {
              ...(updatedMeetings.value[index] as T),
              ...(updatedData as T),
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
    updateMeetingStatuses,
  }
}