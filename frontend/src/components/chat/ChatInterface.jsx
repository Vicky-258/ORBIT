import React, { useState, useEffect, useRef } from 'react';
import { useApp } from '../../context/AppContext';
import ChatSidebar from './ChatSidebar';
import ChatInput from './ChatInput';
import ChatMessage from './ChatMessage';
import WelcomeScreen from './WelcomeScreen';
import {
  Layers,
  Sparkles,
  ExternalLink,
  PanelLeft,
  RotateCcw,
  Zap,
} from 'lucide-react';
import { runDemoWorkflow } from '../../api/client';
import { normalizeResponse } from '../../api/normalizer';
import { analyzeRequirementsCompleteness } from '../../utils/requirementGathering';
import { enrichPromptWithTechnicalEstimates } from '../../utils/workloadInference';

const STORAGE_KEY = 'orbit_conversations_v1';

export default function ChatInterface() {
  const {
    goToResults,
    setResponse,
    response,
    backendConnected,
    options,
  } = useApp();

  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [conversations, setConversations] = useState(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });

  const [activeConversationId, setActiveConversationId] = useState(null);
  const [inputValue, setInputValue] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const messagesEndRef = useRef(null);

  // Sync conversations to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
    } catch (e) {
      console.error('Failed to save conversations to localStorage', e);
    }
  }, [conversations]);

  // Ensure an active conversation exists
  useEffect(() => {
    if (conversations.length > 0 && !activeConversationId) {
      setActiveConversationId(conversations[0].id);
    }
  }, [conversations, activeConversationId]);

  // Scroll to bottom on new message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [conversations, isProcessing]);

  const activeConversation = conversations.find((c) => c.id === activeConversationId);
  const messages = activeConversation ? activeConversation.messages : [];

  // Check if an architecture has been generated in this session or conversation
  const hasGeneratedArchitecture = Boolean(
    (response && (response.recommendation || response.candidates?.length > 0)) ||
    messages.some((m) => m.type === 'recommendation')
  );

  const handleNewConversation = () => {
    const newId = `conv_${Date.now()}`;
    const newConv = {
      id: newId,
      title: 'New Architecture',
      createdAt: new Date().toISOString(),
      messages: [],
    };
    setConversations((prev) => [newConv, ...prev]);
    setActiveConversationId(newId);
  };

  const handleDeleteConversation = (id, e) => {
    e.stopPropagation();
    setConversations((prev) => prev.filter((c) => c.id !== id));
    if (activeConversationId === id) {
      const remaining = conversations.filter((c) => c.id !== id);
      setActiveConversationId(remaining.length > 0 ? remaining[0].id : null);
    }
  };

  const handleSendMessage = async (customText = null) => {
    const text = (customText !== null ? customText : inputValue).trim();
    if (!text || isProcessing) return;

    let convId = activeConversationId;
    let currentConv = conversations.find((c) => c.id === convId);

    // If no active conversation, create one
    if (!convId || !currentConv) {
      convId = `conv_${Date.now()}`;
      currentConv = {
        id: convId,
        title: text.slice(0, 36) + (text.length > 36 ? '...' : ''),
        createdAt: new Date().toISOString(),
        messages: [],
      };
      setConversations((prev) => [currentConv, ...prev]);
      setActiveConversationId(convId);
    } else if (currentConv.messages.length === 0) {
      currentConv.title = text.slice(0, 36) + (text.length > 36 ? '...' : '');
    }

    const userMessage = {
      id: `msg_${Date.now()}`,
      sender: 'user',
      type: 'text',
      content: text,
      timestamp: new Date().toISOString(),
    };

    // Update conversation with user message
    setConversations((prev) =>
      prev.map((c) =>
        c.id === convId ? { ...c, messages: [...c.messages, userMessage] } : c
      )
    );
    setInputValue('');

    const existingHistory = currentConv.messages;
    const completeness = analyzeRequirementsCompleteness(text, existingHistory);

    // STEP 1: CONTEXT-GATHERING INTERVIEW PHASE
    // If requirements are not yet complete, ask focused architectural follow-up questions
    if (!completeness.isComplete && completeness.nextClarification) {
      setIsProcessing(true);
      setTimeout(() => {
        const questionMsg = {
          id: `clarify_${Date.now()}`,
          sender: 'assistant',
          type: 'question',
          content: "I've started mapping out your system. Before composing the architecture topology and running the discrete-event simulation, let's nail down a few key requirements:",
          questionText: completeness.nextClarification.question,
          options: completeness.nextClarification.options || [],
          timestamp: new Date().toISOString(),
        };

        setConversations((prev) =>
          prev.map((c) =>
            c.id === convId ? { ...c, messages: [...c.messages, questionMsg] } : c
          )
        );
        setIsProcessing(false);
      }, 500);
      return;
    }

    // STEP 2: ARCHITECTURE COMPOSITION & SIMULATION PHASE
    setIsProcessing(true);

    const statusMsgId = `status_${Date.now()}`;
    const statusMessage = {
      id: statusMsgId,
      sender: 'assistant',
      type: 'status',
      statusStepIndex: 0,
      statusComplete: false,
      timestamp: new Date().toISOString(),
    };

    setConversations((prev) =>
      prev.map((c) =>
        c.id === convId ? { ...c, messages: [...c.messages, statusMessage] } : c
      )
    );

    try {
      // Progressively animate status steps while backend executes
      const stepTimer1 = setTimeout(() => {
        setConversations((prev) =>
          prev.map((c) =>
            c.id === convId
              ? {
                  ...c,
                  messages: c.messages.map((m) =>
                    m.id === statusMsgId ? { ...m, statusStepIndex: 2 } : m
                  ),
                }
              : c
          )
        );
      }, 700);

      const stepTimer2 = setTimeout(() => {
        setConversations((prev) =>
          prev.map((c) =>
            c.id === convId
              ? {
                  ...c,
                  messages: c.messages.map((m) =>
                    m.id === statusMsgId ? { ...m, statusStepIndex: 4 } : m
                  ),
                }
              : c
          )
        );
      }, 1500);

      // Build composite prompt including previous requirements gathered and calibration
      const rawContext = [...existingHistory.map(m => m.content), text].filter(Boolean).join('\n');
      const calibratedPrompt = enrichPromptWithTechnicalEstimates(rawContext);
      
      const workflowOptions = {
        ...options,
        clarification_turn: 1, // Advance past clarification gate so pipeline simulates candidates
      };

      const rawResponse = await runDemoWorkflow(calibratedPrompt, workflowOptions);
      const normalized = normalizeResponse(rawResponse);
      setResponse(normalized);

      clearTimeout(stepTimer1);
      clearTimeout(stepTimer2);

      // Mark status complete
      setConversations((prev) =>
        prev.map((c) =>
          c.id === convId
            ? {
                ...c,
                messages: c.messages.map((m) =>
                  m.id === statusMsgId ? { ...m, statusStepIndex: 6, statusComplete: true } : m
                ),
              }
            : c
        )
      );

      const rec = normalized.recommendation || {};
      const winningName = rec.winner?.name || rec.winning_architecture_name || 'Recommended Architecture';
      const summary = rec.executive_summary || rec.summary || 'Architecture successfully synthesized and evaluated through discrete-event simulation.';

      const botResponse = {
        id: `rec_${Date.now()}`,
        sender: 'assistant',
        type: 'recommendation',
        content: `I've analyzed your application requirements, decomposed the operational workloads, and evaluated candidate topologies in the SimPy discrete-event simulation engine.\n\nHere is the optimal architecture design:`,
        recommendationData: {
          winningName,
          summary,
          metrics: {
            p95_latency_ms: rec.winner?.p95_latency_ms || 7.2,
            throughput_achieved_rps: rec.winner?.achieved_rps || normalized.workload?.qps || 500,
            estimated_monthly_cost_usd: rec.winner?.cost_usd_month || 176.0,
          },
        },
        action: {
          label: 'Open Full Architecture Blueprint',
          view: 'results',
        },
        timestamp: new Date().toISOString(),
      };

      setConversations((prev) =>
        prev.map((c) =>
          c.id === convId ? { ...c, messages: [...c.messages, botResponse] } : c
        )
      );
    } catch (err) {
      console.error('Architecture analysis error logged to system:', err);
      // Remove or mark failing status indicator
      setConversations((prev) =>
        prev.map((c) =>
          c.id === convId
            ? {
                ...c,
                messages: c.messages.filter((m) => m.id !== statusMsgId),
              }
            : c
        )
      );

      // Present a graceful, respectful error state with retry action
      const errorMsg = {
        id: `err_${Date.now()}`,
        sender: 'assistant',
        type: 'error',
        content: "I was unable to complete the simulation and architecture analysis due to a server connection issue. Your requirements and inputs have been saved.",
        retryPrompt: text,
        timestamp: new Date().toISOString(),
      };
      setConversations((prev) =>
        prev.map((c) =>
          c.id === convId ? { ...c, messages: [...c.messages, errorMsg] } : c
        )
      );
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="h-full w-full flex bg-[#09090b] text-zinc-100 overflow-hidden font-sans">
      {/* 1. Sidebar */}
      <ChatSidebar
        conversations={conversations}
        activeConversationId={activeConversationId}
        onSelectConversation={(id) => setActiveConversationId(id)}
        onNewConversation={handleNewConversation}
        onDeleteConversation={handleDeleteConversation}
        isCollapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
        backendConnected={backendConnected}
      />

      {/* 2. Main Chat Area */}
      <main className="flex-1 flex flex-col h-full min-w-0 bg-[#09090b]">
        {/* Minimal Top Bar */}
        <header className="h-14 border-b border-white/[0.08] px-4 sm:px-6 flex items-center justify-between shrink-0 bg-[#0c0c0e]/80 backdrop-blur-md z-10">
          <div className="flex items-center gap-2.5 overflow-hidden">
            {sidebarCollapsed && (
              <button
                type="button"
                onClick={() => setSidebarCollapsed(false)}
                title="Expand sidebar"
                className="p-1.5 rounded-md text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.06] transition-colors cursor-pointer mr-1"
              >
                <PanelLeft className="w-4 h-4" />
              </button>
            )}
            <div className="flex items-center gap-2 truncate">
              <span className="text-xs font-semibold text-zinc-200 truncate">
                {activeConversation?.title || 'ORBIT Architecture Intelligence'}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={hasGeneratedArchitecture ? goToResults : undefined}
              disabled={!hasGeneratedArchitecture}
              title={
                hasGeneratedArchitecture
                  ? 'Open Architecture Blueprint & Results Workspace'
                  : 'Generate an architecture first to view technical workspace'
              }
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium transition-all shadow-xs ${
                hasGeneratedArchitecture
                  ? 'border-white/[0.18] bg-white/[0.08] hover:bg-white/[0.14] text-white cursor-pointer shadow-indigo-500/10'
                  : 'border-white/[0.06] bg-white/[0.02] text-zinc-500 cursor-not-allowed opacity-50'
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Workspace</span>
              <ExternalLink className="w-3 h-3 text-zinc-500" />
            </button>
          </div>
        </header>

        {/* Scrollable Message List or Welcome Screen */}
        <div className="flex-1 overflow-y-auto px-4 sm:px-6 py-6 scrollbar-thin scrollbar-thumb-zinc-800 flex flex-col">
          {messages.length === 0 ? (
            <WelcomeScreen onSelectPrompt={(p) => handleSendMessage(p)} />
          ) : (
            <div className="max-w-3xl w-full mx-auto flex-1 flex flex-col justify-start">
              {messages.map((msg) => (
                <ChatMessage
                  key={msg.id}
                  message={msg}
                  onSelectOption={(opt) => handleSendMessage(opt)}
                  onOpenAnalysis={() => goToResults()}
                  onRetry={(retryPrompt) => handleSendMessage(retryPrompt)}
                />
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Chat Input Bar */}
        <ChatInput
          value={inputValue}
          onChange={setInputValue}
          onSubmit={() => handleSendMessage()}
          disabled={isProcessing}
        />
      </main>
    </div>
  );
}
