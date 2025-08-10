<template>
  <div>
    <label :for="id" class="block text-sm font-medium leading-6 text-gray-900">
      {{ label }} <span v-if="required" class="text-red-500">*</span>
    </label>
    <div class="mt-2">
      <select
        :id="id"
        :value="modelValue"
        @input="$emit('update:modelValue', ($event.target as HTMLSelectElement).value)"
        :required="required"
        class="block w-full rounded-md border-0 py-1.5 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:text-sm sm:leading-6"
        :class="{ 'ring-red-500 focus:ring-red-500': hasError }"
      >
        <option value="">{{ placeholder }}</option>
        <option
          v-for="client in clients"
          :key="client.id"
          :value="client.id"
        >
          {{ client.name }}{{ client.company ? ` (${client.company})` : '' }}
        </option>
      </select>
      <p v-if="errorMessage" class="mt-2 text-sm text-red-600">
        {{ errorMessage }}
      </p>
      <p v-if="helpText && !errorMessage" class="mt-2 text-sm text-gray-500">
        {{ helpText }}
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Client } from '@/types'

interface Props {
  id?: string
  label?: string
  placeholder?: string
  modelValue: string | number | null
  clients: Client[]
  required?: boolean
  errorMessage?: string
  helpText?: string
}

interface Emits {
  'update:modelValue': [value: string]
}

const props = withDefaults(defineProps<Props>(), {
  id: 'client-selector',
  label: 'Client',
  placeholder: 'Select a client...',
  required: false,
})

defineEmits<Emits>()

const hasError = computed(() => !!props.errorMessage)
</script>