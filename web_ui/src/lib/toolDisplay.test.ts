import { describe, it, expect } from 'vitest';
import { humanizeToolSummary, nestBashUnderSkills } from './toolDisplay';
import type { ThoughtItem, ToolItem } from './agentTimeline';

function tool(overrides: Partial<ToolItem>): ToolItem {
  return {
    kind: 'tool',
    seq: 0,
    id: 't',
    toolName: 'Bash',
    status: 'success',
    startedAt: new Date().toISOString(),
    depth: 0,
    ...overrides,
  };
}

describe('humanizeToolSummary', () => {
  it('Skill: drops skill: prefix and keeps args', () => {
    const s = humanizeToolSummary(tool({
      toolName: 'Skill',
      input: { skill: 'project-jira', args: 'fetch OC-2263' },
    }));
    expect(s).toBe('project-jira — fetch OC-2263');
  });

  it('Skill without args: skill id only', () => {
    expect(humanizeToolSummary(tool({
      toolName: 'Skill',
      input: { skill: 'infrastructure-kubernetes' },
    }))).toBe('infrastructure-kubernetes');
  });

  it('Bash skill-script path: shows script basename + trailing args', () => {
    const s = humanizeToolSummary(tool({
      toolName: 'Bash',
      input: {
        command:
          'python /tmp/sessions/x/.claude/skills/infrastructure-kubernetes/scripts/list_pods.py -n nv13qa-cix',
      },
    }));
    expect(s).toMatch(/^list_pods\.py/);
    expect(s).not.toContain('.claude/skills');
  });

  it('Bash plain command: truncates without inventing a skill name', () => {
    const s = humanizeToolSummary(tool({
      toolName: 'Bash',
      input: { command: 'kubectl get pods -n default' },
    }));
    expect(s).toContain('kubectl get pods');
  });

  it('Read: basename only', () => {
    expect(humanizeToolSummary(tool({
      toolName: 'Read',
      input: { file_path: '/app/sre-agent/.claude/skills/investigate/SKILL.md' },
    }))).toBe('SKILL.md');
  });

  it('Task/Agent: keeps subagent_type: description', () => {
    expect(humanizeToolSummary(tool({
      toolName: 'Agent',
      input: { subagent_type: 'kubernetes', description: 'Check pod health' },
    }))).toBe('kubernetes: Check pod health');
  });

  it('technicalDetails: Bash shows raw command slice including path', () => {
    const cmd =
      'python /tmp/x/.claude/skills/infrastructure-kubernetes/scripts/list_pods.py -n nv13';
    const s = humanizeToolSummary(
      tool({ toolName: 'Bash', input: { command: cmd } }),
      { technicalDetails: true },
    );
    expect(s).toContain('.claude/skills');
  });
});

describe('nestBashUnderSkills', () => {
  it('nests proximity Bash under preceding Skill', () => {
    const skill = tool({
      id: 's1', seq: 0, toolName: 'Skill',
      input: { skill: 'project-jira', args: 'fetch OC-2263' },
    });
    const bash = tool({
      id: 'b1', seq: 1, toolName: 'Bash',
      input: {
        command:
          'python .claude/skills/project-jira/scripts/fetch_issue.py --issue-key OC-2263',
      },
    });
    const out = nestBashUnderSkills([skill, bash]);
    expect(out).toHaveLength(1);
    const row = out[0] as ToolItem & { nestedBash?: ToolItem[] };
    expect(row.id).toBe('s1');
    expect(row.nestedBash?.map((b) => b.id)).toEqual(['b1']);
  });

  it('nests path-matching Bash even if a thought sits between', () => {
    const skill = tool({
      id: 's1', seq: 0, toolName: 'Skill',
      input: { skill: 'infrastructure-kubernetes' },
    });
    const th: ThoughtItem = {
      kind: 'thought', seq: 1, ts: new Date().toISOString(), text: '…', depth: 0,
    };
    const bash = tool({
      id: 'b1', seq: 2, toolName: 'Bash',
      input: {
        command:
          'python /tmp/x/.claude/skills/infrastructure-kubernetes/scripts/list_pods.py -n ns',
      },
    });
    const out = nestBashUnderSkills([skill, th, bash]);
    expect(out.filter((i) => i.kind === 'thought')).toHaveLength(1);
    const skillRow = out.find((i) => i.kind === 'tool' && (i as ToolItem).id === 's1') as ToolItem & {
      nestedBash?: ToolItem[];
    };
    expect(skillRow.nestedBash?.map((b) => b.id)).toEqual(['b1']);
  });

  it('does not nest Bash for a different skill path — leaves standalone', () => {
    const skill = tool({
      id: 's1', seq: 0, toolName: 'Skill',
      input: { skill: 'project-jira' },
    });
    const read = tool({
      id: 'r1', seq: 1, toolName: 'Read',
      input: { file_path: '/tmp/SKILL.md' },
    });
    const bash2 = tool({
      id: 'b2', seq: 2, toolName: 'Bash',
      input: {
        command:
          'python .claude/skills/infrastructure-kubernetes/scripts/list_pods.py',
      },
    });
    const out = nestBashUnderSkills([skill, read, bash2]);
    expect(out.map((i) => (i as ToolItem).id)).toEqual(['s1', 'r1', 'b2']);
  });

  it('closes Skill on Task/Agent — following Bash stays top-level unless path matches open skill (none)', () => {
    const skill = tool({
      id: 's1', seq: 0, toolName: 'Skill',
      input: { skill: 'project-jira' },
    });
    const task = tool({
      id: 't1', seq: 1, toolName: 'Agent',
      input: { subagent_type: 'kubernetes', description: 'pods' },
    });
    const bash = tool({
      id: 'b1', seq: 2, toolName: 'Bash',
      input: { command: 'kubectl get pods' },
    });
    const out = nestBashUnderSkills([skill, task, bash]);
    expect(out.map((i) => (i as ToolItem).id)).toEqual(['s1', 't1', 'b1']);
  });

  it('technicalDetails: returns flat list with no nestedBash', () => {
    const skill = tool({
      id: 's1', seq: 0, toolName: 'Skill',
      input: { skill: 'project-jira' },
    });
    const bash = tool({
      id: 'b1', seq: 1, toolName: 'Bash',
      input: {
        command: 'python .claude/skills/project-jira/scripts/fetch_issue.py',
      },
    });
    const out = nestBashUnderSkills([skill, bash], { technicalDetails: true });
    expect(out.map((i) => (i as ToolItem).id)).toEqual(['s1', 'b1']);
    expect((out[0] as ToolItem & { nestedBash?: ToolItem[] }).nestedBash).toBeUndefined();
  });
});
