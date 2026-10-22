import { describe, it, expect } from 'vitest';
import {
  buildInvestigationPageNumbers,
  investigationTotalPages,
  parseInvestigationsPageParam,
} from './investigationsPager';

describe('investigationsPager', () => {
  it('parses page query param', () => {
    expect(parseInvestigationsPageParam(null)).toBe(1);
    expect(parseInvestigationsPageParam('3')).toBe(3);
    expect(parseInvestigationsPageParam('0')).toBe(1);
    expect(parseInvestigationsPageParam('bad')).toBe(1);
  });

  it('computes total pages', () => {
    expect(investigationTotalPages(45, 20)).toBe(3);
    expect(investigationTotalPages(0, 20)).toBe(0);
  });

  it('builds compact page number window', () => {
    expect(buildInvestigationPageNumbers(1, 3)).toEqual([1, 2, 3]);
    expect(buildInvestigationPageNumbers(5, 10, 5)).toEqual([3, 4, 5, 6, 7]);
  });
});
