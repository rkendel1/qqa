import { Message } from '@/types/chat';

// Configuration constants
const CONFIG = {
  BASE_URL: process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000',
  TIMEOUT: 30000, // 30 seconds
  MAX_RETRIES: 3,
  RETRY_DELAY: 1000, // 1 second
  MAX_HISTORY_LENGTH: 20, // Limit chat history to prevent large payloads
} as const;

// API Response types
interface QueryResponse {
  answer: string;
  sources?: Array<{
    filename: string;
    metadata: Record<string, any>;
  }>;
  retrieved_docs?: string;
  retrieved_chunks?: string[];
  processing_time?: number;
  model_used?: string;
  token_count?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
}

interface ErrorResponse {
  error: string;
  detail?: string;
  status_code?: number;
}

// Custom error classes
class ChatServiceError extends Error {
  constructor(
    message: string,
    public statusCode?: number,
    public originalError?: Error
  ) {
    super(message);
    this.name = 'ChatServiceError';
  }
}

class NetworkError extends ChatServiceError {
  constructor(message: string, originalError?: Error) {
    super(message, 0, originalError);
    this.name = 'NetworkError';
  }
}

class APIError extends ChatServiceError {
  constructor(message: string, statusCode: number, originalError?: Error) {
    super(message, statusCode, originalError);
    this.name = 'APIError';
  }
}

// Utility functions
function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function isNetworkError(error: any): boolean {
  return (
    error instanceof TypeError ||
    error.code === 'NETWORK_ERROR' ||
    error.message?.includes('fetch') ||
    error.message?.includes('network')
  );
}

function sanitizeMessage(content: string): string {
  return content.trim().slice(0, 4000); // Limit message length
}

function filterChatHistory(messages: Message[], excludeMessage?: Message): Message[] {
  return messages
    .filter(m => 
      !m.system && 
      m !== excludeMessage &&
      m.content.trim().length > 0
    )
    .filter(m => 
      m.type !== 'assistant' ||
      !isDefaultWelcomeMessage(m.content)
    )
    .slice(-CONFIG.MAX_HISTORY_LENGTH) // Keep only recent messages
    .map(m => ({
      type: m.type,
      content: sanitizeMessage(m.content),
      timestamp: m.timestamp
    }));
}

function isDefaultWelcomeMessage(content: string): boolean {
  const welcomeMessages = [
    "Hello! I'm your City Hall Assistant. How can I help you today? You can ask me about permits, zoning, city services, or other municipal questions.",
    "Hello! I'm your City Hall Assistant. How can I help you today?",
    "Welcome! How can I assist you with city services today?"
  ];
  return welcomeMessages.some(msg => content.includes(msg));
}

async function makeRequest(
  url: string,
  payload: any,
  signal?: AbortSignal
): Promise<QueryResponse> {
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
    body: JSON.stringify(payload),
    signal,
  });

  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
    
    try {
      const errorData: ErrorResponse = await response.json();
      errorMessage = errorData.error || errorData.detail || errorMessage;
    } catch {
      // If we can't parse error response, use the status text
    }

    throw new APIError(errorMessage, response.status);
  }

  const data = await response.json();
  
  // Validate response structure
  if (!data || typeof data.answer !== 'string') {
    throw new APIError('Invalid response format from server', response.status);
  }

  return data;
}

async function makeRequestWithRetry(
  url: string,
  payload: any,
  maxRetries: number = CONFIG.MAX_RETRIES
): Promise<QueryResponse> {
  let lastError: Error;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      // Create abort controller for timeout
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), CONFIG.TIMEOUT);

      try {
        const result = await makeRequest(url, payload, controller.signal);
        clearTimeout(timeoutId);
        return result;
      } catch (error) {
        clearTimeout(timeoutId);
        throw error;
      }
    } catch (error: any) {
      lastError = error;

      // Don't retry on client errors (4xx) except for specific cases
      if (error instanceof APIError && error.statusCode) {
        const shouldRetry = error.statusCode >= 500 || // Server errors
                           error.statusCode === 429 || // Rate limiting
                           error.statusCode === 408;   // Request timeout
        
        if (!shouldRetry) {
          throw error;
        }
      }

      // Don't retry on abort (user cancelled)
      if (error.name === 'AbortError') {
        throw new NetworkError('Request timed out');
      }

      // If this is the last attempt, throw the error
      if (attempt === maxRetries) {
        if (isNetworkError(error)) {
          throw new NetworkError('Network connection failed. Please check your internet connection.');
        }
        throw error;
      }

      // Wait before retrying (exponential backoff)
      const delay = CONFIG.RETRY_DELAY * Math.pow(2, attempt);
      await sleep(delay);
    }
  }

  throw lastError;
}

