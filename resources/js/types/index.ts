export interface Client {
  id: number
  name: string
  email?: string
  company?: string
  phone?: string
  meetings_count?: number
  created_at: string
  updated_at: string
}

export interface Meeting {
  id: number
  title: string
  client_id: number
  client: Client
  status: 'pending' | 'processing' | 'completed' | 'failed'
  video_path: string
  duration: number | null
  uploaded_at: string
  processing_started_at: string | null
  processing_completed_at: string | null
  created_at: string
  updated_at: string
  transcriptions?: Transcription[]
}

export interface Transcription {
  id: number
  meeting_id: number
  speaker: string
  text: string
  start_time: number
  end_time: number
  confidence: number
  created_at: string
  updated_at: string
  meeting?: Meeting
}

export interface PaginatedResponse<T> {
  data: T[]
  links: Array<{
    url: string | null
    label: string
    active: boolean
  }>
  from: number
  to: number
  total: number
  current_page: number
  last_page: number
  per_page: number
}

export type PaginatedMeetings = PaginatedResponse<Meeting>
export type PaginatedClients = PaginatedResponse<Client>