'use client';

import { clsx } from 'clsx';

export function Skeleton({ className }: { className?: string }) {
  return (
    <div className={clsx('rounded-md bg-slate-100 shimmer', className)} aria-hidden />
  );
}
