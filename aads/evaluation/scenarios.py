"""
AADS Phase 4C: Versioned Evaluation Scenarios and Dataset Splits.
Provides 12 canonical scenario classes across Development and Held-Out splits,
with explicit, frozen reference outcomes labeled with provenance.
"""
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from aads.core.schemas import (
    WorkloadSpec,
    FeasibilityStatus,
)


class ScenarioClass(str, Enum):
    STRAIGHTFORWARD_DECISION = "straightforward_decision"
    NEAR_TIE_DECISION = "near_tie_decision"
    HARD_CONSTRAINT_BOUNDARY = "hard_constraint_boundary"
    INFEASIBLE_WORKLOAD = "infeasible_workload"
    INCOMPLETE_MODEL_COVERAGE = "incomplete_model_coverage"
    HIGH_UNCERTAINTY = "high_uncertainty"
    EVIDENCE_QUALITY_CONFLICT = "evidence_quality_conflict"
    UNNECESSARY_INVESTIGATION = "unnecessary_investigation"
    DECISION_CHANGING_INVESTIGATION = "decision_changing_investigation"
    PROVIDER_FAILURE = "provider_failure"
    CONFLICTING_OBJECTIVES = "conflicting_objectives"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class DatasetSplit(str, Enum):
    DEVELOPMENT = "development"
    HELD_OUT = "held_out"


class ExpectedReferenceOutcome(BaseModel):
    """Defines the expected reference verdict for evaluating planning quality."""
    expected_winner_id: Optional[str] = None
    expected_winner_set: List[str] = Field(default_factory=list)
    expected_status: FeasibilityStatus = FeasibilityStatus.FEASIBLE
    expected_feasible_ids: List[str] = Field(default_factory=list)
    expected_ranking: List[str] = Field(default_factory=list)
    is_abstention_expected: bool = False
    should_stop_early: bool = False
    reference_provenance: str = "synthetic_fixture"  # 'synthetic_fixture' or 'empirical_measurement'
    reference_objective_value: Optional[float] = None
    rationale: str = ""


class EvaluationScenario(BaseModel):
    """Frozen, reproducible scenario definition for evaluating architecture planning strategies."""
    scenario_id: str
    name: str
    description: str
    scenario_class: ScenarioClass
    dataset_split: DatasetSplit
    workload_spec: WorkloadSpec
    expected_reference: ExpectedReferenceOutcome
    include_async: bool = True
    include_unsupported: bool = False
    simulation_duration_seconds: float = 5.0
    random_seed: int = 42
    max_investigation_rounds: int = 3
    investigation_budget_seconds: float = 60.0
    missing_model_keys: List[str] = Field(default_factory=list)
    mock_llm_decisions: Optional[List[Dict[str, Any]]] = None
    simulate_provider_failure: bool = False


# ---------------------------------------------------------------------------
# Development Scenarios (12 Classes)
# ---------------------------------------------------------------------------

