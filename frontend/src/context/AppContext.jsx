import React, { createContext, useContext, useState, useEffect } from 'react';
import { runDemoWorkflow, checkBackendHealth } from '../api/client';
import { getRegisteredFeatures, getInitialFeatureStates } from '../features/registry';
import { CANONICAL_PRESETS, DEFAULT_PROMPT } from '../constants/presets';

const AppContext = createContext(null);

export function AppProvider({ children }) {
  const [prompt, setPrompt] = useState(DEFAULT_PROMPT);
  const [selectedPresetId, setSelectedPresetId] = useState('ecommerce');
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
  const [viewMode, setViewMode] = useState('tabbed'); // 'tabbed' (clean modular tab view) or 'flow' (full dashboard)
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
    setSelectedPresetId(preset.id);
    setPrompt(preset.prompt);
  };

  const updatePrompt = (newPrompt) => {
    setPrompt(newPrompt);
    const matched = CANONICAL_PRESETS.find((p) => p.prompt === newPrompt);
    setSelectedPresetId(matched ? matched.id : null);
  };

  return (
    <AppContext.Provider
      value={{
        prompt,
        setPrompt: updatePrompt,
        selectedPresetId,
        setSelectedPresetId,
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
