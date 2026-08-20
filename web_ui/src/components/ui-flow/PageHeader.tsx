'use client';

import type { ReactNode } from 'react';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';

export function PageHeader({
  eyebrow,
  title,
  subtitle,
  actions,
  backHref,
  backLabel = 'Back',
}: {
  eyebrow: string;
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  backHref?: string;
  backLabel?: string;
}) {
  return (
    <header className="flex items-end justify-between gap-10">
      <div>
        {backHref ? (
          <Link
            href={backHref}
            className="text-sm text-slate-500 hover:text-slate-700 inline-flex items-center gap-1 mb-3"
          >
            <ArrowLeft className="w-4 h-4" />
            {backLabel}
          </Link>
        ) : null}
        <div className="text-[11px] uppercase tracking-[0.22em] text-slate-400 mb-4">
          {eyebrow}
        </div>
        <h1 className="text-5xl md:text-6xl font-medium tracking-tighter leading-[0.95] text-slate-900">
          {title}
          <span className="text-emerald-700">.</span>
        </h1>
        {subtitle ? <p className="mt-4 text-slate-500 text-sm max-w-2xl">{subtitle}</p> : null}
      </div>
      {actions ? <div className="shrink-0 flex items-center gap-3">{actions}</div> : null}
    </header>
  );
}
