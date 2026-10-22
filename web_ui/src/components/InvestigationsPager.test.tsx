import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { InvestigationsPager } from './InvestigationsPager';

describe('InvestigationsPager', () => {
  it('disables Previous on first page and Next on last page', () => {
    const onPageChange = vi.fn();
    const { rerender } = render(
      <InvestigationsPager page={1} total={45} onPageChange={onPageChange} />,
    );

    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Next' })).not.toBeDisabled();

    rerender(
      <InvestigationsPager page={3} total={45} onPageChange={onPageChange} />,
    );
    expect(screen.getByRole('button', { name: 'Previous' })).not.toBeDisabled();
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled();
  });

  it('calls onPageChange when Next is clicked', () => {
    const onPageChange = vi.fn();
    render(
      <InvestigationsPager page={1} total={45} onPageChange={onPageChange} />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(onPageChange).toHaveBeenCalledWith(2);
  });

  it('renders nothing when only one page', () => {
    const { container } = render(
      <InvestigationsPager page={1} total={10} onPageChange={vi.fn()} />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});
