export interface ErrorContext {
  component?: string
  action?: string
  data?: any
  userId?: string | number
}

export interface ErrorDetails {
  message: string
  code?: string | number
  type: 'network' | 'validation' | 'server' | 'client' | 'unknown'
  recoverable: boolean
  userMessage: string
  technicalMessage?: string
  suggestions?: string[]
}

export class ErrorHandler {
  private static instance: ErrorHandler
  private errorLog: Array<{ error: Error; context: ErrorContext; timestamp: Date }> = []

  static getInstance(): ErrorHandler {
    if (!ErrorHandler.instance) {
      ErrorHandler.instance = new ErrorHandler()
    }
    return ErrorHandler.instance
  }

  /**
   * Parse and categorize an error
   */
  parseError(error: any, context?: ErrorContext): ErrorDetails {
    // Network errors
    if (error.name === 'NetworkError' || error.code === 'NETWORK_ERROR' || !navigator.onLine) {
      return {
        message: error.message || 'Network connection failed',
        type: 'network',
        recoverable: true,
        userMessage: 'Connection problem. Please check your internet connection and try again.',
        suggestions: ['Check your internet connection', 'Try refreshing the page', 'Try again in a few moments']
      }
    }

    // Fetch/HTTP errors
    if (error.response || error.status) {
      const status = error.response?.status || error.status
      const data = error.response?.data || error.data

      switch (status) {
        case 400:
          return {
            message: data?.message || 'Bad request',
            code: status,
            type: 'validation',
            recoverable: true,
            userMessage: 'Please check your input and try again.',
            technicalMessage: data?.message,
            suggestions: ['Review the form for errors', 'Make sure all required fields are filled']
          }

        case 401:
          return {
            message: 'Unauthorized',
            code: status,
            type: 'server',
            recoverable: true,
            userMessage: 'Your session has expired. Please refresh the page.',
            suggestions: ['Refresh the page', 'Log in again']
          }

        case 403:
          return {
            message: 'Forbidden',
            code: status,
            type: 'server',
            recoverable: false,
            userMessage: 'You don\'t have permission to perform this action.',
            suggestions: ['Contact support if you believe this is an error']
          }

        case 404:
          return {
            message: 'Not found',
            code: status,
            type: 'server',
            recoverable: false,
            userMessage: 'The requested resource was not found.',
            suggestions: ['Check the URL', 'Go back to the previous page']
          }

        case 413:
          return {
            message: 'File too large',
            code: status,
            type: 'validation',
            recoverable: true,
            userMessage: 'The file you\'re trying to upload is too large.',
            suggestions: ['Try a smaller file', 'Compress your file before uploading']
          }

        case 422:
          return {
            message: 'Validation failed',
            code: status,
            type: 'validation',
            recoverable: true,
            userMessage: 'Please correct the errors in your form.',
            technicalMessage: data?.message,
            suggestions: ['Check all form fields for errors', 'Make sure all required fields are filled']
          }

        case 429:
          return {
            message: 'Too many requests',
            code: status,
            type: 'server',
            recoverable: true,
            userMessage: 'You\'re making requests too quickly. Please wait a moment and try again.',
            suggestions: ['Wait a few seconds and try again', 'Avoid clicking buttons multiple times']
          }

        case 500:
        case 502:
        case 503:
        case 504:
          return {
            message: 'Server error',
            code: status,
            type: 'server',
            recoverable: true,
            userMessage: 'We\'re experiencing technical difficulties. Please try again in a few moments.',
            suggestions: ['Try again in a few minutes', 'Contact support if the problem persists']
          }

        default:
          return {
            message: data?.message || `HTTP ${status} error`,
            code: status,
            type: 'server',
            recoverable: true,
            userMessage: 'Something went wrong. Please try again.',
            technicalMessage: data?.message
          }
      }
    }

    // File upload errors
    if (error.message?.includes('file') || error.message?.includes('upload')) {
      return {
        message: error.message,
        type: 'validation',
        recoverable: true,
        userMessage: 'There was a problem with your file upload.',
        suggestions: ['Check your file format and size', 'Try uploading a different file']
      }
    }

    // Validation errors
    if (error.name === 'ValidationError' || error.type === 'validation') {
      return {
        message: error.message,
        type: 'validation',
        recoverable: true,
        userMessage: 'Please check your input and try again.',
        technicalMessage: error.message,
        suggestions: ['Review the form for errors', 'Make sure all required fields are filled']
      }
    }

    // JavaScript/Client errors
    if (error instanceof TypeError || error instanceof ReferenceError || error instanceof SyntaxError) {
      return {
        message: error.message,
        type: 'client',
        recoverable: false,
        userMessage: 'We encountered a technical problem. Please refresh the page.',
        technicalMessage: error.message,
        suggestions: ['Refresh the page', 'Clear your browser cache', 'Contact support if the problem persists']
      }
    }

    // Generic/Unknown errors
    return {
      message: error.message || 'An unknown error occurred',
      type: 'unknown',
      recoverable: true,
      userMessage: 'Something unexpected happened. Please try again.',
      technicalMessage: error.message,
      suggestions: ['Try again', 'Refresh the page', 'Contact support if the problem persists']
    }
  }