DEV_SCENARIOS: List[EvaluationScenario] = [
    EvaluationScenario(
        scenario_id="dev_01_straightforward",
        name="Straightforward Low-Load Decision",
        description="Low-traffic read-heavy workload where Architecture A easily satisfies all constraints at lowest cost and simplicity.",
        scenario_class=ScenarioClass.STRAIGHTFORWARD_DECISION,
        dataset_split=DatasetSplit.DEVELOPMENT,
        workload_spec=WorkloadSpec(
            app_type="social_media_feed",
            request_rate_rps=150.0,
            peak_load_factor=1.5,
            read_ratio=0.95,
            write_ratio=0.05,
            p95_latency_target_ms=50.0,
            min_throughput_rps=140.0,
            max_monthly_budget_usd=160.0,
            cache_assumed_hit_rate=0.85,
            hard_constraints=["p95_latency", "min_throughput", "max_budget"],
            soft_preferences={"cost": 0.40, "latency": 0.30, "simplicity": 0.30},
        ),
        expected_reference=ExpectedReferenceOutcome(
            expected_winner_id="arch_a_simple",
            expected_status=FeasibilityStatus.FEASIBLE,
            expected_feasible_ids=["arch_a_simple"],
            expected_ranking=["arch_a_simple"],
            reference_provenance="synthetic_fixture",
            rationale="Arch A satisfies all SLAs; Arch B (76) and C (16) exceed budget (60).",
        ),
    ),
    EvaluationScenario(
        scenario_id="dev_02_near_tie",
        name="Near-Tie Between Cached Reads and Async Pipeline",
        description="Mid-RPS workload where Arch B and Arch C both easily meet SLAs with close overall multi-objective scores.",
        scenario_class=ScenarioClass.NEAR_TIE_DECISION,
        dataset_split=DatasetSplit.DEVELOPMENT,
        workload_spec=WorkloadSpec(
            app_type="social_media_feed",
            request_rate_rps=500.0,
            peak_load_factor=2.0,
            read_ratio=0.90,
            write_ratio=0.10,
            p95_latency_target_ms=50.0,
            min_throughput_rps=450.0,
            max_monthly_budget_usd=250.0,
            cache_assumed_hit_rate=0.85,
            hard_constraints=["p95_latency", "min_throughput", "max_budget"],
            soft_preferences={"cost": 0.35, "latency": 0.45, "simplicity": 0.20},
        ),
        expected_reference=ExpectedReferenceOutcome(
            expected_winner_id="arch_b_cached",
            expected_status=FeasibilityStatus.FEASIBLE,
            expected_feasible_ids=["arch_b_cached", "arch_c_async"],
            expected_ranking=["arch_b_cached", "arch_c_async", "arch_a_simple"],
            reference_provenance="synthetic_fixture",
            rationale="Both B and C meet SLAs; B outranks C due to lower cost (76 vs 16) and higher simplicity (0.7 vs 0.4).",
        ),
    ),
    EvaluationScenario(
        scenario_id="dev_03_boundary",
        name="Hard SLA Latency Constraint Boundary",
        description="Workload with strict 8.0ms p95 latency target. Arch B is close to boundary (~7.3ms); Arch C is safely within (~3.3ms).",
        scenario_class=ScenarioClass.HARD_CONSTRAINT_BOUNDARY,
        dataset_split=DatasetSplit.DEVELOPMENT,
        workload_spec=WorkloadSpec(
            app_type="social_media_feed",
            request_rate_rps=550.0,
            peak_load_factor=2.0,
            read_ratio=0.85,
            write_ratio=0.15,
            p95_latency_target_ms=8.0,
            min_throughput_rps=500.0,
            max_monthly_budget_usd=250.0,
            cache_assumed_hit_rate=0.85,
            hard_constraints=["p95_latency", "min_throughput", "max_budget"],
            soft_preferences={"cost": 0.20, "latency": 0.60, "simplicity": 0.20},
        ),
        expected_reference=ExpectedReferenceOutcome(
            expected_winner_id="arch_c_async",
            expected_status=FeasibilityStatus.FEASIBLE,
            expected_feasible_ids=["arch_c_async"],
            expected_ranking=["arch_c_async"],
            reference_provenance="synthetic_fixture",
            rationale="Arch C safely achieves <4ms p95 latency; Arch B uncertainty bound touches or exceeds the 8.0ms boundary.",
        ),
    ),
    EvaluationScenario(
        scenario_id="dev_04_infeasible",
        name="Infeasible Extreme Workload",
        description="2500 RPS with strict 00 budget and 5ms latency target. Mathematically impossible under standard pricing.",
        scenario_class=ScenarioClass.INFEASIBLE_WORKLOAD,
        dataset_split=DatasetSplit.DEVELOPMENT,
        workload_spec=WorkloadSpec(
            app_type="social_media_feed",
            request_rate_rps=2500.0,
            peak_load_factor=2.0,
            read_ratio=0.80,
            write_ratio=0.20,
            p95_latency_target_ms=5.0,
            min_throughput_rps=2400.0,
            max_monthly_budget_usd=100.0,
            cache_assumed_hit_rate=0.85,
            hard_constraints=["p95_latency", "min_throughput", "max_budget"],
            soft_preferences={"cost": 0.35, "latency": 0.45, "simplicity": 0.20},
        ),
        expected_reference=ExpectedReferenceOutcome(
            expected_winner_id=None,
            expected_status=FeasibilityStatus.INFEASIBLE,
            expected_feasible_ids=[],
            is_abstention_expected=True,
            reference_provenance="synthetic_fixture",
            rationale="All candidates breach either budget (00 budget vs minimum 33 Arch A cost) or throughput/latency constraints.",
        ),
    ),
    EvaluationScenario(
        scenario_id="dev_05_incomplete_coverage",
        name="Incomplete Model Coverage",
        description="Candidate candidate generation includes unsupported MongoDB cluster with missing model in registry.",
        scenario_class=ScenarioClass.INCOMPLETE_MODEL_COVERAGE,
        dataset_split=DatasetSplit.DEVELOPMENT,
        include_unsupported=True,
        workload_spec=WorkloadSpec(
            app_type="social_media_feed",
            request_rate_rps=400.0,
            peak_load_factor=1.5,
            read_ratio=0.90,
            write_ratio=0.10,
            p95_latency_target_ms=50.0,
            min_throughput_rps=350.0,
            max_monthly_budget_usd=250.0,
            cache_assumed_hit_rate=0.85,
            hard_constraints=["p95_latency", "min_throughput", "max_budget"],
            soft_preferences={"cost": 0.35, "latency": 0.45, "simplicity": 0.20},
        ),
        expected_reference=ExpectedReferenceOutcome(
            expected_winner_id="arch_b_cached",
            expected_status=FeasibilityStatus.FEASIBLE,
            expected_feasible_ids=["arch_b_cached", "arch_c_async"],
            reference_provenance="synthetic_fixture",
            rationale="Unsupported candidate cannot be simulated or recommended without calibrated model; Arch B is chosen.",
        ),
    ),
    EvaluationScenario(
        scenario_id="dev_06_high_uncertainty",
        name="High Burst Factor Uncertainty",
        description="Workload with 3.5x burst factor causing wide queueing latency variance.",
        scenario_class=ScenarioClass.HIGH_UNCERTAINTY,
        dataset_split=DatasetSplit.DEVELOPMENT,
        workload_spec=WorkloadSpec(
            app_type="social_media_feed",
            request_rate_rps=450.0,
            peak_load_factor=3.5,
            read_ratio=0.85,
            write_ratio=0.15,
            p95_latency_target_ms=15.0,
            min_throughput_rps=400.0,
            max_monthly_budget_usd=250.0,
            cache_assumed_hit_rate=0.85,
            hard_constraints=["p95_latency", "min_throughput", "max_budget"],
            soft_preferences={"cost": 0.30, "latency": 0.50, "simplicity": 0.20},
        ),
        expected_reference=ExpectedReferenceOutcome(
            expected_winner_id="arch_b_cached",
            expected_status=FeasibilityStatus.FEASIBLE,
            expected_feasible_ids=["arch_b_cached", "arch_c_async"],
            reference_provenance="synthetic_fixture",
            rationale="Adaptive inspection of uncertainty clarifies that Arch B and C remain within acceptable bounds despite burstiness.",
        ),
    ),
    EvaluationScenario(
        scenario_id="dev_07_evidence_conflict",
        name="Empirical Calibration vs Synthetic Lookup Model",
        description="Comparison where Postgres model has empirical piecewise ridge calibration while Redis is lookup-based.",
        scenario_class=ScenarioClass.EVIDENCE_QUALITY_CONFLICT,
        dataset_split=DatasetSplit.DEVELOPMENT,
        workload_spec=WorkloadSpec(
            app_type="social_media_feed",
            request_rate_rps=480.0,
            peak_load_factor=2.0,
            read_ratio=0.92,
            write_ratio=0.08,
            p95_latency_target_ms=45.0,
            min_throughput_rps=420.0,
            max_monthly_budget_usd=250.0,
            cache_assumed_hit_rate=0.85,
            hard_constraints=["p95_latency", "min_throughput", "max_budget"],
            soft_preferences={"cost": 0.35, "latency": 0.45, "simplicity": 0.20},
        ),
        expected_reference=ExpectedReferenceOutcome(
            expected_winner_id="arch_b_cached",
            expected_status=FeasibilityStatus.FEASIBLE,
            expected_feasible_ids=["arch_b_cached", "arch_c_async"],
            reference_provenance="synthetic_fixture",
            rationale="Evidence provenance accurately distinguishes empirical postgres models from synthetic cache fixtures.",
        ),
    ),
    EvaluationScenario(
        scenario_id="dev_08_unnecessary_investigation",
        name="Unnecessary Investigation on Obvious Workload",
        description="Very low load (80 RPS) where Arch A is obviously optimal; extra investigation rounds add no decision value.",
        scenario_class=ScenarioClass.UNNECESSARY_INVESTIGATION,
        dataset_split=DatasetSplit.DEVELOPMENT,
        workload_spec=WorkloadSpec(
            app_type="social_media_feed",
            request_rate_rps=80.0,
            peak_load_factor=1.2,
            read_ratio=0.95,
            write_ratio=0.05,
            p95_latency_target_ms=60.0,
            min_throughput_rps=75.0,
            max_monthly_budget_usd=200.0,
            cache_assumed_hit_rate=0.85,
            hard_constraints=["p95_latency", "min_throughput", "max_budget"],
            soft_preferences={"cost": 0.40, "latency": 0.30, "simplicity": 0.30},
        ),
        expected_reference=ExpectedReferenceOutcome(
            expected_winner_id="arch_a_simple",
            expected_status=FeasibilityStatus.FEASIBLE,
            expected_feasible_ids=["arch_a_simple", "arch_b_cached", "arch_c_async"],
            should_stop_early=True,
            reference_provenance="synthetic_fixture",
            rationale="Arch A is feasible, lowest cost (33), and highest simplicity (1.0). Investigation rounds are redundant.",
        ),
    ),
    EvaluationScenario(
        scenario_id="dev_09_decision_changing",
        name="Decision-Changing Constraint Audit",
        description="Latency SLA set at 7.0ms. Initial rough view might favor B, but uncertainty/latency check reveals B risks breaching SLA, favoring C.",
        scenario_class=ScenarioClass.DECISION_CHANGING_INVESTIGATION,
        dataset_split=DatasetSplit.DEVELOPMENT,
        workload_spec=WorkloadSpec(
            app_type="social_media_feed",
            request_rate_rps=520.0,
            peak_load_factor=2.0,
            read_ratio=0.88,
            write_ratio=0.12,
            p95_latency_target_ms=7.0,
            min_throughput_rps=480.0,
            max_monthly_budget_usd=250.0,
            cache_assumed_hit_rate=0.85,
            hard_constraints=["p95_latency", "min_throughput", "max_budget"],
            soft_preferences={"cost": 0.25, "latency": 0.55, "simplicity": 0.20},
        ),
        expected_reference=ExpectedReferenceOutcome(
            expected_winner_id="arch_c_async",
            expected_status=FeasibilityStatus.FEASIBLE,
            expected_feasible_ids=["arch_c_async"],
            reference_provenance="synthetic_fixture",
            rationale="Arch B p95 (~7.25ms) fails the 7.0ms SLA, leaving Arch C as the sole feasible architecture.",
        ),
    ),
    EvaluationScenario(
        scenario_id="dev_10_provider_failure",
        name="LLM Provider Failure Recovery",
        description="Simulates an LLM exception/timeout; validates that deterministic fallback operates without degradation of recommendation.",
        scenario_class=ScenarioClass.PROVIDER_FAILURE,
        dataset_split=DatasetSplit.DEVELOPMENT,
        simulate_provider_failure=True,
        workload_spec=WorkloadSpec(
            app_type="social_media_feed",
            request_rate_rps=500.0,
            peak_load_factor=2.0,
            read_ratio=0.90,
            write_ratio=0.10,
            p95_latency_target_ms=50.0,
            min_throughput_rps=450.0,
            max_monthly_budget_usd=250.0,
            cache_assumed_hit_rate=0.85,
            hard_constraints=["p95_latency", "min_throughput", "max_budget"],
            soft_preferences={"cost": 0.35, "latency": 0.45, "simplicity": 0.20},
        ),
        expected_reference=ExpectedReferenceOutcome(
            expected_winner_id="arch_b_cached",
            expected_status=FeasibilityStatus.FEASIBLE,
            expected_feasible_ids=["arch_b_cached", "arch_c_async"],
            reference_provenance="synthetic_fixture",
            rationale="Deterministic fallback handles planner outage and reliably selects Arch B.",
        ),
    ),
    EvaluationScenario(
        scenario_id="dev_11_conflicting_objectives",
        name="Conflicting Latency vs Cost Preferences",
        description="Latency weight elevated to 0.75, cost to 0.10, simplicity to 0.15, shifting balance heavily toward Arch C.",
        scenario_class=ScenarioClass.CONFLICTING_OBJECTIVES,
        dataset_split=DatasetSplit.DEVELOPMENT,
        workload_spec=WorkloadSpec(
            app_type="social_media_feed",
            request_rate_rps=500.0,
            peak_load_factor=2.0,
            read_ratio=0.90,
            write_ratio=0.10,
            p95_latency_target_ms=50.0,
            min_throughput_rps=450.0,
            max_monthly_budget_usd=250.0,
            cache_assumed_hit_rate=0.85,
            hard_constraints=["p95_latency", "min_throughput", "max_budget"],
            soft_preferences={"cost": 0.10, "latency": 0.75, "simplicity": 0.15},
        ),
        expected_reference=ExpectedReferenceOutcome(
            expected_winner_id="arch_c_async",
            expected_status=FeasibilityStatus.FEASIBLE,
            expected_feasible_ids=["arch_b_cached", "arch_c_async"],
            reference_provenance="synthetic_fixture",
            rationale="Heavy latency preference (75%) overcomes the 0 cost premium of Arch C, making C the top choice.",
        ),
    ),
    EvaluationScenario(
        scenario_id="dev_12_insufficient_evidence",
        name="Insufficient Evidence Abstention",
        description="Workload requires MongoDB for which no model or simulation exists. System must report inconclusive rather than false confidence.",
        scenario_class=ScenarioClass.INSUFFICIENT_EVIDENCE,
        dataset_split=DatasetSplit.DEVELOPMENT,
        include_async=False,
        include_unsupported=True,
        workload_spec=WorkloadSpec(
            app_type="social_media_feed",
            request_rate_rps=1200.0,
            peak_load_factor=2.0,
            read_ratio=0.50,
            write_ratio=0.50,
            p95_latency_target_ms=10.0,
            min_throughput_rps=1100.0,
            max_monthly_budget_usd=120.0,
            cache_assumed_hit_rate=0.85,
            hard_constraints=["p95_latency", "min_throughput", "max_budget"],
            soft_preferences={"cost": 0.35, "latency": 0.45, "simplicity": 0.20},
        ),
        expected_reference=ExpectedReferenceOutcome(
            expected_winner_id=None,
            expected_status=FeasibilityStatus.INFEASIBLE,
            expected_feasible_ids=[],
            is_abstention_expected=True,
            reference_provenance="synthetic_fixture",
            rationale="All standard candidates breach SLA at 1200 RPS write-heavy, and unsupported candidate lacks model.",
        ),
    ),
]


