import React, { createContext, useContext, useEffect, useState, useCallback, useRef, ReactNode } from 'react';

// Types
export interface Message {
  id: string;
  type: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  system?: boolean;
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
}

export interface ChatSettings {
  maxMessages: number;
  autoSave: boolean;
  showTimestamps: boolean;
  enableNotifications: boolean;
}

export interface LoadingState {
  isLoading: boolean;
  operation?: 'sending' | 'loading_context' | 'clearing';
  progress?: number;
}

export interface ErrorState {
  hasError: boolean;
  error?: string;
  timestamp?: string;
}

interface ChatContextType {
  // State
  messages: Message[];
  userContext?: Record<string, string>;
  customContext?: string;
  systemContext?: string;
  settings: ChatSettings;
  loading: LoadingState;
  error: ErrorState;
  isInitialized: boolean;

  // Message operations
  addMessage: (msg: Omit<Message, 'id' | 'timestamp'>) => string;
  updateMessage: (id: string, updates: Partial<Message>) => void;
  deleteMessage: (id: string) => void;
  clearMessages: () => void;
  exportMessages: () => string;
  importMessages: (data: string) => boolean;

  // Context operations
  setUserContext: (context: Record<string, string> | undefined) => void;
  setCustomContext: (context: string | undefined) => void;
  setSystemContext: (context: string | undefined) => void;
  updateUserContext: (key: string, value: string) => void;
  removeUserContextKey: (key: string) => void;

  // Async operations
  loadUserContext: () => Promise<boolean>;
  loadCustomContext: () => Promise<boolean>;
  saveUserContext: () => Promise<boolean>;
  saveCustomContext: () => Promise<boolean>;

  // Settings
  updateSettings: (updates: Partial<ChatSettings>) => void;
  resetSettings: () => void;

  // Error handling
  clearError: () => void;
  setError: (error: string) => void;

  // Utility
  getMessageById: (id: string) => Message | undefined;
  getMessagesByType: (type: Message['type']) => Message[];
  getRecentMessages: (count: number) => Message[];
  searchMessages: (query: string) => Message[];
}

// Configuration
const CONFIG = {
  BASE_URL: process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000',
  STORAGE_KEYS: {
    MESSAGES: 'chat_messages',
    USER_CONTEXT: 'user_context',
    CUSTOM_CONTEXT: 'custom_context',
    SYSTEM_CONTEXT: 'system_context',
    SETTINGS: 'chat_settings',
  },
  DEFAULT_SETTINGS: {
    maxMessages: 100,
    autoSave: true,
    showTimestamps: true,
    enableNotifications: false,
  } as ChatSettings,
  DEFAULT_SYSTEM_CONTEXT: "You are a helpful assistant trained to answer municipal questions like permits, zoning, and city services.",
  DEBOUNCE_DELAY: 500,
} as const;

