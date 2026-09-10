import { describe, expect, it } from 'vitest';
import { formatTriggerMeta } from './triggerMeta';

describe('formatTriggerMeta', () => {
  it('returns channel only when actor is missing', () => {
    expect(formatTriggerMeta('web_ui')).toBe('web ui');
    expect(formatTriggerMeta('teams', null)).toBe('teams');
    expect(formatTriggerMeta('teams', '  ')).toBe('teams');
  });

  it('appends first-run actor when set', () => {
    expect(formatTriggerMeta('web_ui', 'Jane Doe')).toBe('web ui · Jane Doe');
    expect(formatTriggerMeta('teams', ' Jane ')).toBe('teams · Jane');
  });

  it('defaults missing source to web_ui', () => {
    expect(formatTriggerMeta(undefined, 'Jane Doe')).toBe('web ui · Jane Doe');
  });
});
