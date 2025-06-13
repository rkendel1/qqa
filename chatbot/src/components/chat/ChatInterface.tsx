import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Send, Bot, AlertTriangle, RefreshCw, Trash2, Copy } from 'lucide-react';
import { MessageBubble } from './MessageBubble';
import { Message } from '@/types/chat';
import { cn } from '@/lib/utils';
import { generateCityHallResponse } from '@/lib/chatService';

interface ChatInterfaceProps {
  userContext?: { address?: string; userId?: string };
  systemContext?: string;
  className?: string;
  maxMessages?: number;
  onError?: (error: Error) => void;
}

export const ChatInterface: React.FC<ChatInterfaceProps> = ({
  userContext = { address: "7 Spinnaker Ln" },
  systemContext = "You are a helpful municipal assistant.",
  className,
  maxMessages = 100,
  onError,
}) => {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      type: 'assistant',
      content:
        "Hello! I'm your City Hall Assistant. How can I help you today? You can ask me about permits, zoning, city services, or other municipal questions.",
      timestamp: new Date().toISOString(),
    },
  ]);
  
  const [inputMessage, setInputMessage] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'online' | 'offline' | 'error'>('online');
  const [retryCount, setRetryCount] = useState(0);
  
  const messageEndRef = useRef<HTMLDivElement | null>(null);
  const scrollAreaRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Memoized welcome message to prevent unnecessary re-renders
  const welcomeMessage = useMemo(() => messages[0], []);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Focus textarea when component mounts
  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  // Cleanup abort controller on unmount
  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

  // Handle connection status
  useEffect(() => {
    const handleOnline = () => setConnectionStatus('online');
    const handleOffline = () => setConnectionStatus('offline');

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  const handleError = useCallback((error: Error) => {
    console.error('Chat error:', error);
    setConnectionStatus('error');
    onError?.(error);
  }, [onError]);

  const copyToClipboard = useCallback(async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
    } catch (error) {
      console.error('Failed to copy to clipboard:', error);
    }
  }, []);

  const clearChat = useCallback(() => {
    setMessages([welcomeMessage]);
    setRetryCount(0);
    setConnectionStatus('online');
  }, [welcomeMessage]);

  const handleSendMessage = useCallback(async () => {
    if (!inputMessage.trim() || isTyping || connectionStatus === 'offline') return;

    // Cancel any ongoing request
    abortControllerRef.current?.abort();
    abortControllerRef.current = new AbortController();

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      type: 'user',
      content: inputMessage.trim(),
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => {
      const updated = [...prev, userMessage];
      // Limit message history to prevent memory issues
      return updated.length > maxMessages 
        ? [welcomeMessage, ...updated.slice(-(maxMessages - 1))]
        : updated;
    });
    
    setInputMessage('');
    setIsTyping(true);
    setConnectionStatus('online');

    try {
      const response = await generateCityHallResponse({
        messages: [...messages, userMessage],
        userContext,
        systemContext,
        signal: abortControllerRef.current.signal,
      });

      const assistantMessage: Message = {
        id: `assistant-${Date.now()}`,
        type: 'assistant',
        content: response,
        timestamp: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
      setRetryCount(0);
      
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        return; // Request was cancelled, don't show error
      }

      const errorMessage: Message = {
        id: `error-${Date.now()}`,
        type: 'assistant',
        content: retryCount < 2 
          ? 'I apologize, but I encountered an error. Please try again, or click the retry button below.'
          : 'I\'m experiencing technical difficulties. Please try again later or contact support if the issue persists.',
        timestamp: new Date().toISOString(),
        isError: true,
      };

      setMessages((prev) => [...prev, errorMessage]);
      setRetryCount(prev => prev + 1);
      handleError(error as Error);
      
    } finally {
      setIsTyping(false);
    }
  }, [inputMessage, isTyping, connectionStatus, messages, userContext, systemContext, maxMessages, welcomeMessage, retryCount, handleError]);

  const handleRetry = useCallback(() => {
    if (messages.length > 1) {
      const lastUserMessage = [...messages].reverse().find(m => m.type === 'user');
      if (lastUserMessage) {
        setInputMessage(lastUserMessage.content);
        // Remove the last error message
        setMessages(prev => prev.filter(m => !m.isError || m.id !== prev[prev.length - 1]?.id));
      }
    }
  }, [messages]);

  const handleKeyPress = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  }, [handleSendMessage]);

  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputMessage(e.target.value);
  }, []);

  const getStatusIndicator = () => {
    switch (connectionStatus) {
      case 'offline':
        return { color: 'text-red-500', text: 'Offline' };
      case 'error':
        return { color: 'text-amber-500', text: 'Connection issues' };
      default:
        return { color: 'text-green-500', text: 'Online' };
    }
  };

  const status = getStatusIndicator();
  const canSendMessage = inputMessage.trim() && !isTyping && connectionStatus !== 'offline';

  return (
    <div 
      className={cn(
        "bg-white rounded-xl shadow-lg border border-slate-200 overflow-hidden flex flex-col h-[calc(100vh-280px)] min-h-[500px]",
        className
      )}
      role="main"
      aria-label="City Hall Chat Assistant"
    >
      {/* Header */}
      <div className="p-4 border-b border-slate-100 flex items-center justify-between">
        <div className="flex items-center">
          <div className="bg-blue-100 p-2 rounded-full mr-3">
            <Bot className="h-5 w-5 text-blue-600" aria-hidden="true" />
          </div>
          <div>
            <div className="font-medium text-slate-900">City Hall Assistant</div>
            <div className={cn("text-xs flex items-center gap-1", status.color)}>
              <div className="w-2 h-2 rounded-full bg-current" />
              {status.text} • Municipal queries
            </div>
          </div>
        </div>
        
        {/* Action buttons */}
        <div className="flex items-center gap-2">
          {connectionStatus === 'error' && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleRetry}
              className="text-amber-600 hover:text-amber-700"
              aria-label="Retry last message"
            >
              <RefreshCw className="h-4 w-4" />
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={clearChat}
            className="text-slate-500 hover:text-slate-700"
            aria-label="Clear chat history"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Messages */}
      <ScrollArea className="flex-grow p-4" ref={scrollAreaRef}>
        <div className="space-y-6" role="log" aria-live="polite" aria-label="Chat messages">
          {messages.map((message) => (
            <MessageBubble 
              key={message.id} 
              message={message}
              onCopy={() => copyToClipboard(message.content)}
            />
          ))}

          {/* Typing indicator */}
          {isTyping && (
            <div className="flex items-start gap-3" aria-label="Assistant is typing">
              <div className="bg-blue-100 p-2 rounded-full">
                <Bot className="h-5 w-5 text-blue-600" aria-hidden="true" />
              </div>
              <div className="px-4 py-3 bg-slate-100 rounded-2xl rounded-tl-none max-w-[85%]">
                <div className="flex space-x-2" role="status" aria-label="Typing">
                  <div className="h-2 w-2 bg-blue-500 rounded-full animate-bounce" />
                  <div
                    className="h-2 w-2 bg-blue-500 rounded-full animate-bounce"
                    style={{ animationDelay: '0.2s' }}
                  />
                  <div
                    className="h-2 w-2 bg-blue-500 rounded-full animate-bounce"
                    style={{ animationDelay: '0.4s' }}
                  />
                </div>
              </div>
            </div>
          )}

          {/* Connection error indicator */}
          {connectionStatus === 'offline' && (
            <div className="flex items-center justify-center p-4 bg-red-50 rounded-lg border border-red-200">
              <AlertTriangle className="h-5 w-5 text-red-500 mr-2" />
              <span className="text-red-700 text-sm">
                No internet connection. Please check your connection and try again.
              </span>
            </div>
          )}

          <div ref={messageEndRef} />
        </div>
      </ScrollArea>

      {/* Input area */}
      <div className="p-4 border-t border-slate-100">
        <div className="flex items-end gap-2">
          <div className="flex-grow relative">
            <Textarea
              ref={textareaRef}
              className="flex-grow min-h-[60px] max-h-[120px] resize-none pr-10"
              placeholder={
                connectionStatus === 'offline' 
                  ? "Offline - check your connection..."
                  : "Ask a question about city services, permits, etc..."
              }
              value={inputMessage}
              onChange={handleInputChange}
              onKeyDown={handleKeyPress}
              disabled={connectionStatus === 'offline' || isTyping}
              aria-label="Type your message"
              maxLength={1000}
            />
            {inputMessage.length > 800 && (
              <div className="absolute bottom-2 right-2 text-xs text-slate-400">
                {inputMessage.length}/1000
              </div>
            )}
          </div>
          <Button
            onClick={handleSendMessage}
            disabled={!canSendMessage}
            className={cn(
              'h-10 w-10 rounded-full p-2 flex items-center justify-center transition-colors',
              canSendMessage
                ? 'bg-blue-600 hover:bg-blue-700 text-white'
                : 'bg-slate-200 text-slate-400 cursor-not-allowed'
            )}
            aria-label="Send message"
          >
            <Send className="h-5 w-5" />
          </Button>
        </div>
        
        <div className="mt-2 text-xs text-center text-slate-500">
          For emergencies, please call <strong>911</strong> or your local emergency services directly.
        </div>
      </div>
    </div>
  );
};