import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Button } from './Button';

describe('Button', () => {
  it('renders primary pill styles', () => {
    render(<Button variant="primary">New Investigation</Button>);
    const btn = screen.getByRole('button', { name: 'New Investigation' });
    expect(btn.className).toMatch(/rounded-full/);
    expect(btn.className).toMatch(/bg-emerald-100\/50/);
    expect(btn.className).toMatch(/text-emerald-700/);
  });
});
