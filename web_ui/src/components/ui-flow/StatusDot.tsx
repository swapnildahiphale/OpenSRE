'use client';

import { clsx } from 'clsx';

type Tone = 'live' | 'idle' | 'warn' | 'danger';

const TONE: Record<Exclude<Tone, 'live'>, string> = {
  idle: 'bg-slate-300',
  warn: 'bg-amber-400',
  danger: 'bg-rose-500',
};

export function StatusDot({ tone, label }: { tone: Tone; label: string }) {
  return (
    <span
      className={clsx(
        'w-2.5 h-2.5 rounded-full shrink-0',
        tone === 'live' ? 'live-dot' : TONE[tone],
      )}
      aria-label={label}
      title={label}
    />
  );
}
