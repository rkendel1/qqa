import { assemblePrompt } from '@/lib/prompt/assemblePrompt';
import { Message } from '@/types/chat';

export async function generateCityHallResponse({
  messages,
  systemContext,
  userContext,
  customContext,
}: {
  messages: Message[];
  systemContext?: string;
  userContext?: Record<string, string>;
  customContext?: string;
}): Promise<string> {
  try {
    // Exclude system messages and assistant greeting
    const normalizedMessages = messages.filter(
      (m) =>
        !m.system &&
        !m.content.includes("Hello! I'm your City Hall Assistant. How can I help you today?")
    );

    const prompt = assemblePrompt({
      messages: normalizedMessages,
      systemContext,
      userContext,
      customContext,
    });

    const res = await fetch('http://localhost:8000/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: prompt }),
    });

    if (!res.ok) {
      const errorText = await res.text();
      console.error('Backend error:', res.status, errorText);
      throw new Error(`Backend error: ${res.status}`);
    }

    const data = await res.json();
    return data.answer || 'No answer found.';
  } catch (err) {
    console.error('Error generating response:', err);
    return 'There was an error processing your request.';
  }
}
