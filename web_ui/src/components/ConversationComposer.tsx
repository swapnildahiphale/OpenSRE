'use client';

import { useState } from 'react';
import { Send, Square } from 'lucide-react';

interface Props {
  onSend: (message: string) => void;
  onQueueMessage?: (message: string) => void | Promise<void>;
  onStop?: () => void;
  busy?: boolean;
  queuedMessages?: string[];
  disabled?: boolean;
  disabledReason?: string;
  placeholder?: string;
}

export default function ConversationComposer({
  onSend,
  onQueueMessage,
  onStop,
  busy,
  queuedMessages = [],
  disabled,
  disabledReason,
  placeholder: idlePlaceholder = 'Ask a follow-up…',
}: Props) {
  const [value, setValue] = useState('');
  const [queueError, setQueueError] = useState<string | null>(null);

  // Running investigations always get a Stop control, even when follow-ups are
  // not yet resumable (e.g. detail page opened from the drawer mid-run).
  if (disabled && !busy) {
    return (
      <div className="mt-6 rounded-xl border border-stone-200 dark:border-stone-700 bg-stone-50 dark:bg-stone-800/40 px-4 py-3 text-sm text-stone-500">
        {disabledReason}
      </div>
    );
  }

  const submit = async () => {
    const text = value.trim();
    if (!text) return;
    if (busy && onQueueMessage) {
      setQueueError(null);
      try {
        await Promise.resolve(onQueueMessage(text));
        setValue('');
      } catch (err) {
        setQueueError((err as Error).message || 'Failed to queue message');
      }
      return;
    }
    if (busy) return;
    onSend(text);
    setValue('');
  };

  const placeholder = busy ? 'Queue a message…' : idlePlaceholder;

  return (
    <div className="mt-6">
      {queuedMessages.length > 0 && (
        <ul
          data-testid="conversation-composer-queued-list"
          className="mb-2 space-y-1.5"
        >
          {queuedMessages.map((msg, index) => (
            <li
              key={`${index}-${msg}`}
              data-testid="conversation-composer-queued-item"
              className="flex items-start justify-between gap-3 text-sm"
            >
              <span className="text-stone-700 dark:text-stone-300">{msg}</span>
              <span className="shrink-0 rounded-full bg-forest/10 px-2 py-0.5 text-xs font-medium text-forest">
                Queued
              </span>
            </li>
          ))}
        </ul>
      )}
      {queueError ? (
        <p
          data-testid="conversation-composer-queue-error"
          className="mb-2 text-sm text-clay"
        >
          {queueError}
        </p>
      ) : null}
      <div className="flex items-end gap-2">
        <textarea
          data-testid="conversation-composer-input"
          className="flex-1 resize-none rounded-xl border border-stone-200 dark:border-stone-700 bg-white dark:bg-stone-900 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-forest/40 disabled:opacity-60"
          rows={2}
          placeholder={placeholder}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void submit(); } }}
        />
        {busy && onStop ? (
          <button
            data-testid="conversation-composer-stop"
            onClick={onStop}
            className="h-11 w-11 shrink-0 rounded-xl bg-clay text-white flex items-center justify-center"
            aria-label="Stop investigation"
          >
            <Square className="w-4 h-4 fill-current" />
          </button>
        ) : null}
        <button
          data-testid="conversation-composer-send"
          onClick={() => void submit()}
          disabled={!value.trim()}
          className="h-11 w-11 shrink-0 rounded-xl bg-forest text-white flex items-center justify-center disabled:opacity-40"
          aria-label={busy ? 'Queue message' : 'Send follow-up'}
        >
          <Send className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
}
