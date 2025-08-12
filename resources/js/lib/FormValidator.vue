<template>
  <form @submit.prevent="handleSubmit" :class="formClass">
    <slot 
      :errors="allErrors"
      :hasErrors="hasAnyErrors"
      :isSubmitting="isSubmitting"
      :isValid="isFormValid"
      :validate="validateField"
      :clearErrors="clearFieldErrors"
    />
  </form>
</template>

<script setup lang="ts">
import { ref, computed, watch, provide } from 'vue'

interface ValidationRule {
  required?: boolean
  min?: number
  max?: number
  email?: boolean
  url?: boolean
  pattern?: RegExp
  custom?: (value: any) => string | null
}

interface FieldValidation {
  [fieldName: string]: ValidationRule
}

interface Props {
  validationRules?: FieldValidation
  showErrorsOnSubmit?: boolean
  validateOnBlur?: boolean
  validateOnInput?: boolean
  formClass?: string
}

interface Emits {
  (e: 'submit', data: { isValid: boolean; errors: Record<string, string> }): void
  (e: 'validation-change', data: { isValid: boolean; errors: Record<string, string> }): void
}

const props = withDefaults(defineProps<Props>(), {
  showErrorsOnSubmit: true,
  validateOnBlur: true,
  validateOnInput: false,
  formClass: ''
})

const emit = defineEmits<Emits>()

const fieldErrors = ref<Record<string, string>>({})
const fieldValues = ref<Record<string, any>>({})
const touchedFields = ref<Set<string>>(new Set())
const isSubmitting = ref(false)

const allErrors = computed(() => fieldErrors.value)

const hasAnyErrors = computed(() => {
  return Object.keys(fieldErrors.value).length > 0
})

const isFormValid = computed(() => {
  if (!props.validationRules) return true
  
  // Check if all required fields have values and no errors exist
  const requiredFields = Object.entries(props.validationRules)
    .filter(([_, rules]) => rules.required)
    .map(([fieldName]) => fieldName)
  
  const hasAllRequiredFields = requiredFields.every(field => {
    const value = fieldValues.value[field]
    return value !== undefined && value !== null && String(value).trim() !== ''
  })
  
  return hasAllRequiredFields && !hasAnyErrors.value
})

const validateField = (fieldName: string, value: any): string | null => {
  if (!props.validationRules || !props.validationRules[fieldName]) {
    return null
  }
  
  const rules = props.validationRules[fieldName]
  
  // Required validation
  if (rules.required && (value === undefined || value === null || String(value).trim() === '')) {
    return 'This field is required'
  }
  
  // Skip other validations if field is empty and not required
  if (!rules.required && (value === undefined || value === null || String(value).trim() === '')) {
    return null
  }
  
  const stringValue = String(value)
  
  // Min length validation
  if (rules.min && stringValue.length < rules.min) {
    return `Minimum ${rules.min} characters required`
  }
  
  // Max length validation
  if (rules.max && stringValue.length > rules.max) {
    return `Maximum ${rules.max} characters allowed`
  }
  
  // Email validation
  if (rules.email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (!emailRegex.test(stringValue)) {
      return 'Please enter a valid email address'
    }
  }
  
  // URL validation
  if (rules.url) {
    try {
      new URL(stringValue)
    } catch {
      return 'Please enter a valid URL'
    }
  }
  
  // Pattern validation
  if (rules.pattern && !rules.pattern.test(stringValue)) {
    return 'Please enter a valid format'
  }
  
  // Custom validation
  if (rules.custom) {
    const customError = rules.custom(value)
    if (customError) {
      return customError
    }
  }
  
  return null
}

const updateFieldValue = (fieldName: string, value: any) => {
  fieldValues.value[fieldName] = value
  
  // Validate on input if enabled and field is touched
  if (props.validateOnInput && touchedFields.value.has(fieldName)) {
    const error = validateField(fieldName, value)
    if (error) {
      fieldErrors.value[fieldName] = error
    } else {
      delete fieldErrors.value[fieldName]
    }
  }
}

const markFieldTouched = (fieldName: string) => {
  touchedFields.value.add(fieldName)
  
  // Validate on blur if enabled
  if (props.validateOnBlur) {
    const value = fieldValues.value[fieldName]
    const error = validateField(fieldName, value)
    if (error) {
      fieldErrors.value[fieldName] = error
    } else {
      delete fieldErrors.value[fieldName]
    }
  }
}

const clearFieldErrors = (fieldName?: string) => {
  if (fieldName) {
    delete fieldErrors.value[fieldName]
  } else {
    fieldErrors.value = {}
  }
}

const validateAllFields = (): boolean => {
  if (!props.validationRules) return true
  
  const errors: Record<string, string> = {}
  
  Object.keys(props.validationRules).forEach(fieldName => {
    const value = fieldValues.value[fieldName]
    const error = validateField(fieldName, value)
    if (error) {
      errors[fieldName] = error
    }
  })
  
  fieldErrors.value = errors
  return Object.keys(errors).length === 0
}

const handleSubmit = () => {
  isSubmitting.value = true
  
  let isValid = true
  if (props.showErrorsOnSubmit) {
    isValid = validateAllFields()
  }
  
  emit('submit', {
    isValid,
    errors: fieldErrors.value
  })
  
  isSubmitting.value = false
}

// Watch for validation changes and emit events
watch([isFormValid, fieldErrors], () => {
  emit('validation-change', {
    isValid: isFormValid.value,
    errors: fieldErrors.value
  })
}, { deep: true })

// Provide form context to child components
provide('formValidator', {
  updateFieldValue,
  markFieldTouched,
  validateField,
  clearFieldErrors,
  fieldErrors: computed(() => fieldErrors.value),
  isSubmitting: computed(() => isSubmitting.value)
})

// Expose methods for parent component
defineExpose({
  validate: validateAllFields,
  clearErrors: clearFieldErrors,
  isValid: isFormValid,
  errors: allErrors,
  setFieldValue: updateFieldValue,
  markFieldTouched
})
</script>