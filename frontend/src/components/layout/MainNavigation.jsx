import React from 'react';
import { useApp } from '../../context/AppContext';
import { Award, Layers, ShieldCheck } from 'lucide-react';

export default function MainNavigation() {
  const { activeTab, setActiveTab, response } = useApp();
  const candidatesCount = response?.candidates?.length || response?.decision_result?.candidates?.length || 3;

  const NAV_ITEMS = [
    { id: 'blueprint', label: 'Architecture Blueprint', num: '01', icon: Award },
    { id: 'compare', label: `Compare Options (${candidatesCount})`, num: '02', icon: Layers },
    { id: 'technical', label: 'Technical Proof & Benchmarks', num: '03', icon: ShieldCheck },
  ];

  return (
    <div className="border-b border-white/[0.08] bg-[#0a0e1c]/90 backdrop-blur-md px-6 py-2 flex items-center justify-between gap-4 overflow-x-auto shrink-0 z-10">
      <div className="inline-flex items-center gap-1 p-1 rounded-xl bg-slate-950/70 border border-white/[0.08] shadow-inner">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;

          return (
            <button
              key={item.id}
              type="button"
              onClick={() => setActiveTab(item.id)}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-medium flex items-center gap-2 transition-all cursor-pointer ${
                isActive
                  ? 'bg-gradient-to-b from-indigo-500/25 to-indigo-600/15 text-white shadow-sm border border-indigo-500/35 font-semibold'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-white/[0.04] border border-transparent'
              }`}
            >
              <span className={`text-[10px] font-mono px-1.5 py-0.2 rounded ${isActive ? 'bg-indigo-500/20 text-indigo-300' : 'text-slate-500'}`}>
                {item.num}
              </span>
              <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-indigo-300' : 'text-slate-400'}`} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
