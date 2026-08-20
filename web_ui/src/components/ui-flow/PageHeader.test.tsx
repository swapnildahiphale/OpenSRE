import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { PageHeader } from './PageHeader';

describe('PageHeader', () => {
  it('renders eyebrow and dotted title', () => {
    render(<PageHeader eyebrow="Dashboard" title="Today" />);
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Today.');
  });
});
