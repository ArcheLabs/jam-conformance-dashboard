'use client';

import { motion } from 'framer-motion';
import { BarChart3, TrendingUp, Activity, Layers, Sigma } from 'lucide-react';

interface MethodologyExplainerProps {
  scoring?: {
    description: string;
    lane_weights: Record<string, number>;
    aggregation: string;
  };
}

export function MethodologyExplainer({ scoring }: MethodologyExplainerProps) {
  if (!scoring) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="relative overflow-hidden rounded-2xl bg-white/[0.02] backdrop-blur-xl border border-white/10 shadow-2xl"
    >
      <div className="absolute inset-0 bg-gradient-to-br from-white/[0.05] via-white/[0.02] to-white/[0.05]" />

      <div className="relative p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 bg-white/5 rounded-lg border border-white/10">
            <BarChart3 className="w-5 h-5 text-white/60" />
          </div>
          <h3 className="text-xl font-bold text-white">Scoring Methodology</h3>
        </div>

        <div className="space-y-4">
          <div>
            <p className="text-sm text-slate-300 leading-relaxed">
              Each lane score is a weighted combination of the median (P50), high percentile (P90), extreme percentile (P99), and a capped maximum — with the median carrying the most weight. The overall score is the geometric mean across all completed lanes.
            </p>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {Object.entries(scoring.lane_weights).map(([metric, weight]) => {
              const metricInfo = {
                p50: { name: 'P50', icon: TrendingUp, color: 'from-cyan-500 to-cyan-600' },
                p90: { name: 'P90', icon: Activity, color: 'from-blue-500 to-blue-600' },
                p99: { name: 'P99', icon: Layers, color: 'from-purple-500 to-purple-600' },
                max: { name: 'Max (capped)', icon: Sigma, color: 'from-amber-500 to-amber-600' },
              }[metric] || { name: metric, icon: BarChart3, color: 'from-slate-500 to-slate-600' };

              const Icon = metricInfo.icon;
              const percentage = (weight * 100).toFixed(0);

              return (
                <div
                  key={metric}
                  className="p-3 bg-white/[0.03] rounded-lg border border-white/5"
                >
                  <div className="flex items-center gap-2 mb-2">
                    <div className={`p-1 rounded bg-gradient-to-br ${metricInfo.color}`}>
                      <Icon className="w-3 h-3 text-white" />
                    </div>
                    <span className="text-sm font-medium text-white">{metricInfo.name}</span>
                  </div>
                  <div className="flex items-baseline gap-1">
                    <span className="text-2xl font-bold text-white">{percentage}</span>
                    <span className="text-sm text-slate-400">%</span>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="p-3 bg-white/[0.03] rounded-lg border border-white/5">
            <div className="flex items-center gap-2 mb-1">
              <Sigma className="w-4 h-4 text-cyan-400" />
              <span className="text-sm font-medium text-white">Aggregation Method</span>
            </div>
            <p className="text-sm text-slate-400">
              The overall score is the geometric mean of all lane scores, giving equal weight to each lane. Within a lane, the score is a weighted combination of the median (P50), high percentile (P90), extreme percentile (P99), and a capped maximum — with the median carrying the most weight. Only completed lanes without errors are included in the ranking. Teams with incomplete lanes are grouped separately.
            </p>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
