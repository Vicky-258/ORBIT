/**
 * ORBIT REST API Client
 */

const API_BASE = '/api';

export async function runDemoWorkflow(prompt, options = {}) {
  const payload = {
    prompt,
    auto_benchmark_missing: options.auto_benchmark_missing ?? true,
    force_synthetic: options.force_synthetic ?? true,
    simulation_duration_seconds: options.simulation_duration_seconds ?? 5.0,
    random_seed: options.random_seed ?? 42,
    include_async: options.include_async ?? true,
    include_unsupported: options.include_unsupported ?? false,
    max_investigation_rounds: options.max_investigation_rounds ?? 3,
    investigation_budget_seconds: options.investigation_budget_seconds ?? 60.0,
  };

  const response = await fetch(`${API_BASE}/demo/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`API error ${response.status}: ${errorText}`);
  }

  return await response.json();
}

export async function listRegistryModels() {
  const response = await fetch(`${API_BASE}/registry/models`);
  if (!response.ok) {
    throw new Error(`Failed to fetch models: ${response.status}`);
  }
  return await response.json();
}

export async function listCandidates() {
  const response = await fetch(`${API_BASE}/candidates?include_async=true&include_unsupported=false`);
  if (!response.ok) {
    throw new Error(`Failed to fetch candidates: ${response.status}`);
  }
  return await response.json();
}

export async function checkBackendHealth() {
  try {
    const response = await fetch(`${API_BASE}/health`);
    return response.ok;
  } catch (err) {
    return false;
  }
}
