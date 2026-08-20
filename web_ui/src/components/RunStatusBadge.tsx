import {
  Activity,
  CheckCircle,
  Clock,
  Square,
  XCircle,
} from 'lucide-react';

export type RunStatus =
  | 'running'
  | 'completed'
  | 'failed'
  | 'timeout'
  | 'interrupted';

const RUN_STATUS_COLORS: Record<string, string> = {
  completed: 'text-green-600 bg-green-100',
  failed: 'text-rose-600 bg-rose-100',
  timeout: 'text-yellow-600 bg-yellow-100',
  interrupted: 'text-amber-600 bg-amber-100',
  running: 'text-emerald-600 bg-emerald-100/50',
};

export function runStatusColor(status: string): string {
  return RUN_STATUS_COLORS[status] ?? 'text-stone-600 bg-stone-100 dark:bg-stone-700';
}

type BadgeSize = 'sm' | 'md';

const LIVE_DOT_SIZE: Record<BadgeSize, string> = {
  sm: 'w-2 h-2',
  md: 'w-2.5 h-2.5',
};

function runStatusIcon(status: string, className: string, size: BadgeSize) {
  if (status === 'completed') return <CheckCircle className={className} />;
  if (status === 'failed') return <XCircle className={className} />;
  if (status === 'timeout') return <Clock className={className} />;
  if (status === 'interrupted') return <Square className={`${className} fill-current`} />;
  if (status === 'running') {
    return (
      <span
        className={`live-dot rounded-full shrink-0 ${LIVE_DOT_SIZE[size]}`}
        aria-hidden="true"
      />
    );
  }
  return <Activity className={className} />;
}

const ICON_SIZE: Record<BadgeSize, string> = {
  sm: 'w-3 h-3',
  md: 'w-4 h-4',
};

const PILL_PADDING: Record<BadgeSize, string> = {
  sm: 'p-1',
  md: 'p-1.5',
};

/** Icon-only pill for agent run status (completed, running, failed, etc.). */
export function RunStatusBadge({
  status,
  size = 'md',
}: {
  status: string;
  size?: BadgeSize;
}) {
  const iconClass = ICON_SIZE[size];
  const label = status.replace(/_/g, ' ');

  return (
    <span
      className={`inline-flex items-center justify-center rounded-full shrink-0 ${PILL_PADDING[size]} ${runStatusColor(status)}`}
      aria-label={label}
      title={label}
    >
      {runStatusIcon(status, iconClass, size)}
    </span>
  );
}

const RESOLUTION_COLORS = {
  resolved: 'text-green-600 bg-green-100',
  unresolved: 'text-slate-500 bg-slate-100',
} as const;

/** Text label pill for episode resolution (paired with icon-only RunStatusBadge). */
export function EpisodeResolutionBadge({
  resolved,
  size = 'md',
  showIcon = true,
}: {
  resolved: boolean;
  size?: BadgeSize;
  /** When false, shows short text label only (investigations list). */
  showIcon?: boolean;
}) {
  const iconClass = ICON_SIZE[size];
  const label = resolved ? 'resolved' : 'unresolved';
  const color = resolved ? RESOLUTION_COLORS.resolved : RESOLUTION_COLORS.unresolved;
  const textClass = 'text-xs';

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full shrink-0 px-2 py-0.5 font-medium ${textClass} ${color}`}
      title={label}
    >
      {showIcon &&
        (resolved ? (
          <CheckCircle className={iconClass} />
        ) : (
          <XCircle className={iconClass} />
        ))}
      {label}
    </span>
  );
}
