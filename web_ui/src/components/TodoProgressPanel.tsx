'use client';

// Visualizes the agent's todo/task list inside the agent run window.
// Renders a simple "N/M done" summary plus a per-item list with status icons.

import { Circle, ListTodo } from 'lucide-react';
import { SuccessCheck } from '@/components/ui-flow/SuccessCheck';
import type { TodoItem, TodoStatus } from '@/lib/todoSnapshot';
import { todoProgress } from '@/lib/todoSnapshot';

const STATUS_TEXT: Record<TodoStatus, string> = {
  completed: 'text-emerald-500',
  in_progress: 'text-emerald-600',
  pending: 'text-slate-300 dark:text-stone-600',
};

function statusIcon(s: TodoStatus) {
  switch (s) {
    case 'completed':
      return (
        <SuccessCheck
          className={`w-3 h-3 ${STATUS_TEXT.completed} flex-shrink-0 mt-1`}
        />
      );
    case 'in_progress':
      return (
        <span
          className="live-dot w-2 h-2 rounded-full flex-shrink-0 mt-1.5"
          aria-hidden="true"
        />
      );
    default:
      return (
        <Circle
          className={`w-3 h-3 ${STATUS_TEXT.pending} flex-shrink-0 mt-1`}
          strokeWidth={1.75}
        />
      );
  }
}

function ItemRow({ t }: { t: TodoItem }) {
  const label = t.status === 'in_progress' ? (t.activeForm ?? t.subject) : t.subject;
  const className =
    t.status === 'completed'
      ? 'text-slate-400 line-through truncate'
      : t.status === 'in_progress'
        ? 'text-slate-900 dark:text-white font-medium truncate'
        : 'text-slate-600 dark:text-stone-400 truncate';
  return (
    <li className="flex items-start gap-2 text-sm">
      {statusIcon(t.status)}
      <span className={className}>{label}</span>
    </li>
  );
}

export default function TodoProgressPanel({ todos }: { todos: TodoItem[] }) {
  if (todos.length === 0) return null;

  const { total, completed } = todoProgress(todos);

  return (
    <div className="rounded-xl border border-slate-200/80 dark:border-stone-700 bg-white dark:bg-stone-800 p-3">
      <div className="flex items-center gap-2 mb-2">
        <ListTodo className="w-4 h-4 text-emerald-600 flex-shrink-0" />
        <span className="text-sm font-medium text-slate-700 dark:text-stone-300">Plan</span>
        <span className="text-xs text-slate-400 ml-auto tabular-nums">
          {completed}/{total} done
        </span>
      </div>

      <ul className="space-y-1">
        {todos.map((t) => (
          <ItemRow key={t.id} t={t} />
        ))}
      </ul>
    </div>
  );
}
