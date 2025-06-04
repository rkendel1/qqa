import { useContext } from 'react';
import { ChatContext } from './ChatContext'; // You might need to export ChatContext from ChatContext.tsx

export const useChat = () => {
  const context = useContext(ChatContext);
  if (!context) throw new Error('useChat must be used within a ChatProvider');
  return context;
};