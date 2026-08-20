'use client';

import type { HTMLAttributes, ReactNode } from 'react';
import { clsx } from 'clsx';

type PanelAs = 'div' | 'ul' | 'section';

export function Panel({
  as: Tag = 'div',
  className,
  children,
  ...props
}: HTMLAttributes<HTMLElement> & { as?: PanelAs; children: ReactNode }) {
  return (
    <Tag
      {...props}
      className={clsx(
        'bg-white border border-slate-200/70 rounded-[1.25rem] overflow-hidden',
        className,
      )}
    >
      {children}
    </Tag>
  );
}
