/** Page numbers to show in the investigations list pager (1-based, inclusive). */
export function buildInvestigationPageNumbers(
  currentPage: number,
  totalPages: number,
  maxVisible = 7,
): number[] {
  if (totalPages <= 0) return [];
  if (totalPages <= maxVisible) {
    return Array.from({ length: totalPages }, (_, i) => i + 1);
  }

  const half = Math.floor(maxVisible / 2);
  let start = Math.max(1, currentPage - half);
  let end = start + maxVisible - 1;
  if (end > totalPages) {
    end = totalPages;
    start = end - maxVisible + 1;
  }
  return Array.from({ length: end - start + 1 }, (_, i) => start + i);
}

export function investigationTotalPages(total: number, pageSize: number): number {
  if (total <= 0 || pageSize <= 0) return 0;
  return Math.ceil(total / pageSize);
}

export function parseInvestigationsPageParam(raw: string | null): number {
  const n = Number.parseInt(raw ?? '1', 10);
  if (!Number.isFinite(n) || n < 1) return 1;
  return n;
}
