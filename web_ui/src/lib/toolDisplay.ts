import type { ThoughtItem, ToolItem } from './agentTimeline';
import { todoProgress } from './todoSnapshot';

const SKILL_SCRIPT_RE =
  /\.claude\/skills\/[^/\s]+(?:\/[^/\s]+)*\/scripts\/([^\s]+)/;

export type DisplayTraceItem =
  | ThoughtItem
  | (ToolItem & { nestedBash?: ToolItem[] });

/** Extract skill id from a Bash command that invokes a skill script. */
function skillIdFromCommand(command: string): string | null {
  const m = command.match(/\.claude\/skills\/([^/\s]+)/);
  return m ? m[1] : null;
}

/** Whether a Bash command's skill path matches the Skill tool's input.skill (Phase 2 path hint). */
function pathMatchesSkill(command: string, skill: string): boolean {
  const fromPath = skillIdFromCommand(command);
  if (!fromPath) return false;
  return fromPath === skill || skill.endsWith(fromPath) || fromPath.endsWith(skill);
}

/** Tools that close an open Skill — subsequent Bash stays top-level unless path matches. */
function closesSkill(toolName: string): boolean {
  return (
    toolName === 'Skill' ||
    toolName === 'Task' ||
    toolName === 'Agent' ||
    toolName === 'Read' ||
    toolName === 'Write' ||
    toolName === 'Edit' ||
    toolName === 'Grep' ||
    toolName === 'Glob' ||
    toolName.startsWith('Todo') ||
    toolName.startsWith('Task')
  );
}

/**
 * Nest Bash tools under the preceding open Skill within one agent node.
 * Phase 1: proximity — while a Skill is open, any Bash nests under it.
 * Thoughts pass through; nested Bash rows are removed from the top-level list.
 */
export function nestBashUnderSkills(
  items: (ToolItem | ThoughtItem)[],
  opts?: { technicalDetails?: boolean },
): DisplayTraceItem[] {
  if (opts?.technicalDetails) return [...items];

  const sorted = [...items].sort((a, b) => a.seq - b.seq);
  const out: DisplayTraceItem[] = [];
  let openSkill: (ToolItem & { nestedBash: ToolItem[] }) | null = null;

  for (const it of sorted) {
    if (it.kind === 'thought') {
      out.push(it);
      continue;
    }
    if (it.toolName === 'Skill') {
      openSkill = { ...it, nestedBash: [] };
      out.push(openSkill);
      continue;
    }
    if (it.toolName === 'Bash' && openSkill) {
      // Proximity: while Skill is still open, nest any Bash.
      openSkill.nestedBash.push(it);
      continue;
    }
    if (closesSkill(it.toolName)) {
      openSkill = null;
    }
    out.push(it);
  }
  return out;
}

/** Mirrors ConversationTranscript `toolSummary` — used for technicalDetails mode and Todo* tools. */
function legacyToolSummary(call: ToolItem): string | null {
  const input = call.input;
  if (!input) return null;
  switch (call.toolName) {
    case 'Bash':
      return input.command ? String(input.command).slice(0, 120) : null;
    case 'Skill':
      return input.skill
        ? `skill: ${input.skill}${input.args ? ` — ${String(input.args).slice(0, 80)}` : ''}`
        : null;
    case 'Read':
    case 'Write':
    case 'Edit':
      return input.file_path ? String(input.file_path) : null;
    case 'Grep':
      return input.pattern ? `pattern: "${input.pattern}"` : null;
    case 'Glob':
      return input.pattern ? `glob: "${input.pattern}"` : null;
    case 'Task':
    case 'Agent':
      return input.description
        ? `${input.subagent_type || 'subagent'}: ${String(input.description).slice(0, 100)}`
        : null;
    case 'TodoWrite': {
      const todos = Array.isArray(input.todos) ? input.todos : [];
      const p = todoProgress(
        todos.map((t: Record<string, unknown>, i: number) => ({
          id: String(i),
          subject: String(t.content ?? ''),
          status: (t.status ?? 'pending') as 'pending' | 'in_progress' | 'completed',
        })),
      );
      return `rewrite plan — ${p.completed}/${p.total} done`;
    }
    case 'TaskCreate':
      return input.subject ? `+ ${String(input.subject).slice(0, 100)}` : 'new task';
    case 'TaskUpdate': {
      const id = (input.taskId ?? input.id ?? input.task_id) as string | undefined;
      const st = input.status ? ` → ${input.status}` : '';
      const subj = input.subject
        ? ` ${String(input.subject).slice(0, 80)}`
        : id
          ? ` ${id.slice(0, 8)}`
          : '';
      return `update${subj}${st}`;
    }
    case 'TaskList':
      return 'snapshot';
    case 'TaskGet':
      return (input.taskId ?? input.id)
        ? `read ${(input.taskId ?? input.id) as string}`.slice(0, 100)
        : 'read task';
    default: {
      const v = Object.values(input).find((x) => typeof x === 'string');
      return v ? String(v).slice(0, 100) : null;
    }
  }
}

export function humanizeToolSummary(
  call: ToolItem,
  opts?: { technicalDetails?: boolean },
): string | null {
  if (opts?.technicalDetails) {
    return legacyToolSummary(call);
  }

  const input = call.input;
  if (!input) return null;

  switch (call.toolName) {
    case 'Bash': {
      const cmd = input.command ? String(input.command) : '';
      if (!cmd) return null;
      const m = cmd.match(SKILL_SCRIPT_RE);
      if (m) {
        const after = cmd.slice(cmd.indexOf(m[1]) + m[1].length).trim();
        return after ? `${m[1]} ${after}`.slice(0, 120) : m[1];
      }
      return cmd.slice(0, 100);
    }
    case 'Skill': {
      if (!input.skill) return null;
      const skill = String(input.skill);
      const args = input.args ? String(input.args).slice(0, 80) : '';
      return args ? `${skill} — ${args}` : skill;
    }
    case 'Read':
    case 'Write':
    case 'Edit': {
      if (!input.file_path) return null;
      const p = String(input.file_path);
      const base = p.split('/').pop() || p;
      return base;
    }
    case 'Grep':
      return input.pattern ? `pattern: "${input.pattern}"` : null;
    case 'Glob':
      return input.pattern ? `glob: "${input.pattern}"` : null;
    case 'Task':
    case 'Agent':
      return input.description
        ? `${input.subagent_type || 'subagent'}: ${String(input.description).slice(0, 100)}`
        : null;
    case 'TodoWrite':
    case 'TaskCreate':
    case 'TaskUpdate':
    case 'TaskList':
    case 'TaskGet':
      return legacyToolSummary(call);
    default: {
      const v = Object.values(input).find((x) => typeof x === 'string');
      return v ? String(v).slice(0, 100) : null;
    }
  }
}
