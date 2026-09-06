import React, { useState, useEffect, useRef } from 'react';
import { ChatMessage, SourceCitation } from '../types';
import { MessageItem } from './MessageItem';
import { TypingIndicator } from './TypingIndicator';
import {
  Moon,
  Sun,
  Trash2,
  X,
  Send,
  Square,
  ShieldCheck,
  AlertCircle
} from 'lucide-react';

interface ChatWindowProps {
  onClose: () => void;
}

export const ChatWindow: React.FC<ChatWindowProps> = ({ onClose }) => {
  const [messages, setMessages] = useState<ChatMessage[]>(() => [
    {
      id: 'welcome',
      role: 'assistant',
      content:
        'Hello! I am the official enterprise website assistant. How can I help you today with our company, products, or services?',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      confidence: 'grounded'
    }
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [darkMode, setDarkMode] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isStreaming]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const toggleDarkMode = () => {
    setDarkMode(!darkMode);
    document.documentElement.classList.toggle('dark');
  };

  const handleClearHistory = async () => {
    if (conversationId) {
      try {
        await fetch(`/api/v1/conversations/${conversationId}`, { method: 'DELETE' });
      } catch (err) {
        // Continue clearing local state
      }
    }
    setConversationId(null);
    setMessages([
      {
        id: 'welcome-reset',
        role: 'assistant',
        content: 'Conversation reset. How can I assist you today?',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        confidence: 'grounded'
      }
    ]);
  };

  const handleStopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsStreaming(false);
  };

  const handleSendMessage = async (textToSend?: string) => {
    const text = (textToSend || inputValue).trim();
    if (!text || isStreaming) return;

    setErrorMessage(null);
    setInputValue('');

    const userMessageId = `user-${Date.now()}`;
    const userMessage: ChatMessage = {
      id: userMessageId,
      role: 'user',
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    const assistantMessageId = `asst-${Date.now()}`;
    const initialAssistantMessage: ChatMessage = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      isStreaming: true
    };

    setMessages((prev) => [...prev, userMessage, initialAssistantMessage]);
    setIsStreaming(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      // Use SSE streaming endpoint
      const response = await fetch('/api/v1/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          conversation_id: conversationId,
          stream: true
        }),
        signal: controller.signal
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.message || `Server responded with status ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let accumulatedContent = '';
      let receivedCitations: SourceCitation[] = [];
      let finalConfidence: any = 'grounded';

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const dataStr = line.slice(6).trim();
              if (!dataStr) continue;

              try {
                const parsed = JSON.parse(dataStr);
                if (parsed.token) {
                  accumulatedContent += parsed.token;
                  setMessages((prev) =>
                    prev.map((msg) =>
                      msg.id === assistantMessageId
                        ? { ...msg, content: accumulatedContent }
                        : msg
                    )
                  );
                } else if (parsed.conversation_id) {
                  setConversationId(parsed.conversation_id);
                  if (parsed.sources) receivedCitations = parsed.sources;
                  if (parsed.confidence) finalConfidence = parsed.confidence;
                } else if (parsed.message) {
                  // Guardrail rejection or error
                  accumulatedContent = parsed.message;
                  finalConfidence = 'insufficient_evidence';
                }
              } catch (e) {
                // Ignore chunk parse errors
              }
            }
          }
        }
      }

      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMessageId
            ? {
                ...msg,
                content: accumulatedContent || 'No response generated.',
                citations: receivedCitations,
                confidence: finalConfidence,
                isStreaming: false
              }
            : msg
        )
      );
    } catch (err: any) {
      if (err.name === 'AbortError') {
        // User voluntarily stopped generation
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMessageId ? { ...msg, isStreaming: false } : msg
          )
        );
      } else {
        const errMsg = err.message || 'Failed to connect to the assistant.';
        setErrorMessage(errMsg);
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMessageId
              ? {
                  ...msg,
                  content: errMsg,
                  error: true,
                  isStreaming: false
                }
              : msg
          )
        );
      }
    } finally {
      setIsStreaming(false);
      abortControllerRef.current = null;
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    } else if (e.key === 'Escape') {
      onClose();
    }
  };

  return (
    <div
      className="fixed bottom-24 right-6 w-[410px] max-w-[calc(100vw-2rem)] h-[620px] max-h-[calc(100vh-8rem)] bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-2xl flex flex-col overflow-hidden z-50 transition-all"
      role="dialog"
      aria-modal="true"
      aria-label="Enterprise Chat Assistant"
    >
      {/* Header */}
      <div className="px-4 py-3.5 bg-gradient-to-r from-indigo-600 to-violet-600 text-white flex items-center justify-between shadow-sm">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-full bg-white/20 backdrop-blur-md flex items-center justify-center">
            <ShieldCheck className="w-5 h-5 text-white" />
          </div>
          <div>
            <h2 className="text-sm font-bold tracking-tight">Enterprise Assistant</h2>
            <div className="flex items-center gap-1.5 text-[11px] text-indigo-100">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span>Official Assistant • Verified Knowledge</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1">
          <button
            onClick={toggleDarkMode}
            className="p-1.5 rounded-lg hover:bg-white/15 text-white transition-colors"
            title="Toggle theme"
            aria-label="Toggle theme"
          >
            {darkMode ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </button>
          <button
            onClick={handleClearHistory}
            className="p-1.5 rounded-lg hover:bg-white/15 text-white transition-colors"
            title="Reset conversation"
            aria-label="Reset conversation"
          >
            <Trash2 className="w-4 h-4" />
          </button>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-white/15 text-white transition-colors"
            title="Close chat"
            aria-label="Close chat"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Error Banner if any */}
      {errorMessage && (
        <div className="bg-red-50 dark:bg-red-950/50 border-b border-red-200 dark:border-red-900/60 px-4 py-2 flex items-center gap-2 text-xs text-red-600 dark:text-red-300">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span className="truncate">{errorMessage}</span>
        </div>
      )}

      {/* Messages Container */}
      <div className="flex-1 overflow-y-auto px-4 py-3 bg-slate-50/50 dark:bg-slate-950/40">
        {messages.map((m) => (
          <MessageItem key={m.id} message={m} onRetry={(text) => handleSendMessage(text)} />
        ))}
        {isStreaming && <TypingIndicator />}
        <div ref={messagesEndRef} />
      </div>

      {/* Footer / Input Area */}
      <div className="p-3 bg-white dark:bg-slate-900 border-t border-slate-200 dark:border-slate-800">
        {isStreaming && (
          <div className="flex justify-center mb-2">
            <button
              onClick={handleStopGeneration}
              className="inline-flex items-center gap-1.5 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 text-xs font-semibold px-3 py-1 rounded-full border border-slate-300 dark:border-slate-700 transition-colors shadow-sm"
            >
              <Square className="w-3 h-3 fill-current text-red-500" />
              Stop Generating
            </button>
          </div>
        )}

        <div className="flex items-end gap-2 bg-slate-100 dark:bg-slate-800/80 rounded-xl p-1.5 border border-slate-200 dark:border-slate-700/80 focus-within:border-indigo-500 dark:focus-within:border-indigo-400 transition-all">
          <textarea
            ref={inputRef}
            rows={1}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question about our company or services..."
            className="flex-1 bg-transparent resize-none outline-none text-sm text-slate-800 dark:text-slate-200 placeholder-slate-400 dark:placeholder-slate-500 px-2 py-1 max-h-28 overflow-y-auto"
            disabled={isStreaming}
          />

          <button
            onClick={() => handleSendMessage()}
            disabled={!inputValue.trim() || isStreaming}
            className={`p-2 rounded-lg transition-all ${
              inputValue.trim() && !isStreaming
                ? 'bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm'
                : 'text-slate-400 cursor-not-allowed'
            }`}
            aria-label="Send message"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>

        <div className="flex items-center justify-between text-[10px] text-slate-400 px-1 mt-1.5">
          <span>Incerro Assistant • Guardrail Protected</span>
          <span>{inputValue.length}/4000</span>
        </div>
      </div>
    </div>
  );
};
