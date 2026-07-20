// web_ui/src/lib/todoSnapshot.ts
//
// Derived todo/task visualization state for the agent run window.
//
// Handles BOTH todo tool shapes the Claude Agent SDK can emit:
//   1. Legacy `TodoWrite` — one call rewrites the full `input.todos` array.
//   2. Structured Task tools (`TaskCreate`, `TaskUpdate`, `TaskList`, `TaskGet`)
//      which replaced TodoWrite in TypeScript SDK 0.3.142 / Claude Code v2.1.142
//      (and Python SDK 0.2.82+). These accumulate state keyed by `taskId`.
//
// Reference: https://code.claude.com/docs/en/agent-sdk/todo-tracking
//
// The functions here are PURE and deterministic: they reduce an ordered list of
// tool-call items into the current todo snapshot. This lets one code path serve
// both live runs (feed tool items as they stream in) and historical/replayed
// runs (feed the persisted tool-call trace from the DB).

export type TodoStatus = 'pending' | 'in_progress' | 'completed';

export interface TodoItem {
  id: string;
  subject: string;
  status: TodoStatus;
  activeForm?: string;
}

// Minimal shape we need from a ToolItem. Keeps this module decoupled from the
// exact ToolItem interface in agentTimeline.ts.
export interface ToolLike {
  kind: 'tool';
  toolName: string;
  input?: Record<string, unknown> | null;
  output?: string | null;
  seq: number;
}

export interface TodoProgress {
  total: number;
  completed: number;
  inProgress: number;
  pending: number;
}

// Tool names that participate in the todo/task visualization.
export const TODO_TOOLS = new Set([
  'TodoWrite',
  'TaskCreate',
  'TaskUpdate',
  'TaskList',
  'TaskGet',
]);

export const isTodoTool = (name: string): boolean => TODO_TOOLS.has(name);

