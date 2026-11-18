import React, { createContext, useContext, useState, useEffect, useMemo, useCallback } from 'react';
import { runDemoWorkflow, checkBackendHealth } from '../api/client';
import { getInitialFeatureStates } from '../features/registry';
import { CANONICAL_PRESETS, DEFAULT_PROMPT } from '../constants/presets';
import { normalizeResponse } from '../api/normalizer';
import canonicalScenarios from '../constants/canonicalScenarios.json';

const AppContext = createContext(null);

export function AppProvider({ children }) {
  const [selectedPresetId, setSelectedPresetId] = useState('ecommerce');
  const [prompt, setPrompt] = useState(DEFAULT_PROMPT);

  // Editable workload parameters
  const [workloadInputs, setWorkloadInputs] = useState({
    qps: 500,
    p95_sla_ms: 100,
    read_ratio: 0.90,
    write_ratio: 0.10,
    budget_usd: 250,
  });

  // Track the exact workload parameters that produced the current response
  const [lastSimulatedWorkload, setLastSimulatedWorkload] = useState({
    prompt: DEFAULT_PROMPT,
    qps: 500,
    p95_sla_ms: 100,
    read_ratio: 0.90,
    write_ratio: 0.10,
    budget_usd: 250,
  });

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

  // Pre-load default Scenario 1 (E-commerce Catalog)
  const [response, setResponse] = useState(() => {
    return normalizeResponse(canonicalScenarios.scenario_1_ecommerce);
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [viewMode, setViewMode] = useState('chat'); // 'chat' | 'prompt' | 'results'
  const [activeTab, setActiveTab] = useState('blueprint'); // 'blueprint' | 'compare' | 'technical'
  const [backendConnected, setBackendConnected] = useState(true);

  const goToChat = useCallback(() => setViewMode('chat'), []);
  const goToPrompt = useCallback(() => setViewMode('prompt'), []);
  const goToResults = useCallback(() => setViewMode('results'), []);

  // Modal / Drawer open states
  const [isWorkloadDrawerOpen, setIsWorkloadDrawerOpen] = useState(false);
  const [isPromptModalOpen, setIsPromptModalOpen] = useState(false);
  const [isFeatureManagerOpen, setIsFeatureManagerOpen] = useState(false);
  const [featureStates, setFeatureStates] = useState(getInitialFeatureStates);

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

  // Determine if the current inputs have diverged from the last simulated result (Stale Detection)
  const isStale = useMemo(() => {
    if (!lastSimulatedWorkload) return false;
    return (
      prompt !== lastSimulatedWorkload.prompt ||
      workloadInputs.qps !== lastSimulatedWorkload.qps ||
      workloadInputs.p95_sla_ms !== lastSimulatedWorkload.p95_sla_ms ||
      workloadInputs.read_ratio !== lastSimulatedWorkload.read_ratio ||
      workloadInputs.budget_usd !== lastSimulatedWorkload.budget_usd
    );
  }, [prompt, workloadInputs, lastSimulatedWorkload]);

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

  // 1-Click Preset Loader
  const loadPreset = useCallback((preset) => {
    setSelectedPresetId(preset.id);
    setPrompt(preset.prompt);
    setError(null);

    // Extract default numbers from preset
    const qpsNum = preset.id === 'ecommerce' ? 500 : preset.id === 'transactional' ? 150 : 300;
    const slaNum = preset.id === 'transactional' ? 150 : 100;
    const readNum = preset.id === 'ecommerce' ? 0.90 : preset.id === 'transactional' ? 0.40 : 0.10;
    const writeNum = 1 - readNum;
    const budgetNum = preset.id === 'ecommerce' ? 250 : preset.id === 'transactional' ? 300 : 350;

    const newInputs = {
      qps: qpsNum,
      p95_sla_ms: slaNum,
      read_ratio: readNum,
      write_ratio: writeNum,
      budget_usd: budgetNum,
    };

    setWorkloadInputs(newInputs);

    // Load pre-computed canonical scenario simulation data
    const scenarioKey = preset.scenarioKey || (
      preset.id === 'ecommerce' ? 'scenario_1_ecommerce' :
      preset.id === 'transactional' ? 'scenario_2_transactional' :
      'scenario_3_background_worker'
    );

    const fixture = canonicalScenarios[scenarioKey];
    if (fixture) {
      const normalized = normalizeResponse(fixture);
      setResponse(normalized);
      setLastSimulatedWorkload({
        prompt: preset.prompt,
        ...newInputs,
      });
    }
  }, []);

  const updateWorkloadField = (field, value) => {
    setWorkloadInputs((prev) => {
      const updated = { ...prev, [field]: value };
      if (field === 'read_ratio') {
        updated.write_ratio = parseFloat((1 - value).toFixed(2));
      } else if (field === 'write_ratio') {
        updated.read_ratio = parseFloat((1 - value).toFixed(2));
      }
      return updated;
    });
  };

  const handleRunWorkflow = async (overridePrompt, overrideOptions) => {
    const queryPrompt = overridePrompt || prompt;
    const queryOptions = overrideOptions || options;
    setLoading(true);
    setError(null);
    setViewMode('results');

    try {
      const rawData = await runDemoWorkflow(queryPrompt, queryOptions);
      const normalized = normalizeResponse(rawData);
      setResponse(normalized);
      setLastSimulatedWorkload({
        prompt: queryPrompt,
        ...workloadInputs,
      });
      setIsWorkloadDrawerOpen(false);
    } catch (err) {
      console.error('Simulation execution failed:', err);
      setError(err.message || 'Simulation execution failed. Please verify API status and retry.');
    } finally {
      setLoading(false);
    }
  };

  const resetToDefault = () => {
    loadPreset(CANONICAL_PRESETS[0]);
    setActiveTab('blueprint');
    setError(null);
  };

  return (
    <AppContext.Provider
      value={{
        prompt,
        setPrompt,
        workloadInputs,
        setWorkloadInputs,
        updateWorkloadField,
        lastSimulatedWorkload,
        isStale,
        selectedPresetId,
        setSelectedPresetId,
        options,
        setOptions,
        response,
        setResponse,
        loading,
        error,
        setError,
        handleRunWorkflow,
        loadPreset,
        resetToDefault,
        viewMode,
        setViewMode,
        goToChat,
        goToPrompt,
        goToResults,
        activeTab,
        setActiveTab,
        isWorkloadDrawerOpen,
        setIsWorkloadDrawerOpen,
        isPromptModalOpen,
        setIsPromptModalOpen,
        isFeatureManagerOpen,
        setIsFeatureManagerOpen,
        featureStates,
        toggleFeature,
        setFeatureEnabled,
        resetFeatures,
        backendConnected,
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
