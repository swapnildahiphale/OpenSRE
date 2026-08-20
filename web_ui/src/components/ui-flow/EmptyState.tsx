'use client';

import type { ReactNode } from 'react';

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="rounded-[1.25rem] bg-white border border-slate-200/70 p-12 flex flex-col items-center text-center">
      <h2 className="text-xl font-medium tracking-tight text-slate-900">{title}</h2>
      {description ? (
        <p className="mt-3 text-sm text-slate-500 leading-relaxed max-w-[48ch]">{description}</p>
      ) : null}
      {action ? <div className="mt-6">{action}</div> : null}
    </div>
  );
}
