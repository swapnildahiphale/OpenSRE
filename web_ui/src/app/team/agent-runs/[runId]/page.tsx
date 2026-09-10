'use client';

import { useCallback, useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useConversation } from '@/lib/useConversation';
import { useAgentStream } from '@/lib/useAgentStream';
import { timelineToTurns, mergeTurns } from '@/lib/agentTimeline';
import ConversationTranscript from '@/components/ConversationTranscript';
import ConversationComposer from '@/components/ConversationComposer';
import { isOrphanedRun } from '@/lib/orphanRun';
import { abandonRun, interruptThread } from '@/lib/streamRequest';
import {
  EpisodeResolutionBadge,
  RunStatusBadge,
} from '@/components/RunStatusBadge';
import { Skeleton, TeamPageShell } from '@/components/ui-flow';
import { ArrowLeft } from 'lucide-react';
import { formatTriggerMeta } from '@/lib/triggerMeta';

const NO_RESUME = "This conversation can't be continued (no saved session). Start a new investigation.";
const INTERRUPTED_HALT =
  'This turn was interrupted. Send a follow-up to continue.';
const STORAGE_KEY = 'opensre.trace.technicalDetails';

export default function AgentRunDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  const router = useRouter();
  const {
    turns: historicalTurns, title, status,
    sessionId, threadId, sessionAlive, continuable, errorMessage, loading, error, reload,
    activeKnown, consecutiveInactivePolls,
    episode, triggerSource, triggerActor,
  } = useConversation(runId);

  const stream = useAgentStream({
    threadId: threadId ?? undefined,
    resumeSessionId: sessionId ?? undefined,
  });

  const {
    reset: resetStream,
    sendMessage,
    stop: stopStream,
    queueMessage,
    queuedMessages,
    backgroundWaiting,
  } = stream;
  const isOrphaned = isOrphanedRun({
    status,
    activeKnown,
    sessionAlive,
    isStreaming: stream.isStreaming,
    consecutiveInactivePolls,
  });
  const isLiveTurn = stream.isStreaming || (status === 'running' && !isOrphaned);

  const settle = useCallback(async () => { await reload(); resetStream(); }, [reload, resetStream]);

  const onSend = useCallback((message: string) => {
    sendMessage(message);
  }, [sendMessage]);

  const onStop = useCallback(async () => {
    if (stream.isStreaming) {
      await stopStream();
      return;
    }
    if (isOrphaned) {
      await abandonRun(runId);
      await reload();
      return;
    }
    if (!threadId) return;
    try {
      await interruptThread(threadId);
    } catch (e) {
      const msg = e instanceof Error ? e.message : '';
      if (msg !== 'No active session to interrupt') throw e;
      await abandonRun(runId);
    }
    await reload();
  }, [stream.isStreaming, stopStream, isOrphaned, threadId, runId, reload]);

  const [technicalDetails, setTechnicalDetails] = useState(false);

  useEffect(() => {
    try {
      setTechnicalDetails(localStorage.getItem(STORAGE_KEY) === '1');
    } catch { /* ignore */ }
  }, []);

  const onToggle = (next: boolean) => {
    setTechnicalDetails(next);
    try {
      localStorage.setItem(STORAGE_KEY, next ? '1' : '0');
    } catch { /* ignore */ }
  };

  useEffect(() => {
    if (!stream.isStreaming && stream.timeline.length && stream.runStatus !== 'running') {
      settle();
    }
  }, [stream.isStreaming, stream.runStatus, stream.timeline.length, settle]);

  if (loading) {
    return (
      <TeamPageShell variant="conversation">
        <div className="py-12 space-y-4">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-32 w-full rounded-xl" />
          <Skeleton className="h-48 w-full rounded-xl" />
        </div>
      </TeamPageShell>
    );
  }
  if (error) {
    return (
      <TeamPageShell variant="conversation">
        <p className="py-12 text-center text-slate-500">{error}</p>
      </TeamPageShell>
    );
  }

  const liveTurns = timelineToTurns(stream.timeline);
  const turns = mergeTurns(historicalTurns, liveTurns, stream.runId);

  const displayStatus = isOrphaned
    ? 'interrupted'
    : isLiveTurn
      ? 'running'
      : (stream.runStatus === 'timeout' ? 'timeout' : status);
  const haltMessage = displayStatus === 'interrupted'
    ? INTERRUPTED_HALT
    : (stream.error || errorMessage);
  const showHaltBanner = !isLiveTurn && !!haltMessage && (
    displayStatus === 'timeout' || displayStatus === 'failed' || displayStatus === 'interrupted'
  );

  const turnLabel = `${turns.length} turn${turns.length === 1 ? '' : 's'}`;

  return (
    <TeamPageShell
      variant="conversation"
      footer={
        <div className="py-4">
          {/* Full column width — same edges as run title / transcript */}
          <ConversationComposer
            embedded
            onSend={onSend}
            onQueueMessage={queueMessage}
            queuedMessages={queuedMessages}
            onStop={isLiveTurn || isOrphaned ? onStop : undefined}
            busy={isLiveTurn}
            disabled={!isLiveTurn && !continuable && !isOrphaned}
            disabledReason={
              !continuable && !isOrphaned && !threadId ? NO_RESUME : undefined
            }
          />
        </div>
      }
    >
      <div className="py-8">
        <button
          type="button"
          onClick={() => router.push('/team/agent-runs')}
          className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-slate-700 mb-5 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to investigations
        </button>

        <header className="mb-6 min-w-0">
          <div className="flex flex-wrap items-start gap-3 mb-2">
            <h1 className="text-2xl md:text-3xl font-medium tracking-tight text-slate-900 leading-snug flex-1 min-w-0 dark:text-white">
              {title}
            </h1>
            <RunStatusBadge status={displayStatus} size="md" />
          </div>
          <div className="flex flex-wrap items-center gap-2 text-sm">
            {episode?.issue_type && (
              <span className="font-mono text-[12px] text-slate-500">
                {episode.issue_type}
              </span>
            )}
            {episode && (
              <EpisodeResolutionBadge
                resolved={episode.resolved ?? false}
                size="sm"
                showIcon={false}
              />
            )}
            <span className="text-xs text-slate-400 font-mono tabular-nums">
              · {turnLabel} · {formatTriggerMeta(triggerSource, triggerActor)}
            </span>
          </div>
        </header>

        {showHaltBanner && (
          <div className="mb-4 rounded-xl border border-yellow-200 dark:border-yellow-800/50 bg-yellow-50 dark:bg-yellow-900/20 px-4 py-3 text-sm text-yellow-900 dark:text-yellow-100">
            {haltMessage}
          </div>
        )}

        <label className="flex items-center gap-2 text-xs text-slate-500 mb-4 cursor-pointer select-none">
          <input
            type="checkbox"
            className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500/30"
            checked={technicalDetails}
            onChange={(e) => onToggle(e.target.checked)}
          />
          Debug Mode
        </label>

        {/* Full column width — align agent chat with run title edges */}
        <ConversationTranscript
          turns={turns}
          isRunning={isLiveTurn}
          technicalDetails={technicalDetails}
          backgroundWaiting={backgroundWaiting}
        />
      </div>
    </TeamPageShell>
  );
}
