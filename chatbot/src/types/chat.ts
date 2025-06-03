
export type MessageType = 'user' | 'assistant';

export interface Message {
  id: string;
  type: MessageType;
  content: string;
  timestamp: Date;
}
