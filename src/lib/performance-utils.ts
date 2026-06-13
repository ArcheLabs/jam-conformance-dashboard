export function formatRelativePerformance(relative: number): string {
  if (relative < 1) {
    return `${(1 / relative).toFixed(1)}x faster`;
  } else if (relative > 1) {
    return `${relative.toFixed(1)}x slower`;
  }
  return 'baseline';
}

export function getPerformanceColor(relative: number): string {
  if (relative < 0.8) return 'text-emerald-500';
  if (relative < 1.5) return 'text-cyan-500';
  if (relative < 3) return 'text-amber-500';
  if (relative < 10) return 'text-orange-500';
  return 'text-red-500';
}

export function getPerformanceGradient(relative: number): string {
  if (relative < 0.8) return 'from-cyan-500/20 to-cyan-500/5';
  if (relative < 1.5) return 'from-purple-500/20 to-purple-500/5';
  if (relative < 3) return 'from-amber-500/20 to-amber-500/5';
  if (relative < 10) return 'from-orange-500/20 to-orange-500/5';
  return 'from-slate-800/50 to-slate-700/30';
}

export function formatScore(score: number | null): string {
  if (score === null || score === undefined) return '-';
  return score.toFixed(2);
}

export function formatLatency(value: number | null | undefined): string {
  if (value === null || value === undefined) return '-';
  return value.toFixed(2);
}
