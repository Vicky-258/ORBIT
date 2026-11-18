import React, { useRef, useEffect } from 'react';
import { ArrowUp, CornerDownLeft, Sparkles, Paperclip } from 'lucide-react';

export default function ChatInput({
  value,
  onChange,
  onSubmit,
  disabled = false,
  placeholder = "Describe your application idea, requirements, or ask a question...",
}) {
  const textareaRef = useRef(null);

  // Auto-resize textarea height up to a maximum
  useEffect(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = 'auto';
      el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
    }
  }, [value]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!disabled && value.trim()) {
        onSubmit();
      }
    }
  };

  return (
    <div className="w-full max-w-3xl mx-auto px-4 sm:px-6 pb-5 pt-2">
      <div className="relative rounded-2xl border border-white/[0.12] bg-[#141417] shadow-xl focus-within:border-zinc-500 focus-within:ring-1 focus-within:ring-zinc-500/50 transition-all duration-200">
        <textarea
          ref={textareaRef}
          rows={1}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder={placeholder}
          className="w-full bg-transparent text-sm text-zinc-100 placeholder-zinc-500 px-4 pt-3.5 pb-12 resize-none outline-none overflow-y-auto leading-relaxed scrollbar-thin scrollbar-thumb-zinc-700"
          style={{ minHeight: '52px', maxHeight: '180px' }}
        />

        {/* Input Bar Controls */}
        <div className="absolute left-3 right-3 bottom-2.5 flex items-center justify-between pointer-events-none">
          {/* Left placeholder for attachments / future tools */}
          <div className="flex items-center gap-1 pointer-events-auto">
            <button
              type="button"
              disabled
              title="Attachments coming in future phase"
              className="p-1.5 rounded-lg text-zinc-600 hover:text-zinc-500 transition-colors cursor-not-allowed opacity-50"
            >
              <Paperclip className="w-4 h-4" />
            </button>
            <span className="text-[11px] text-zinc-600 hidden sm:inline-block ml-1">
              Press <kbd className="font-mono px-1 py-0.5 rounded bg-white/[0.06] text-zinc-400 text-[10px]">Enter</kbd> to send, <kbd className="font-mono px-1 py-0.5 rounded bg-white/[0.06] text-zinc-400 text-[10px]">Shift+Enter</kbd> for newline
            </span>
          </div>

          {/* Right: Submit Button */}
          <div className="pointer-events-auto">
            <button
              type="button"
              onClick={onSubmit}
              disabled={disabled || !value.trim()}
              className={`w-8 h-8 rounded-xl flex items-center justify-center transition-all duration-150 cursor-pointer ${
                disabled || !value.trim()
                  ? 'bg-zinc-800 text-zinc-500 cursor-not-allowed'
                  : 'bg-zinc-100 hover:bg-white text-zinc-950 shadow-sm active:scale-95'
              }`}
              title="Send message"
            >
              <ArrowUp className="w-4 h-4 stroke-[2.5]" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
