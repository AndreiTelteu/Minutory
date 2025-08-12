export interface RetryOptions {
  maxAttempts?: number
  delay?: number
  backoff?: 'linear' | 'exponential'
  maxDelay?: number
  retryCondition?: (error: any) => boolean
  onRetry?: (attempt: number, error: any) => void
}

export class RetryError extends Error {
  public attempts: number
  public lastError: any

  constructor(message: string, attempts: number, lastError: any) {
    super(message)
    this.name = 'RetryError'
    this.attempts = attempts
    this.lastError = lastError
  }
}

/**
 * Retry a function with configurable options
 */
export async function retry<T>(
  fn: () => Promise<T>,
  options: RetryOptions = {}
): Promise<T> {
  const {
    maxAttempts = 3,
    delay = 1000,
    backoff = 'exponential',
    maxDelay = 30000,
    retryCondition = () => true,
    onRetry
  } = options

  let lastError: any
  
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      return await fn()
    } catch (error) {
      lastError = error
      
      // Don't retry if this is the last attempt
      if (attempt === maxAttempts) {
        break
      }
      
      // Check if we should retry this error
      if (!retryCondition(error)) {
        throw error
      }
      
      // Call retry callback
      if (onRetry) {
        onRetry(attempt, error)
      }
      
      // Calculate delay
      let currentDelay = delay
      if (backoff === 'exponential') {
        currentDelay = Math.min(delay * Math.pow(2, attempt - 1), maxDelay)
      } else if (backoff === 'linear') {
        currentDelay = Math.min(delay * attempt, maxDelay)
      }
      
      // Add some jitter to prevent thundering herd
      const jitter = Math.random() * 0.1 * currentDelay
      currentDelay += jitter
      
      await sleep(currentDelay)
    }
  }
  
  throw new RetryError(
    `Failed after ${maxAttempts} attempts`,
    maxAttempts,
    lastError
  )
}

/**
 * Sleep for a given number of milliseconds
 */
export function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}

/**
 * Retry specifically for network requests
 */
export async function retryNetworkRequest<T>(
  requestFn: () => Promise<T>,
  options: Partial<RetryOptions> = {}
): Promise<T> {
  return retry(requestFn, {
    maxAttempts: 3,
    delay: 1000,
    backoff: 'exponential',
    retryCondition: (error) => {
      // Retry on network errors, timeouts, and 5xx server errors
      if (error.name === 'NetworkError' || error.name === 'TimeoutError') {
        return true
      }
      
      if (error.response) {
        const status = error.response.status
        return status >= 500 || status === 408 || status === 429
      }
      
      return false
    },
    ...options
  })
}

/**
 * Retry with exponential backoff and jitter
 */
export async function retryWithBackoff<T>(
  fn: () => Promise<T>,
  maxAttempts: number = 3,
  baseDelay: number = 1000
): Promise<T> {
  return retry(fn, {
    maxAttempts,
    delay: baseDelay,
    backoff: 'exponential',
    maxDelay: 30000
  })
}

/**
 * Create a retryable version of a function
 */
export function makeRetryable<T extends any[], R>(
  fn: (...args: T) => Promise<R>,
  options: RetryOptions = {}
) {
  return async (...args: T): Promise<R> => {
    return retry(() => fn(...args), options)
  }
}

/**
 * Utility for retrying file uploads
 */
export async function retryFileUpload(
  uploadFn: () => Promise<any>,
  options: Partial<RetryOptions> = {}
): Promise<any> {
  return retry(uploadFn, {
    maxAttempts: 3,
    delay: 2000,
    backoff: 'exponential',
    retryCondition: (error) => {
      // Don't retry validation errors or file too large errors
      if (error.response) {
        const status = error.response.status
        return !(status === 400 || status === 413 || status === 422)
      }
      return true
    },
    onRetry: (attempt, error) => {
      console.log(`Upload attempt ${attempt} failed:`, error.message)
      if (window.toast) {
        window.toast.info(
          'Upload Retry',
          `Retrying upload (attempt ${attempt})...`
        )
      }
    },
    ...options
  })
}

/**
 * Circuit breaker pattern for preventing cascading failures
 */
export class CircuitBreaker {
  private failures = 0
  private lastFailureTime = 0
  private state: 'closed' | 'open' | 'half-open' = 'closed'

  constructor(
    private maxFailures: number = 5,
    private timeout: number = 60000 // 1 minute
  ) {}

  async execute<T>(fn: () => Promise<T>): Promise<T> {
    if (this.state === 'open') {
      if (Date.now() - this.lastFailureTime > this.timeout) {
        this.state = 'half-open'
      } else {
        throw new Error('Circuit breaker is open')
      }
    }

    try {
      const result = await fn()
      this.onSuccess()
      return result
    } catch (error) {
      this.onFailure()
      throw error
    }
  }

  private onSuccess() {
    this.failures = 0
    this.state = 'closed'
  }

  private onFailure() {
    this.failures++
    this.lastFailureTime = Date.now()
    
    if (this.failures >= this.maxFailures) {
      this.state = 'open'
    }
  }

  getState() {
    return this.state
  }

  reset() {
    this.failures = 0
    this.state = 'closed'
    this.lastFailureTime = 0
  }
}