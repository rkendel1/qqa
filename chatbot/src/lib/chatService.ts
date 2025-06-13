
import { Message } from '@/types/chat';

export async function generateCityHallResponse({
    messages,
    userContext,
    systemContext,
  }: {
    messages: Message[];
    userContext?: Record<string, string>;
    systemContext?: string;
  }): Promise<string> {
    const latestUserMessage = messages.filter(m => m.type === 'user').at(-1);
    const chatHistory = messages.filter(m => !m.system && m !== latestUserMessage);
  
    const payload = {
      question: latestUserMessage?.content || '',
      system_context: systemContext,
      chat_history: chatHistory
        .filter(
          m =>
            m.type !== 'assistant' ||
            m.content !==
              "Hello! I'm your City Hall Assistant. How can I help you today? You can ask me about permits, zoning, city services, or other municipal questions."
        )
        .map(m => ({ type: m.type, content: m.content })),
    };
  
    const res = await fetch('http://localhost:8000/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  
    const data = await res.json();
    return data.answer || 'No answer found.';
  }