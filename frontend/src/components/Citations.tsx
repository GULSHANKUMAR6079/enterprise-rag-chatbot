import React from 'react';
import { SourceCitation } from '../types';
import { BookOpen, ExternalLink } from 'lucide-react';

interface CitationsProps {
  citations: SourceCitation[];
}

export const Citations: React.FC<CitationsProps> = ({ citations }) => {
  if (!citations || citations.length === 0) return null;

  return (
    <div className="mt-3 pt-2.5 border-t border-slate-200/80 dark:border-slate-800/80">
      <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-600 dark:text-slate-400 mb-2">
        <BookOpen className="w-3.5 h-3.5 text-indigo-500" />
        <span>Verified Sources ({citations.length})</span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {citations.map((c) => (
          <div
            key={c.id}
            className="inline-flex items-center gap-1 bg-slate-100 dark:bg-slate-800/90 hover:bg-indigo-50 dark:hover:bg-indigo-950/60 border border-slate-200 dark:border-slate-700/60 text-slate-700 dark:text-slate-300 text-xs px-2 py-1 rounded-md transition-all shadow-sm group"
          >
            <span className="font-bold text-indigo-600 dark:text-indigo-400">[{c.id}]</span>
            <span className="truncate max-w-[180px]">{c.title}</span>
            {c.url && (
              <a
                href={c.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400"
                aria-label={`Open source ${c.title}`}
              >
                <ExternalLink className="w-3 h-3" />
              </a>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