# ---------------------------------------------------------------------------
# Held-Out Scenarios (12 Classes with independent parameters)
# ---------------------------------------------------------------------------

HELDOUT_SCENARIOS: List[EvaluationScenario] = [
    EvaluationScenario(
        scenario_id="heldout_01_straightforward",
        name="Held-Out: Straightforward Low-Load Feed",
        description="180 RPS with 50 budget. Only Arch A fits budget while easily satisfying 45ms latency target.",
        scenario_class=ScenarioClass.STRAIGHTFORWARD_DECISION,
        dataset_split=DatasetSplit.HELD_OUT,
        workload_spec=WorkloadSpec(
            app_type="social_media_feed",
            request_rate_rps=180.0,
            peak_load_factor=1.4,
            read_ratio=0.92,
            write_ratio=0.08,
            p95_latency_target_ms=45.0,
            min_throughput_rps=170.0,
            max_monthly_budget_usd=150.0,
            cache_assumed_hit_rate=0.85,
            hard_constraints=["p95_latency", "min_throughput", "max_budget"],
            soft_preferences={"cost": 0.45, "latency": 0.30, "simplicity": 0.25},
        ),
        expected_reference=ExpectedReferenceOutcome(
            expected_winner_id="arch_a_simple",
            expected_status=FeasibilityStatus.FEASIBLE,
            expected_feasible_ids=["arch_a_simple"],
            expected_ranking=["arch_a_simple"],
            reference_provenance="synthetic_fixture",
            rationale="Arch A is sole candidate within 50 budget.",
        ),
    ),
    EvaluationScenario(
        scenario_id="heldout_02_near_tie",
        name="Held-Out: Near-Tie at 420 RPS",
        description="420 RPS workload with moderate constraints where Arch B and Arch C are closely matched.",
        scenario_class=ScenarioClass.NEAR_TIE_DECISION,
        dataset_split=DatasetSplit.HELD_OUT,
        workload_spec=WorkloadSpec(
            app_type="social_media_feed",
            request_rate_rps=420.0,
            peak_load_factor=1.8,
            read_ratio=0.91,
            write_ratio=0.09,
            p95_latency_target_ms=40.0,
            min_throughput_rps=400.0,
            max_monthly_budget_usd=260.0,
            cache_assumed_hit_rate=0.85,
            hard_constraints=["p95_latency", "min_throughput", "max_budget"],
            soft_preferences={"cost": 0.35, "latency": 0.45, "simplicity": 0.20},
        ),
        expected_reference=ExpectedReferenceOutcome(
            expected_winner_id="arch_b_cached",
            expected_status=FeasibilityStatus.FEASIBLE,
            expected_feasible_ids=["arch_b_cached", "arch_c_async"],
            expected_ranking=["arch_b_cached", "arch_c_async", "arch_a_simple"],
            reference_provenance="synthetic_fixture",
            rationale="Arch B balances cost and performance effectively under standard preferences.",
        ),
    ),
    EvaluationScenario(
        scenario_id="heldout_03_boundary",
        name="Held-Out: Tight 7.5ms Latency Boundary",
        description="Tight 7.5ms latency target at 480 RPS. Arch B p95 touches boundary while Arch C is comfortably safe.",
        scenario_class=ScenarioClass.HARD_CONSTRAINT_BOUNDARY,
        dataset_split=DatasetSplit.HELD_OUT,
        workload_spec=WorkloadSpec(
            app_type="social_media_feed",
            request_rate_rps=480.0,
            peak_load_factor=1.8,
            read_ratio=0.86,
            write_ratio=0.14,
            p95_latency_target_ms=7.5,
            min_throughput_rps=450.0,
            max_monthly_budget_usd=250.0,
            cache_assumed_hit_rate=0.85,
            hard_constraints=["p95_latency", "min_throughput", "max_budget"],
            soft_preferences={"cost": 0.25, "latency": 0.55, "simplicity": 0.20},
        ),
        expected_reference=ExpectedReferenceOutcome(
            expected_winner_id="arch_c_async",
            expected_status=FeasibilityStatus.FEASIBLE,
            expected_feasible_ids=["arch_c_async"],
            reference_provenance="synthetic_fixture",
            rationale="Arch C reliably meets <4ms p95 latency whereas Arch B upper bound exceeds 7.5ms.",
        ),
    ),
    EvaluationScenario(
        scenario_id="heldout_04_infeasible",
        name="Held-Out: Infeasible 3000 RPS Budget Breach",
        description="Extreme 3000 RPS workload with 20 budget. No architecture can possibly satisfy constraints.",
        scenario_class=ScenarioClass.INFEASIBLE_WORKLOAD,
        dataset_split=DatasetSplit.HELD_OUT,
        workload_spec=WorkloadSpec(
            app_type="social_media_feed",
            request_rate_rps=3000.0,
            peak_load_factor=2.0,
            read_ratio=0.85,
            write_ratio=0.15,
            p95_latency_target_ms=10.0,
            min_throughput_rps=2800.0,
            max_monthly_budget_usd=120.0,
            cache_assumed_hit_rate=0.85,
            hard_constraints=["p95_latency", "min_throughput", "max_budget"],
            soft_preferences={"cost": 0.35, "latency": 0.45, "simplicity": 0.20},
        ),
        expected_reference=ExpectedReferenceOutcome(
            expected_winner_id=None,
            expected_status=FeasibilityStatus.INFEASIBLE,
            expected_feasible_ids=[],
            is_abstention_expected=True,
            reference_provenance="synthetic_fixture",
            rationale="All candidates fail budget and latency thresholds.",
        ),
    ),
    EvaluationScenario(
        scenario_id="heldout_05_incomplete_coverage",
        name="Held-Out: Incomplete Coverage with MongoDB Candidate",
        description="Evaluates uncalibrated MongoDB candidate rejection under 350 RPS workload.",
        scenario_class=ScenarioClass.INCOMPLETE_MODEL_COVERAGE,
        dataset_split=DatasetSplit.HELD_OUT,
        include_unsupported=True,
        workload_spec=WorkloadSpec(
            app_type="social_media_feed",
            request_rate_rps=350.0,
            peak_load_factor=1.5,
            read_ratio=0.90,
            write_ratio=0.10,
            p95_latency_target_ms=45.0,
            min_throughput_rps=320.0,
            max_monthly_budget_usd=250.0,
            cache_assumed_hit_rate=0.85,
            hard_constraints=["p95_latency", "min_throughput", "max_budget"],
            soft_preferences={"cost": 0.35, "latency": 0.45, "simplicity": 0.20},
        ),
        expected_reference=ExpectedReferenceOutcome(
            expected_winner_id="arch_b_cached",
            expected_status=FeasibilityStatus.FEASIBLE,
            expected_feasible_ids=["arch_b_cached", "arch_c_async"],
            reference_provenance="synthetic_fixture",
            rationale="Uncalibrated component is detected and excluded from winner selection.",
        ),
    ),
    EvaluationScenario(
        scenario_id="heldout_06_high_uncertainty",
        name="Held-Out: Burst Factor 4.0x Uncertainty",
        description="Heavy burst factor (4.0x) testing queue and uncertainty management.",
        scenario_class=ScenarioClass.HIGH_UNCERTAINTY,
        dataset_split=DatasetSplit.HELD_OUT,
        workload_spec=WorkloadSpec(
            app_type="social_media_feed",
            request_rate_rps=380.0,
            peak_load_factor=4.0,
            read_ratio=0.82,
            write_ratio=0.18,
            p95_latency_target_ms=20.0,
            min_throughput_rps=350.0,
            max_monthly_budget_usd=250.0,
            cache_assumed_hit_rate=0.85,
            hard_constraints=["p95_latency", "min_throughput", "max_budget"],
            soft_preferences={"cost": 0.30, "latency": 0.50, "simplicity": 0.20},
        ),
        expected_reference=ExpectedReferenceOutcome(
            expected_winner_id="arch_b_cached",
            expected_status=FeasibilityStatus.FEASIBLE,
            expected_feasible_ids=["arch_b_cached", "arch_c_async"],
            reference_provenance="synthetic_fixture",
            rationale="Simulated peak handling verifies Arch B maintains p95 within 20ms target.",
        ),
    ),
    EvaluationScenario(
        scenario_id="heldout_07_evidence_conflict",
        name="Held-Out: Calibration Model Contrast at 520 RPS",
        description="Contrasts empirical DB calibration with synthetic cache lookup under 520 RPS load.",
        scenario_class=ScenarioClass.EVIDENCE_QUALITY_CONFLICT,
        dataset_split=DatasetSplit.HELD_OUT,
        workload_spec=WorkloadSpec(
            app_type="social_media_feed",
            request_rate_rps=520.0,
            peak_load_factor=2.0,
            read_ratio=0.90,
            write_ratio=0.10,
            p95_latency_target_ms=40.0,
            min_throughput_rps=480.0,
            max_monthly_budget_usd=250.0,
            cache_assumed_hit_rate=0.85,
            hard_constraints=["p95_latency", "min_throughput", "max_budget"],
            soft_preferences={"cost": 0.35, "latency": 0.45, "simplicity": 0.20},
        ),
        expected_reference=ExpectedReferenceOutcome(
            expected_winner_id="arch_b_cached",
            expected_status=FeasibilityStatus.FEASIBLE,
            expected_feasible_ids=["arch_b_cached", "arch_c_async"],
            reference_provenance="synthetic_fixture",
            rationale="Component provenance clearly separates empirical postgres from synthetic redis models.",
        ),
    ),
    EvaluationScenario(
        scenario_id="heldout_08_unnecessary_investigation",
        name="Held-Out: 60 RPS Minimal Workload",
        description="60 RPS load where Arch A is undeniably optimal and investigation should yield zero marginal gain.",
        scenario_class=ScenarioClass.UNNECESSARY_INVESTIGATION,
        dataset_split=DatasetSplit.HELD_OUT,
        workload_spec=WorkloadSpec(
            app_type="social_media_feed",
            request_rate_rps=60.0,
            peak_load_factor=1.2,
            read_ratio=0.95,
            write_ratio=0.05,
            p95_latency_target_ms=75.0,
            min_throughput_rps=55.0,
            max_monthly_budget_usd=220.0,
            cache_assumed_hit_rate=0.85,
            hard_constraints=["p95_latency", "min_throughput", "max_budget"],
            soft_preferences={"cost": 0.40, "latency": 0.30, "simplicity": 0.30},
        ),
        expected_reference=ExpectedReferenceOutcome(
            expected_winner_id="arch_a_simple",
            expected_status=FeasibilityStatus.FEASIBLE,
            expected_feasible_ids=["arch_a_simple", "arch_b_cached", "arch_c_async"],
            should_stop_early=True,
            reference_provenance="synthetic_fixture",
            rationale="Arch A satisfies all constraints with minimum operational complexity.",
        ),
    ),
    EvaluationScenario(
        scenario_id="heldout_09_decision_changing",
        name="Held-Out: Latency SLA at 6.5ms Flips Winner to C",
        description="6.5ms latency target where Arch B (~7.2ms) is disqualified and Arch C (~3.3ms) is the only feasible choice.",
        scenario_class=ScenarioClass.DECISION_CHANGING_INVESTIGATION,
        dataset_split=DatasetSplit.HELD_OUT,
        workload_spec=WorkloadSpec(
            app_type="social_media_feed",
            request_rate_rps=490.0,
            peak_load_factor=1.8,
            read_ratio=0.87,
            write_ratio=0.13,
            p95_latency_target_ms=6.5,
            min_throughput_rps=450.0,
            max_monthly_budget_usd=250.0,
            cache_assumed_hit_rate=0.85,
            hard_constraints=["p95_latency", "min_throughput", "max_budget"],
            soft_preferences={"cost": 0.20, "latency": 0.60, "simplicity": 0.20},
        ),
        expected_reference=ExpectedReferenceOutcome(
            expected_winner_id="arch_c_async",
            expected_status=FeasibilityStatus.FEASIBLE,
            expected_feasible_ids=["arch_c_async"],
            reference_provenance="synthetic_fixture",
            rationale="Detailed inspection confirms Arch B violates the 6.5ms SLA, making Arch C the sole winner.",
        ),
    ),
    EvaluationScenario(
        scenario_id="heldout_10_provider_failure",
        name="Held-Out: Provider Timeout at 460 RPS",
        description="Evaluates deterministic fallback when LLM connection drops or times out.",
        scenario_class=ScenarioClass.PROVIDER_FAILURE,
        dataset_split=DatasetSplit.HELD_OUT,
        simulate_provider_failure=True,
        workload_spec=WorkloadSpec(
            app_type="social_media_feed",
            request_rate_rps=460.0,
            peak_load_factor=1.9,
            read_ratio=0.89,
            write_ratio=0.11,
            p95_latency_target_ms=45.0,
            min_throughput_rps=420.0,
            max_monthly_budget_usd=250.0,
            cache_assumed_hit_rate=0.85,
            hard_constraints=["p95_latency", "min_throughput", "max_budget"],
            soft_preferences={"cost": 0.35, "latency": 0.45, "simplicity": 0.20},
        ),
        expected_reference=ExpectedReferenceOutcome(
            expected_winner_id="arch_b_cached",
            expected_status=FeasibilityStatus.FEASIBLE,
            expected_feasible_ids=["arch_b_cached", "arch_c_async"],
            reference_provenance="synthetic_fixture",
            rationale="Deterministic fallback gracefully handles provider failure without recommendation degradation.",
        ),
    ),
    EvaluationScenario(
        scenario_id="heldout_11_conflicting_objectives",
        name="Held-Out: 80% Latency Weight Shifting to C",
        description="Latency weight set to 0.80 and cost to 0.10, testing objective preference sensitivity.",
        scenario_class=ScenarioClass.CONFLICTING_OBJECTIVES,
        dataset_split=DatasetSplit.HELD_OUT,
        workload_spec=WorkloadSpec(
            app_type="social_media_feed",
            request_rate_rps=450.0,
            peak_load_factor=1.8,
            read_ratio=0.88,
            write_ratio=0.12,
            p95_latency_target_ms=45.0,
            min_throughput_rps=400.0,
            max_monthly_budget_usd=260.0,
            cache_assumed_hit_rate=0.85,
            hard_constraints=["p95_latency", "min_throughput", "max_budget"],
            soft_preferences={"cost": 0.10, "latency": 0.80, "simplicity": 0.10},
        ),
        expected_reference=ExpectedReferenceOutcome(
            expected_winner_id="arch_c_async",
            expected_status=FeasibilityStatus.FEASIBLE,
            expected_feasible_ids=["arch_b_cached", "arch_c_async"],
            reference_provenance="synthetic_fixture",
            rationale="High latency weight causes Arch C's superior latency to dominate overall score.",
        ),
    ),
    EvaluationScenario(
        scenario_id="heldout_12_insufficient_evidence",
        name="Held-Out: 1500 RPS Inconclusive Load",
        description="High-concurrency write-heavy load where models lack supported calibration and all candidates breach SLA.",
        scenario_class=ScenarioClass.INSUFFICIENT_EVIDENCE,
        dataset_split=DatasetSplit.HELD_OUT,
        include_async=False,
        include_unsupported=True,
        workload_spec=WorkloadSpec(
            app_type="social_media_feed",
            request_rate_rps=1500.0,
            peak_load_factor=2.2,
            read_ratio=0.40,
            write_ratio=0.60,
            p95_latency_target_ms=8.0,
            min_throughput_rps=1400.0,
            max_monthly_budget_usd=130.0,
            cache_assumed_hit_rate=0.85,
            hard_constraints=["p95_latency", "min_throughput", "max_budget"],
            soft_preferences={"cost": 0.35, "latency": 0.45, "simplicity": 0.20},
        ),
        expected_reference=ExpectedReferenceOutcome(
            expected_winner_id=None,
            expected_status=FeasibilityStatus.INFEASIBLE,
            expected_feasible_ids=[],
            is_abstention_expected=True,
            reference_provenance="synthetic_fixture",
            rationale="Infeasible SLA combined with missing models mandates abstention / inconclusive verdict.",
        ),
    ),
]


PILOT_SCENARIOS: List[EvaluationScenario] = [
    s for s in DEV_SCENARIOS if s.scenario_id in ("dev_01_straightforward", "dev_03_boundary", "dev_05_incomplete_coverage")
]


def get_scenario_by_id(scenario_id: str) -> Optional[EvaluationScenario]:
    all_scenarios = DEV_SCENARIOS + HELDOUT_SCENARIOS
    for s in all_scenarios:
        if s.scenario_id == scenario_id:
            return s
    return None


def get_scenarios(split: Optional[str] = None) -> List[EvaluationScenario]:
    if split in ("pilot", "dev_pilot"):
        return list(PILOT_SCENARIOS)
    elif split in ("development", "dev"):
        return list(DEV_SCENARIOS)
    elif split in ("held_out", "heldout"):
        return list(HELDOUT_SCENARIOS)
    return list(DEV_SCENARIOS + HELDOUT_SCENARIOS)
