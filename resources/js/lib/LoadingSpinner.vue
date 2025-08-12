<template>
  <div :class="containerClass">
    <div class="flex items-center justify-center" :class="contentClass">
      <div class="relative">
        <!-- Spinner -->
        <div 
          class="animate-spin rounded-full border-2 border-gray-300"
          :class="spinnerClass"
          :style="{ borderTopColor: color }"
        ></div>
        
        <!-- Optional inner dot -->
        <div 
          v-if="showDot"
          class="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 rounded-full"
          :class="dotClass"
          :style="{ backgroundColor: color }"
        ></div>
      </div>
      
      <!-- Loading text -->
      <div v-if="text" class="ml-3">
        <p :class="textClass">{{ text }}</p>
        <p v-if="subtext" :class="subtextClass">{{ subtext }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  size?: 'sm' | 'md' | 'lg' | 'xl'
  color?: string
  text?: string
  subtext?: string
  overlay?: boolean
  fullscreen?: boolean
  showDot?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  size: 'md',
  color: '#3B82F6',
  overlay: false,
  fullscreen: false,
  showDot: false
})

const containerClass = computed(() => {
  const base = []
  
  if (props.fullscreen) {
    base.push('fixed inset-0 z-50 bg-white bg-opacity-90')
  } else if (props.overlay) {
    base.push('absolute inset-0 bg-white bg-opacity-75 z-10')
  }
  
  return base.join(' ')
})

const contentClass = computed(() => {
  if (props.fullscreen || props.overlay) {
    return 'h-full'
  }
  return ''
})

const spinnerClass = computed(() => {
  const sizes = {
    sm: 'h-4 w-4',
    md: 'h-6 w-6', 
    lg: 'h-8 w-8',
    xl: 'h-12 w-12'
  }
  return sizes[props.size]
})

const dotClass = computed(() => {
  const sizes = {
    sm: 'h-1 w-1',
    md: 'h-1.5 w-1.5',
    lg: 'h-2 w-2', 
    xl: 'h-3 w-3'
  }
  return sizes[props.size]
})

const textClass = computed(() => {
  const sizes = {
    sm: 'text-sm',
    md: 'text-base',
    lg: 'text-lg',
    xl: 'text-xl'
  }
  return `font-medium text-gray-900 ${sizes[props.size]}`
})

const subtextClass = computed(() => {
  const sizes = {
    sm: 'text-xs',
    md: 'text-sm', 
    lg: 'text-base',
    xl: 'text-lg'
  }
  return `text-gray-600 ${sizes[props.size]}`
})
</script>