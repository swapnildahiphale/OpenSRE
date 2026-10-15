import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ResolutionStatusBadge } from './RunStatusBadge';

describe('ResolutionStatusBadge', () => {
  it('renders Fix unconfirmed for open', () => {
    render(<ResolutionStatusBadge status="open" />);
    expect(screen.getByText('Fix unconfirmed')).toBeInTheDocument();
  });

  it('renders Fix confirmed for confirmed', () => {
    render(<ResolutionStatusBadge status="confirmed" />);
    expect(screen.getByText('Fix confirmed')).toBeInTheDocument();
  });

  it('renders Abandoned for abandoned', () => {
    render(<ResolutionStatusBadge status="abandoned" />);
    expect(screen.getByText('Abandoned')).toBeInTheDocument();
  });

  it('renders nothing for ignored', () => {
    const { container } = render(<ResolutionStatusBadge status="ignored" />);
    expect(container).toBeEmptyDOMElement();
  });
});
