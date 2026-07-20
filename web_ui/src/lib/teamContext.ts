export interface TeamContextSection {
  id: string;
  title: string;
  content: string;
}

/** UI-only starter template — not a schema constraint */
export const SUGGESTED_SECTIONS: Array<{ id: string; title: string; hint: string; placeholder: string }> = [
  {
    id: 'source_control',
    title: 'Source Control',
    hint: 'Which VCS and repos should the agent use?',
    placeholder:
      '- **Primary VCS:** (your org default, e.g. Bitbucket or GitHub)\n- Do NOT search alternate VCS unless the ticket names it.',
  },
  {
    id: 'infrastructure',
    title: 'Infrastructure',
    hint: 'Clouds, clusters, regions, namespaces, observability',
    placeholder: 'EKS cluster, AWS account, default namespaces...',
  },
  {
    id: 'environments',
    title: 'Environments',
    hint: 'Dev/QA/prod patterns, dynamic envs, env schedulers',
    placeholder: 'Dynamic env namespace pattern, where QA is hosted...',
  },
  {
    id: 'incident_workflow',
    title: 'Incident Workflow',
    hint: 'Escalation, approvals, on-call tools',
    placeholder: 'Scale via your env scheduler UI, not kubectl scale...',
  },
  {
    id: 'known_issues',
    title: 'Known Issues',
    hint: 'Ongoing migrations, flaky systems',
    placeholder: 'Migration in progress on...',
  },
];

export const TEAM_CONTEXT_HARD_CAP = 6000;

function sectionLines(sections: TeamContextSection[]): string[] {
  const lines: string[] = [];
  for (const sec of sections) {
    const body = (sec.content || '').trim();
    if (!body) continue;
    const title = (sec.title || sec.id || 'Section').trim();
    lines.push(`### ${title}\n\n${body}\n`);
  }
  return lines;
}

/** Matches sre-agent render_team_context_block() output (incl. leading newlines). */
export function renderTeamContextBlock(sections: TeamContextSection[]): string {
  const lines = sectionLines(sections);
  if (!lines.length) return '';
  const block = `## Team Context\n\n${lines.join('\n')}`;
  let result = `\n\n${block}`;
  if (result.length > TEAM_CONTEXT_HARD_CAP) {
    result = result.slice(0, TEAM_CONTEXT_HARD_CAP) + '...[truncated]';
  }
  return result;
}

/** Markdown body for UI preview (without leading newlines). */
export function renderTeamContextPreview(sections: TeamContextSection[]): string {
  const block = renderTeamContextBlock(sections);
  if (!block) return '';
  return block.startsWith('\n\n') ? block.slice(2) : block;
}

export function renderedTeamContextLength(sections: TeamContextSection[]): number {
  return renderTeamContextBlock(sections).length;
}

export function totalContentChars(sections: TeamContextSection[]): number {
  return sections.reduce((n, s) => n + (s.content?.length || 0), 0);
}

export function newSectionId(title: string): string {
  const slug = title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_|_$/g, '');
  return slug || `section_${Date.now()}`;
}

export function applyStarterTemplate(): TeamContextSection[] {
  return SUGGESTED_SECTIONS.map((s) => ({
    id: s.id,
    title: s.title,
    content: s.placeholder,
  }));
}
