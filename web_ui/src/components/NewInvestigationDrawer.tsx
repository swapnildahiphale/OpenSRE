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
      <div className="absolute inset-0 bg-slate-900/20" onClick={closeChat} />
      <div className="relative flex h-full w-full max-w-2xl flex-col bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-200/70 px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-100/55">
              <Sparkles className="h-5 w-5 text-emerald-600" />
            </div>
            <div>
              <h2 className="font-semibold text-slate-900">New Investigation</h2>
              <p className="text-xs text-slate-500">AI-powered incident investigation</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {runId && !isStreaming && (
              <button
                onClick={() => router.push(`/team/agent-runs/${runId}`)}
                className="rounded-full bg-emerald-100/50 px-3 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-100/80"
              >
                View saved run
              </button>
            )}
            <button
              onClick={closeChat}
              className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-6">
          {timeline.length === 0 && !isStreaming ? (
            <div className="py-12 text-center">
              <Bot className="mx-auto mb-4 h-12 w-12 text-slate-300" />
              <p className="mb-2 text-slate-600">Start an investigation</p>
              <p className="text-sm text-slate-400">
                Describe the issue and the AI will analyze your systems.
              </p>
            </div>
          ) : (
            <ConversationTranscript turns={timelineToTurns(timeline)} isRunning={isStreaming} backgroundWaiting={backgroundWaiting} />
          )}
        </div>
        <div className="border-t border-slate-200/70 px-4 pb-4 [&>div]:mt-4">
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
