
import React from 'react';
import { cn } from '@/lib/utils';
import { Bot, User, Shield, Eye } from 'lucide-react';
import { MessageType, Message } from '@/types/chat';
import { formatDistanceToNow } from 'date-fns';

interface MessageBubbleProps {
  message: Message;
}

export const MessageBubble = ({ message }: MessageBubbleProps) => {
  const isUser = message.type === 'user';
  
  const getUserIcon = () => {
    // This would dynamically change based on user auth level in a real app
    const userType = localStorage.getItem('userType') || 'anonymous';
    
    if (userType === 'verified') return Shield;
    if (userType === 'registered') return User;
    return Eye;
  };

  const Icon = isUser ? getUserIcon() : Bot;
  
  const avatarColor = isUser ? 'bg-blue-600' : 'bg-blue-100';
  const iconColor = isUser ? 'text-white' : 'text-blue-600';
  
  const bubbleStyle = isUser 
    ? 'bg-blue-600 text-white rounded-2xl rounded-tr-none ml-auto'
    : 'bg-slate-100 text-slate-800 rounded-2xl rounded-tl-none';
    
  return (
    <div className={cn("flex items-start gap-3", isUser && "flex-row-reverse")}>
      <div className={cn("p-2 rounded-full", avatarColor)}>
        <Icon className={cn("h-5 w-5", iconColor)} />
      </div>
      
      <div className={cn("px-4 py-3 max-w-[85%]", bubbleStyle)}>
        <div className="prose prose-sm">
          {message.content}
        </div>
        <div className={cn("text-xs mt-1", isUser ? "text-blue-200" : "text-slate-500")}>
          {formatDistanceToNow(message.timestamp, { addSuffix: true })}
        </div>
      </div>
    </div>
  );
};
