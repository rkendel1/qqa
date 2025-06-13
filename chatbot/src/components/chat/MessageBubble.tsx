import React, { useMemo } from 'react';
import { cn } from '@/lib/utils';
import { Bot, User, Shield, Eye } from 'lucide-react';
import { MessageType, Message } from '@/types/chat';
import { formatDistanceToNow, parseISO, isValid } from 'date-fns';

// Enhanced types for better type safety
interface UserData {
  verified?: boolean;
  name?: string;
  id?: string;
}

type UserType = 'verified' | 'registered' | 'anonymous';

interface MessageBubbleProps {
  message: Message;
  currentUser?: UserData;
  accessToken?: string;
  className?: string;
}

export const MessageBubble = ({ 
  message, 
  currentUser, 
  accessToken,
  className 
}: MessageBubbleProps) => {
  const isUser = message.type === 'user';
  
  // Memoize user type calculation to avoid recalculation on every render
  const userType: UserType = useMemo(() => {
    if (!accessToken) return 'anonymous';
    return currentUser?.verified ? 'verified' : 'registered';
  }, [accessToken, currentUser?.verified]);

  // Memoize icon selection
  const Icon = useMemo(() => {
    if (!isUser) return Bot;
    
    switch (userType) {
      case 'verified':
        return Shield;
      case 'registered':
        return User;
      default:
        return Eye;
    }
  }, [isUser, userType]);

  // Memoize timestamp formatting with error handling
  const formattedTime = useMemo(() => {
    try {
      const date = parseISO(message.timestamp);
      if (!isValid(date)) {
        return 'Invalid date';
      }
      return formatDistanceToNow(date, { addSuffix: true });
    } catch (error) {
      console.warn('Error formatting timestamp:', error);
      return 'Unknown time';
    }
  }, [message.timestamp]);

  // Enhanced styling with CSS custom properties for easier theming
  const avatarStyles = useMemo(() => {
    const baseStyles = "flex items-center justify-center w-10 h-10 rounded-full flex-shrink-0";
    
    if (isUser) {
      const userStyles = {
        verified: "bg-green-600 text-white",
        registered: "bg-blue-600 text-white",
        anonymous: "bg-slate-600 text-white"
      };
      return cn(baseStyles, userStyles[userType]);
    }
    
    return cn(baseStyles, "bg-blue-100 text-blue-600");
  }, [isUser, userType]);

  const bubbleStyles = useMemo(() => {
    const baseStyles = "px-4 py-3 max-w-[min(85%,_28rem)] word-wrap break-words";
    
    if (isUser) {
      return cn(
        baseStyles,
        "bg-blue-600 text-white rounded-2xl rounded-tr-md ml-auto",
        "shadow-sm"
      );
    }
    
    return cn(
      baseStyles,
      "bg-white text-slate-800 rounded-2xl rounded-tl-md border border-slate-200",
      "shadow-sm"
    );
  }, [isUser]);

  const timestampStyles = useMemo(() => {
    return cn(
      "text-xs mt-2 font-medium",
      isUser ? "text-blue-100" : "text-slate-500"
    );
  }, [isUser]);

  // Enhanced accessibility attributes
  const getAriaLabel = () => {
    const sender = isUser ? `You (${userType})` : 'Assistant';
    return `Message from ${sender}, sent ${formattedTime}`;
  };

  return (
    <div 
      className={cn(
        "flex items-end gap-3 group transition-opacity hover:opacity-100",
        isUser && "flex-row-reverse",
        className
      )}
      role="listitem"
      aria-label={getAriaLabel()}
    >
      {/* Avatar */}
      <div className={avatarStyles} aria-hidden="true">
        <Icon className="h-5 w-5" />
      </div>
      
      {/* Message content */}
      <div className={bubbleStyles}>
        {/* Message text */}
        <div 
          className="prose prose-sm max-w-none"
          style={{
            // Ensure proper text rendering
            wordBreak: 'break-word',
            overflowWrap: 'break-word',
            hyphens: 'auto'
          }}
        >
          {message.content}
        </div>
        
        {/* Timestamp */}
        <div className={timestampStyles}>
          <time 
            dateTime={message.timestamp}
            title={new Date(message.timestamp).toLocaleString()}
          >
            {formattedTime}
          </time>
        </div>
      </div>
    </div>
  );
};

// Default export for easier importing
export default MessageBubble;