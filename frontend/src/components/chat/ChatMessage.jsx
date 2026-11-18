import React from 'react';
import {
  Sparkles,
  User,
  Bot,
  HelpCircle,
  CheckCircle2,
  ExternalLink,
  Layers,
  ArrowRight,
  BarChart2,
  Sliders,
  Cpu
} from 'lucide-react';
import AgentStatusIndicator from './AgentStatusIndicator';

/**
 * Message Types Supported:
 * - 'text'          : Normal conversational responses
 * - 'question'      : Context-gathering clarification questions
 * - 'options'       : Selectable suggested responses
 * - 'status'        : Agent execution progress
 * - 'visualization' : Embedded architecture visuals (foundation)
 * - 'metrics'       : Performance summaries (foundation)
 * - 'recommendation': Architecture recommendations (foundation)
 * - 'action'        : Navigation to deeper analysis
 */

export default function ChatMessage({ message, onSelectOption, onOpenAnalysis }) {
  const isUser = message.sender === 'user';

  return (
    <div className={`w-full py-4 flex gap-3.5 sm:gap-4 ${isUser ? 'justify-end' : 'justify-start'}`}>
      {/* Bot Avatar (Left) */}
      {!isUser && (
        <div className="w-8 h-8 rounded-xl bg-zinc-100 border border-white/[0.1] text-zinc-950 flex items-center justify-center shrink-0 mt-0.5 shadow-sm">
          <Bot className="w-4 h-4" />
        </div>
      )}

      {/* Message Content Container */}
      <div className={`flex flex-col max-w-[85%] sm:max-w-[78%] ${isUser ? 'items-end' : 'items-start'}`}>
        {/* Author Label (optional subtle header) */}
        <div className="text-[11px] text-zinc-500 mb-1 px-1">
          {isUser ? 'You' : 'ORBIT Architecture Copilot'}
        </div>

        {/* Message Bubble */}
        <div
          className={`rounded-2xl px-4.5 py-3.5 text-sm leading-relaxed ${
            isUser
              ? 'bg-zinc-100 text-zinc-950 font-normal rounded-tr-xs shadow-sm'
              : 'bg-[#151518] text-zinc-200 border border-white/[0.08] rounded-tl-xs shadow-xs'
          }`}
        >
          {/* 1. TEXT TYPE */}
          {message.content && (
            <div className="whitespace-pre-wrap leading-relaxed">
              {message.content}
            </div>
          )}

          {/* 2. QUESTION TYPE */}
          {message.type === 'question' && (
            <div className="mt-2.5 pt-2.5 border-t border-white/[0.08] flex items-start gap-2 text-zinc-300">
              <HelpCircle className="w-4 h-4 text-zinc-400 mt-0.5 shrink-0" />
              <div className="font-medium text-white">{message.questionText}</div>
            </div>
          )}

          {/* 3. OPTIONS TYPE (Selectable suggestion chips) */}
          {message.options && message.options.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {message.options.map((opt, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => onSelectOption && onSelectOption(opt)}
                  className="px-3 py-1.5 rounded-lg border border-white/[0.12] bg-white/[0.04] hover:bg-white/[0.08] hover:border-white/[0.22] text-xs font-medium text-zinc-200 hover:text-white transition-all duration-150 cursor-pointer text-left shadow-xs flex items-center gap-1.5 active:scale-98"
                >
                  <span>{opt}</span>
                  <ArrowRight className="w-3 h-3 text-zinc-500" />
                </button>
              ))}
            </div>
          )}

          {/* 4. STATUS TYPE */}
          {message.type === 'status' && (
            <AgentStatusIndicator
              currentStepIndex={message.statusStepIndex ?? 0}
              isComplete={message.statusComplete ?? false}
            />
          )}

          {/* 5. RECOMMENDATION TYPE (Rich architectural recommendation card) */}
          {message.type === 'recommendation' && message.recommendationData && (
            <div className="mt-3 p-3.5 rounded-xl bg-white/[0.04] border border-white/[0.1] text-xs space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-white text-sm">
                  {message.recommendationData.winningName || 'Recommended Architecture'}
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  OPTIMAL SLA
                </span>
              </div>
              <p className="text-zinc-400 leading-relaxed">
                {message.recommendationData.summary}
              </p>
              {message.recommendationData.metrics && (
                <div className="grid grid-cols-3 gap-2 pt-1 border-t border-white/[0.06] text-center">
                  <div className="p-2 rounded bg-black/30">
                    <div className="text-[10px] text-zinc-500">p95 Latency</div>
                    <div className="font-mono font-semibold text-zinc-200">
                      {message.recommendationData.metrics.p95_latency_ms} ms
                    </div>
                  </div>
                  <div className="p-2 rounded bg-black/30">
                    <div className="text-[10px] text-zinc-500">Throughput</div>
                    <div className="font-mono font-semibold text-zinc-200">
                      {message.recommendationData.metrics.throughput_achieved_rps} RPS
                    </div>
                  </div>
                  <div className="p-2 rounded bg-black/30">
                    <div className="text-[10px] text-zinc-500">Monthly Cost</div>
                    <div className="font-mono font-semibold text-zinc-200">
                      ${message.recommendationData.metrics.estimated_monthly_cost_usd}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* 6. ACTION TYPE (e.g. Deep dive into visual blueprint / comparison) */}
          {message.action && (
            <div className="mt-3.5 pt-2.5 border-t border-white/[0.08] flex items-center justify-end">
              <button
                type="button"
                onClick={() => onOpenAnalysis && onOpenAnalysis(message.action)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-100 hover:bg-white text-zinc-950 font-medium text-xs transition-colors cursor-pointer shadow-xs"
              >
                <span>{message.action.label || 'Open Architecture Blueprint'}</span>
                <ExternalLink className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
        </div>

        {/* Timestamp */}
        <span className="text-[10px] text-zinc-600 mt-1 px-1">
          {message.timestamp
            ? new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            : ''}
        </span>
      </div>

      {/* User Avatar (Right) */}
      {isUser && (
        <div className="w-8 h-8 rounded-xl bg-white/[0.1] border border-white/[0.1] text-zinc-200 flex items-center justify-center shrink-0 mt-0.5 shadow-sm">
          <User className="w-4 h-4" />
        </div>
      )}
    </div>
  );
}
