import React, { useRef, useEffect } from 'react';
import { ArrowUp, Paperclip } from 'lucide-react';

export default function ChatInput({
  value,
  onChange,
  onSubmit,
  disabled = false,
  placeholder = "Describe your application idea, requirements, or ask a question...",
}) {
  const textareaRef = useRef(null);

  // Auto-resize textarea height cleanly up to 160px then scroll internally
  useEffect(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = 'auto';
      const scrollH = el.scrollHeight;
      el.style.height = `${Math.min(Math.max(scrollH, 24), 160)}px`;
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

  const hasText = Boolean(value && value.trim().length > 0);

  return (
    <div className="w-full max-w-3xl mx-auto px-4 sm:px-6 pb-5 pt-2">
      <div className="flex flex-col rounded-2xl border border-white/[0.12] bg-[#141417] shadow-xl focus-within:border-zinc-500/80 focus-within:ring-1 focus-within:ring-zinc-500/30 transition-all duration-200 overflow-hidden">
        {/* Top Textarea Container: Pure text input that expands naturally */}
        <div className="px-4 pt-3.5 pb-2">
          <textarea
            ref={textareaRef}
            rows={1}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            placeholder={placeholder}
            className="w-full bg-transparent text-sm text-zinc-100 placeholder-zinc-500 resize-none outline-none overflow-y-auto leading-relaxed scrollbar-thin scrollbar-thumb-zinc-700 m-0 p-0 block"
            style={{ minHeight: '24px', maxHeight: '160px' }}
          />
        </div>

        {/* Bottom Toolbar: Completely separate row with helper hint on left and action button on right */}
        <div className="flex items-center justify-between px-3 py-2 border-t border-white/[0.04] bg-[#121215]/60 min-h-[38px]">
          {/* Left Action / Keyboard Shortcut Hint */}
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled
              title="Attachments coming in future phase"
              className="p-1 rounded-lg text-zinc-500 hover:text-zinc-400 transition-colors cursor-not-allowed opacity-60"
            >
              <Paperclip className="w-3.5 h-3.5" />
            </button>
            <span className="text-[11px] text-zinc-400 hidden sm:inline-block">
              Shift + Enter for a new line
            </span>
          </div>

          {/* Right Action: Send Button */}
          <div>
            <button
              type="button"
              onClick={onSubmit}
              disabled={disabled || !hasText}
              className={`w-7 h-7 rounded-lg flex items-center justify-center transition-all duration-150 cursor-pointer ${
                disabled || !hasText
                  ? 'bg-zinc-800 text-zinc-500 cursor-not-allowed opacity-50'
                  : 'bg-zinc-100 hover:bg-white text-zinc-950 shadow-sm active:scale-95'
              }`}
              title="Send message"
            >
              <ArrowUp className="w-3.5 h-3.5 stroke-[2.5]" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
