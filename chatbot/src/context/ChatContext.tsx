import React, { createContext, useEffect, useState, ReactNode } from 'react';

export interface Message {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  timestamp?: string;
  system?: boolean;
}

interface ChatContextType {
  messages: Message[];
  userContext?: Record<string, string>;
  customContext?: string;
  systemContext?: string;

  addMessage: (msg: Message) => void;
  clearMessages: () => void;

  setUserContext: React.Dispatch<React.SetStateAction<Record<string, string> | undefined>>;
  setCustomContext: React.Dispatch<React.SetStateAction<string | undefined>>;
  setSystemContext: React.Dispatch<React.SetStateAction<string | undefined>>;

  loadUserContext: () => Promise<void>;
  loadCustomContext: () => Promise<void>;
}

export const ChatContext = createContext<ChatContextType | undefined>(undefined);

export const ChatProvider = ({ children }: { children: ReactNode }) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [userContext, setUserContext] = useState<Record<string, string> | undefined>(undefined);
  const [customContext, setCustomContext] = useState<string | undefined>(undefined);
  const [systemContext, setSystemContext] = useState<string | undefined>(
    "You are a helpful assistant trained to answer municipal questions like permits, zoning, and city services."
  );

  // Load persisted state on mount
  useEffect(() => {
    if (typeof window === 'undefined') return;

    const storedMessages = sessionStorage.getItem('chat_messages');
    if (storedMessages) {
      try {
        setMessages(JSON.parse(storedMessages));
      } catch {
        sessionStorage.removeItem('chat_messages');
      }
    }

    const storedUserContext = sessionStorage.getItem('user_context');
    if (storedUserContext) {
      try {
        setUserContext(JSON.parse(storedUserContext));
      } catch {
        sessionStorage.removeItem('user_context');
      }
    }

    const storedCustomContext = sessionStorage.getItem('custom_context');
    if (storedCustomContext) {
      setCustomContext(storedCustomContext);
    }

    const storedSystemContext = sessionStorage.getItem('system_context');
    if (storedSystemContext) {
      setSystemContext(storedSystemContext);
    }
  }, []);

  // Persist on changes
  useEffect(() => {
    if (typeof window === 'undefined') return;
    sessionStorage.setItem('chat_messages', JSON.stringify(messages));
  }, [messages]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (userContext) {
      sessionStorage.setItem('user_context', JSON.stringify(userContext));
    } else {
      sessionStorage.removeItem('user_context');
    }
  }, [userContext]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (customContext) {
      sessionStorage.setItem('custom_context', customContext);
    } else {
      sessionStorage.removeItem('custom_context');
    }
  }, [customContext]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (systemContext) {
      sessionStorage.setItem('system_context', systemContext);
    } else {
      sessionStorage.removeItem('system_context');
    }
  }, [systemContext]);

  const addMessage = (msg: Message) => {
    setMessages((prev) => [...prev, msg]);
  };

  const clearMessages = () => {
    setMessages([]);
    if (typeof window !== 'undefined') {
      sessionStorage.removeItem('chat_messages');
    }
  };

  const loadUserContext = async () => {
    try {
      const res = await fetch('http://localhost:8000/user/context', {
        headers: {
          Authorization: `Bearer ${localStorage.getItem('access_token') || ''}`,
        },
      });

      if (!res.ok) throw new Error('Failed to load user context');

      const data = await res.json();
      setUserContext(data.userContext || {});

      // Optionally, merge backend messages if provided
      const backendMessages: Message[] = data.messages || [];
      setMessages((prev) => {
        const existingIds = new Set(prev.map((m) => m.id));
        const newMessages = backendMessages.filter((m) => !existingIds.has(m.id));
        return [...prev, ...newMessages];
      });
    } catch (error) {
      console.error('Error loading user context:', error);
    }
  };

  const loadCustomContext = async () => {
    try {
      const res = await fetch('http://localhost:8000/custom/context', {
        headers: {
          Authorization: `Bearer ${localStorage.getItem('access_token') || ''}`,
        },
      });

      if (!res.ok) throw new Error('Failed to load custom context');

      const data = await res.json();
      setCustomContext(data.customContext || '');
    } catch (error) {
      console.error('Error loading custom context:', error);
    }
  };

  return (
    <ChatContext.Provider
      value={{
        messages,
        userContext,
        customContext,
        systemContext,
        addMessage,
        clearMessages,
        setUserContext,
        setCustomContext,
        setSystemContext,
        loadUserContext,
        loadCustomContext,
      }}
    >
      {children}
    </ChatContext.Provider>
  );
};