  /**
   * Handle an error with appropriate user feedback
   */
  handleError(error: any, context?: ErrorContext): ErrorDetails {
    const errorDetails = this.parseError(error, context)
    
    // Log the error
    this.logError(error, context)
    
    // Show user-friendly notification
    this.showErrorNotification(errorDetails)
    
    return errorDetails
  }

  /**
   * Log error for debugging and monitoring
   */
  private logError(error: Error, context?: ErrorContext) {
    const logEntry = {
      error,
      context: context || {},
      timestamp: new Date()
    }
    
    this.errorLog.push(logEntry)
    
    // Keep only last 50 errors in memory
    if (this.errorLog.length > 50) {
      this.errorLog.shift()
    }
    
    // Console log for development
    console.error('Error handled:', {
      message: error.message,
      stack: error.stack,
      context
    })
    
    // In production, you might want to send to error tracking service
    // this.sendToErrorTracking(logEntry)
  }

  /**
   * Show error notification to user
   */
  private showErrorNotification(errorDetails: ErrorDetails) {
    if (typeof window !== 'undefined' && window.toast) {
      const actions = errorDetails.recoverable ? [
        {
          label: 'Try Again',
          handler: () => window.location.reload(),
          primary: true
        }
      ] : undefined

      window.toast.error(
        errorDetails.userMessage,
        errorDetails.suggestions?.join(' • '),
        {
          duration: errorDetails.type === 'network' ? 0 : 8000, // Network errors don't auto-dismiss
          actions
        }
      )
    }
  }

  /**
   * Get recent error logs (for debugging)
   */
  getErrorLog() {
    return this.errorLog
  }

  /**
   * Clear error log
   */
  clearErrorLog() {
    this.errorLog = []
  }
}

// Global error handler instance
export const errorHandler = ErrorHandler.getInstance()

// Global error event listeners
if (typeof window !== 'undefined') {
  // Catch unhandled JavaScript errors
  window.addEventListener('error', (event) => {
    errorHandler.handleError(event.error, {
      component: 'global',
      action: 'unhandled_error'
    })
  })

  // Catch unhandled promise rejections
  window.addEventListener('unhandledrejection', (event) => {
    errorHandler.handleError(event.reason, {
      component: 'global',
      action: 'unhandled_promise_rejection'
    })
  })
}

// Utility functions for common error scenarios
export const handleApiError = (error: any, context?: ErrorContext) => {
  return errorHandler.handleError(error, { ...context, action: 'api_call' })
}

export const handleFormError = (error: any, context?: ErrorContext) => {
  return errorHandler.handleError(error, { ...context, action: 'form_submission' })
}

export const handleFileUploadError = (error: any, context?: ErrorContext) => {
  return errorHandler.handleError(error, { ...context, action: 'file_upload' })
}

export const handleNetworkError = (error: any, context?: ErrorContext) => {
  return errorHandler.handleError(error, { ...context, action: 'network_request' })
}

// Type declarations for global toast
declare global {
  interface Window {
    toast: {
      success: (title: string, message?: string, options?: any) => string
      error: (title: string, message?: string, options?: any) => string
      warning: (title: string, message?: string, options?: any) => string
      info: (title: string, message?: string, options?: any) => string
      remove: (id: string) => void
      clear: () => void
    }
  }
}