// Utility functions
function generateId(): string {
  return `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

function isValidMessage(msg: any): msg is Message {
  return (
    typeof msg === 'object' &&
    msg !== null &&
    typeof msg.id === 'string' &&
    ['user', 'assistant', 'system'].includes(msg.type) &&
    typeof msg.content === 'string' &&
    typeof msg.timestamp === 'string'
  );
}

function safeJsonParse<T>(json: string, fallback: T): T {
  try {
    const parsed = JSON.parse(json);
    return parsed ?? fallback;
  } catch {
    return fallback;
  }
}

function safeSessionStorage() {
  if (typeof window === 'undefined') {
    return {
      getItem: () => null,
      setItem: () => {},
      removeItem: () => {},
    };
  }
  return sessionStorage;
}

// Context creation
export const ChatContext = createContext<ChatContextType | undefined>(undefined);

// Custom hook for using chat context
export const useChatContext = () => {
  const context = useContext(ChatContext);
  if (!context) {
    throw new Error('useChatContext must be used within a ChatProvider');
  }
  return context;
};

// Provider component
export const ChatProvider = ({ children }: { children: ReactNode }) => {
  // State
  const [messages, setMessages] = useState<Message[]>([]);
  const [userContext, setUserContextState] = useState<Record<string, string> | undefined>(undefined);
  const [customContext, setCustomContextState] = useState<string | undefined>(undefined);
  const [systemContext, setSystemContextState] = useState<string | undefined>(CONFIG.DEFAULT_SYSTEM_CONTEXT);
  const [settings, setSettings] = useState<ChatSettings>(CONFIG.DEFAULT_SETTINGS);
  const [loading, setLoading] = useState<LoadingState>({ isLoading: false });
  const [error, setErrorState] = useState<ErrorState>({ hasError: false });
  const [isInitialized, setIsInitialized] = useState(false);

  // Refs for debouncing
  const saveTimeoutRef = useRef<NodeJS.Timeout>();
  const isLoadingRef = useRef(false);

  // Debounced save function
  const debouncedSave = useCallback((key: string, value: any) => {
    if (!settings.autoSave) return;

    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }

    saveTimeoutRef.current = setTimeout(() => {
      const storage = safeSessionStorage();
      if (value === undefined || value === null) {
        storage.removeItem(key);
      } else {
        storage.setItem(key, JSON.stringify(value));
      }
    }, CONFIG.DEBOUNCE_DELAY);
  }, [settings.autoSave]);

  // Initialize from storage
  useEffect(() => {
    if (isLoadingRef.current) return;
    isLoadingRef.current = true;

    const storage = safeSessionStorage();
    
    try {
      // Load messages
      const storedMessages = storage.getItem(CONFIG.STORAGE_KEYS.MESSAGES);
      if (storedMessages) {
        const parsed = safeJsonParse<Message[]>(storedMessages, []);
        const validMessages = parsed.filter(isValidMessage);
        setMessages(validMessages);
      }

      // Load contexts
      const storedUserContext = storage.getItem(CONFIG.STORAGE_KEYS.USER_CONTEXT);
      if (storedUserContext) {
        setUserContextState(safeJsonParse(storedUserContext, undefined));
      }

      const storedCustomContext = storage.getItem(CONFIG.STORAGE_KEYS.CUSTOM_CONTEXT);
      if (storedCustomContext) {
        setCustomContextState(storedCustomContext);
      }

      const storedSystemContext = storage.getItem(CONFIG.STORAGE_KEYS.SYSTEM_CONTEXT);
      if (storedSystemContext) {
        setSystemContextState(storedSystemContext);
      }

      // Load settings
      const storedSettings = storage.getItem(CONFIG.STORAGE_KEYS.SETTINGS);
      if (storedSettings) {
        const parsed = safeJsonParse(storedSettings, CONFIG.DEFAULT_SETTINGS);
        setSettings({ ...CONFIG.DEFAULT_SETTINGS, ...parsed });
      }

    } catch (error) {
      console.error('Failed to load chat data from storage:', error);
      setErrorState({
        hasError: true,
        error: 'Failed to load chat history',
        timestamp: new Date().toISOString(),
      });
    } finally {
      setIsInitialized(true);
      isLoadingRef.current = false;
    }
  }, []);

  // Auto-save effects
  useEffect(() => {
    if (!isInitialized) return;
    debouncedSave(CONFIG.STORAGE_KEYS.MESSAGES, messages);
  }, [messages, debouncedSave, isInitialized]);

  useEffect(() => {
    if (!isInitialized) return;
    debouncedSave(CONFIG.STORAGE_KEYS.USER_CONTEXT, userContext);
  }, [userContext, debouncedSave, isInitialized]);

  useEffect(() => {
    if (!isInitialized) return;
    debouncedSave(CONFIG.STORAGE_KEYS.CUSTOM_CONTEXT, customContext);
  }, [customContext, debouncedSave, isInitialized]);

  useEffect(() => {
    if (!isInitialized) return;
    debouncedSave(CONFIG.STORAGE_KEYS.SYSTEM_CONTEXT, systemContext);
  }, [systemContext, debouncedSave, isInitialized]);

  useEffect(() => {
    if (!isInitialized) return;
    debouncedSave(CONFIG.STORAGE_KEYS.SETTINGS, settings);
  }, [settings, debouncedSave, isInitialized]);

  // Message operations
  const addMessage = useCallback((msg: Omit<Message, 'id' | 'timestamp'>): string => {
    const id = generateId();
    const timestamp = new Date().toISOString();
    const newMessage: Message = { ...msg, id, timestamp };

    setMessages(prevMessages => {
      const updatedMessages = [...prevMessages, newMessage];
      // Trim messages if exceeding max
      if (updatedMessages.length > settings.maxMessages) {
        return updatedMessages.slice(-settings.maxMessages);
      }
      return updatedMessages;
    });

    return id;
  }, [settings.maxMessages]);

  const updateMessage = useCallback((id: string, updates: Partial<Message>) => {
    setMessages(prevMessages =>
      prevMessages.map(msg =>
        msg.id === id ? { ...msg, ...updates } : msg
      )
    );
  }, []);

  const deleteMessage = useCallback((id: string) => {
    setMessages(prevMessages => prevMessages.filter(msg => msg.id !== id));
  }, []);

  const clearMessages = useCallback(() => {
    setLoading({ isLoading: true, operation: 'clearing' });
    setMessages([]);
    const storage = safeSessionStorage();
    storage.removeItem(CONFIG.STORAGE_KEYS.MESSAGES);
    setLoading({ isLoading: false });
  }, []);

  const exportMessages = useCallback((): string => {
    const exportData = {
      messages,
      userContext,
      customContext,
      systemContext,
      exportedAt: new Date().toISOString(),
      version: '1.0',
    };
    return JSON.stringify(exportData, null, 2);
  }, [messages, userContext, customContext, systemContext]);

  const importMessages = useCallback((data: string): boolean => {
    try {
      const parsed = JSON.parse(data);
      
      if (parsed.messages && Array.isArray(parsed.messages)) {
        const validMessages = parsed.messages.filter(isValidMessage);
        setMessages(validMessages);
      }
      
      if (parsed.userContext) {
        setUserContextState(parsed.userContext);
      }
      
      if (parsed.customContext) {
        setCustomContextState(parsed.customContext);
      }
      
      if (parsed.systemContext) {
        setSystemContextState(parsed.systemContext);
      }
      
      return true;
    } catch (error) {
      console.error('Failed to import messages:', error);
      setErrorState({
        hasError: true,
        error: 'Failed to import chat data',
        timestamp: new Date().toISOString(),
      });
      return false;
    }
  }, []);

  // Context operations
  const setUserContext = useCallback((context: Record<string, string> | undefined) => {
    setUserContextState(context);
  }, []);

  const setCustomContext = useCallback((context: string | undefined) => {
    setCustomContextState(context);
  }, []);

  const setSystemContext = useCallback((context: string | undefined) => {
    setSystemContextState(context);
  }, []);

  const updateUserContext = useCallback((key: string, value: string) => {
    setUserContextState(prev => ({
      ...prev,
      [key]: value,
    }));
  }, []);

  const removeUserContextKey = useCallback((key: string) => {
    setUserContextState(prev => {
      if (!prev) return prev;
      const { [key]: removed, ...rest } = prev;
      return Object.keys(rest).length > 0 ? rest : undefined;
    });
  }, []);

  // Async operations
  const makeAuthenticatedRequest = useCallback(async (endpoint: string, options: RequestInit = {}) => {
    const token = localStorage.getItem('access_token');
    
    const response = await fetch(`${CONFIG.BASE_URL}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token && { Authorization: `Bearer ${token}` }),
        ...options.headers,
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }, []);

  const loadUserContext = useCallback(async (): Promise<boolean> => {
    try {
      setLoading({ isLoading: true, operation: 'loading_context' });
      
      const data = await makeAuthenticatedRequest('/user/context');
      
      setUserContextState(data.userContext || {});
      
      // Optionally merge backend messages
      if (data.messages && Array.isArray(data.messages)) {
        const backendMessages: Message[] = data.messages.filter(isValidMessage);
        setMessages(prevMessages => {
          const existingIds = new Set(prevMessages.map(m => m.id));
          const newMessages = backendMessages.filter(m => !existingIds.has(m.id));
          return [...prevMessages, ...newMessages];
        });
      }
      
      return true;
    } catch (error) {
      console.error('Error loading user context:', error);
      setErrorState({
        hasError: true,
        error: error instanceof Error ? error.message : 'Failed to load user context',
        timestamp: new Date().toISOString(),
      });
      return false;
    } finally {
      setLoading({ isLoading: false });
    }
  }, [makeAuthenticatedRequest]);

  const loadCustomContext = useCallback(async (): Promise<boolean> => {
    try {
      setLoading({ isLoading: true, operation: 'loading_context' });
      
      const data = await makeAuthenticatedRequest('/custom/context');
      setCustomContextState(data.customContext || '');
      
      return true;
    } catch (error) {
      console.error('Error loading custom context:', error);
      setErrorState({
        hasError: true,
        error: error instanceof Error ? error.message : 'Failed to load custom context',
        timestamp: new Date().toISOString(),
      });
      return false;
    } finally {
      setLoading({ isLoading: false });
    }
  }, [makeAuthenticatedRequest]);

  const saveUserContext = useCallback(async (): Promise<boolean> => {
    try {
      setLoading({ isLoading: true, operation: 'loading_context' });
      
      await makeAuthenticatedRequest('/user/context', {
        method: 'POST',
        body: JSON.stringify({ userContext }),
      });
      
      return true;
    } catch (error) {
      console.error('Error saving user context:', error);
      setErrorState({
        hasError: true,
        error: error instanceof Error ? error.message : 'Failed to save user context',
        timestamp: new Date().toISOString(),
      });
      return false;
    } finally {
      setLoading({ isLoading: false });
    }
  }, [makeAuthenticatedRequest, userContext]);

  const saveCustomContext = useCallback(async (): Promise<boolean> => {
    try {
      setLoading({ isLoading: true, operation: 'loading_context' });
      
      await makeAuthenticatedRequest('/custom/context', {
        method: 'POST',
        body: JSON.stringify({ customContext }),
      });
      
      return true;
    } catch (error) {
      console.error('Error saving custom context:', error);
      setErrorState({
        hasError: true,
        error: error instanceof Error ? error.message : 'Failed to save custom context',
        timestamp: new Date().toISOString(),
      });
      return false;
    } finally {
      setLoading({ isLoading: false });
    }
  }, [makeAuthenticatedRequest, customContext]);

  // Settings operations
  const updateSettings = useCallback((updates: Partial<ChatSettings>) => {
    setSettings(prev => ({ ...prev, ...updates }));
  }, []);

  const resetSettings = useCallback(() => {
    setSettings(CONFIG.DEFAULT_SETTINGS);
  }, []);

  // Error handling
  const clearError = useCallback(() => {
    setErrorState({ hasError: false });
  }, []);

  const setError = useCallback((error: string) => {
    setErrorState({
      hasError: true,
      error,
      timestamp: new Date().toISOString(),
    });
  }, []);

  // Utility functions
  const getMessageById = useCallback((id: string): Message | undefined => {
    return messages.find(msg => msg.id === id);
  }, [messages]);

  const getMessagesByType = useCallback((type: Message['type']): Message[] => {
    return messages.filter(msg => msg.type === type);
  }, [messages]);

  const getRecentMessages = useCallback((count: number): Message[] => {
    return messages.slice(-count);
  }, [messages]);

  const searchMessages = useCallback((query: string): Message[] => {
    const lowercaseQuery = query.toLowerCase();
    return messages.filter(msg =>
      msg.content.toLowerCase().includes(lowercaseQuery)
    );
  }, [messages]);

  // Cleanup
  useEffect(() => {
    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }
    };
  }, []);

  const contextValue: ChatContextType = {
    // State
    messages,
    userContext,
    customContext,
    systemContext,
    settings,
    loading,
    error,
    isInitialized,

    // Message operations
    addMessage,
    updateMessage,
    deleteMessage,
    clearMessages,
    exportMessages,
    importMessages,

    // Context operations
    setUserContext,
    setCustomContext,
    setSystemContext,
    updateUserContext,
    removeUserContextKey,

    // Async operations
    loadUserContext,
    loadCustomContext,
    saveUserContext,
    saveCustomContext,

    // Settings
    updateSettings,
    resetSettings,

    // Error handling
    clearError,
    setError,

    // Utility
    getMessageById,
    getMessagesByType,
    getRecentMessages,
    searchMessages,
  };

  return (
    <ChatContext.Provider value={contextValue}>
      {children}
    </ChatContext.Provider>
  );
};

export default ChatProvider;