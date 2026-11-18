import React from 'react';
import {
  MessageSquare,
  Plus,
  PanelLeftClose,
  PanelLeft,
  Clock,
  Sparkles,
  Settings,
  Layers,
  ChevronRight,
  Trash2
} from 'lucide-react';

export default function ChatSidebar({
  conversations = [],
  activeConversationId,
  onSelectConversation,
  onNewConversation,
  onDeleteConversation,
  isCollapsed,
  onToggleCollapse,
  backendConnected = true,
}) {
  return (
    <aside
      className={`h-full border-r border-white/[0.08] bg-[#0c0c0e] flex flex-col transition-all duration-300 ease-in-out shrink-0 select-none z-30 ${
        isCollapsed ? 'w-16' : 'w-72'
      }`}
    >
      {/* 1. Header & Brand */}
      <div className="h-14 border-b border-white/[0.08] flex items-center justify-between px-3.5">
        {!isCollapsed ? (
          <div className="flex items-center gap-2.5 overflow-hidden">
            <div className="w-8 h-8 rounded-lg bg-zinc-100 flex items-center justify-center text-zinc-950 shrink-0 shadow-sm">
              <Layers className="w-4 h-4 stroke-[2.5]" />
            </div>
            <div className="flex flex-col">
              <div className="flex items-center gap-1.5">
                <span className="font-semibold text-sm tracking-tight text-white">ORBIT</span>
                <span className="text-[10px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded bg-white/[0.08] text-zinc-400">
                  AI
                </span>
              </div>
              <span className="text-[11px] text-zinc-500 truncate">Architecture Intelligence</span>
            </div>
          </div>
        ) : (
          <div className="w-full flex justify-center">
            <div className="w-8 h-8 rounded-lg bg-zinc-100 flex items-center justify-center text-zinc-950 shadow-sm">
              <Layers className="w-4 h-4 stroke-[2.5]" />
            </div>
          </div>
        )}

        <button
          type="button"
          onClick={onToggleCollapse}
          title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          className={`p-1.5 rounded-md text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.06] transition-colors cursor-pointer ${
            isCollapsed ? 'hidden' : 'block'
          }`}
        >
          <PanelLeftClose className="w-4 h-4" />
        </button>
      </div>

      {/* 2. New Chat Action Button */}
      <div className="p-3">
        <button
          type="button"
          onClick={onNewConversation}
          className={`w-full flex items-center gap-2 rounded-lg border border-white/[0.1] bg-white/[0.04] hover:bg-white/[0.08] hover:border-white/[0.16] text-zinc-200 text-xs font-medium transition-all duration-150 cursor-pointer shadow-xs ${
            isCollapsed ? 'justify-center p-2.5' : 'px-3 py-2.5'
          }`}
          title="Start new conversation"
        >
          <Plus className="w-4 h-4 text-zinc-400 shrink-0" />
          {!isCollapsed && <span>New Architecture</span>}
        </button>
      </div>

      {/* 3. Conversation List */}
      <div className="flex-1 overflow-y-auto px-2 py-1 space-y-1 scrollbar-thin scrollbar-thumb-zinc-800">
        {!isCollapsed && (
          <div className="px-2 pt-2 pb-1 text-[10px] font-medium tracking-wider uppercase text-zinc-500">
            Recent Conversations
          </div>
        )}

        {conversations.length === 0 ? (
          !isCollapsed && (
            <div className="px-3 py-6 text-center text-xs text-zinc-500 italic">
              No recent conversations
            </div>
          )
        ) : (
          conversations.map((conv) => {
            const isActive = conv.id === activeConversationId;
            return (
              <div
                key={conv.id}
                onClick={() => onSelectConversation(conv.id)}
                className={`group relative flex items-center gap-2.5 rounded-lg text-xs cursor-pointer transition-colors ${
                  isCollapsed ? 'justify-center p-2.5' : 'px-3 py-2.5'
                } ${
                  isActive
                    ? 'bg-white/[0.1] text-white font-medium border border-white/[0.1]'
                    : 'text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.04]'
                }`}
                title={conv.title}
              >
                <MessageSquare className={`w-3.5 h-3.5 shrink-0 ${isActive ? 'text-zinc-200' : 'text-zinc-500'}`} />
                {!isCollapsed && (
                  <>
                    <span className="truncate flex-1 text-left">{conv.title || 'Untitled Discussion'}</span>
                    {onDeleteConversation && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          onDeleteConversation(conv.id);
                        }}
                        className="opacity-0 group-hover:opacity-100 p-1 text-zinc-500 hover:text-rose-400 transition-opacity"
                        title="Delete conversation"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* 4. Footer & Health Indicator */}
      <div className="p-3 border-t border-white/[0.08] flex items-center justify-between">
        {!isCollapsed ? (
          <div className="flex items-center gap-2 text-[11px] text-zinc-500">
            <span
              className={`w-2 h-2 rounded-full shrink-0 ${
                backendConnected ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]' : 'bg-amber-500'
              }`}
            />
            <span className="truncate">{backendConnected ? 'Simulation engine active' : 'Simulation engine ready'}</span>
          </div>
        ) : (
          <div className="w-full flex justify-center">
            <span
              className={`w-2 h-2 rounded-full ${
                backendConnected ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]' : 'bg-emerald-500/70'
              }`}
              title={backendConnected ? 'Simulation engine active' : 'Simulation engine ready'}
            />
          </div>
        )}

        {isCollapsed && (
          <button
            type="button"
            onClick={onToggleCollapse}
            title="Expand sidebar"
            className="p-1 rounded text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.06] cursor-pointer mt-2"
          >
            <PanelLeft className="w-4 h-4" />
          </button>
        )}
      </div>
    </aside>
  );
}