// Parse tool_result output from SSE or DB. Prefer JSON; fall back to Python repr
// from agent str(dict) on older persisted rows (single-quoted keys/values).
export function parseToolOutput(output?: string | null): unknown | undefined {
  if (!output) return undefined;
  try {
    return JSON.parse(output);
  } catch {
    // Python repr: {'task': {'id': '1', 'subject': 'List pods...'}}
    const taskIdInTask = output.match(/'task'\s*:\s*\{[^}]*'id'\s*:\s*'([^']+)'/);
    const subjectInTask = output.match(
      /'task'\s*:\s*\{[^}]*'subject'\s*:\s*'((?:\\'|[^'])*)'/,
    );
    if (taskIdInTask || subjectInTask) {
      return {
        task: {
          ...(taskIdInTask ? { id: taskIdInTask[1] } : {}),
          ...(subjectInTask
            ? { subject: subjectInTask[1].replace(/\\'/g, "'") }
            : {}),
        },
      };
    }
    const idTop = output.match(/'id'\s*:\s*'([^']+)'/);
    const subjectTop = output.match(/'subject'\s*:\s*'((?:\\'|[^'])*)'/);
    if (idTop || subjectTop) {
      return {
        ...(idTop ? { id: idTop[1] } : {}),
        ...(subjectTop ? { subject: subjectTop[1].replace(/\\'/g, "'") } : {}),
      };
    }
    return undefined;
  }
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined;
}

// Read the task id from a TaskUpdate input DEFENSIVELY.
// Claude Code repairs close-but-incorrect key names (id/task_id -> taskId) before
// execution, but that repair is NOT reflected in the streamed input. So accept
// all three spellings, as the official migration doc instructs.
function taskIdOf(input: Record<string, unknown>): string | undefined {
  const raw = input.taskId ?? input.id ?? input.task_id;
  return raw != null ? String(raw) : undefined;
}

// TaskCreate's assigned id is NOT in its input. It comes back in the matching
// tool_result as { task: { id, subject } }. SDK may assign short numeric ids
// ('1', '2', …) — do not require UUID-length tokens.
function idFromTaskCreateOutput(output?: string | null): string | undefined {
  const parsed = parseToolOutput(output);
  const root = asRecord(parsed);
  if (!root) return undefined;
  const task = asRecord(root.task) ?? root;
  const id = task.id ?? root.id;
  if (id != null) return String(id);
  return undefined;
}

function subjectFromTaskCreateOutput(output?: string | null): string | undefined {
  const parsed = parseToolOutput(output);
  const root = asRecord(parsed);
  if (!root) return undefined;
  const task = asRecord(root.task) ?? root;
  const subject = task.subject ?? root.subject;
  return subject != null ? String(subject) : undefined;
}

// Parse a TaskList tool_result into a TodoItem[] snapshot.
// Accept either a bare array or { tasks: [...] } / { items: [...] } wrappers.
// Items with status "deleted" are dropped.
function listFromTaskListOutput(output?: string | null): TodoItem[] | undefined {
  const parsed = parseToolOutput(output);
  if (parsed == null) return undefined;
  const arr: unknown[] = Array.isArray(parsed)
    ? parsed
    : Array.isArray((parsed as Record<string, unknown>)?.tasks)
      ? ((parsed as Record<string, unknown>).tasks as unknown[])
      : Array.isArray((parsed as Record<string, unknown>)?.items)
        ? ((parsed as Record<string, unknown>).items as unknown[])
        : [];
  return arr
    .filter((raw) => (raw as Record<string, unknown>).status !== 'deleted')
    .map((raw, i) => {
      const t = raw as Record<string, unknown>;
      return {
        id: String(t.id ?? t.taskId ?? `task-${i}`),
        subject: String(t.subject ?? t.content ?? ''),
        status: (t.status ?? 'pending') as TodoStatus,
        activeForm: (t.activeForm ?? t.active_form) as string | undefined,
      };
    });
}

// Reduce an ordered list of tool items into the current todo snapshot.
// Tools are processed in `seq` order; non-todo tools are ignored.
// Returns the final snapshot (last-write-wins per id; TodoWrite replaces all).
export function deriveTodoSnapshot(items: ToolLike[]): TodoItem[] {
  const byId = new Map<string, TodoItem>();
  const order: string[] = [];

  const sorted = [...items].sort((a, b) => a.seq - b.seq);

  for (const tool of sorted) {
    const { toolName, input } = tool;
    if (!input) continue;

    // Legacy: full snapshot in input.todos. Replaces all prior state.
    if (toolName === 'TodoWrite') {
      const todos = Array.isArray(input.todos) ? input.todos : [];
      byId.clear();
      order.length = 0;
      for (const raw of todos) {
        const t = raw as Record<string, unknown>;
        const status = (t.status ?? 'pending') as TodoStatus | 'deleted';
        if (status === 'deleted') continue;
        const item: TodoItem = {
          id: String(t.id ?? `todo-${order.length}`),
          subject: String(t.content ?? t.subject ?? ''),
          status,
          activeForm: (t.activeForm ?? t.active_form) as string | undefined,
        };
        if (!byId.has(item.id)) order.push(item.id);
        byId.set(item.id, item);
      }
      continue;
    }

    // New Task tools: accumulate by id.
    if (toolName === 'TaskCreate') {
      const realId = idFromTaskCreateOutput(tool.output);
      const id = realId ?? String(input.id ?? `task-pending-${order.length}`);
      const subject = String(
        input.subject ?? subjectFromTaskCreateOutput(tool.output) ?? '',
      );
      const item: TodoItem = {
        id,
        subject,
        status: 'pending',
        activeForm: input.activeForm as string | undefined,
      };
      if (!byId.has(id)) order.push(id);
      byId.set(id, item);
      continue;
    }

    if (toolName === 'TaskUpdate') {
      const id = taskIdOf(input);
      if (!id) continue;
      const status = input.status as TodoStatus | 'deleted' | undefined;
      if (status === 'deleted') {
        byId.delete(id);
        const idx = order.indexOf(id);
        if (idx >= 0) order.splice(idx, 1);
        continue;
      }
      const existing = byId.get(id);
      const updated: TodoItem = {
        id,
        subject: existing?.subject ?? String(input.subject ?? ''),
        status: status ?? existing?.status ?? 'pending',
        activeForm:
          (input.activeForm as string | undefined) ?? existing?.activeForm,
      };
      if (!byId.has(id)) order.push(id);
      byId.set(id, updated);
      continue;
    }

    if (toolName === 'TaskList') {
      const list = listFromTaskListOutput(tool.output);
      if (list) {
        byId.clear();
        order.length = 0;
        for (const it of list) {
          if (!byId.has(it.id)) order.push(it.id);
          byId.set(it.id, it);
        }
      }
      continue;
    }

    // TaskGet: single-item read; no snapshot change needed for visualization.
  }

  return order
    .map((id) => byId.get(id))
    .filter((x): x is TodoItem => Boolean(x && x.subject.trim()));
}

export function todoProgress(items: TodoItem[]): TodoProgress {
  let completed = 0;
  let inProgress = 0;
  let pending = 0;
  for (const it of items) {
    if (it.status === 'completed') completed++;
    else if (it.status === 'in_progress') inProgress++;
    else pending++;
  }
  return { total: items.length, completed, inProgress, pending };
}
