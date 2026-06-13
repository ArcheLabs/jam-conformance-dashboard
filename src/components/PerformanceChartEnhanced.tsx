'use client';

import { LeaderboardEntry } from '@/types/performance';
import { motion } from 'framer-motion';
import { BarChart3, Zap } from 'lucide-react';
import { getPerformanceColor } from '@/lib/performance-utils';
import { UI_CONFIG } from '@/config';

interface PerformanceChartEnhancedProps {
  teams: LeaderboardEntry[];
  lane?: string;
  baselineTeam?: LeaderboardEntry;
}

export function PerformanceChartEnhanced({ teams, lane, baselineTeam }: PerformanceChartEnhancedProps) {
  if (!teams || teams.length === 0) return null;

  const baseTeam = baselineTeam || teams[0];
  const baselineScore = baseTeam.score ?? 0;

  const getDisplayValue = (t: LeaderboardEntry) => {
    if (lane && lane !== 'overview') {
      const ls = t.lanes[lane];
      if (ls) return ls.p50 ?? ls.p90 ?? 0;
    }
    return t.score ?? 0;
  };

  const getBaselineValue = () => {
    if (lane && lane !== 'overview') {
      const ls = baseTeam.lanes[lane];
      if (ls) return ls.p50 ?? ls.p90 ?? baselineScore;
    }
    return baselineScore;
  };

  const baselineVal = getBaselineValue();
  const maxValue = Math.max(...teams.map(getDisplayValue));
  const minValue = Math.min(...teams.filter(t => getDisplayValue(t) > 0).map(getDisplayValue));
  const range = maxValue / Math.max(minValue, 0.01);
  const shouldUseLogScale = range > 50;

  const getBarWidth = (value: number) => {
    if (shouldUseLogScale) {
      const logMax = Math.log10(maxValue || 1);
      const logMin = Math.log10(minValue || 1);
      return Math.max(2, ((Math.log10(value || 1) - logMin) / (logMax - logMin)) * 100);
    }
    return Math.max(2, (value / maxValue) * 100);
  };

  const getGradientByPerformance = (val: number) => {
    const rel = val / Math.max(baselineVal, 0.01);
    if (rel < 1.2) return 'from-emerald-500 to-emerald-400';
    if (rel < 2) return 'from-cyan-500 to-cyan-400';
    if (rel < 5) return 'from-blue-500 to-blue-400';
    if (rel < 10) return 'from-purple-500 to-purple-400';
    if (rel < 20) return 'from-amber-500 to-amber-400';
    if (rel < 50) return 'from-orange-500 to-orange-400';
    return 'from-red-500 to-red-400';
  };

  const formatRelative = (val: number) => {
    const rel = val / Math.max(baselineVal, 0.01);
    if (rel < 1) return `${(1 / rel).toFixed(1)}x faster`;
    if (rel > 1.05) return `${rel.toFixed(1)}x slower`;
    return 'baseline';
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: UI_CONFIG.animation.mediumDuration }}
      className="relative overflow-hidden rounded-2xl bg-white/[0.02] backdrop-blur-xl border border-white/10 shadow-2xl"
    >
      <div className="absolute inset-0 bg-gradient-to-br from-white/[0.05] via-white/[0.02] to-white/[0.05]" />

      <div className="relative p-6">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-white/5 rounded-lg border border-white/10">
              <BarChart3 className="w-6 h-6 text-white/60" />
            </div>
            <div>
              <h3 className="text-2xl font-bold text-white">Performance Comparison</h3>
              <p className="text-sm text-slate-400 mt-1">
                All implementations relative to {baseTeam.client_name}
                <span className="text-xs ml-2">(baseline {baselineVal.toFixed(2)}ms)</span>
              </p>
            </div>
          </div>
        </div>

        <div className="space-y-1.5">
          {teams.map((team, index) => {
            const value = getDisplayValue(team);
            const percentage = getBarWidth(value);
            const gradient = getGradientByPerformance(value);
            const isBaseline = team.team_id === baseTeam.team_id;
            const relStr = formatRelative(value);

            const laneStats = lane && lane !== 'overview' ? team.lanes[lane] : null;

            return (
              <motion.div
                key={team.team_id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.02, duration: 0.3 }}
                className="group"
              >
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="text-[10px] font-mono text-slate-600 w-6 text-right">
                      {team.rank}
                    </span>
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-sm font-medium text-white truncate">
                        {team.client_name}
                      </span>
                      {isBaseline && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-full bg-white/10 text-white/70 border border-white/20">
                          <Zap className="w-3 h-3" />
                          Baseline
                        </span>
                      )}
                      {team.language && (
                        <div className="inline-flex items-center">
                          <span
                            className="w-2 h-2 rounded-full mr-1.5"
                            style={{ backgroundColor: team.language_color || '#666' }}
                          />
                          <span className="text-xs text-slate-500">
                            {team.language}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-3 ml-4">
                    <span className={`text-xs ${getPerformanceColor(value / Math.max(baselineVal, 0.01))}`}>
                      {relStr}
                    </span>
                    <span className="text-sm font-mono text-slate-300 w-20 text-right">
                      {value.toFixed(2)}ms
                    </span>
                  </div>
                </div>

                <div className="relative h-6 bg-black/30 rounded-lg overflow-hidden ml-10 group-hover:bg-black/50 transition-colors">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${percentage}%` }}
                    transition={{ duration: 0.8, delay: index * 0.02, ease: "easeOut" }}
                    className={`absolute inset-y-0 left-0 bg-gradient-to-r ${gradient} opacity-80 group-hover:opacity-100 transition-opacity`}
                  >
                    <div className="absolute inset-0 bg-gradient-to-r from-white/10 to-transparent" />
                  </motion.div>

                  {laneStats && (
                    <div className="absolute inset-0 flex items-center">
                      <div className="flex-1 relative">
                        {laneStats.p50 != null && laneStats.p50 <= maxValue && (
                          <div className="absolute top-1/2 -translate-y-1/2 w-[1px] h-4 bg-white/40" style={{ left: `${Math.min(getBarWidth(laneStats.p50), 100)}%` }} />
                        )}
                        {laneStats.p90 != null && laneStats.p90 <= maxValue && (
                          <div className="absolute top-1/2 -translate-y-1/2 w-[1px] h-3 bg-white/30" style={{ left: `${Math.min(getBarWidth(laneStats.p90), 100)}%` }} />
                        )}
                        {laneStats.p99 != null && laneStats.p99 <= maxValue && (
                          <div className="absolute top-1/2 -translate-y-1/2 w-[1px] h-2 bg-white/20" style={{ left: `${Math.min(getBarWidth(laneStats.p99), 100)}%` }} />
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </motion.div>
            );
          })}
        </div>

        <div className="mt-4 pt-4 border-t border-neutral-800/50">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div className="text-xs text-slate-500">
              {shouldUseLogScale ? 'Logarithmic scale' : 'Linear scale'} — Lower is better
            </div>
            <div className="flex items-center gap-6 text-xs">
              {lane && lane !== 'overview' && (
                <div className="flex items-center gap-3 pr-4 border-r border-slate-700/50">
                  <span className="text-slate-500">Percentiles:</span>
                  <div className="flex items-center gap-1"><div className="w-[1px] h-4 bg-white/40" /><span className="text-slate-400 ml-1">P50</span></div>
                  <div className="flex items-center gap-1"><div className="w-[1px] h-3 bg-white/30" /><span className="text-slate-400 ml-1">P90</span></div>
                  <div className="flex items-center gap-1"><div className="w-[1px] h-2 bg-white/20" /><span className="text-slate-400 ml-1">P99</span></div>
                </div>
              )}

              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1.5"><div className="w-3 h-3 rounded bg-gradient-to-r from-emerald-500 to-emerald-400" /><span className="text-slate-400">&lt;1.2x</span></div>
                <div className="flex items-center gap-1.5"><div className="w-3 h-3 rounded bg-gradient-to-r from-cyan-500 to-cyan-400" /><span className="text-slate-400">&lt;2x</span></div>
                <div className="flex items-center gap-1.5"><div className="w-3 h-3 rounded bg-gradient-to-r from-purple-500 to-purple-400" /><span className="text-slate-400">&lt;10x</span></div>
                <div className="flex items-center gap-1.5"><div className="w-3 h-3 rounded bg-gradient-to-r from-red-500 to-red-400" /><span className="text-slate-400">&gt;50x</span></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
