import React from 'react';
import {
  SlidersHorizontal,
  Bot,
  Layers,
  Award,
  ShieldCheck,
  Database,
  Code2,
  TrendingUp,
} from 'lucide-react';

// Feature components
import WorkloadInput from './WorkloadInput';
import InvestigationTrace from './InvestigationTrace';
import ArchitectureComparison from './ArchitectureComparison';
import RecommendationView from './RecommendationView';
import EvidenceDisclosure from './EvidenceDisclosure';
import ModelRegistryBrowser from './ModelRegistryBrowser';
import CostSensitivityAnalyzer from './CostSensitivityAnalyzer';

/**
 * Dynamic Feature Registry
 * 
 * To ADD a new feature:
 * 1. Create a component in `src/features/YourFeature/index.jsx`
 * 2. Add an entry to the `FEATURE_DEFINITIONS` list below (or call `registerFeature(...)`)
 * That's it! It automatically appears in the UI, navigation, and Feature Manager.
 * 
 * To REMOVE a feature:
 * - Either toggle it off in the Feature Manager UI at runtime, or set `defaultEnabled: false`,
 *   or remove its definition entry.
 */

const FEATURE_DEFINITIONS = [
  {
    id: 'workload-input',
    title: 'Workload & Presets',
    badge: 'Section A',
    category: 'Input & Specifications',
    icon: SlidersHorizontal,
    description: 'Natural language input, 1-click canonical scenario presets, and fine-tuning constraint controls.',
    order: 10,
    defaultEnabled: true,
    required: true,
    component: WorkloadInput,
  },
  {
    id: 'investigation-trace',
    title: 'Agent Investigation',
    badge: 'Section B',
    category: 'Agent Orchestration',
    icon: Bot,
    description: 'Real-time trace of bounded agent actions, rounds, elapsed time, and deterministic policy gatekeeper guardrails.',
    order: 20,
    defaultEnabled: true,
    required: false,
    component: InvestigationTrace,
  },
  {
    id: 'architecture-comparison',
    title: 'Candidate Simulation',
    badge: 'Section C',
    category: 'SimPy & Metrics',
    icon: Layers,
    description: 'Side-by-side architecture comparison matrix with latency, throughput, cost, and SLA pass/fail validation.',
    order: 30,
    defaultEnabled: true,
    required: false,
    component: ArchitectureComparison,
  },
  {
    id: 'recommendation',
    title: 'Recommendation & Trade-Offs',
    badge: 'Section D',
    category: 'Decision Engine',
    icon: Award,
    description: 'Winning architecture rationale, rejected alternatives breakdown, and explicit boundary conditions for change.',
    order: 40,
    defaultEnabled: true,
    required: false,
    component: RecommendationView,
  },
  {
    id: 'evidence-disclosure',
    title: 'Evidence & Epistemics',
    badge: 'Section E',
    category: 'Integrity & Audit',
    icon: ShieldCheck,
    description: 'Epistemic breakdown: empirically measured vs model-derived vs SimPy-derived vs agent-assumed parameters.',
    order: 50,
    defaultEnabled: true,
    required: false,
    component: EvidenceDisclosure,
  },
  {
    id: 'model-registry',
    title: 'Empirical Model Registry',
    badge: 'Registry Extension',
    category: 'Extensions & Tools',
    icon: Database,
    description: 'Browse the 24 active empirical component performance models, supported operating bounds, and experiment history.',
    order: 60,
    defaultEnabled: true,
    required: false,
    component: ModelRegistryBrowser,
  },
  {
    id: 'cost-sensitivity',
    title: 'Cost & Scale Sensitivity',
    badge: 'Plugin Extension',
    category: 'Extensions & Tools',
    icon: TrendingUp,
    description: 'Explore cloud infrastructure cost and latency projections under 0.5x to 5.0x traffic growth.',
    order: 70,
    defaultEnabled: true,
    required: false,
    component: CostSensitivityAnalyzer,
  },
];

// Runtime registry storage
let registryList = [...FEATURE_DEFINITIONS];

/**
 * Register a new custom feature/plugin at runtime or compile time.
 */
export function registerFeature(featureDef) {
  if (!featureDef.id || !featureDef.title || !featureDef.component) {
    throw new Error('Feature definition must include id, title, and component.');
  }
  const existingIndex = registryList.findIndex((f) => f.id === featureDef.id);
  if (existingIndex >= 0) {
    registryList[existingIndex] = { ...registryList[existingIndex], ...featureDef };
  } else {
    registryList.push({
      order: 100,
      defaultEnabled: true,
      required: false,
      icon: Code2,
      category: 'Custom Plugins',
      ...featureDef,
    });
  }
  registryList.sort((a, b) => (a.order || 0) - (b.order || 0));
}

/**
 * Unregister / remove a feature by ID.
 */
export function unregisterFeature(featureId) {
  registryList = registryList.filter((f) => f.id !== featureId);
}

/**
 * Get all registered features sorted by order.
 */
export function getRegisteredFeatures() {
  return [...registryList].sort((a, b) => (a.order || 0) - (b.order || 0));
}

/**
 * Get map of initial feature states (featureId -> boolean).
 */
export function getInitialFeatureStates() {
  const states = {};
  registryList.forEach((feature) => {
    states[feature.id] = feature.defaultEnabled;
  });
  return states;
}
