import React, { useState, useRef, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Send, Bot } from 'lucide-react';
import { MessageBubble } from './MessageBubble';
import { Message } from '@/types/chat';
import { cn } from '@/lib/utils';
import { generateCityHallResponse } from '@/lib/chatService';

export const ChatInterface = () => {
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
  const messageEndRef = useRef<HTMLDivElement | null>(null);
  const scrollAreaRef = useRef<HTMLDivElement | null>(null);

  // Example user and system context (replace with real context provider as needed)
  const userContext = { address: "7 Spinnaker Ln" };
  const systemContext = "You are a helpful municipal assistant.";

  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSendMessage = async () => {
    if (!inputMessage.trim()) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      type: 'user',
      content: inputMessage,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputMessage('');
    setIsTyping(true);

    try {
      // Prepare chat history excluding latest user message for prompt
      const chatHistory = [...messages, userMessage].filter(
        (m) => m.type !== 'system' && m.id !== userMessage.id
      );

      const response = await generateCityHallResponse({
        messages: [...messages, userMessage],
        userContext,
        systemContext,
      });

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content: response,
        timestamp: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 2).toString(),
          type: 'assistant',
          content: 'Error contacting the assistant. Please try again later.',
          timestamp: new Date().toISOString(),
        },
      ]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-lg border border-slate-200 overflow-hidden flex flex-col h-[calc(100vh-280px)] min-h-[500px]">
      <div className="p-4 border-b border-slate-100 flex items-center">
        <div className="bg-blue-100 p-2 rounded-full mr-3">
          <Bot className="h-5 w-5 text-blue-600" />
        </div>
        <div>
          <div className="font-medium text-slate-900">City Hall Assistant</div>
          <div className="text-xs text-slate-500">Online • Answers municipal queries</div>
        </div>
      </div>

      <ScrollArea className="flex-grow p-4" ref={scrollAreaRef}>
        <div className="space-y-6">
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}

          {isTyping && (
            <div className="flex items-start gap-3">
              <div className="bg-blue-100 p-2 rounded-full">
                <Bot className="h-5 w-5 text-blue-600" />
              </div>
              <div className="px-4 py-3 bg-slate-100 rounded-2xl rounded-tl-none max-w-[85%]">
                <div className="flex space-x-2">
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

          <div ref={messageEndRef} />
        </div>
      </ScrollArea>

      <div className="p-4 border-t border-slate-100">
        <div className="flex items-end gap-2">
          <Textarea
            className="flex-grow min-h-[60px] max-h-[120px] resize-none"
            placeholder="Ask a question about city services, permits, etc..."
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyDown={handleKeyPress}
          />
          <Button
            onClick={handleSendMessage}
            disabled={!inputMessage.trim() || isTyping}
            className={cn(
              'h-10 w-10 rounded-full p-2 flex items-center justify-center',
              !inputMessage.trim() || isTyping
                ? 'bg-slate-200 text-slate-400'
                : 'bg-blue-600 hover:bg-blue-700'
            )}
          >
            <Send className="h-5 w-5" />
          </Button>
        </div>
        <div className="mt-2 text-xs text-center text-slate-500">
          For emergencies, please call 911 or your local emergency services directly.
        </div>
      </div>
    </div>
  );
};