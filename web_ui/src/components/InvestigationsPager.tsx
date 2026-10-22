'use client';

import { clsx } from 'clsx';
import {
  buildInvestigationPageNumbers,
  investigationTotalPages,
} from '@/lib/investigationsPager';

export const INVESTIGATIONS_PAGE_SIZE = 20;

type InvestigationsPagerProps = {
  page: number;
  total: number;
  pageSize?: number;
  onPageChange: (page: number) => void;
};

export function InvestigationsPager({
  page,
  total,
  pageSize = INVESTIGATIONS_PAGE_SIZE,
  onPageChange,
}: InvestigationsPagerProps) {
  const totalPages = investigationTotalPages(total, pageSize);
  if (totalPages <= 1) return null;

  const pageNumbers = buildInvestigationPageNumbers(page, totalPages);

  return (
    <nav
      className="mt-6 flex flex-wrap items-center justify-center gap-2"
      aria-label="Investigations pagination"
    >
      <button
        type="button"
        onClick={() => onPageChange(page - 1)}
        disabled={page <= 1}
        className={pagerButtonClass(page <= 1)}
      >
        Previous
      </button>
      {pageNumbers.map((n) => (
        <button
          key={n}
          type="button"
          onClick={() => onPageChange(n)}
          aria-current={n === page ? 'page' : undefined}
          className={clsx(
            pagerButtonClass(false),
            'min-w-9 font-mono tabular-nums',
            n === page && 'border-emerald-400 bg-emerald-50 text-emerald-800',
          )}
        >
          {n}
        </button>
      ))}
      <button
        type="button"
        onClick={() => onPageChange(page + 1)}
        disabled={page >= totalPages}
        className={pagerButtonClass(page >= totalPages)}
      >
        Next
      </button>
    </nav>
  );
}

function pagerButtonClass(disabled: boolean): string {
  return clsx(
    'px-3 py-1.5 text-sm rounded-lg border border-slate-200/80 bg-white text-slate-700',
    'hover:bg-slate-50 transition-colors',
    disabled && 'opacity-40 cursor-not-allowed hover:bg-white',
  );
}
