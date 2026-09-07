// Pure helpers for building the agent stream request and deriving resumability.
// Kept separate from the hook so they are unit-testable under vitest (node env).

export interface StreamBodyInput {
  message: string;
  threadId?: string | null;
  resumeSessionId?: string | null;
  agentName?: string | null;
}

export function buildStreamBody(input: StreamBodyInput): Record<string, unknown> {
  const { message, threadId, resumeSessionId, agentName } = input;
  return {
    message,
    ...(threadId ? { thread_id: threadId } : {}),
    // resume_session_id only matters with a thread_id (which thread to revive).
    ...(threadId && resumeSessionId ? { resume_session_id: resumeSessionId } : {}),
    ...(agentName ? { agent_name: agentName } : {}),
  };
}

export function isResumable(sessionId: string | null | undefined): boolean {
  return typeof sessionId === 'string' && sessionId.length > 0;
}

/** Latest non-empty sdkSessionId in startedAt-ascending runs (running row included). */
export function pickLatestSdkSessionId(
  runs: Array<{ sdkSessionId?: string | null }>,
): string | null {
  return [...runs].reverse().map((r) => r.sdkSessionId).find(Boolean) ?? null;
}

/** Cold resume, warm in-process session, or same-thread follow-up after the turn is not live. */
export function canContinueConversation(opts: {
  sessionId?: string | null;
  sessionAlive?: boolean;
  threadId?: string | null;
  isLive?: boolean;
}): boolean {
  if (opts.isLive === true) return true;
  if (isResumable(opts.sessionId)) return true;
  if (opts.sessionAlive === true) return true;
  if (opts.threadId && opts.isLive === false) return true;
  return false;
}

const INTERRUPT_RETRY_MS = 50;
const INTERRUPT_DEADLINE_MS = 5000;

/** Ask sre-agent to stop an in-flight investigation (simple-mode /interrupt). */
export async function interruptThread(threadId: string): Promise<void> {
  const deadline = Date.now() + INTERRUPT_DEADLINE_MS;
  while (Date.now() < deadline) {
    const res = await fetch('/api/team/agent/interrupt', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ thread_id: threadId }),
    });
    if (res.ok) return;
    if (res.status !== 404) {
      const err = await res.json().catch(() => ({}));
      throw new Error((err as { error?: string }).error || `Interrupt failed (${res.status})`);
    }
    await new Promise((resolve) => setTimeout(resolve, INTERRUPT_RETRY_MS));
  }
  throw new Error('No active session to interrupt');
}

/** Mark a zombie agent run interrupted (config-service abandon). */
export async function abandonRun(runId: string): Promise<void> {
  const res = await fetch(`/api/team/agent-runs/${runId}/abandon`, {
    method: 'POST',
  });
  if (res.ok) return;
  if (res.status === 409) return; // already terminal
  const err = await res.json().catch(() => ({}));
  throw new Error((err as { error?: string; detail?: string }).error
    || (err as { detail?: string }).detail
    || `Abandon failed (${res.status})`);
}
