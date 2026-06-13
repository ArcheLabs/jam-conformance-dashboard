'use client';

import { LeaderboardEntry } from '@/types/performance';
import { formatRelativePerformance, getPerformanceColor, getPerformanceGradient } from '@/lib/performance-utils';
import { cn } from '@/lib/utils';
import { motion } from 'framer-motion';
import { Minus } from 'lucide-react';
import { LanguageBadge } from './LanguageBadge';

interface LeaderboardTableProps {
  teams: LeaderboardEntry[];
  currentTab?: string;
}

export function LeaderboardTable({ teams, currentTab }: LeaderboardTableProps) {
  if (!teams || teams.length === 0) {
    return (
      <div className="relative overflow-hidden rounded-2xl bg-white/[0.02] backdrop-blur-xl border border-white/10 shadow-2xl">
        <div className="relative p-8 text-center text-slate-400">
          No data available for this view.
        </div>
      </div>
    );
  }

  const baseline = teams[0];
  const baselineScore = baseline.score ?? 0;

  const getP50 = (t: LeaderboardEntry) => {
    if (currentTab) {
      const ls = t.lanes[currentTab];
      if (ls) return ls.p50;
    }
    return t.metrics.geo_p50;
  };

  const getP90 = (t: LeaderboardEntry) => {
    if (currentTab) {
      const ls = t.lanes[currentTab];
      if (ls) return ls.p90;
    }
    return t.metrics.geo_p90;
  };

  return (
    <div className="relative overflow-hidden rounded-2xl bg-white/[0.02] backdrop-blur-xl border border-white/10 shadow-2xl">
      <div className="absolute inset-0 bg-gradient-to-br from-white/[0.05] via-white/[0.02] to-white/[0.05]" />

      <div className="relative">
        <div className="px-8 py-6 border-b border-neutral-800/50">
          <h2 className="text-2xl font-bold text-white">Performance Rankings</h2>
          <p className="text-sm text-slate-400 mt-1">
            Baseline: {baseline.client_name}
            <span className="text-white/60 ml-2">
              (Score: {baseline.score?.toFixed(1)})
            </span>
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-neutral-800">
                <th className="px-6 py-4 text-left text-sm font-medium text-slate-400">Rank</th>
                <th className="px-6 py-4 text-left text-sm font-medium text-slate-400">Client</th>
                <th className="px-6 py-4 text-left text-sm font-medium text-slate-400">Language</th>
                <th className="px-6 py-4 text-right text-sm font-medium text-slate-400">Score</th>
                <th className="px-6 py-4 text-right text-sm font-medium text-slate-400">P50 (ms)</th>
                <th className="px-6 py-4 text-right text-sm font-medium text-slate-400">P90 (ms)</th>
                <th className="px-6 py-4 text-right text-sm font-medium text-slate-400">Relative Performance</th>
                <th className="px-6 py-4 text-center text-sm font-medium text-slate-400">Trend</th>
              </tr>
            </thead>
            <tbody>
              {teams.map((team, index) => {
                const relativeToBaseline = baselineScore > 0 ? (team.score ?? 0) / baselineScore : 1;
                const isBaseline = team.rank === 1;

                return (
                  <motion.tr
                    key={team.team_id}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.05 }}
                    className="border-b border-neutral-800/50 hover:bg-white/5 transition-colors"
                  >
                    <td className="px-6 py-4">
                      <span className="font-mono text-lg text-white">{team.rank}</span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="font-medium text-white">
                        {team.client_name}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <LanguageBadge
                        language={team.language}
                        color={team.language_color}
                      />
                    </td>
                    <td className="px-6 py-4 text-right">
                      <span className="font-mono text-sm text-slate-300">
                        {team.score?.toFixed(1) ?? '-'}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <span className="font-mono text-sm text-slate-300">
                        {getP50(team) != null ? getP50(team)!.toFixed(2) : '-'}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <span className="font-mono text-sm text-slate-300">
                        {getP90(team) != null ? getP90(team)!.toFixed(2) : '-'}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <div className={cn(
                        "inline-flex items-center gap-2 px-3 py-1 rounded-full text-sm font-medium whitespace-nowrap",
                        "bg-gradient-to-r",
                        getPerformanceGradient(relativeToBaseline)
                      )}>
                        <span className={cn("font-mono text-xs", getPerformanceColor(relativeToBaseline))}>
                          {isBaseline ? 'baseline' : formatRelativePerformance(relativeToBaseline)}
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex justify-center">
                        <Minus className="w-5 h-5 text-slate-500" />
                      </div>
                    </td>
                  </motion.tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
