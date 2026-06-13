export const PERFORMANCE_CONFIG = {
  thresholds: {
    excellent: 5,
    good: 10,
    fair: 20,
    moderate: 50,
    poor: 100,
    veryPoor: 200,
    critical: 500,
  },

  scoring: {
    laneWeights: {
      p50: 0.50,
      p90: 0.30,
      p99: 0.15,
      max: 0.05,
    },
    aggregation: 'geometric_mean',
  },

  visualization: {
    logScaleThreshold: 50,
  },
};

export function getPerformanceCategory(score: number | null): string {
  if (score === null) return 'unknown';
  const { thresholds } = PERFORMANCE_CONFIG;

  if (score <= thresholds.excellent) return 'excellent';
  if (score < thresholds.good) return 'good';
  if (score < thresholds.fair) return 'fair';
  if (score < thresholds.moderate) return 'moderate';
  if (score < thresholds.poor) return 'poor';
  if (score < thresholds.veryPoor) return 'veryPoor';
  return 'critical';
}
