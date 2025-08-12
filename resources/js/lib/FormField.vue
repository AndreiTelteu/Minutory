<template>
  <div class="form-field">
    <label
      v-if="label"
      :for="fieldId"
      :class="[
        'block text-sm font-medium mb-2',
        hasError ? 'text-red-700' : 'text-gray-700',
        required && 'after:content-[\'*\'] after:ml-1 after:text-red-500'
      ]"
    >
      {{ label }}
    </label>

    <div class="relative">
      <!-- Input Field -->
      <input
        v-if="type !== 'textarea' && type !== 'select'"
        :id="fieldId"
        :type="type"
        :value="modelValue"
        @input="handleInput"
        @blur="handleBlur"
        @focus="handleFocus"
        :placeholder="placeholder"
        :required="required"
        :disabled="disabled"
        :readonly="readonly"
        :class="[
          'w-full rounded-md border shadow-sm transition-colors duration-200',
          'focus:outline-none focus:ring-2 focus:ring-offset-2',
          hasError
            ? 'border-red-300 focus:border-red-500 focus:ring-red-500'
            : 'border-gray-300 focus:border-blue-500 focus:ring-blue-500',
          disabled && 'bg-gray-50 cursor-not-allowed',
          readonly && 'bg-gray-50',
          'px-3 py-2'
        ]"
        :autocomplete="autocomplete"
      />

      <!-- Textarea -->
      <textarea
        v-else-if="type === 'textarea'"
        :id="fieldId"
        :value="modelValue"
        @input="handleInput"
        @blur="handleBlur"
        @focus="handleFocus"
        :placeholder="placeholder"
        :required="required"
        :disabled="disabled"
        :readonly="readonly"
        :rows="rows || 3"
        :class="[
          'w-full rounded-md border shadow-sm transition-colors duration-200',
          'focus:outline-none focus:ring-2 focus:ring-offset-2',
          hasError
            ? 'border-red-300 focus:border-red-500 focus:ring-red-500'
            : 'border-gray-300 focus:border-blue-500 focus:ring-blue-500',
          disabled && 'bg-gray-50 cursor-not-allowed',
          readonly && 'bg-gray-50',
          'px-3 py-2'
        ]"
      />

      <!-- Select -->
      <select
        v-else-if="type === 'select'"
        :id="fieldId"
        :value="modelValue"
        @change="handleInput"
        @blur="handleBlur"
        @focus="handleFocus"
        :required="required"
        :disabled="disabled"
        :class="[
          'w-full rounded-md border shadow-sm transition-colors duration-200',
          'focus:outline-none focus:ring-2 focus:ring-offset-2',
          hasError
            ? 'border-red-300 focus:border-red-500 focus:ring-red-500'
            : 'border-gray-300 focus:border-blue-500 focus:ring-blue-500',
          disabled && 'bg-gray-50 cursor-not-allowed',
          'px-3 py-2'
        ]"
      >
        <option v-if="placeholder" value="">{{ placeholder }}</option>
        <option
          v-for="option in options"
          :key="option.value"
          :value="option.value"
        >
          {{ option.label }}
        </option>
      </select>

      <!-- Loading indicator -->
      <div
        v-if="loading"
        class="absolute inset-y-0 right-0 flex items-center pr-3"
      >
        <LoadingSpinner size="sm" />
      </div>

      <!-- Success indicator -->
      <div
        v-else-if="showSuccess && !hasError && modelValue"
        class="absolute inset-y-0 right-0 flex items-center pr-3"
      >
        <svg class="h-5 w-5 text-green-500" fill="currentColor" viewBox="0 0 20 20">
          <path
            fill-rule="evenodd"
            d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
            clip-rule="evenodd"
          />
        </svg>
      </div>

      <!-- Error indicator -->
      <div
        v-else-if="hasError"
        class="absolute inset-y-0 right-0 flex items-center pr-3"
      >
        <svg class="h-5 w-5 text-red-500" fill="currentColor" viewBox="0 0 20 20">
          <path
            fill-rule="evenodd"
            d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
            clip-rule="evenodd"
          />
        </svg>
      </div>
    </div>

    <!-- Help text -->
    <p v-if="help && !hasError" class="mt-1 text-sm text-gray-600">
      {{ help }}
    </p>

    <!-- Error message -->
    <p v-if="hasError" class="mt-1 text-sm text-red-600">
      {{ errorMessage }}
    </p>

    <!-- Character count -->
    <p
      v-if="maxLength && (type === 'text' || type === 'textarea')"
      :class="[
        'mt-1 text-xs text-right',
        characterCount > maxLength ? 'text-red-600' : 'text-gray-500'
      ]"
    >
      {{ characterCount }}/{{ maxLength }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import LoadingSpinner from './LoadingSpinner.vue'

interface Option {
  value: string | number
  label: string
}

interface Props {
  modelValue: string | number
  type?: 'text' | 'email' | 'password' | 'number' | 'tel' | 'url' | 'textarea' | 'select'
  label?: string
  placeholder?: string
  help?: string
  error?: string
  required?: boolean
  disabled?: boolean
  readonly?: boolean
  loading?: boolean
  showSuccess?: boolean
  autocomplete?: string
  rows?: number
  maxLength?: number
  options?: Option[]
  validateOnBlur?: boolean
  validateOnInput?: boolean
  validator?: (value: string | number) => string | null
}

interface Emits {
  (e: 'update:modelValue', value: string | number): void
  (e: 'blur'): void
  (e: 'focus'): void
  (e: 'validate', isValid: boolean): void
}

const props = withDefaults(defineProps<Props>(), {
  type: 'text',
  validateOnBlur: true,
  validateOnInput: false,
  showSuccess: true
})

const emit = defineEmits<Emits>()

const fieldId = `field-${Math.random().toString(36).substr(2, 9)}`
const isFocused = ref(false)
const isTouched = ref(false)
const localError = ref<string>('')

const characterCount = computed(() => {
  return String(props.modelValue || '').length
})

const hasError = computed(() => {
  return !!(props.error || localError.value)
})

const errorMessage = computed(() => {
  return props.error || localError.value
})

const handleInput = (event: Event) => {
  const target = event.target as HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement
  let value: string | number = target.value

  // Convert to number for number inputs
  if (props.type === 'number' && value !== '') {
    value = Number(value)
  }

  emit('update:modelValue', value)

  // Validate on input if enabled
  if (props.validateOnInput && isTouched.value) {
    validateField(value)
  }
}

const handleBlur = () => {
  isFocused.value = false
  isTouched.value = true
  emit('blur')

  // Validate on blur if enabled
  if (props.validateOnBlur) {
    validateField(props.modelValue)
  }
}

const handleFocus = () => {
  isFocused.value = true
  emit('focus')
}

const validateField = (value: string | number) => {
  localError.value = ''

  // Required validation
  if (props.required && (!value || String(value).trim() === '')) {
    localError.value = 'This field is required'
    emit('validate', false)
    return
  }

  // Max length validation
  if (props.maxLength && String(value).length > props.maxLength) {
    localError.value = `Maximum ${props.maxLength} characters allowed`
    emit('validate', false)
    return
  }

  // Email validation
  if (props.type === 'email' && value) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (!emailRegex.test(String(value))) {
      localError.value = 'Please enter a valid email address'
      emit('validate', false)
      return
    }
  }

  // URL validation
  if (props.type === 'url' && value) {
    try {
      new URL(String(value))
    } catch {
      localError.value = 'Please enter a valid URL'
      emit('validate', false)
      return
    }
  }

  // Custom validator
  if (props.validator && value) {
    const validationError = props.validator(value)
    if (validationError) {
      localError.value = validationError
      emit('validate', false)
      return
    }
  }

  emit('validate', true)
}

// Clear local error when external error changes
watch(() => props.error, (newError) => {
  if (newError) {
    localError.value = ''
  }
})

// Validate when model value changes externally
watch(() => props.modelValue, (newValue) => {
  if (isTouched.value && (props.validateOnInput || props.validateOnBlur)) {
    validateField(newValue)
  }
})

// Expose validation method
defineExpose({
  validate: () => validateField(props.modelValue),
  focus: () => document.getElementById(fieldId)?.focus(),
  blur: () => document.getElementById(fieldId)?.blur()
})
</script>