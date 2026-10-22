import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import InvestigationHaltBanner from './InvestigationHaltBanner';

describe('InvestigationHaltBanner', () => {
  it('renders the halt message', () => {
    render(
      <InvestigationHaltBanner message="Investigation stopped after 10 minutes (time limit)." />,
    );
    expect(screen.getByTestId('investigation-halt-banner')).toHaveTextContent(
      'Investigation stopped after 10 minutes (time limit).',
    );
  });

  it('invokes follow-up handler when the action is clicked', () => {
    const onFollowUp = vi.fn();
    render(
      <InvestigationHaltBanner
        message="Work may be incomplete."
        onFollowUp={onFollowUp}
      />,
    );
    fireEvent.click(screen.getByTestId('investigation-halt-banner-follow-up'));
    expect(onFollowUp).toHaveBeenCalledOnce();
  });
});
