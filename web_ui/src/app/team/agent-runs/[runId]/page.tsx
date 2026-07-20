'use client';

import { useCallback, useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useConversation } from '@/lib/useConversation';
import { useAgentStream } from '@/lib/useAgentStream';
import { timelineToTurns, mergeTurns } from '@/lib/agentTimeline';
import ConversationTranscript from '@/components/ConversationTranscript';
import ConversationComposer from '@/components/ConversationComposer';
import { interruptThread } from '@/lib/streamRequest';
import { ArrowLeft, Loader2, CheckCircle, XCircle, Activity, Square, Clock } from 'lucide-react';

const statusBadge = (s: string) => {
  if (s === 'completed') return <CheckCircle className="w-4 h-4 text-green-600" />;
  if (s === 'failed') return <XCircle className="w-4 h-4 text-clay" />;
  if (s === 'timeout') return <Clock className="w-4 h-4 text-yellow-600" />;
  if (s === 'interrupted') return <Square className="w-4 h-4 text-amber-600 fill-current" />;
  if (s === 'running') return <Loader2 className="w-4 h-4 animate-spin text-forest" />;
  return <Activity className="w-4 h-4 text-stone-400" />;
};

const NO_RESUME = "This conversation can't be continued (no saved session). Start a new investigation.";
const STORAGE_KEY = 'opensre.trace.technicalDetails';

export default function AgentRunDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  const router = useRouter();
  const {
    turns: historicalTurns, title, status,
    sessionId, threadId, continuable, errorMessage, loading, error, reload,
  } = useConversation(runId);

  const stream = useAgentStream({
    threadId: threadId ?? undefined,
    resumeSessionId: sessionId ?? undefined,
  });

  // Pull stable callbacks out so settle/onSend deps don't churn every render.
  // useAgentStream returns a plain object literal — not memoized — so referencing
  // stream.reset directly in a dep array would re-create the callbacks each render.
  const {
    reset: resetStream,
    sendMessage,
    stop: stopStream,
    queueMessage,
    queuedMessages,
    backgroundWaiting,
  } = stream;
  const isRunning = status === 'running' || stream.isStreaming;

  // When a live follow-up settles, refresh history (which now includes the new
  // run) then clear the live timeline. reload-then-reset avoids a content gap.
  const settle = useCallback(async () => { await reload(); resetStream(); }, [reload, resetStream]);

  const onSend = useCallback((message: string) => {
    sendMessage(message);
  }, [sendMessage]);

  // Stop works for live SSE on this page OR for runs still "running" in the DB
  // after navigating here from the investigation drawer (no local stream).
  const onStop = useCallback(async () => {
    if (stream.isStreaming) {
      await stopStream();
      return;
    }
    if (threadId) {
      await interruptThread(threadId);
      await reload();
    }
  }, [stream.isStreaming, stopStream, threadId, reload]);

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

  if (loading) return <div className="p-8 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-stone-400" /></div>;
  if (error) return <div className="p-8 text-center text-stone-500">{error}</div>;

  const liveTurns = timelineToTurns(stream.timeline);
  // mergeTurns drops the historical copy of the run being live-streamed
  // (stream.runId) so an in-flight follow-up isn't rendered twice — once from
  // the polled DB trace and once from the SSE stream. See mergeTurns docstring.
  const turns = mergeTurns(historicalTurns, liveTurns, stream.runId);

  const displayStatus = isRunning
    ? 'running'
    : (stream.runStatus === 'timeout' ? 'timeout' : status);
  const haltMessage = stream.error || errorMessage;
  const showHaltBanner = !isRunning && !!haltMessage && (
    displayStatus === 'timeout' || displayStatus === 'failed'
  );

  return (
    <div className="max-w-4xl mx-auto p-6">
      <button onClick={() => router.push('/team/agent-runs')} className="flex items-center gap-2 text-sm text-stone-500 hover:text-stone-700 mb-4">
        <ArrowLeft className="w-4 h-4" /> Back to investigations
      </button>
      <div className="mb-6 min-w-0">
        <h1 className="text-xl font-semibold text-stone-900 dark:text-white flex items-center gap-2 min-w-0">
          <span className="truncate">{title}</span>
          {statusBadge(displayStatus)}
        </h1>
      </div>
      {showHaltBanner && (
        <div className="mb-4 rounded-xl border border-yellow-200 dark:border-yellow-800/50 bg-yellow-50 dark:bg-yellow-900/20 px-4 py-3 text-sm text-yellow-900 dark:text-yellow-100">
          {haltMessage}
        </div>
      )}
      <label className="flex items-center gap-2 text-xs text-stone-500 mb-3">
        <input
          type="checkbox"
          checked={technicalDetails}
          onChange={(e) => onToggle(e.target.checked)}
        />
        Debug Mode
      </label>
      <ConversationTranscript
        turns={turns}
        isRunning={isRunning}
        technicalDetails={technicalDetails}
        backgroundWaiting={backgroundWaiting}
      />
      <ConversationComposer
        onSend={onSend}
        onQueueMessage={queueMessage}
        queuedMessages={queuedMessages}
        onStop={isRunning ? onStop : undefined}
        busy={isRunning}
        disabled={!isRunning && !continuable}
        disabledReason={NO_RESUME}
      />
    </div>
  );
}
