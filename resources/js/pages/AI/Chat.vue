<template>
  <AppLayout>
    <div class="max-w-4xl mx-auto py-8 px-4">
      <div class="bg-white rounded-lg shadow-lg overflow-hidden">
        <!-- Header -->
        <div class="bg-blue-600 text-white p-6">
          <h1 class="text-2xl font-bold">AI Meeting Assistant</h1>
          <p class="text-blue-100 mt-2">
            Ask me anything about your meetings. I can search through transcriptions and help you find specific information.
          </p>
        </div>

        <!-- Chat Messages -->
        <div class="h-96 overflow-y-auto p-6 space-y-4" ref="messagesContainer">
          <div v-if="messages.length === 0" class="text-center text-gray-500 py-8">
            <div class="text-4xl mb-4">🤖</div>
            <p>Hi! I'm your AI meeting assistant. Ask me to search through your meeting transcriptions.</p>
            <div class="mt-4 text-sm">
              <p class="font-medium mb-2">Try asking:</p>
              <ul class="space-y-1">
                <li>"Find mentions of budget in recent meetings"</li>
                <li>"What did John say about the project timeline?"</li>
                <li>"Search for discussions about marketing strategy"</li>
              </ul>
            </div>
          </div>

          <div
            v-for="(message, index) in messages"
            :key="index"
            class="flex"
            :class="message.role === 'user' ? 'justify-end' : 'justify-start'"
          >
            <div
              class="max-w-xs lg:max-w-md px-4 py-2 rounded-lg"
              :class="
                message.role === 'user'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-200 text-gray-800'
              "
            >
              <div class="whitespace-pre-wrap">{{ message.content }}</div>
              
              <!-- Search Results -->
              <div v-if="message.searchResults && message.searchResults.length > 0" class="mt-3 space-y-2">
                <div class="text-sm font-medium border-t pt-2">
                  Found {{ message.searchResults.length }} results:
                </div>
                <div
                  v-for="result in message.searchResults"
                  :key="`${result.meeting_id}-${result.timestamp}`"
                  class="bg-white rounded p-3 border text-sm"
                >
                  <div class="flex justify-between items-start mb-2">
                    <div>
                      <div class="font-medium text-blue-600">{{ result.meeting_title }}</div>
                      <div class="text-gray-600">{{ result.client_name }} • {{ result.speaker }}</div>
                    </div>
                    <div class="text-xs text-gray-500">{{ result.formatted_timestamp }}</div>
                  </div>
                  <div class="text-gray-800" v-html="formatSearchResult(result.text)"></div>
                  <div class="mt-2">
                    <a
                      :href="`/meetings/${result.meeting_id}?t=${result.timestamp}`"
                      class="text-blue-600 hover:text-blue-800 text-xs font-medium"
                      target="_blank"
                    >
                      View in meeting →
                    </a>
                  </div>
                </div>
              </div>
              
              <div v-if="message.timestamp" class="text-xs opacity-75 mt-2">
                {{ formatTime(message.timestamp) }}
              </div>
            </div>
          </div>

          <div v-if="isLoading" class="flex justify-start">
            <div class="bg-gray-200 text-gray-800 max-w-xs lg:max-w-md px-4 py-2 rounded-lg">
              <div class="flex items-center space-x-2">
                <div class="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
                <span>Thinking...</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Input Form -->
        <div class="border-t p-6">
          <form @submit.prevent="sendMessage" class="flex space-x-4">
            <input
              v-model="currentMessage"
              type="text"
              placeholder="Ask me about your meetings..."
              class="flex-1 border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              :disabled="isLoading"
            />
            <button
              type="submit"
              :disabled="!currentMessage.trim() || isLoading"
              class="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Send
            </button>
          </form>
        </div>
      </div>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { router, usePage } from '@inertiajs/vue3'
import AppLayout from '@/lib/AppLayout.vue'

interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  searchResults?: SearchResult[]
}

interface SearchResult {
  meeting_id: number
  meeting_title: string
  client_name: string
  speaker: string
  text: string
  timestamp: number
  formatted_timestamp: string
  confidence: number
  meeting_url: string
}

const messages = ref<Message[]>([])
const currentMessage = ref('')
const isLoading = ref(false)
const messagesContainer = ref<HTMLElement>()
const page = usePage<{ csrf_token: string }>()

const sendMessage = async () => {
  if (!currentMessage.value.trim() || isLoading.value) return

  const userMessage: Message = {
    role: 'user',
    content: currentMessage.value,
    timestamp: new Date()
  }

  messages.value.push(userMessage)
  const messageToSend = currentMessage.value
  currentMessage.value = ''
  isLoading.value = true

  await scrollToBottom()

  try {
    console.log(page)
    const response = await fetch('/ai/chat', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRF-TOKEN': page.props.csrf_token
      },
      body: JSON.stringify({
        message: messageToSend,
        conversation_history: messages.value.slice(0, -1).map(msg => ({
          role: msg.role,
          content: msg.content
        }))
      })
    })

    const data = await response.json()

    if (data.success) {
      const assistantMessage: Message = {
        role: 'assistant',
        content: data.response,
        timestamp: new Date()
      }

      // Check if there are search results from tool calls
      if (data.tool_calls && data.tool_calls.length > 0) {
        const searchToolCall = data.tool_calls.find((call: any) => call.name === 'search_meetings')
        if (searchToolCall && searchToolCall.result && searchToolCall.result.results) {
          assistantMessage.searchResults = searchToolCall.result.results
        }
      }

      messages.value.push(assistantMessage)
    } else {
      messages.value.push({
        role: 'assistant',
        content: data.error || 'Sorry, I encountered an error. Please try again.',
        timestamp: new Date()
      })
    }
  } catch (error) {
    console.error('Chat error:', error)
    messages.value.push({
      role: 'assistant',
      content: 'Sorry, I encountered a network error. Please check your connection and try again.',
      timestamp: new Date()
    })
  } finally {
    isLoading.value = false
    await scrollToBottom()
  }
}

const scrollToBottom = async () => {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

const formatTime = (date: Date) => {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

const formatSearchResult = (text: string) => {
  // Convert markdown-style bold to HTML
  return text.replace(/\*\*(.*?)\*\*/g, '<strong class="bg-yellow-200">$1</strong>')
}
</script>