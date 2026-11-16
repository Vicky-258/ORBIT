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
    <div className="border-b border-slate-200 bg-white px-6 py-2.5 flex items-center justify-between gap-4 overflow-x-auto shrink-0 shadow-2xs">
      <div className="inline-flex items-center gap-1 p-1 rounded-lg bg-slate-100 border border-slate-200/80">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;

          return (
            <button
              key={item.id}
              type="button"
              onClick={() => setActiveTab(item.id)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium flex items-center gap-2 transition-all cursor-pointer ${
                isActive
                  ? 'bg-white text-slate-900 shadow-xs border border-slate-200/80 font-semibold'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-white/60 border border-transparent'
              }`}
            >
              <span className={`text-[10px] font-mono px-1.5 py-0.2 rounded ${isActive ? 'bg-slate-100 text-slate-700 font-semibold' : 'text-slate-400'}`}>
                {item.num}
              </span>
              <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-slate-900' : 'text-slate-400'}`} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
