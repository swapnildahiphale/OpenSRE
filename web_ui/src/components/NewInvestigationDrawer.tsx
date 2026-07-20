'use client';

// Shared "start a new investigation" slide-over panel.
//
// Extracted from the agent-runs list page so both the Dashboard and the
// Agent Runs page can open the same investigation composer without
// duplicating the slide-over JSX + useAgentStream wiring. The drawer owns
// its own stream lifecycle (useAgentStream). Callers pass an `onComplete`
// pass an `onComplete` callback to refresh their own lists/stats once the
// run finishes, and `onClose` to dismiss the panel.
//
// API chain is unchanged from the original inline implementation:
//   useAgentStream -> POST /api/team/agent/stream -> sre-agent /investigate (SSE).
import { useRouter } from 'next/navigation';
import { Bot, Sparkles, X } from 'lucide-react';
import { useAgentStream } from '@/lib/useAgentStream';
import { timelineToTurns } from '@/lib/agentTimeline';
import ConversationTranscript from './ConversationTranscript';
import ConversationComposer from './ConversationComposer';

type Props = {
  open: boolean;
  onClose: () => void;
  // Called when the streaming run finishes so the host page can refresh
  // its own data (run list, dashboard stats, onboarding state, etc.).
  onComplete?: () => void;
};

export function NewInvestigationDrawer({ open, onClose, onComplete }: Props) {
  const router = useRouter();
  const { timeline, runId, isStreaming, backgroundWaiting, sendMessage, queueMessage, queuedMessages, stop, reset } = useAgentStream({
    // useAgentStream passes the final output text; callers here only need a
    // signal that the run completed, so we drop the argument.
    onComplete: () => onComplete?.(),
  });

  // Close + reset stream state so reopening starts a fresh conversation
  // (no carried-over thread_id from the previous investigation).
  const closeChat = () => {
    onClose();
    reset();
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/20 dark:bg-black/40" onClick={closeChat} />
      <div className="relative w-full max-w-2xl bg-white dark:bg-stone-800 shadow-2xl flex flex-col h-full">
        <div className="flex items-center justify-between px-6 py-4 border-b border-stone-200 dark:border-stone-700">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-forest-light/15 dark:bg-forest/30 flex items-center justify-center"><Sparkles className="w-5 h-5 text-forest" /></div>
            <div><h2 className="font-semibold text-stone-900 dark:text-white">Ask OpenSRE</h2><p className="text-xs text-stone-500">AI-powered incident investigation</p></div>
          </div>
          <div className="flex items-center gap-2">
            {runId && !isStreaming && (
              <button onClick={() => router.push(`/team/agent-runs/${runId}`)} className="text-xs text-forest hover:underline">View saved run</button>
            )}
            <button onClick={closeChat} className="p-2 text-stone-400 hover:text-stone-600 dark:hover:text-stone-300 rounded-lg hover:bg-stone-100 dark:hover:bg-stone-800"><X className="w-5 h-5" /></button>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-6">
          {timeline.length === 0 && !isStreaming ? (
            <div className="text-center py-12">
              <Bot className="w-12 h-12 mx-auto text-stone-300 dark:text-stone-600 mb-4" />
              <p className="text-stone-500 mb-2">Start an investigation</p>
              <p className="text-sm text-stone-400">Describe the issue and the AI will analyze your systems.</p>
            </div>
          ) : (
            <ConversationTranscript turns={timelineToTurns(timeline)} isRunning={isStreaming} backgroundWaiting={backgroundWaiting} />
          )}
        </div>
        <div className="border-t border-stone-200 dark:border-stone-700 px-4 pb-4 [&>div]:mt-4">
          <ConversationComposer
            onSend={sendMessage}
            onQueueMessage={queueMessage}
            queuedMessages={queuedMessages}
            onStop={stop}
            busy={isStreaming}
            placeholder="Describe the issue to investigate..."
          />
        </div>
      </div>
    </div>
  );
}
