import React, { useState, useEffect } from 'react';
import { ChatWindow } from './ChatWindow';
import { MessageSquare, X } from 'lucide-react';

export const ChatWidget: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    const handleOpen = () => setIsOpen(true);
    window.addEventListener('open-chat', handleOpen);
    return () => window.removeEventListener('open-chat', handleOpen);
  }, []);

  return (
    <>
      {isOpen && <ChatWindow onClose={() => setIsOpen(false)} />}

      {/* Floating Launcher Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="fixed bottom-6 right-6 w-14 h-14 rounded-full bg-gradient-to-tr from-indigo-600 to-violet-600 hover:from-indigo-700 hover:to-violet-700 text-white shadow-xl shadow-indigo-500/25 flex items-center justify-center transition-all duration-300 hover:scale-105 active:scale-95 z-50 focus:outline-none focus:ring-4 focus:ring-indigo-300 dark:focus:ring-indigo-900"
        aria-label={isOpen ? 'Close chat assistant' : 'Open chat assistant'}
      >
        {isOpen ? (
          <X className="w-6 h-6 transition-transform duration-200" />
        ) : (
          <div className="relative">
            <MessageSquare className="w-6 h-6 transition-transform duration-200" />
            <span className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-emerald-400 border-2 border-white dark:border-slate-900 animate-pulse" />
          </div>
        )}
      </button>
    </>
  );
};
