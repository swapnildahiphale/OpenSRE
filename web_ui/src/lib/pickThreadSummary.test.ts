import { describe, it, expect } from 'vitest';
import { pickThreadSummary } from './pickThreadSummary';

describe('pickThreadSummary', () => {
  const firstRun = {
    status: 'completed' as const,
    triggerMessage: 'checkout-service latency spike',
  };

  it('prefers the original trigger message over timeout error text', () => {
    const title = pickThreadSummary(
      undefined,
      {
        status: 'timeout',
        errorMessage:
          'Investigation stopped after 10 minutes (time limit). Work may be incomplete — send a follow-up to summarize or continue.',
      },
      firstRun,
    );
    expect(title).toBe('checkout-service latency spike');
  });

  it('uses error message when there is no trigger message', () => {
    const title = pickThreadSummary(
      undefined,
      {
        status: 'timeout',
        errorMessage: 'Investigation stopped after 10 minutes (time limit).',
      },
      { status: 'completed', triggerMessage: '' },
    );
    expect(title).toBe('Investigation stopped after 10 minutes (time limit).');
  });
});
