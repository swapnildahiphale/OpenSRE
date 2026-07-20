'use client';

import type { ReactNode } from 'react';
import Link from 'next/link';
import { ArrowLeft, type LucideIcon } from 'lucide-react';

interface TeamPageHeaderProps {
  icon: LucideIcon;
  title: string;
  subtitle?: string;
  accent?: 'forest' | 'clay';
  backHref?: string;
  backLabel?: string;
  actions?: ReactNode;
}

export function TeamPageHeader({
  icon: Icon,
  title,
  subtitle,
  accent = 'forest',
  backHref,
  backLabel = 'Back',
  actions,
}: TeamPageHeaderProps) {
  const accentClass = accent === 'clay' ? 'bg-clay' : 'bg-forest';

  return (
    <div>
      {backHref ? (
        <Link
          href={backHref}
          className="text-sm text-stone-500 hover:text-stone-700 dark:hover:text-stone-300 flex items-center gap-1 mb-2"
        >
          <ArrowLeft className="w-4 h-4" />
          {backLabel}
        </Link>
      ) : null}

      <div className="flex justify-between">
        <div className="flex items-center gap-3">
          <div
            className={`w-10 h-10 rounded-xl flex items-center justify-center ${accentClass}`}
          >
            <Icon className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold text-stone-900 dark:text-white">
              {title}
            </h1>
            {subtitle ? (
              <p className="text-sm text-stone-500">{subtitle}</p>
            ) : null}
          </div>
        </div>

        {actions ? <div>{actions}</div> : null}
      </div>
    </div>
  );
}
