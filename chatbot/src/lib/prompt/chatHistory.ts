import { Message } from '@/types/chat';

export function buildChatHistory(messages: Message[]): string {
  return messages
    .map((m) => `${m.type === 'user' ? 'User' : 'Assistant'}: ${m.content}`)
    .join('\n');
}