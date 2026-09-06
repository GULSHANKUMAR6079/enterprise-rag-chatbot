/**
 * Safe markdown formatter that escapes HTML characters to prevent XSS attacks.
 * Formats bold, italic, code blocks, lists, and citation brackets [1].
 */
export function formatSafeMarkdown(text: string): string {
  if (!text) return '';

  // 1. HTML entity escape to neutralize any raw HTML / XSS injection
  let safe = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');

  // 2. Code blocks ```code```
  safe = safe.replace(/```([\s\S]*?)```/g, '<pre class="bg-slate-800 text-slate-100 p-2.5 rounded my-2 text-xs overflow-x-auto font-mono"><code>$1</code></pre>');

  // 3. Inline code `code`
  safe = safe.replace(/`([^`]+)`/g, '<code class="bg-slate-200 dark:bg-slate-800 text-indigo-600 dark:text-indigo-400 px-1.5 py-0.5 rounded text-xs font-mono">$1</code>');

  // 4. Bold **text**
  safe = safe.replace(/\*\*([^*]+)\*\*/g, '<strong class="font-semibold text-slate-900 dark:text-white">$1</strong>');

  // 5. Italic *text*
  safe = safe.replace(/\*([^*]+)\*/g, '<em class="italic">$1</em>');

  // 6. Highlight Citation badges like [1], [2]
  safe = safe.replace(/\[(\d+)\]/g, '<span class="inline-flex items-center justify-center bg-indigo-100 dark:bg-indigo-900/60 text-indigo-700 dark:text-indigo-300 text-[11px] font-bold px-1.5 py-0.5 rounded-full mx-0.5 cursor-pointer hover:bg-indigo-200 dark:hover:bg-indigo-800 transition-colors" title="Source Citation [$1]">[$1]</span>');

  // 7. Bullet lists
  safe = safe.replace(/^\s*[-*]\s+(.+)$/gm, '<li class="ml-4 list-disc">$1</li>');

  // 8. Newlines to <br/>
  safe = safe.replace(/\n/g, '<br/>');

  return safe;
}
