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

/** Cold resume (sdk_session_id) or warm in-process session still alive in sre-agent. */
export function canContinueConversation(opts: {
  sessionId?: string | null;
  sessionAlive?: boolean;
}): boolean {
  return isResumable(opts.sessionId) || opts.sessionAlive === true;
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
