import React, { createContext, useContext, useState, useEffect } from 'react';
import { runDemoWorkflow, checkBackendHealth } from '../api/client';
import { getRegisteredFeatures, getInitialFeatureStates } from '../features/registry';

const AppContext = createContext(null);

const DEFAULT_PROMPT =
  "I am building an e-commerce catalog API that must handle 2000 QPS with p95 latency under 50ms and 15% write ratio. Monthly budget is $800. What architecture should I use?";

export const CANONICAL_PRESETS = [
  {
    id: 'ecommerce',
    title: 'Scenario 1: E-commerce Catalog',
    badge: 'Read-Heavy',
    badgeColor: 'badge-emerald',
    description: '2000 QPS, 15% writes, p95 < 50ms, $800 budget. Tests read-replica and caching superiority.',
    prompt:
      "I am building an e-commerce catalog API that must handle 2000 QPS with p95 latency under 50ms and 15% write ratio. Monthly budget is $800. What architecture should I use?",
    expectedWinner: 'Architecture B (PostgreSQL + Redis Cache)',
  },
  {
    id: 'transactional',
    title: 'Scenario 2: High-Contention OLTP',
    badge: 'Write-Heavy',
    badgeColor: 'badge-amber',
    description: '400 QPS, 75% writes, p95 < 80ms, $400 budget. Cache is invalid; tests primary relational scaling.',
    prompt:
      "We are designing a high-contention financial ledger and order execution engine handling 400 QPS with 75% writes. Latency p95 must be under 80ms and budget is $400/month. Recommender must evaluate consistency trade-offs.",
    expectedWinner: 'Architecture A (Direct PostgreSQL)',
  },
  {
    id: 'analytics',
    title: 'Scenario 3: Async Analytics Pipeline',
    badge: 'Bursty Event Stream',
    badgeColor: 'badge-cyan',
    description: '3500 QPS bursts, 90% writes, $1200 budget. Synchronous DB fails; tests Kafka decoupling.',
    prompt:
      "We need an analytics event ingestion pipeline receiving 3500 QPS bursty tracking data with 90% writes. Monthly budget is $1200. Background persistence can be asynchronous. Suggest the best decoupled architecture.",
    expectedWinner: 'Architecture C (Async Event Pipeline with Kafka)',
  },
];

export function AppProvider({ children }) {
  const [prompt, setPrompt] = useState(DEFAULT_PROMPT);
  const [options, setOptions] = useState({
    auto_benchmark_missing: true,
    force_synthetic: true,
    simulation_duration_seconds: 5.0,
    random_seed: 42,
    include_async: true,
    include_unsupported: false,
    max_investigation_rounds: 3,
    investigation_budget_seconds: 60.0,
  });

  const [response, setResponse] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('workload-input');
  const [viewMode, setViewMode] = useState('flow'); // 'flow' (full dashboard) or 'tabbed' (single tab view)
  const [featureStates, setFeatureStates] = useState(getInitialFeatureStates);
  const [backendConnected, setBackendConnected] = useState(null);
  const [isFeatureManagerOpen, setIsFeatureManagerOpen] = useState(false);

  // Check backend health periodically
  useEffect(() => {
    async function checkHealth() {
      const isHealthy = await checkBackendHealth();
      setBackendConnected(isHealthy);
    }
    checkHealth();
    const interval = setInterval(checkHealth, 10000);
    return () => clearInterval(interval);
  }, []);

  const toggleFeature = (featureId) => {
    setFeatureStates((prev) => ({
      ...prev,
      [featureId]: !prev[featureId],
    }));
  };

  const setFeatureEnabled = (featureId, enabled) => {
    setFeatureStates((prev) => ({
      ...prev,
      [featureId]: enabled,
    }));
  };

  const resetFeatures = () => {
    setFeatureStates(getInitialFeatureStates());
  };

  const handleRunWorkflow = async (overridePrompt, overrideOptions) => {
    const queryPrompt = overridePrompt || prompt;
    const queryOptions = overrideOptions || options;
    setLoading(true);
    setError(null);

    try {
      const data = await runDemoWorkflow(queryPrompt, queryOptions);
      setResponse(data);
      // If in tabbed mode, automatically move to architecture comparison or recommendation
      if (viewMode === 'tabbed') {
        setActiveTab('recommendation');
      }
    } catch (err) {
      console.error('Agent execution error:', err);
      setError(err.message || 'Execution failed');
    } finally {
      setLoading(false);
    }
  };

  const loadPreset = (preset) => {
    setPrompt(preset.prompt);
  };

  return (
    <AppContext.Provider
      value={{
        prompt,
        setPrompt,
        options,
        setOptions,
        response,
        setResponse,
        loading,
        error,
        activeTab,
        setActiveTab,
        viewMode,
        setViewMode,
        featureStates,
        toggleFeature,
        setFeatureEnabled,
        resetFeatures,
        backendConnected,
        isFeatureManagerOpen,
        setIsFeatureManagerOpen,
        handleRunWorkflow,
        loadPreset,
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
}
