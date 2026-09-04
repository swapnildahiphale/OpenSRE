import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import InvestigationReport from './InvestigationReport';

describe('InvestigationReport action items', () => {
  it('renders an action item that has no priority field without crashing', () => {
    render(
      <InvestigationReport
        report={{
          title: 'Test incident',
          action_items: [{ action: 'Restart the pod' } as any],
        }}
      />
    );
    expect(screen.getByText('Restart the pod')).toBeInTheDocument();
  });

  it('tags an additional action item without affecting a primary one', () => {
    render(
      <InvestigationReport
        report={{
          title: 'Test incident',
          action_items: [
            { action: 'Scale the deployment' },
            { action: 'Add alerting for this case', additional: true },
          ],
        }}
      />
    );
    expect(screen.getByText('Scale the deployment')).toBeInTheDocument();
    expect(screen.getByText('Add alerting for this case')).toBeInTheDocument();
    expect(screen.getByText('additional')).toBeInTheDocument();
  });
});
