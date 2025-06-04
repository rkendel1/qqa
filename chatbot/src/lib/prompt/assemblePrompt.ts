import { buildSystemContext } from './systemContext';
import { buildUserContext } from './userContext';
import { buildCustomContext } from './customContext';
import { buildChatHistory } from './chatHistory';
import { Message } from '@/types/chat';

export function assemblePrompt({
  systemContext,
  userContext,
  customContext,
  messages,
}: {
  systemContext?: string;
  userContext?: Record<string, string>;
  customContext?: string;
  messages: Message[];
}): string {
  return [
    buildSystemContext(systemContext),
    buildUserContext(userContext),
    buildCustomContext(customContext),
    buildChatHistory(messages),
    'Assistant:',
  ]
    .filter(Boolean)
    .join('\n\n');
}