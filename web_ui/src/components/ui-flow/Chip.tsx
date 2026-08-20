'use client';

import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { clsx } from 'clsx';

export function Chip({
  active = false,
  className,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { active?: boolean; children?: ReactNode }) {
  return (
    <button
      type="button"
      {...props}
      className={clsx(
        'h-8 px-3 rounded-full text-xs font-medium transition',
        active
          ? 'bg-emerald-100/55 text-emerald-700'
          : 'bg-white border border-slate-200/70 text-slate-600 hover:bg-slate-50',
        className,
      )}
    >
      {children}
    </button>
  );
}
