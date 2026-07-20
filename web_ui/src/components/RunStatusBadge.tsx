import {
  Activity,
  CheckCircle,
  Clock,
  Loader2,
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
  completed: 'text-green-600 bg-green-100 dark:bg-green-900/30',
  failed: 'text-clay bg-clay-light/15 dark:bg-clay/20',
  timeout: 'text-yellow-600 bg-yellow-100 dark:bg-yellow-900/30',
  interrupted: 'text-amber-600 bg-amber-100 dark:bg-amber-900/30',
  running: 'text-forest bg-forest-light/15 dark:bg-forest/30',
};

export function runStatusColor(status: string): string {
  return RUN_STATUS_COLORS[status] ?? 'text-stone-600 bg-stone-100 dark:bg-stone-700';
}

function runStatusIcon(status: string, className: string) {
  if (status === 'completed') return <CheckCircle className={className} />;
  if (status === 'failed') return <XCircle className={className} />;
  if (status === 'timeout') return <Clock className={className} />;
  if (status === 'interrupted') return <Square className={`${className} fill-current`} />;
  if (status === 'running') return <Loader2 className={`${className} animate-spin`} />;
  return <Activity className={className} />;
}

type BadgeSize = 'sm' | 'md';

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
      {runStatusIcon(status, iconClass)}
    </span>
  );
}

const RESOLUTION_COLORS = {
  resolved: 'text-green-600 bg-green-100 dark:bg-green-900/30',
  unresolved: 'text-clay bg-clay-light/15 dark:bg-clay/20',
} as const;

/** Icon + label pill for episode resolution (paired with icon-only RunStatusBadge). */
export function EpisodeResolutionBadge({
  resolved,
  size = 'md',
}: {
  resolved: boolean;
  size?: BadgeSize;
}) {
  const iconClass = ICON_SIZE[size];
  const label = resolved ? 'resolved' : 'unresolved';
  const color = resolved ? RESOLUTION_COLORS.resolved : RESOLUTION_COLORS.unresolved;
  const textClass = size === 'sm' ? 'text-xs' : 'text-xs';

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full shrink-0 px-2 py-0.5 font-medium ${textClass} ${color}`}
      title={label}
    >
      {resolved ? (
        <CheckCircle className={iconClass} />
      ) : (
        <XCircle className={iconClass} />
      )}
      {label}
    </span>
  );
}
