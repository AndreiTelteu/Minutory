<template>
  <span
    :class="[
      'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
      statusClasses[status]
    ]"
  >
    <svg
      v-if="status === 'processing'"
      class="animate-spin -ml-1 mr-1.5 h-3 w-3"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        class="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        stroke-width="4"
      ></circle>
      <path
        class="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      ></path>
    </svg>
    <div
      v-else
      :class="[
        'w-2 h-2 rounded-full mr-1.5',
        dotClasses[status]
      ]"
    ></div>
    {{ statusText[status] }}
  </span>
</template>

<script setup lang="ts">
interface Props {
  status: 'pending' | 'processing' | 'completed' | 'failed'
}

defineProps<Props>()

const statusClasses = {
  pending: 'bg-yellow-100 text-yellow-800',
  processing: 'bg-blue-100 text-blue-800',
  completed: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800'
}

const dotClasses = {
  pending: 'bg-yellow-400',
  processing: 'bg-blue-400',
  completed: 'bg-green-400',
  failed: 'bg-red-400'
}

const statusText = {
  pending: 'Pending',
  processing: 'Processing',
  completed: 'Completed',
  failed: 'Failed'
}
</script>