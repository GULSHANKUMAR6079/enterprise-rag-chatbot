import React, { useState } from 'react';
import { ChatMessage } from '../types';
import { formatSafeMarkdown } from '../utils/sanitize';
import { Citations } from './Citations';
import { Check, Copy, RotateCcw, ShieldCheck, User } from 'lucide-react';

interface MessageItemProps {
  message: ChatMessage;
  onRetry?: (text: string) => void;
}

export const MessageItem: React.FC<MessageItemProps> = ({ message, onRetry }) => {
  const isUser = message.role === 'user';
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      className={`flex items-start gap-2.5 my-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}
      role="article"
      aria-label={`${message.role} message`}
    >
      {/* Avatar */}
      <div
        className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold shrink-0 shadow-sm ${
          isUser
            ? 'bg-slate-700 text-white'
            : 'bg-gradient-to-tr from-indigo-600 to-violet-600 text-white'
        }`}
      >
        {isUser ? <User className="w-4 h-4" /> : <ShieldCheck className="w-4 h-4" />}
      </div>

      {/* Message Bubble */}
      <div
        className={`relative max-w-[85%] rounded-2xl px-4 py-3 shadow-sm text-sm leading-relaxed transition-all ${
          isUser
            ? 'bg-indigo-600 text-white rounded-tr-sm'
            : message.error
            ? 'bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900/60 text-red-700 dark:text-red-300 rounded-tl-sm'
            : 'bg-white dark:bg-slate-900 border border-slate-200/90 dark:border-slate-800/90 text-slate-800 dark:text-slate-200 rounded-tl-sm'
        }`}
      >
        {/* Grounding Confidence Badge for Assistant */}
        {!isUser && message.confidence && (
          <div className="flex items-center justify-between gap-2 mb-1.5 pb-1 border-b border-slate-100 dark:border-slate-800 text-[11px] font-medium text-slate-500 dark:text-slate-400">
            <span className="inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
              <ShieldCheck className="w-3 h-3" />
              {message.confidence === 'grounded'
                ? 'Verified Knowledge'
                : message.confidence === 'partially_grounded'
                ? 'Partially Grounded'
                : 'Limited Evidence'}
            </span>
            <span className="text-[10px] text-slate-400">{message.timestamp}</span>
          </div>
        )}

        {/* Content Body (Sanitized Markdown) */}
        <div
          className="prose prose-sm dark:prose-invert max-w-none break-words"
          dangerouslySetInnerHTML={{ __html: formatSafeMarkdown(message.content) }}
        />

        {/* Citations if available */}
        {!isUser && message.citations && message.citations.length > 0 && (
          <Citations citations={message.citations} />
        )}

        {/* Error Retry Option */}
        {message.error && onRetry && (
          <button
            onClick={() => onRetry(message.content)}
            className="mt-2 inline-flex items-center gap-1.5 text-xs text-red-600 dark:text-red-400 hover:underline font-semibold"
          >
            <RotateCcw className="w-3 h-3" /> Retry Message
          </button>
        )}

        {/* Action Toolbar (Copy button) */}
        {!isUser && !message.error && (
          <div className="flex items-center justify-end gap-1 mt-2 pt-1 border-t border-slate-100 dark:border-slate-800/80">
            <button
              onClick={handleCopy}
              className="p-1 rounded text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
              title="Copy answer"
              aria-label="Copy answer to clipboard"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
