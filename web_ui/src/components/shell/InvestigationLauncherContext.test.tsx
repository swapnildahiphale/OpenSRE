import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import {
  InvestigationLauncherProvider,
  useInvestigationLauncher,
} from './InvestigationLauncherContext';

function Probe() {
  const { isOpen, open, close } = useInvestigationLauncher();
  return (
    <div>
      <span data-testid="open-state">{isOpen ? 'yes' : 'no'}</span>
      <button onClick={open}>open</button>
      <button onClick={close}>close</button>
    </div>
  );
}

describe('InvestigationLauncher', () => {
  it('toggles open state', () => {
    render(
      <InvestigationLauncherProvider>
        <Probe />
      </InvestigationLauncherProvider>,
    );
    expect(screen.getByTestId('open-state')).toHaveTextContent('no');
    fireEvent.click(screen.getByText('open'));
    expect(screen.getByTestId('open-state')).toHaveTextContent('yes');
  });

  it('invokes registered onComplete handler', () => {
    const handler = vi.fn();

    function CompletionProbe() {
      const { registerOnComplete, onComplete } = useInvestigationLauncher();
      registerOnComplete(handler);
      return <button onClick={onComplete}>complete</button>;
    }

    render(
      <InvestigationLauncherProvider>
        <CompletionProbe />
      </InvestigationLauncherProvider>,
    );

    expect(handler).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText('complete'));
    expect(handler).toHaveBeenCalledOnce();
  });
});
