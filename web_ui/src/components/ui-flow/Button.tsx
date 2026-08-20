'use client';

import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { clsx } from 'clsx';

type Variant = 'primary' | 'secondary' | 'soft' | 'ghost';

/** flow-ui soft accent (e.g. Overview “Resume last”) — primary CTAs use this, not solid emerald */
export const ACCENT_BUTTON =
  'bg-emerald-100/50 text-emerald-700 hover:bg-emerald-100/80';

const VARIANT: Record<Variant, string> = {
  primary: ACCENT_BUTTON,
  secondary: 'bg-white text-slate-900 border border-slate-200/70 hover:bg-slate-50',
  soft: ACCENT_BUTTON,
  ghost: 'text-slate-600 hover:bg-slate-100/70 hover:text-slate-900',
};

export function Button({
  variant = 'secondary',
  className,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; children?: ReactNode }) {
  return (
    <button
      {...props}
      className={clsx(
        'inline-flex items-center gap-2 h-9 px-3.5 rounded-full text-[13.5px] font-medium transition active:translate-y-[1px] disabled:opacity-50',
        VARIANT[variant],
        className,
      )}
    >
      {children}
    </button>
  );
}
