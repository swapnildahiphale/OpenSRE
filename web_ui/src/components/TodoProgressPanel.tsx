'use client';

// web_ui/src/components/TodoProgressPanel.tsx
//
// Visualizes the agent's todo/task list inside the agent run window.
// Renders a simple "N/M done" summary plus a per-item list with status icons.
//
// Shown for any turn whose tool trace contains a TodoWrite or Task* tool call.
// Works for both live and replayed historical runs because the snapshot is
// derived purely from tool items (see deriveTodoSnapshot in lib/todoSnapshot).

import { CheckCircle, Loader2, Circle, ListTodo } from 'lucide-react';
import type { TodoItem, TodoStatus } from '@/lib/todoSnapshot';
import { todoProgress } from '@/lib/todoSnapshot';

const STATUS_TEXT: Record<TodoStatus, string> = {
  completed: 'text-green-500',
  in_progress: 'text-forest',
  pending: 'text-stone-300 dark:text-stone-600',
};

function statusIcon(s: TodoStatus) {
  switch (s) {
    case 'completed':
      return <CheckCircle className={`w-4 h-4 ${STATUS_TEXT.completed} flex-shrink-0 mt-0.5`} />;
    case 'in_progress':
      return <Loader2 className={`w-4 h-4 ${STATUS_TEXT.in_progress} animate-spin flex-shrink-0 mt-0.5`} />;
    default:
      return <Circle className={`w-4 h-4 ${STATUS_TEXT.pending} flex-shrink-0 mt-0.5`} />;
  }
}

function ItemRow({ t }: { t: TodoItem }) {
  const label = t.status === 'in_progress' ? (t.activeForm ?? t.subject) : t.subject;
  const className =
    t.status === 'completed'
      ? 'text-stone-400 line-through truncate'
      : t.status === 'in_progress'
        ? 'text-stone-900 dark:text-white font-medium truncate'
        : 'text-stone-600 dark:text-stone-400 truncate';
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
    <div className="rounded-lg border border-stone-200 dark:border-stone-700 bg-white dark:bg-stone-800 p-3">
      <div className="flex items-center gap-2 mb-2">
        <ListTodo className="w-4 h-4 text-forest flex-shrink-0" />
        <span className="text-sm font-medium text-stone-700 dark:text-stone-300">Plan</span>
        <span className="text-xs text-stone-400 ml-auto">
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
