'use client';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Components } from 'react-markdown';

const components: Components = {
  h1: ({ children }) => (
    <h1 className="text-xl font-bold text-stone-900 dark:text-white mb-3 mt-4 first:mt-0">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="text-lg font-semibold text-stone-900 dark:text-white mb-2 mt-3 first:mt-0">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="text-base font-semibold text-stone-800 dark:text-stone-200 mb-1.5 mt-2">{children}</h3>
  ),
  p: ({ children }) => (
    <p className="text-sm text-stone-700 dark:text-stone-300 mb-2 leading-relaxed">{children}</p>
  ),
  ul: ({ children }) => (
    <ul className="list-disc list-inside text-sm text-stone-700 dark:text-stone-300 mb-2 space-y-0.5">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="list-decimal list-inside text-sm text-stone-700 dark:text-stone-300 mb-2 space-y-0.5">{children}</ol>
  ),
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  strong: ({ children }) => (
    <strong className="font-semibold text-stone-900 dark:text-white">{children}</strong>
  ),
  em: ({ children }) => <em className="italic text-stone-600 dark:text-stone-400">{children}</em>,
  code: ({ children, className }) => {
    const isBlock = className?.includes('language-');
    if (isBlock) {
      return (
        <code className="block bg-stone-100 dark:bg-stone-700 rounded p-3 text-xs font-mono text-stone-800 dark:text-stone-200 overflow-x-auto mb-2">
          {children}
        </code>
      );
    }
    return (
      <code className="bg-stone-100 dark:bg-stone-700 rounded px-1 py-0.5 text-xs font-mono text-stone-800 dark:text-stone-200">
        {children}
      </code>
    );
  },
  pre: ({ children }) => <pre className="mb-2">{children}</pre>,
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 border-stone-300 dark:border-stone-600 pl-3 text-sm text-stone-600 dark:text-stone-400 italic mb-2">
      {children}
    </blockquote>
  ),
  hr: () => <hr className="border-stone-200 dark:border-stone-600 my-3" />,
  table: ({ children }) => (
    <div className="overflow-x-auto mb-2">
      <table className="text-sm border-collapse w-full">{children}</table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border border-stone-200 dark:border-stone-600 bg-stone-50 dark:bg-stone-700 px-2 py-1 text-left text-xs font-semibold text-stone-700 dark:text-stone-300">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="border border-stone-200 dark:border-stone-600 px-2 py-1 text-sm text-stone-700 dark:text-stone-300">
      {children}
    </td>
  ),
};

export default function MarkdownFallback({ content }: { content: string }) {
  return (
    <div className="bg-white dark:bg-stone-800 p-3 rounded-lg border border-stone-200 dark:border-stone-600">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
