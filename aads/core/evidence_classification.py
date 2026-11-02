"""
Evidence Classification and Performance Finding Framework (Phase 4F.3).

Provides structured classification for benchmark findings, enforcing epistemological
boundaries between direct observations, calculated derivations, statistical correlations,
unverified hypotheses, and controlled causal validations.

Enforces strict scientific validation guardrails (Phase 4F.3.2 FIX 05):
- Requires explicit control and treatment experiment IDs
- Disallows duplicate replications as causal interventions
- Verifies manipulated variable, expected intervention, observed intervention, and comparable baselines
- Prevents unsubstantiated causal claims from being promoted as empirical facts.
"""
from enum import Enum
import re
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field, model_validator


class EvidenceClassification(str, Enum):
    """
    Epistemological taxonomy for performance assertions.
    """
    OBSERVED = "OBSERVED"        # Directly measured by instrumented hardware/OS/engine sensors
    DERIVED = "DERIVED"          # Calculated or aggregated from measured observations (e.g. TPS = N/duration)
    CORRELATED = "CORRELATED"    # Multiple observations show temporal or statistical association without causal proof
    HYPOTHESIS = "HYPOTHESIS"    # Plausible domain-knowledge explanation without direct supporting instrumentation
    VALIDATED = "VALIDATED"      # Causal mechanism confirmed via controlled experiment with variable isolation


