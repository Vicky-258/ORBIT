import React from 'react';
import { useApp } from '../../context/AppContext';
import { Award, Layers, ShieldCheck } from 'lucide-react';

export default function MainNavigation() {
  const { activeTab, setActiveTab, response } = useApp();
  const candidatesCount = response?.candidates?.length || response?.decision_result?.candidates?.length || 3;

  const NAV_ITEMS = [
    { id: 'blueprint', label: '01. Architecture Blueprint', icon: Award },
    { id: 'compare', label: `02. Compare Options (${candidatesCount})`, icon: Layers },
    { id: 'technical', label: '03. Technical Proof & Benchmarks', icon: ShieldCheck },
  ];

  return (
    <div className="border-b border-white/[0.08] bg-[#0c101a] px-5 sm:px-6 flex items-center justify-between gap-4 overflow-x-auto shrink-0 z-10">
      <div className="flex items-center gap-1">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;

          return (
            <button
              key={item.id}
              type="button"
              onClick={() => setActiveTab(item.id)}
              className={`px-4 py-3 text-xs font-medium flex items-center gap-2 border-b-2 transition-all cursor-pointer ${
                isActive
                  ? 'border-indigo-500 text-indigo-300 font-semibold'
                  : 'border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-700'
              }`}
            >
              <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-indigo-400' : 'text-slate-400'}`} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
