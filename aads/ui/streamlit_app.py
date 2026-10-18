"""
Streamlit Web UI for Agentic Architecture Design & Simulation (AADS).
Provides an end-to-end interactive workflow for workload specification,
architecture generation, model discovery, benchmarking, SimPy simulation,
and explainable recommendations.
"""
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from aads.core.schemas import (
    WorkloadSpec,
    ArchitectureGraph,
    SimulationResult,
    RecommendationResult,
    FeasibilityStatus,
    InformationProvenance,
)
from aads.generator.candidate_generator import ArchitectureGenerator
from aads.registry.component_registry import ComponentRegistry
from aads.benchmark.docker_runner import DockerBenchmarkRunner
from aads.benchmark.synthetic_runner import SyntheticBenchmarkRunner
from aads.benchmark.experiment_manager import AdaptiveExperimentManager
from aads.modeling.model_trainer import ModelTrainer
from aads.simulation.simpy_engine import SimPyEngine
from aads.evaluation.recommender import ArchitectureRecommender

st.set_page_config(
    page_title="AADS — Agentic Architecture Design & Simulation",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for rich aesthetics and clean typography
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(90deg, #3b82f6, #8b5cf6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        color: #94a3b8;
        font-size: 1.05rem;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #1e293b;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
    }
    .badge-feasible {
        background-color: #065f46;
        color: #34d399;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-uncertain {
        background-color: #78350f;
        color: #fbbf24;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-infeasible {
        background-color: #7f1d1d;
        color: #f87171;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-fixture {
        background-color: #312e81;
        color: #c7d2fe;
        padding: 4px 8px;
        border-radius: 6px;
        font-size: 0.8rem;
    }
</style>
""", unsafe_allow_html=True)


# Initialize Session State
@st.cache_resource
def get_services():
    reg = ComponentRegistry()
    reg.seed_baseline_data()
    gen = ArchitectureGenerator()
    sim = SimPyEngine(reg)
    doc_run = DockerBenchmarkRunner()
    syn_run = SyntheticBenchmarkRunner()
    exp_mgr = AdaptiveExperimentManager(reg, doc_run, syn_run)
    return reg, gen, sim, doc_run, syn_run, exp_mgr

registry, generator, sim_engine, docker_runner, synthetic_runner, exp_manager = get_services()

if "workload" not in st.session_state:
    st.session_state.workload = WorkloadSpec()

if "sim_results" not in st.session_state:
    st.session_state.sim_results = None

if "recommendation" not in st.session_state:
    st.session_state.recommendation = None


# Header
st.markdown('<div class="main-header">⚡ AADS: Agentic Architecture Design & Simulation</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Empirical benchmarking, discrete-event SimPy simulation, and explainable multi-objective architectural recommendations.</div>', unsafe_allow_html=True)

# Sidebar: Quick Workload Config
with st.sidebar:
    st.header("⚙️ Workload Configuration")
    req_rps = st.slider("Target Request Rate (RPS)", min_value=50.0, max_value=2000.0, value=float(st.session_state.workload.request_rate_rps), step=50.0)
    p95_target = st.slider("p95 Latency SLA Cap (ms)", min_value=5.0, max_value=200.0, value=float(st.session_state.workload.p95_latency_target_ms), step=5.0)
    max_budget = st.slider("Max Monthly Budget ($)", min_value=50.0, max_value=600.0, value=float(st.session_state.workload.max_monthly_budget_usd), step=25.0)
    
    st.markdown("---")
    st.subheader("Traffic Mix & Cache")
    read_ratio = st.slider("Read Ratio", min_value=0.50, max_value=0.99, value=float(st.session_state.workload.read_ratio), step=0.05)
    cache_hit = st.slider("Expected Cache Hit Rate", min_value=0.50, max_value=0.98, value=float(st.session_state.workload.cache_assumed_hit_rate), step=0.05)
    
    st.markdown("---")
    st.subheader("Objective Preferences")
    cost_weight = st.slider("Cost Weight", 0.0, 1.0, float(st.session_state.workload.soft_preferences.get("cost", 0.35)), 0.05)
    lat_weight = st.slider("Latency Weight", 0.0, 1.0, float(st.session_state.workload.soft_preferences.get("latency", 0.45)), 0.05)
    simp_weight = st.slider("Simplicity Weight", 0.0, 1.0, float(st.session_state.workload.soft_preferences.get("simplicity", 0.20)), 0.05)

    # Update session workload
    st.session_state.workload = WorkloadSpec(
        request_rate_rps=req_rps,
        p95_latency_target_ms=p95_target,
        max_monthly_budget_usd=max_budget,
        read_ratio=read_ratio,
        write_ratio=round(1.0 - read_ratio, 2),
        cache_assumed_hit_rate=cache_hit,
        soft_preferences={"cost": cost_weight, "latency": lat_weight, "simplicity": simp_weight},
    )

# Tabs
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "1. Requirements & Assumptions",
    "2. Candidate Architectures",
    "3. Registry & Model Discovery",
    "4. Benchmark Runner",
    "5. SimPy Simulation",
    "6. Recommendation & Trade-offs",
])

# ----------------- TAB 1: Requirements & Assumptions -----------------
with tab1:
    st.subheader("Application Requirements & Provenance Tracking")
    st.markdown("""
    AADS strictly distinguishes three categories of information:
    1. **User-Provided Facts**: Explicit SLA targets and domain specifications.
    2. **Agent Assumptions**: Suggested defaults labeled for transparency and full editability.
    3. **Empirical Measurements**: Derived from controlled benchmarks.
    """)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### 👤 User-Provided Facts")
        facts_data = [
            {"Parameter": "Application Type", "Value": st.session_state.workload.app_type, "Role": "Domain specification"},
            {"Parameter": "Offered Load", "Value": f"{st.session_state.workload.request_rate_rps} RPS", "Role": "Target throughput"},
            {"Parameter": "p95 Latency SLA", "Value": f"<= {st.session_state.workload.p95_latency_target_ms} ms", "Role": "Hard constraint"},
            {"Parameter": "Max Budget", "Value": f"${st.session_state.workload.max_monthly_budget_usd}/month", "Role": "Hard spending cap"},
            {"Parameter": "Read/Write Ratio", "Value": f"{st.session_state.workload.read_ratio:.0%} Read / {st.session_state.workload.write_ratio:.0%} Write", "Role": "Workload distribution"},
        ]
        st.table(pd.DataFrame(facts_data))

    with col2:
        st.markdown("#### 🤖 Agent Assumptions (Editable)")
        assump_data = [
            {"Assumption": "Cache Hit Rate", "Value": f"{st.session_state.workload.cache_assumed_hit_rate:.0%}", "Justification": "Standard working set for social media timeline feed (80-90%)"},
            {"Assumption": "Peak Burst Factor", "Value": f"{st.session_state.workload.peak_load_factor}x", "Justification": "Accounts for sudden diurnal traffic surges"},
            {"Assumption": "Data Growth Rate", "Value": f"{st.session_state.workload.dataset_growth_monthly_pct}%/mo", "Justification": "Estimated post creation and media metadata volume"},
            {"Assumption": "Infrastructure Pricing", "Value": "Standard Cloud", "Justification": "$24/vCPU, $4/GB RAM, $25 base DB instance per month"},
        ]
        st.table(pd.DataFrame(assump_data))

# ----------------- TAB 2: Candidate Architectures -----------------
with tab2:
    st.subheader("Generated Candidate Architectures")
    include_async = st.checkbox("Include Architecture C (Async Processing)", value=True)
    include_unsupported = st.checkbox("Include Intentionally Unsupported MongoDB Candidate (Demonstrates Model Discovery)", value=True)
    
    candidates = generator.generate_candidates(include_async=include_async, include_unsupported=include_unsupported)

    cols = st.columns(len(candidates))
    for idx, (col, cand) in enumerate(zip(cols, candidates)):
        with col:
            st.markdown(f"### {cand.name}")
            st.markdown(f"*{cand.description}*")
            st.markdown(f"**Estimated Cost:** `${cand.total_monthly_cost_usd:.2f} / month`")
            st.markdown(f"**Required Models:** `{', '.join(cand.required_models)}`")
            
            st.markdown("**Components & Resources:**")
            comp_rows = []
            for c_id, comp in cand.components.items():
                comp_rows.append({
                    "Node": comp.name,
                    "Type": comp.component_type.value,
                    "vCPU": comp.cpu_cores,
                    "RAM": f"{comp.memory_mb} MB",
                    "Pool": comp.concurrency_limit,
                    "Cost": f"${comp.monthly_cost_usd}",
                })
            st.dataframe(pd.DataFrame(comp_rows), use_container_width=True, hide_index=True)

            st.markdown("**Request Flow:**")
            st.code(f"Read:  {' ➔ '.join(cand.read_path)}\nWrite: {' ➔ '.join(cand.write_path)}", language="text")

# ----------------- TAB 3: Registry & Model Discovery -----------------
with tab3:
    st.subheader("Component & Performance Model Registry")
    st.markdown("Verifies whether compatible, calibrated performance models exist for all components before simulation.")

    models = registry.list_models()
    model_rows = []
    for m in models:
        model_rows.append({
            "Component": m.component_name,
            "Version": m.version,
            "Model Type": m.model_type,
            "R² Score": m.r2_score,
            "RMSE (ms)": m.validation_rmse_ms,
            "MAPE (%)": f"{m.validation_mape_pct}%",
            "Supported RPS": f"[{m.min_supported_rps:.0f}, {m.max_supported_rps:.0f}]",
            "Validated": "✅ YES" if m.is_validated else "❌ NO",
            "Fixture": "⚠️ Synthetic" if m.is_synthetic_fixture else "🖥️ Docker Real",
        })
    st.dataframe(pd.DataFrame(model_rows), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("🔍 Model Discovery & Compatibility Check")
    test_comp = st.selectbox(
        "Select Component to inspect:",
        ["postgres_db:postgres:16-alpine", "redis_cache:redis:7.2-alpine", "mongodb_cluster:mongodb:7.0-cluster"],
    )
    c_name, c_ver = test_comp.split(":")
    status, model_rec, warnings = registry.check_compatibility(c_name, c_ver, st.session_state.workload)

    if status == "VALIDATED":
        st.success(f"✅ **{c_name}:{c_ver}** is VALIDATED and covers the current workload ({st.session_state.workload.request_rate_rps} RPS).")
    elif status == "MISSING":
        st.error(f"❌ **{c_name}:{c_ver}** is MISSING. No calibrated model exists in the registry!")
        st.markdown("The agent detects missing performance models and can automatically trigger a controlled benchmark campaign.")
        if st.button("🚀 Trigger Missing-Model Benchmark & Calibration", key="btn_discover"):
            with st.spinner("Executing controlled benchmark matrix and fitting performance model..."):
                campaign = exp_manager.run_campaign(
                    component_name=c_name,
                    version=c_ver,
                    workload=st.session_state.workload,
                    budget_runs=6,
                    force_synthetic=True,
                )
                new_model, metrics = ModelTrainer.train_and_validate(c_name, c_ver, campaign["experiments"])
                if new_model.is_validated:
                    registry.register_model(new_model)
                    st.success(f"🎉 Successfully calibrated and registered model `{new_model.model_id}` with R² = {new_model.r2_score} and RMSE = {new_model.validation_rmse_ms}ms!")
                    st.rerun()

# ----------------- TAB 4: Benchmark Runner -----------------
with tab4:
    st.subheader("Controlled Benchmark Runner")
    st.markdown("""
    AADS can run real benchmarks against live Docker containers (`pgbench` / `redis-benchmark`) with hard resource limits,
    or use clearly labeled deterministic synthetic fixtures for rapid offline demonstration.
    """)

    b_col1, b_col2 = st.columns(2)
    with b_col1:
        bench_mode = st.radio("Benchmark Execution Mode:", ["Synthetic Calibrated Fixture (Fast)", "Real Docker Container (Isolated --cpus 1.0 --memory 512m)"])
    with b_col2:
        bench_comp = st.selectbox("Benchmark Target:", ["postgres_db", "redis_cache"])

    use_docker = "Docker" in bench_mode

    if st.button("⚡ Run Controlled Benchmark Matrix", key="btn_run_bench"):
        with st.spinner(f"Running benchmark trials for {bench_comp}..."):
            runner = docker_runner if use_docker else synthetic_runner
            try:
                exps = runner.run_benchmark_matrix(
                    component_name=bench_comp,
                    version="postgres:16-alpine" if "postgres" in bench_comp else "redis:7.2-alpine",
                    concurrency_levels=[1, 4, 8, 16],
                    replications=3,
                )
                for e in exps:
                    registry.save_experiment(e)

                st.success(f"Completed {len(exps)} benchmark configurations (3 replications each)!")
                
                exp_table = []
                for e in exps:
                    exp_table.append({
                        "Concurrency": e.concurrency,
                        "Offered RPS": e.offered_rps,
                        "Achieved RPS": e.achieved_rps,
                        "p50 (ms)": e.p50_ms,
                        "p95 (ms)": e.p95_ms,
                        "p99 (ms)": e.p99_ms,
                        "CPU %": f"{e.cpu_pct}%",
                        "RAM (MB)": e.memory_mb,
                        "Variance (ms²)": e.variance_ms2,
                        "Synthetic": "YES" if e.is_synthetic_fixture else "NO (Real Docker)",
                    })
                st.dataframe(pd.DataFrame(exp_table), use_container_width=True, hide_index=True)

            except Exception as exc:
                st.error(f"Benchmark error: {exc}")

    st.markdown("#### Recent Benchmark Experiment History")
    all_exps = registry.list_all_experiments()[:10]
    if all_exps:
        history_rows = [{
            "Experiment ID": e.experiment_id,
            "Component": f"{e.component_name}:{e.version}",
            "Framework": e.benchmark_framework,
            "Concurrency": e.concurrency,
            "Achieved RPS": e.achieved_rps,
            "p95 (ms)": e.p95_ms,
            "Variance (ms²)": e.variance_ms2,
            "Mode": "⚠️ Synthetic" if e.is_synthetic_fixture else "🖥️ Docker Real",
        } for e in all_exps]
        st.dataframe(pd.DataFrame(history_rows), use_container_width=True, hide_index=True)
    else:
        st.info("No benchmark records stored yet.")

# ----------------- TAB 5: SimPy Simulation -----------------
with tab5:
    st.subheader("Discrete-Event Simulation (SimPy)")
    st.markdown("""
    Models synthetic requests arriving as a Poisson process, simulating queuing delays,
    resource concurrency contention, cache hits/misses, and asynchronous write pipelines.
    """)

    sim_duration = st.slider("Simulation Duration (simulated seconds)", 3.0, 30.0, 8.0, 1.0)
    sim_seed = st.number_input("Random Seed", value=42, step=1)

    if st.button("▶️ Run Multi-Architecture Simulation", key="btn_sim", type="primary"):
        with st.spinner("Simulating individual requests through SimPy event loops..."):
            candidates_to_sim = generator.generate_candidates(include_async=True, include_unsupported=False)
            results = [
                sim_engine.simulate_architecture(
                    architecture=c,
                    workload=st.session_state.workload,
                    duration_seconds=sim_duration,
                    random_seed=int(sim_seed),
                )
                for c in candidates_to_sim
            ]
            st.session_state.sim_results = results

            # Compute recommendation immediately
            st.session_state.recommendation = ArchitectureRecommender.evaluate_and_recommend(
                workload=st.session_state.workload,
                sim_results=results,
            )

    if st.session_state.sim_results:
        st.markdown("### 📊 Simulation Results Summary")
        results = st.session_state.sim_results

        res_cols = st.columns(len(results))
        for col, r in zip(res_cols, results):
            with col:
                st.markdown(f"#### {r.architecture_name.split('—')[0]}")
                st.metric("Throughput Achieved", f"{r.throughput_achieved_rps:.1f} RPS")
                st.metric("p95 Latency", f"{r.p95_latency_ms:.2f} ms")
                st.metric("p50 / p99 Latency", f"{r.p50_latency_ms:.2f} / {r.p99_latency_ms:.2f} ms")
                st.metric("Bottleneck Resource", f"{r.bottleneck_component.upper()}")
                if r.cache_hit_rate is not None:
                    st.metric("Cache Hit Rate", f"{r.cache_hit_rate:.1%}")
                st.metric("Monthly Cost", f"${r.estimated_monthly_cost_usd:.2f}/mo")

        st.markdown("---")
        # Visualizations
        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            st.markdown("#### Latency Percentiles Comparison")
            arch_names = [r.architecture_name.split('—')[0].strip() for r in results]
            p50s = [r.p50_latency_ms for r in results]
            p95s = [r.p95_latency_ms for r in results]
            p99s = [r.p99_latency_ms for r in results]

            fig, ax = plt.subplots(figsize=(6, 3.8))
            x = np.arange(len(arch_names))
            width = 0.25

            ax.bar(x - width, p50s, width, label='p50', color='#3b82f6')
            ax.bar(x, p95s, width, label='p95', color='#f59e0b')
            ax.bar(x + width, p99s, width, label='p99', color='#ef4444')
            ax.axhline(st.session_state.workload.p95_latency_target_ms, color='red', linestyle='--', label=f'p95 SLA ({st.session_state.workload.p95_latency_target_ms}ms)')
            ax.set_xticks(x)
            ax.set_xticklabels(arch_names)
            ax.set_ylabel("Latency (ms)")
            ax.legend()
            ax.grid(axis='y', alpha=0.3)
            st.pyplot(fig)

        with chart_col2:
            st.markdown("#### Monthly Cost vs p95 Latency Trade-off")
            fig2, ax2 = plt.subplots(figsize=(6, 3.8))
            costs = [r.estimated_monthly_cost_usd for r in results]
            colors = ['#3b82f6', '#10b981', '#8b5cf6']

            for i, r in enumerate(results):
                name = r.architecture_name.split('—')[0].strip()
                ax2.scatter(r.estimated_monthly_cost_usd, r.p95_latency_ms, s=180, color=colors[i % len(colors)], label=name, zorder=5)
                ax2.annotate(name, (r.estimated_monthly_cost_usd + 2, r.p95_latency_ms + 0.1))

            ax2.axhline(st.session_state.workload.p95_latency_target_ms, color='red', linestyle='--', alpha=0.7, label='p95 Cap')
            ax2.axvline(st.session_state.workload.max_monthly_budget_usd, color='gray', linestyle=':', alpha=0.7, label='Budget Cap')
            ax2.set_xlabel("Monthly Cost ($ USD)")
            ax2.set_ylabel("p95 Latency (ms)")
            ax2.grid(True, alpha=0.3)
            ax2.legend()
            st.pyplot(fig2)

# ----------------- TAB 6: Recommendation & Trade-offs -----------------
with tab6:
    st.subheader("Architectural Recommendation & Trade-off Analysis")

    if not st.session_state.recommendation:
        st.info("Run the simulation in Tab 5 to generate the architecture recommendation.")
    else:
        rec = st.session_state.recommendation

        # Executive Card
        status_badge = "badge-feasible" if rec.status == FeasibilityStatus.FEASIBLE else "badge-uncertain"
        st.markdown(f"""
        <div class="metric-card">
            <span class="{status_badge}">{rec.status.value}</span>
            <h2 style="margin-top: 8px;">Recommended: {rec.selected_architecture_name}</h2>
            <p style="font-size: 1.1rem; line-height: 1.5;">{rec.executive_summary}</p>
        </div>
        """, unsafe_allow_html=True)

        col_a, col_b = st.columns([3, 2])
        with col_a:
            st.markdown("### 🏆 Stage 1: Feasibility Filtering")
            feas_rows = []
            for ev in rec.evaluations:
                for chk in ev.checks:
                    feas_rows.append({
                        "Architecture": ev.architecture_name.split("—")[0].strip(),
                        "Constraint": chk.criterion,
                        "Target": f"{chk.target_value}",
                        "Predicted": f"{chk.predicted_value:.2f}",
                        "Status": chk.status.value,
                        "Explanation": chk.explanation,
                    })
            st.dataframe(pd.DataFrame(feas_rows), use_container_width=True, hide_index=True)

            st.markdown("### ⚖️ Stage 2: Multi-Objective Trade-off Scores")
            score_rows = []
            for ev in rec.evaluations:
                score_rows.append({
                    "Architecture": ev.architecture_name.split("—")[0].strip(),
                    "Cost Score": ev.cost_score,
                    "Latency Score": ev.latency_score,
                    "Complexity Score": ev.complexity_score,
                    "Overall Score": ev.overall_score,
                    "Pareto Dominated": "YES" if ev.is_pareto_dominated else "NO",
                })
            st.dataframe(pd.DataFrame(score_rows), use_container_width=True, hide_index=True)

        with col_b:
            st.markdown("### 🧭 Decision Rationale")
            for r in rec.rationale:
                st.markdown(f"- {r}")

            st.markdown("### ⚠️ Trade-offs & Disadvantages")
            for t in rec.trade_offs_and_risks:
                st.markdown(f"- {t}")

            st.markdown("### 📋 Assumptions Cited")
            for a in rec.assumptions_cited:
                st.markdown(f"- {a}")

            st.markdown("### 🔬 Recommended Next Experiment")
            st.info(rec.recommended_next_experiment)

        st.markdown("---")
        st.markdown("### 🔀 Alternative Recommendations")
        alts = rec.predicted_metrics.get("alternatives", {})
        alt_cols = st.columns(3)
        with alt_cols[0]:
            st.markdown("#### 💰 Lowest Cost")
            lc = alts.get("lowest_cost", {})
            st.markdown(f"**{lc.get('name', 'N/A')}**")
            st.markdown(f"Cost: **${lc.get('cost', 0):.2f}/mo** | p95: **{lc.get('p95_ms', 0):.2f} ms**")
        with alt_cols[1]:
            st.markdown("#### ⚡ Best Performance")
            bp = alts.get("best_performance", {})
            st.markdown(f"**{bp.get('name', 'N/A')}**")
            st.markdown(f"Cost: **${bp.get('cost', 0):.2f}/mo** | p95: **{bp.get('p95_ms', 0):.2f} ms**")
        with alt_cols[2]:
            st.markdown("#### ⚖️ Recommended Balanced")
            rc = alts.get("recommended", {})
            st.markdown(f"**{rc.get('name', 'N/A')}**")
            st.markdown(f"Cost: **${rc.get('cost', 0):.2f}/mo** | p95: **{rc.get('p95_ms', 0):.2f} ms**")