class PerformanceFinding(BaseModel):
    """
    Structured performance assertion with explicit provenance, evidence, and uncertainty bounds.
    """
    finding_id: str
    classification: EvidenceClassification
    title: str
    claim: str
    workload_profile: Optional[str] = None
    concurrency: Optional[int] = None
    scale_factor: Optional[int] = None

    # Controlled intervention fields (MANDATORY for VALIDATED) [FIX 05]
    control_experiment_id: Optional[str] = None
    treatment_experiment_id: Optional[str] = None
    manipulated_variable: Optional[str] = None
    expected_intervention: Optional[str] = None
    observed_intervention: Optional[str] = None
    comparable_baseline_confirmed: bool = False
    outcome_metrics: List[str] = Field(default_factory=list)

    supporting_experiment_ids: List[str] = Field(default_factory=list)
    supporting_metrics: List[str] = Field(
        default_factory=list,
        description="Names of instrumented metrics directly supporting this assertion."
    )
    methodology: str
    confidence: str = Field(description="Qualitative or quantitative confidence assessment")
    limitations: List[str] = Field(default_factory=list)
    further_work_required: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_classification_integrity(self) -> "PerformanceFinding":
        """
        Enforce scientific validation guardrails.
        """
        # Rule 1: Strict requirements for VALIDATED claims (FIX 05)
        if self.classification == EvidenceClassification.VALIDATED:
            if not self.control_experiment_id or not self.treatment_experiment_id:
                raise ValueError(
                    f"Finding '{self.finding_id}' classified as VALIDATED requires explicit "
                    f"'control_experiment_id' and 'treatment_experiment_id'."
                )

            ctrl = self.control_experiment_id.strip()
            treat = self.treatment_experiment_id.strip()

            if ctrl == treat:
                raise ValueError(
                    f"Finding '{self.finding_id}' has identical control and treatment experiment IDs ('{ctrl}'). "
                    f"VALIDATED classification requires two distinct configurations."
                )

            # Check for duplicate replications masquerading as an intervention
            # e.g., exp_pg_sf2_c8_r0 vs exp_pg_sf2_c8_r1
            ctrl_rep = re.search(r'_(?:r|rep)\d+', ctrl)
            treat_rep = re.search(r'_(?:r|rep)\d+', treat)
            if ctrl_rep and treat_rep:
                ctrl_prefix = re.sub(r'_(?:r|rep)\d+.*', '', ctrl)
                treat_prefix = re.sub(r'_(?:r|rep)\d+.*', '', treat)
                if ctrl_prefix == treat_prefix:
                    raise ValueError(
                        f"Finding '{self.finding_id}' pairs duplicate replications ('{ctrl}' vs '{treat}') "
                        f"of the same configuration. Replications do not qualify as an intervention for VALIDATED causal claims."
                    )

            if not self.manipulated_variable or not self.manipulated_variable.strip():
                raise ValueError(
                    f"Finding '{self.finding_id}' classified as VALIDATED requires an explicit 'manipulated_variable'."
                )
            if not self.expected_intervention or not self.expected_intervention.strip():
                raise ValueError(
                    f"Finding '{self.finding_id}' classified as VALIDATED requires an explicit 'expected_intervention'."
                )
            if not self.observed_intervention or not self.observed_intervention.strip():
                raise ValueError(
                    f"Finding '{self.finding_id}' classified as VALIDATED requires an explicit 'observed_intervention'."
                )

            if not self.comparable_baseline_confirmed:
                raise ValueError(
                    f"Finding '{self.finding_id}' classified as VALIDATED requires 'comparable_baseline_confirmed=True'. "
                    f"Baseline starting conditions (dataset, configuration, fingerprint) must be verified as comparable."
                )

            all_outcomes = set(self.outcome_metrics + self.supporting_metrics)
            if not all_outcomes:
                raise ValueError(
                    f"Finding '{self.finding_id}' classified as VALIDATED requires relevant 'outcome_metrics'."
                )

            if ctrl not in self.supporting_experiment_ids:
                self.supporting_experiment_ids.append(ctrl)
            if treat not in self.supporting_experiment_ids:
                self.supporting_experiment_ids.append(treat)

            if len(self.supporting_experiment_ids) < 2:
                raise ValueError(
                    f"Finding '{self.finding_id}' classified as VALIDATED must reference at least two supporting experiments."
                )

        # Rule 2: Row lock contention assertions cannot be OBSERVED or VALIDATED without lock wait instrumentation
        claim_lower = self.claim.lower()
        if "lock" in claim_lower and ("contention" in claim_lower or "serialization" in claim_lower):
            has_lock_metric = any("lock" in m.lower() or "wait" in m.lower() for m in self.supporting_metrics)
            if not has_lock_metric and self.classification in (EvidenceClassification.OBSERVED, EvidenceClassification.VALIDATED):
                raise ValueError(
                    f"Finding '{self.finding_id}' asserts lock contention/serialization but lacks supporting lock/wait metrics. "
                    f"Must be classified as HYPOTHESIS or CORRELATED, not {self.classification.value}."
                )

        # Rule 3: Storage/disk bottleneck assertions cannot be OBSERVED or VALIDATED without storage I/O instrumentation
        if "disk" in claim_lower or "storage-bound" in claim_lower or "fsync" in claim_lower:
            has_io_metric = any("io" in m.lower() or "disk" in m.lower() or "wal_sync" in m.lower() for m in self.supporting_metrics)
            if not has_io_metric and self.classification in (EvidenceClassification.OBSERVED, EvidenceClassification.VALIDATED):
                raise ValueError(
                    f"Finding '{self.finding_id}' asserts storage/disk-bound bottleneck but lacks supporting I/O metrics. "
                    f"Must be classified as HYPOTHESIS, not {self.classification.value}."
                )

        # Rule 4: OBSERVED findings cannot assert causal explanations (must be purely descriptive)
        if self.classification == EvidenceClassification.OBSERVED:
            causal_words = ["caused by", "because of", "due to", "resulting from", "governed by"]
            if any(w in claim_lower for w in causal_words):
                raise ValueError(
                    f"Finding '{self.finding_id}' classified as OBSERVED contains causal language ('{claim_lower}'). "
                    f"OBSERVED findings must be purely descriptive. Use CORRELATED, HYPOTHESIS, or VALIDATED for causal claims."
                )

        return self


