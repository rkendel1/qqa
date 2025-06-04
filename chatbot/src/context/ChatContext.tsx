import React, { createContext, useEffect, useState, ReactNode } from 'react';

export interface Message {
  type: 'user' | 'assistant';
  content: string;
  timestamp?: string;
}

interface ChatContextType {
  messages: Message[];
  addMessage: (msg: Message) => void;
  clearMessages: () => void;
  loadUserContext: () => Promise<void>;
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
}

export const ChatContext = createContext<ChatContextType | undefined>(undefined);

export const ChatProvider = ({ children }: { children: ReactNode }) => {
  const [messages, setMessages] = useState<Message[]>([]);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const stored = sessionStorage.getItem('chat_messages');
      if (stored) {
        try {
          setMessages(JSON.parse(stored));
        } catch {
          sessionStorage.removeItem('chat_messages');
        }
      }
    }
  }, []);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      sessionStorage.setItem('chat_messages', JSON.stringify(messages));
    }
  }, [messages]);

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
      const backendMessages: Message[] = data.messages || [];

      setMessages((prev) => {
        const existingTimestamps = new Set(prev.map(m => m.timestamp));
        const newMessages = backendMessages.filter(m => !existingTimestamps.has(m.timestamp));
        return [...prev, ...newMessages];
      });
    } catch (error) {
      console.error('Error loading user context:', error);
    }
  };

  return (
    <ChatContext.Provider
      value={{ messages, addMessage, clearMessages, loadUserContext, setMessages }}
    >
      {children}
    </ChatContext.Provider>
  );
};