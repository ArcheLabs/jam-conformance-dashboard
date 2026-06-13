'use client';

import { motion } from 'framer-motion';
import { Activity, Layers, BarChart3, Box, Database } from 'lucide-react';

interface BenchmarkTabsProps {
  currentBenchmark: string;
  onBenchmarkChange: (benchmark: string) => void;
}

const benchmarks = [
  { id: '', name: 'Overview', icon: Activity, description: 'Overall leaderboard' },
  { id: 'L2a', name: 'L2a', icon: Layers, description: 'Tiny spec — import with mutations, without Safrole' },
  { id: 'L2b', name: 'L2b', icon: BarChart3, description: 'Full spec — import with mutations, without Safrole' },
  { id: 'L3a', name: 'L3a', icon: Box, description: 'Tiny spec — Safrole with validators-management workload, no mutations' },
  { id: 'L3b', name: 'L3b', icon: Database, description: 'Full spec — Safrole with empty workload, no mutations' },
];

export function BenchmarkTabs({ currentBenchmark, onBenchmarkChange }: BenchmarkTabsProps) {
  return (
    <div className="flex flex-wrap gap-2 p-1 bg-black/30 rounded-xl border border-white/5">
      {benchmarks.map((benchmark) => {
        const Icon = benchmark.icon;
        const isActive = currentBenchmark === benchmark.id;

        return (
          <button
            key={benchmark.id}
            onClick={() => onBenchmarkChange(benchmark.id)}
            className={`
              relative flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-sm
              transition-all duration-200
              ${isActive
                ? 'bg-white/10 text-white border border-white/20'
                : 'text-slate-400 hover:text-white hover:bg-white/5'
              }
            `}
          >
            <Icon className="w-4 h-4" />
            <span>{benchmark.name}</span>
            {isActive && (
              <motion.div
                layoutId="benchmark-tab"
                className="absolute inset-0 bg-white/5 rounded-lg -z-10"
                transition={{ type: "spring", bounce: 0.2, duration: 0.6 }}
              />
            )}
          </button>
        );
      })}
    </div>
  );
}
