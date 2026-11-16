import React, { useState, useEffect } from 'react';
import { useApp } from '../../context/AppContext';
import { X, Copy, Check, Terminal, RefreshCw } from 'lucide-react';
import { generateAIPrompt } from '../../utils/aiPromptGenerator';

export default function ImplementationPromptModal() {
  const {
    isPromptModalOpen,
    setIsPromptModalOpen,
    response,
  } = useApp();

  const decisionResult = response?.decision_result || response?.decisionResult;
  const workload = decisionResult?.workload || response?.workload || {};
  const candidates = response?.candidates || [];
  const recommendation = response?.recommendation || {};
  const winner = recommendation.winner || candidates.find((c) => c.id === recommendation.winner_id) || candidates[0];

  const [promptText, setPromptText] = useState('');
  const [copied, setCopied] = useState(false);

  // Generate prompt when modal opens or simulation response changes
  useEffect(() => {
    if (winner) {
      const generated = generateAIPrompt(winner, workload, recommendation, decisionResult);
      setPromptText(generated);
    }
  }, [winner, workload, recommendation, decisionResult, isPromptModalOpen]);

  // Handle escape key
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isPromptModalOpen) {
        setIsPromptModalOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isPromptModalOpen, setIsPromptModalOpen]);

  if (!isPromptModalOpen) return null;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(promptText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch (err) {
      console.error('Failed to copy to clipboard:', err);
    }
  };

  const handleRegenerate = () => {
    const fresh = generateAIPrompt(winner, workload, recommendation, decisionResult);
    setPromptText(fresh);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/70 backdrop-blur-xs transition-opacity"
        onClick={() => setIsPromptModalOpen(false)}
      />

      {/* Modal Dialog */}
      <div className="relative w-full max-w-3xl bg-[#0c101a] border border-white/[0.1] rounded-2xl shadow-2xl flex flex-col z-10 max-h-[90vh] overflow-hidden">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-white/[0.08] flex items-center justify-between shrink-0 bg-[#090d16]">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
              <Terminal className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-100 tracking-tight flex items-center gap-2">
                <span>AI Implementation Blueprint</span>
                <span className="badge badge-indigo text-[10px] py-0 px-1.5 font-mono">
                  Cursor · Claude Code · Copilot
                </span>
              </h2>
              <p className="text-[11px] text-slate-400">
                Structured specification with strict infrastructure boundaries and non-goals
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={() => setIsPromptModalOpen(false)}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-white/[0.06] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body: Editable Prompt Preview */}
        <div className="p-6 flex-1 overflow-y-auto space-y-3 font-mono text-xs">
          <div className="flex items-center justify-between text-slate-400 text-[11px] font-sans">
            <span>You can review, edit, or copy this prompt directly into your AI coding agent:</span>
            <span className="text-slate-500">{promptText.length} characters</span>
          </div>

          <textarea
            value={promptText}
            onChange={(e) => setPromptText(e.target.value)}
            rows={18}
            className="w-full bg-black/40 border border-white/[0.08] focus:border-indigo-500 rounded-xl p-4 font-mono text-xs text-slate-200 leading-relaxed resize-none focus:outline-none"
            spellCheck={false}
          />
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-4 border-t border-white/[0.08] bg-[#090d16] flex items-center justify-between gap-3 shrink-0">
          <button
            type="button"
            onClick={handleRegenerate}
            className="btn btn-ghost text-xs py-2 px-3 text-slate-400 hover:text-slate-200 flex items-center gap-1.5"
            title="Reset edits to canonical generated prompt"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Reset Edits</span>
          </button>

          <div className="flex items-center gap-2.5">
            <button
              type="button"
              onClick={() => setIsPromptModalOpen(false)}
              className="btn btn-secondary text-xs py-2 px-4"
            >
              Close
            </button>

            <button
              type="button"
              onClick={handleCopy}
              className="btn btn-primary text-xs py-2 px-4 flex items-center gap-2"
            >
              {copied ? (
                <>
                  <Check className="w-4 h-4 text-emerald-300" />
                  <span className="text-emerald-200 font-semibold">Copied to Clipboard!</span>
                </>
              ) : (
                <>
                  <Copy className="w-4 h-4" />
                  <span>Copy Prompt</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