class HistoricalSF2FindingsCatalog:
    """
    Standardized, epistemologically corrected findings from the Phase 4F.1/4F.2 empirical campaign.
    Corrects historical over-claims while preserving empirical measurements.
    """

    @staticmethod
    def get_corrected_findings() -> List[PerformanceFinding]:
        return [
            PerformanceFinding(
                finding_id="FINDING_4F_01",
                classification=EvidenceClassification.OBSERVED,
                title="100ms Read-Only Tail Latency Periodicity",
                claim=(
                    "Under read_only_select at c=4, 8, and 16, transaction tail-latency spikes (>=10ms) occur in synchronized "
                    "bursts with a median inter-spike interval of exactly 100.0ms matching the Linux CFS period."
                ),
                workload_profile="read_only_select",
                concurrency=4,
                scale_factor=2,
                supporting_experiment_ids=[
                    "exp_pg_sf2_read_only_select_c4_r0_4f46a2f5",
                    "exp_pg_sf2_read_only_select_c4_r1_1899e6c8",
                    "exp_pg_sf2_read_only_select_c4_r2_71ed1774",
                ],
                supporting_metrics=["pgbench_tx_timestamps_usec", "pgbench_latencies_usec"],
                methodology="Microsecond pgbench transaction log timestamp analysis and inter-spike interval calculation.",
                confidence="HIGH (100% mathematical consistency across all 3 replications; >99.7% of spikes match 100ms).",
                limitations=["500ms cgroup sampling interval could not resolve individual 100ms boundaries directly."],
                further_work_required=False,
            ),
            PerformanceFinding(
                finding_id="FINDING_4F_02",
                classification=EvidenceClassification.VALIDATED,
                title="CFS CPU Quota Throttling as Causal Driver of Read-Only Tail Skew",
                claim=(
                    "Linux CFS quota exhaustion causes the bimodal tail latency (70-90ms) in CPU-saturated read_only_select workloads; "
                    "doubling the quota from 1.0 to 2.0 vCPU doubles throughput (+101.7%), halves mean latency (-50.6%), and halves "
                    "the tail spike proportion from 0.361% to 0.179%."
                ),
                workload_profile="read_only_select",
                concurrency=8,
                scale_factor=2,
                control_experiment_id="exp_pg_sf2_read_only_select_c8_1vcpu_ctrl",
                treatment_experiment_id="exp_pg_sf2_read_only_select_c8_2vcpu_treatment",
                manipulated_variable="cpu_limit",
                expected_intervention="Increase CPU quota from 1.0 vCPU (cpu.max=100000 100000) to 2.0 vCPU (cpu.max=200000 100000).",
                observed_intervention="Container cpu.max verified at 200000 vs 100000; measured active CPU increased from 1.00 cores to 1.99 cores.",
                comparable_baseline_confirmed=True,
                outcome_metrics=["achieved_tps", "mean_latency_ms", "tail_spike_proportion_pct", "cgroup_nr_throttled"],
                supporting_experiment_ids=[
                    "exp_pg_sf2_read_only_select_c8_1vcpu_ctrl",
                    "exp_pg_sf2_read_only_select_c8_2vcpu_treatment",
                ],
                supporting_metrics=[
                    "cgroup_nr_throttled",
                    "cgroup_throttled_usec",
                    "container_cpu_utilization_pct",
                    "achieved_tps",
                    "p999_latency_ms",
                ],
                methodology="Controlled variable manipulation: doubling cpu.max from 100000 to 200000 holding all other parameters constant.",
                confidence="VERY HIGH (Controlled causal confirmation matching Little's Law to within 0.9%).",
                limitations=["Conducted only at scale factor 2 with in-memory dataset."],
                further_work_required=False,
            ),
            PerformanceFinding(
                finding_id="FINDING_4F_03",
                classification=EvidenceClassification.OBSERVED,
                title="TPC-B Throughput Inversion at Higher Concurrencies",
                claim=(
                    "Under balanced_oltp_tpcb at SF=2, throughput peaks at c=4 (1,361.4 TPS) and degrades monotonically at "
                    "c=8 (1,315.6 TPS) and c=16 (1,213.0 TPS), with p95 latency escalating from 5.51ms to 44.12ms."
                ),
                workload_profile="balanced_oltp_tpcb",
                scale_factor=2,
                supporting_experiment_ids=[
                    "exp_pg_sf2_balanced_oltp_tpcb_c4_agg_5f689d33",
                    "exp_pg_sf2_balanced_oltp_tpcb_c8_agg_d8ba3fe1",
                    "exp_pg_sf2_balanced_oltp_tpcb_c16_agg_eb0624e3",
                ],
                supporting_metrics=["achieved_tps", "p95_latency_ms", "mean_latency_ms"],
                methodology="Direct pgbench throughput and microsecond latency percentile calculation.",
                confidence="HIGH (Observed across 9 independent trials, 3 replications per concurrency).",
                limitations=["Descriptive metric; does not directly isolate the internal queuing mechanism."],
                further_work_required=True,
            ),
            PerformanceFinding(
                finding_id="FINDING_4F_04",
                classification=EvidenceClassification.HYPOTHESIS,
                title="Row Lock Serialization on Branch and Teller Tables",
                claim=(
                    "TPC-B throughput inversion at c >= 8 is hypothesized to be caused by row-level lock serialization on the "
                    "2 branch rows and 20 teller rows present at SF=2, creating FIFO transaction queues."
                ),
                workload_profile="balanced_oltp_tpcb",
                scale_factor=2,
                supporting_experiment_ids=[
                    "exp_pg_sf2_balanced_oltp_tpcb_c16_agg_eb0624e3",
                    "exp_pg_sf2_simple_write_ingest_c16_agg_7379c057",
                ],
                supporting_metrics=["achieved_tps", "p95_latency_ms"],
                methodology="Indirect comparative deduction: simple_write_ingest (which skips branch/teller updates) scaled to 3,325 TPS.",
                confidence="MODERATE (Supported by workload contrast, but internal pg_locks and wait_event metrics were not instrumented).",
                limitations=["No direct pg_stat_activity or pg_locks wait event samples were collected during execution."],
                further_work_required=True,
            ),
            PerformanceFinding(
                finding_id="FINDING_4F_05",
                classification=EvidenceClassification.OBSERVED,
                title="Simultaneous 3.15s 4-Client Transaction Stall in TPC-B c=4 Rep 1",
                claim=(
                    "In balanced_oltp_tpcb c=4 Rep 1, all 4 client connections stalled simultaneously for 3.146 to 3.153 seconds "
                    "between timestamps 1793597016.418 and 1793597019.562 UTC, during which zero transactions completed."
                ),
                workload_profile="balanced_oltp_tpcb",
                concurrency=4,
                scale_factor=2,
                supporting_experiment_ids=["exp_pg_sf2_balanced_oltp_tpcb_c4_r1_2785388b"],
                supporting_metrics=["pgbench_tx_timestamps_usec", "pgbench_latencies_usec"],
                methodology="Microsecond transaction log timestamp reconciliation across all 4 client connection threads.",
                confidence="VERY HIGH (Direct observation of 4 client completion timestamps: 3146.41ms, 3151.18ms, 3151.28ms, 3152.95ms).",
                limitations=["Root cause (checkpoint flush vs OS writeback vs host pause) is UNVERIFIED due to uninstrumented engine metrics."],
                further_work_required=True,
            ),
            PerformanceFinding(
                finding_id="FINDING_4F_06",
                classification=EvidenceClassification.HYPOTHESIS,
                title="Single-Client Write Throughput Bound by Synchronous WAL Commit",
                claim=(
                    "Single-client write throughput (~1,128 TPS in TPC-B and ~1,157 TPS in simple-write) is hypothesized to be "
                    "bounded by PostgreSQL synchronous commit WAL fsync latency to physical storage."
                ),
                workload_profile="balanced_oltp_tpcb",
                concurrency=1,
                scale_factor=2,
                supporting_experiment_ids=[
                    "exp_pg_sf2_balanced_oltp_tpcb_c1_agg_b6345007",
                    "exp_pg_sf2_simple_write_ingest_c1_agg_d9ca3a36",
                ],
                supporting_metrics=["achieved_tps", "mean_latency_ms"],
                methodology="Domain architectural deduction from single-threaded synchronous ACID commit semantics.",
                confidence="MODERATE (Plausible domain theory, but fsync duration and cgroup io.stat were uninstrumented).",
                limitations=["No physical I/O latency or pg_stat_wal sync times were measured."],
                further_work_required=True,
            ),
        ]
