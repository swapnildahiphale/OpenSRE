'use client';

import { clsx } from 'clsx';

export const SUMMARIZE_FOLLOW_UP = 'Summarize what you found so far';

interface Props {
  message: string;
  className?: string;
  /** When set, shows a one-click follow-up action (typically above the composer). */
  onFollowUp?: () => void;
  followUpLabel?: string;
}

export default function InvestigationHaltBanner({
  message,
  className,
  onFollowUp,
  followUpLabel = 'Summarize findings',
}: Props) {
  return (
    <div
      data-testid="investigation-halt-banner"
      className={clsx(
        'rounded-xl border border-yellow-200 dark:border-yellow-800/50 bg-yellow-50 dark:bg-yellow-900/20 px-4 py-3 text-sm text-yellow-900 dark:text-yellow-100',
        className,
      )}
    >
      <p>{message}</p>
      {onFollowUp ? (
        <button
          type="button"
          data-testid="investigation-halt-banner-follow-up"
          onClick={onFollowUp}
          className="mt-2 text-sm font-medium text-yellow-800 dark:text-yellow-200 underline underline-offset-2 hover:text-yellow-950 dark:hover:text-yellow-50"
        >
          {followUpLabel}
        </button>
      ) : null}
    </div>
  );
}
