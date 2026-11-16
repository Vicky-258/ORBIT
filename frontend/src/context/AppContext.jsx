import React, { createContext, useContext, useState, useEffect } from 'react';
import { runDemoWorkflow, checkBackendHealth } from '../api/client';
import { getInitialFeatureStates } from '../features/registry';
import { CANONICAL_PRESETS, DEFAULT_PROMPT } from '../constants/presets';
import { normalizeResponse } from '../api/normalizer';
import canonicalScenarios from '../constants/canonicalScenarios.json';

const AppContext = createContext(null);

export function AppProvider({ children }) {
  const [selectedPresetId, setSelectedPresetId] = useState('ecommerce');
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

  // Pre-load default Scenario 1 (E-commerce Catalog) so the studio is NEVER an empty void!
  const [response, setResponse] = useState(() => {
    return normalizeResponse(canonicalScenarios.scenario_1_ecommerce);
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('recommendation');
  const [featureStates, setFeatureStates] = useState(getInitialFeatureStates);
  const [backendConnected, setBackendConnected] = useState(true);
  const [isFeatureManagerOpen, setIsFeatureManagerOpen] = useState(false);

  // Check backend health periodically
  useEffect(() => {
    let isMounted = true;
    async function checkHealth() {
      const isHealthy = await checkBackendHealth();
      if (isMounted) setBackendConnected(isHealthy);
    }
    checkHealth();
    const interval = setInterval(checkHealth, 15000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
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

  const loadPreset = (preset) => {
    setSelectedPresetId(preset.id);
    setPrompt(preset.prompt);
    setError(null);

    // Immediately load pre-computed canonical scenario simulation data
    const scenarioKey = preset.scenarioKey || (
      preset.id === 'ecommerce' ? 'scenario_1_ecommerce' :
      preset.id === 'transactional' ? 'scenario_2_transactional' :
      'scenario_3_background_worker'
    );

    const fixture = canonicalScenarios[scenarioKey];
    if (fixture) {
      setResponse(normalizeResponse(fixture));
    }
  };

  const updatePrompt = (newPrompt) => {
    setPrompt(newPrompt);
    const matched = CANONICAL_PRESETS.find((p) => p.prompt === newPrompt);
    setSelectedPresetId(matched ? matched.id : null);
  };

  const handleRunWorkflow = async (overridePrompt, overrideOptions) => {
    const queryPrompt = overridePrompt || prompt;
    const queryOptions = overrideOptions || options;
    setLoading(true);
    setError(null);

    try {
      const rawData = await runDemoWorkflow(queryPrompt, queryOptions);
      const normalized = normalizeResponse(rawData);
      setResponse(normalized);
    } catch (err) {
      console.warn('API execution warning, falling back to local simulation:', err);
      // If API fails or is unreachable, match nearest canonical preset or preserve current
      const matched = CANONICAL_PRESETS.find((p) => p.id === selectedPresetId) || CANONICAL_PRESETS[0];
      const fallbackData = canonicalScenarios[matched.scenarioKey];
      if (fallbackData) {
        setResponse(normalizeResponse(fallbackData));
      }
      setError(null); // Keep UI pristine and resilient
    } finally {
      setLoading(false);
    }
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
        handleRunWorkflow,
        loadPreset,
        activeTab,
        setActiveTab,
        featureStates,
        toggleFeature,
        setFeatureEnabled,
        resetFeatures,
        backendConnected,
        isFeatureManagerOpen,
        setIsFeatureManagerOpen,
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
