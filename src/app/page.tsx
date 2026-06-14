'use client';

import { useState } from 'react';
import { LeaderboardTable } from '@/components/LeaderboardTable';
import { BenchmarkTabs } from '@/components/BenchmarkTabs';
import { MethodologyExplainer } from '@/components/MethodologyExplainer';
import { PerformanceChartEnhanced } from '@/components/PerformanceChartEnhanced';
import { BarChart3 } from 'lucide-react';
import leaderboardData from '@/data/leaderboard.json';
import { APP_CONFIG } from '@/config';
import { LeaderboardData } from '@/types/performance';

const data = leaderboardData as unknown as LeaderboardData;

export default function Home() {
  const [currentTab, setCurrentTab] = useState('');

  const basePath = APP_CONFIG.paths.basePath;
  const baselineTeam = data.teams[0];

  const filteredTeams = () => {
    if (!currentTab) return data.teams;
    return data.teams
      .filter(t => t.lanes[currentTab])
      .sort((a, b) => {
        const sa = a.lanes[currentTab].p50 ?? a.lanes[currentTab].p90 ?? Infinity;
        const sb = b.lanes[currentTab].p50 ?? b.lanes[currentTab].p90 ?? Infinity;
        return sa - sb;
      })
      .map((t, i) => ({ ...t, rank: i + 1 }));
  };

  return (
    <main className="min-h-screen" style={{ backgroundImage: `url(${basePath}${APP_CONFIG.paths.backgroundImage})`, backgroundRepeat: 'repeat', backgroundSize: '1024px 1059px', backgroundColor: '#000000' }}>
      <div className="relative z-10">
        <div className="container mx-auto px-4 py-12">
          {/* Header - left aligned as original */}
          <div className="flex flex-col md:flex-row items-center justify-between mb-12">
            <div className="text-center md:text-left mb-6 md:mb-0">
              <h1 className="text-4xl md:text-5xl font-black text-white mb-4 tracking-tighter">
                M1 Conformance Evaluation Runtime Statistics
              </h1>
              <p className="max-w-4xl text-sm md:text-base text-slate-400 font-light leading-6">
                This page summarizes runtime statistics from the M1 conformance tests to help JAM implementations identify targeted optimization opportunities. The data should be treated as reference only and not as strict performance benchmark results.
              </p>
            </div>
          </div>

          {/* Tabs */}
          <div className="mb-8">
            <BenchmarkTabs
              currentBenchmark={currentTab}
              onBenchmarkChange={setCurrentTab}
            />
          </div>

          {/* Overview: Info box + Chart */}
          {!currentTab && (
            <div className="mb-12">
              <PerformanceChartEnhanced teams={data.teams} baselineTeam={baselineTeam} />
            </div>
          )}

          {/* Lane view: description + chart */}
          {currentTab && (
            <>
              {(() => {
                const descs: Record<string, { name: string; desc: string }> = {
                  L2a: { name: 'L2a — Mutations (Tiny)', desc: 'Import with mutations and error handling, without Safrole.' },
                  L2b: { name: 'L2b — Mutations (Full)', desc: 'Import with mutations and error handling, without Safrole.' },
                  L3a: { name: 'L3a — Safrole (validators-management)', desc: 'Exercise Safrole with validators-management workload, no mutations.' },
                  L3b: { name: 'L3b — Safrole (empty)', desc: 'Exercise Safrole with empty workload, no mutations.' },
                };
                const info = descs[currentTab];
                if (!info) return null;
                return (
                  <div className="mb-8 p-4 bg-white/5 border border-white/10 rounded-lg">
                    <div className="flex items-start gap-3">
                      <BarChart3 className="w-5 h-5 text-cyan-400 mt-0.5 flex-shrink-0" />
                      <div className="text-sm text-slate-300">
                        <p className="font-semibold text-white mb-1">{info.name}</p>
                        <p>{info.desc}</p>
                      </div>
                    </div>
                  </div>
                );
              })()}
              <div className="mb-12">
              <PerformanceChartEnhanced
                teams={filteredTeams()}
                lane={currentTab}
                baselineTeam={baselineTeam}
              />
              </div>
            </>
          )}

          {/* Table */}
          <div className="mb-12">
            <LeaderboardTable teams={filteredTeams()} currentTab={currentTab} />
          </div>

          {/* Methodology */}
          {!currentTab && (
            <div className="w-full">
              <MethodologyExplainer scoring={data.scoring} />
            </div>
          )}

          {/* Footer */}
          <div className="mt-16 text-center text-sm text-slate-500">
            <p>
              Methodology v{data.methodology_version} | Lanes: {data.lanes.join(', ')}
            </p>
            <p className="mt-2">
              Data generated: {data.generated_at?.split('T')[0] || '-'}
            </p>
            <p className="mt-2">
              <a
                href={APP_CONFIG.externalLinks.jamConformance}
                target="_blank"
                rel="noopener noreferrer"
                className="text-cyan-400 hover:text-cyan-300 transition-colors"
              >
                jam-conformance
              </a>
              {' | '}
              <a
                href={APP_CONFIG.externalLinks.graypaperClients}
                target="_blank"
                rel="noopener noreferrer"
                className="text-cyan-400 hover:text-cyan-300 transition-colors"
              >
                View all clients
              </a>
              {' | '}
              <a
                href={APP_CONFIG.externalLinks.viblyNetwork}
                target="_blank"
                rel="noopener noreferrer"
                className="text-cyan-400 hover:text-cyan-300 transition-colors"
              >
                Vibly Network
              </a>
            </p>
          </div>
        </div>
      </div>
    </main>
  );
}