// Health check function
export async function checkAPIHealth(): Promise<{
  status: 'healthy' | 'unhealthy';
  details: Record<string, any>;
}> {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000); // 5 second timeout

    const response = await fetch(`${CONFIG.BASE_URL}/health`, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (response.ok) {
      const data = await response.json();
      return {
        status: 'healthy',
        details: data
      };
    } else {
      return {
        status: 'unhealthy',
        details: {
          error: `HTTP ${response.status}: ${response.statusText}`
        }
      };
    }
  } catch (error: any) {
    return {
      status: 'unhealthy',
      details: {
        error: error.message || 'Unknown error',
        type: error.name || 'Error'
      }
    };
  }
}

// Main chat function
export async function generateCityHallResponse({
  messages,
  userContext,
  systemContext,
  includeMetadata = false,
}: {
  messages: Message[];
  userContext?: Record<string, string>;
  systemContext?: string;
  includeMetadata?: boolean;
}): Promise<{
  answer: string;
  metadata?: {
    sources?: Array<{
      filename: string;
      metadata: Record<string, any>;
    }>;
    processing_time?: number;
    model_used?: string;
    token_count?: {
      prompt_tokens: number;
      completion_tokens: number;
      total_tokens: number;
    };
  };
}> {
  try {
    // Validate inputs
    if (!messages || messages.length === 0) {
      throw new ChatServiceError('No messages provided');
    }

    const latestUserMessage = messages.filter(m => m.type === 'user').at(-1);
    
    if (!latestUserMessage?.content?.trim()) {
      throw new ChatServiceError('No valid user message found');
    }

    const chatHistory = filterChatHistory(messages, latestUserMessage);

    // Prepare payload
    const payload = {
      question: sanitizeMessage(latestUserMessage.content),
      system_context: systemContext || undefined,
      user_context: userContext || undefined,
      chat_history: chatHistory,
      include_metadata: includeMetadata,
    };

    // Remove undefined values to keep payload clean
    Object.keys(payload).forEach(key => {
      if (payload[key as keyof typeof payload] === undefined) {
        delete payload[key as keyof typeof payload];
      }
    });

    const url = `${CONFIG.BASE_URL}/query`;
    const response = await makeRequestWithRetry(url, payload);

    const result: {
      answer: string;
      metadata?: any;
    } = {
      answer: response.answer || 'No answer found.',
    };

    // Include metadata if requested and available
    if (includeMetadata) {
      result.metadata = {
        sources: response.sources,
        processing_time: response.processing_time,
        model_used: response.model_used,
        token_count: response.token_count,
      };
    }

    return result;

  } catch (error: any) {
    console.error('Chat service error:', error);

    // Re-throw known errors
    if (error instanceof ChatServiceError) {
      throw error;
    }

    // Handle unknown errors
    if (isNetworkError(error)) {
      throw new NetworkError('Failed to connect to the server. Please check your internet connection and try again.');
    }

    throw new ChatServiceError(
      'An unexpected error occurred while processing your request. Please try again.',
      undefined,
      error
    );
  }
}

// Streaming response function (if your backend supports streaming)
export async function generateCityHallResponseStream({
  messages,
  userContext,
  systemContext,
  onChunk,
}: {
  messages: Message[];
  userContext?: Record<string, string>;
  systemContext?: string;
  onChunk: (chunk: string) => void;
}): Promise<void> {
  try {
    const latestUserMessage = messages.filter(m => m.type === 'user').at(-1);
    
    if (!latestUserMessage?.content?.trim()) {
      throw new ChatServiceError('No valid user message found');
    }

    const chatHistory = filterChatHistory(messages, latestUserMessage);

    const payload = {
      question: sanitizeMessage(latestUserMessage.content),
      system_context: systemContext || undefined,
      user_context: userContext || undefined,
      chat_history: chatHistory,
      stream: true,
    };

    const response = await fetch(`${CONFIG.BASE_URL}/query/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new APIError(`HTTP ${response.status}: ${response.statusText}`, response.status);
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new ChatServiceError('Unable to read streaming response');
    }

    const decoder = new TextDecoder();
    
    try {
      while (true) {
        const { done, value } = await reader.read();
        
        if (done) break;
        
        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') {
              return;
            }
            try {
              const parsed = JSON.parse(data);
              if (parsed.chunk) {
                onChunk(parsed.chunk);
              }
            } catch {
              // Skip invalid JSON
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }

  } catch (error: any) {
    console.error('Streaming chat service error:', error);
    throw error instanceof ChatServiceError ? error : new ChatServiceError(
      'Streaming request failed',
      undefined,
      error
    );
  }
}

// Export error classes for error handling in components
export { ChatServiceError, NetworkError, APIError };

// Export configuration for use in other parts of the application
export { CONFIG as ChatServiceConfig };