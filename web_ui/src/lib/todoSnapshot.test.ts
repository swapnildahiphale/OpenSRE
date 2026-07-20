// web_ui/src/lib/todoSnapshot.test.ts
import { describe, it, expect } from 'vitest';
import { deriveTodoSnapshot, parseToolOutput, type ToolLike } from './todoSnapshot';

const mk = (
  toolName: string,
  seq: number,
  input: Record<string, unknown>,
  output?: string | null,
): ToolLike => ({
  kind: 'tool',
  toolName,
  seq,
  input,
  output,
});

// Fixture from run 679f709565634ea48af799127b929710 (Python repr tool_output in DB).
const RUN_679F_FIXTURE: ToolLike[] = [
  mk('TaskCreate', 4, { subject: 'List all pods in gi1qa-cai namespace', activeForm: 'Listing pods in gi1qa-cai' },
    "{'task': {'id': '1', 'subject': 'List all pods in gi1qa-cai namespace'}}"),
  mk('TaskCreate', 5, { subject: 'Check ArgoCD application sync status in gi1qa-cai', activeForm: 'Checking ArgoCD app status' },
    "{'task': {'id': '2', 'subject': 'Check ArgoCD application sync status in gi1qa-cai'}}"),
  mk('TaskUpdate', 6, { status: 'in_progress', taskId: '1' },
    "{'success': True, 'taskId': '1', 'updatedFields': ['status']}"),
  mk('TaskUpdate', 7, { status: 'in_progress', taskId: '2' },
    "{'success': True, 'taskId': '2', 'updatedFields': ['status']}"),
  mk('TaskUpdate', 11, { status: 'completed', taskId: '1' },
    "{'success': True, 'taskId': '1', 'updatedFields': ['status']}"),
  mk('TaskCreate', 12, { subject: 'Investigate livekit-server pod restarts', activeForm: 'Investigating livekit-server restarts' },
    "{'task': {'id': '3', 'subject': 'Investigate livekit-server pod restarts'}}"),
  mk('TaskCreate', 13, { subject: 'Investigate redis-cluster pod restarts', activeForm: 'Investigating redis-cluster restarts' },
    "{'task': {'id': '4', 'subject': 'Investigate redis-cluster pod restarts'}}"),
  mk('TaskUpdate', 14, { status: 'in_progress', taskId: '3' },
    "{'success': True, 'taskId': '3', 'updatedFields': ['status']}"),
  mk('TaskUpdate', 15, { status: 'in_progress', taskId: '4' },
    "{'success': True, 'taskId': '4', 'updatedFields': ['status']}"),
  mk('TaskUpdate', 36, { status: 'completed', taskId: '2' },
    "{'success': True, 'taskId': '2', 'updatedFields': ['status']}"),
  mk('TaskUpdate', 37, { status: 'completed', taskId: '3' },
    "{'success': True, 'taskId': '3', 'updatedFields': ['status']}"),
  mk('TaskUpdate', 38, { status: 'completed', taskId: '4' },
    "{'success': True, 'taskId': '4', 'updatedFields': ['status']}"),
];

describe('parseToolOutput', () => {
  it('parses JSON TaskCreate output', () => {
    const parsed = parseToolOutput('{"task":{"id":"1","subject":"List pods"}}');
    expect(parsed).toEqual({ task: { id: '1', subject: 'List pods' } });
  });

  it('parses Python repr TaskCreate output with short numeric id', () => {
    const parsed = parseToolOutput("{'task': {'id': '1', 'subject': 'List pods'}}");
    expect(parsed).toEqual({ task: { id: '1', subject: 'List pods' } });
  });
});

describe('deriveTodoSnapshot', () => {
  it('resolves run 679f fixture: 4 labeled tasks, not 8 phantoms', () => {
    const todos = deriveTodoSnapshot(RUN_679F_FIXTURE);
    expect(todos).toHaveLength(4);
    expect(todos.every((t) => t.subject.length > 0)).toBe(true);
    expect(todos.map((t) => t.status)).toEqual([
      'completed', 'completed', 'completed', 'completed',
    ]);
    expect(todos[0].subject).toContain('List all pods');
    expect(todos[1].subject).toContain('ArgoCD');
  });

  it('handles JSON TaskCreate output with short numeric ids', () => {
    const todos = deriveTodoSnapshot([
      mk('TaskCreate', 1, { subject: 'A' }, '{"task":{"id":"1","subject":"A"}}'),
      mk('TaskUpdate', 2, { taskId: '1', status: 'completed' }),
    ]);
    expect(todos).toHaveLength(1);
    expect(todos[0]).toMatchObject({ id: '1', subject: 'A', status: 'completed' });
  });

  it('supports legacy TodoWrite full snapshot', () => {
    const todos = deriveTodoSnapshot([
      mk('TodoWrite', 1, {
        todos: [
          { content: 'Step 1', status: 'completed' },
          { content: 'Step 2', status: 'in_progress', activeForm: 'Doing step 2' },
        ],
      }),
    ]);
    expect(todos).toHaveLength(2);
    expect(todos[1].activeForm).toBe('Doing step 2');
  });

  it('replaces state on TaskList snapshot', () => {
    const todos = deriveTodoSnapshot([
      mk('TaskCreate', 1, { subject: 'old' }, '{"task":{"id":"o1","subject":"old"}}'),
      mk('TaskList', 2, {}, JSON.stringify([{ id: 'n1', subject: 'new plan item', status: 'pending' }])),
    ]);
    expect(todos).toHaveLength(1);
    expect(todos[0]).toMatchObject({ id: 'n1', subject: 'new plan item' });
  });

  it('accepts defensive task_id key on TaskUpdate', () => {
    const todos = deriveTodoSnapshot([
      mk('TaskCreate', 1, { subject: 'A' }, '{"task":{"id":"x1","subject":"A"}}'),
      mk('TaskUpdate', 2, { task_id: 'x1', status: 'completed' }),
    ]);
    expect(todos[0].status).toBe('completed');
  });
});
