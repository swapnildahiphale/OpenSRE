'use client';

import { clsx } from 'clsx';
import type { ReactNode } from 'react';

/** Canonical team-console column — keeps H1 left edge at 214px (collapsed sidebar). */
export const TEAM_PAGE_COLUMN = 'max-w-[1240px] mx-auto px-10 w-full';

type Variant = 'standard' | 'fixedHeader' | 'conversation';

export function TeamPageShell({
  variant = 'standard',
  header,
  children,
  bleed,
  footer,
  className,
}: {
  variant?: Variant;
  header?: ReactNode;
  children?: ReactNode;
  /** Full-width zone under the fixed header band (topology canvas, KB explorer). */
  bleed?: ReactNode;
  footer?: ReactNode;
  className?: string;
}) {
  // Conversation: column-aligned scroll body + sticky footer; TopBar is 57px tall.
  if (variant === 'conversation') {
    return (
      <div className={clsx('flex flex-col min-h-[calc(100dvh-57px)]', className)}>
        <div className="flex-1 overflow-y-auto">
          <div className={TEAM_PAGE_COLUMN}>{children}</div>
        </div>
        {footer ? (
          <div className="shrink-0 border-t border-slate-200/60 bg-white/80 backdrop-blur dark:bg-stone-900/80 dark:border-stone-700">
            <div className={TEAM_PAGE_COLUMN}>{footer}</div>
          </div>
        ) : null}
      </div>
    );
  }

  // Fixed header: column header band, optional full-bleed body, column scroll children.
  if (variant === 'fixedHeader') {
    return (
      <div className={clsx('flex flex-col min-h-[calc(100dvh-57px)]', className)}>
        {header ? (
          <div className="shrink-0 border-b border-slate-200/70 bg-white dark:bg-slate-900">
            <div className={clsx(TEAM_PAGE_COLUMN, 'pt-10 pb-6 space-y-6')}>{header}</div>
          </div>
        ) : null}
        {bleed ? <div className="flex-1 min-h-0 flex flex-col">{bleed}</div> : null}
        {children ? (
          <div
            className={clsx(
              bleed ? 'shrink-0' : 'flex-1 min-h-0 overflow-y-auto',
            )}
          >
            <div className={clsx(TEAM_PAGE_COLUMN, 'py-8')}>{children}</div>
          </div>
        ) : null}
      </div>
    );
  }

  // Standard: single centered column with vertical padding.
  return (
    <div className={clsx(TEAM_PAGE_COLUMN, 'py-12 space-y-8', className)}>
      {header}
      {children}
    </div>
  );
}
