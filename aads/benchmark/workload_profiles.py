"""
Workload Profile Definitions for AADS Benchmarking Harness.
Defines typed transaction profiles, statement compositions, read/write ratios,
WAL generation impact, and lock contention semantics for PostgreSQL pgbench.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class WorkloadProfileType(str, Enum):
    READ_ONLY_SELECT = "read_only_select"
    BALANCED_OLTP_TPCB = "balanced_oltp_tpcb"
    SIMPLE_WRITE_INGEST = "simple_write_ingest"


@dataclass(frozen=True)
class WorkloadProfile:
    """
    Typed specification for a benchmark transaction profile.
    Replaces ambiguous scalar read ratios with explicit statement breakdowns.
    """
    name: str
    command_flags: List[str]
    description: str
    read_statements_per_tx: int
    write_statements_per_tx: int
    statement_read_ratio: float
    statement_write_ratio: float
    wal_impact: str  # "NONE", "MODERATE", "HIGH"
    lock_contention: str  # "NONE", "LOW", "HIGH"
    statements: List[str] = field(default_factory=list)
    diagnostic_purpose: str = ""

    @property
    def total_statements_per_tx(self) -> int:
        return self.read_statements_per_tx + self.write_statements_per_tx

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "command_flags": list(self.command_flags),
            "description": self.description,
            "read_statements_per_tx": self.read_statements_per_tx,
            "write_statements_per_tx": self.write_statements_per_tx,
            "statement_read_ratio": self.statement_read_ratio,
            "statement_write_ratio": self.statement_write_ratio,
            "total_statements_per_tx": self.total_statements_per_tx,
            "wal_impact": self.wal_impact,
            "lock_contention": self.lock_contention,
            "statements": list(self.statements),
            "diagnostic_purpose": self.diagnostic_purpose,
        }


# Canonical Phase 4F Workload Profiles
READ_ONLY_SELECT = WorkloadProfile(
    name=WorkloadProfileType.READ_ONLY_SELECT.value,
    command_flags=["-S"],
    description="Pure Read-Only Select (pgbench -S)",
    read_statements_per_tx=1,
    write_statements_per_tx=0,
    statement_read_ratio=1.0,
    statement_write_ratio=0.0,
    wal_impact="NONE",
    lock_contention="NONE",
    statements=[
        "SELECT abalance FROM pgbench_accounts WHERE aid = :aid;",
    ],
    diagnostic_purpose=(
        "Calibrates baseline unconstrained query engine throughput, network concurrency scaling, "
        "and in-memory buffer read performance with zero WAL or lock serialization."
    ),
)

BALANCED_OLTP_TPCB = WorkloadProfile(
    name=WorkloadProfileType.BALANCED_OLTP_TPCB.value,
    command_flags=[],
    description="Balanced Mixed OLTP TPC-B-like (Standard pgbench)",
    read_statements_per_tx=1,
    write_statements_per_tx=4,
    statement_read_ratio=0.20,
    statement_write_ratio=0.80,
    wal_impact="HIGH",
    lock_contention="HIGH",
    statements=[
        "SELECT abalance FROM pgbench_accounts WHERE aid = :aid;",
        "UPDATE pgbench_branches SET bbalance = bbalance + :delta WHERE bid = :bid;",
        "UPDATE pgbench_tellers SET tbalance = tbalance + :delta WHERE tid = :tid;",
        "UPDATE pgbench_accounts SET abalance = abalance + :delta WHERE aid = :aid;",
        "INSERT INTO pgbench_history (tid, bid, aid, delta, mtime) VALUES (:tid, :bid, :aid, :delta, CURRENT_TIMESTAMP);",
    ],
    diagnostic_purpose=(
        "Calibrates transaction commit overhead, WAL sync latency, dirty buffer flushing, "
        "and row-level lock serialization on low-cardinality branch and teller tables."
    ),
)

SIMPLE_WRITE_INGEST = WorkloadProfile(
    name=WorkloadProfileType.SIMPLE_WRITE_INGEST.value,
    command_flags=["-N"],
    description="Simple Write / Low-Contention Ingestion (pgbench -N)",
    read_statements_per_tx=1,
    write_statements_per_tx=2,
    statement_read_ratio=0.333,
    statement_write_ratio=0.667,
    wal_impact="MODERATE",
    lock_contention="LOW",
    statements=[
        "SELECT abalance FROM pgbench_accounts WHERE aid = :aid;",
        "UPDATE pgbench_accounts SET abalance = abalance + :delta WHERE aid = :aid;",
        "INSERT INTO pgbench_history (tid, bid, aid, delta, mtime) VALUES (:tid, :bid, :aid, :delta, CURRENT_TIMESTAMP);",
    ],
    diagnostic_purpose=(
        "Isolates write-path WAL throughput, buffer dirtying, and checkpointing from "
        "artificial branch and teller lock contention."
    ),
)

WORKLOAD_PROFILES: Dict[str, WorkloadProfile] = {
    READ_ONLY_SELECT.name: READ_ONLY_SELECT,
    BALANCED_OLTP_TPCB.name: BALANCED_OLTP_TPCB,
    SIMPLE_WRITE_INGEST.name: SIMPLE_WRITE_INGEST,
}

# Aliases for convenience and backward compatibility
PROFILE_ALIASES: Dict[str, str] = {
    "read_only": READ_ONLY_SELECT.name,
    "select_only": READ_ONLY_SELECT.name,
    "select": READ_ONLY_SELECT.name,
    "pgbench:16-select-only": READ_ONLY_SELECT.name,
    "-s": READ_ONLY_SELECT.name,
    "tpcb": BALANCED_OLTP_TPCB.name,
    "tpc_b": BALANCED_OLTP_TPCB.name,
    "balanced_oltp": BALANCED_OLTP_TPCB.name,
    "read_write": BALANCED_OLTP_TPCB.name,
    "standard": BALANCED_OLTP_TPCB.name,
    "pgbench:16-tpcb": BALANCED_OLTP_TPCB.name,
    "simple_write": SIMPLE_WRITE_INGEST.name,
    "simple_update": SIMPLE_WRITE_INGEST.name,
    "write_ingest": SIMPLE_WRITE_INGEST.name,
    "ingest": SIMPLE_WRITE_INGEST.name,
    "pgbench:16-simple-update": SIMPLE_WRITE_INGEST.name,
    "-n": SIMPLE_WRITE_INGEST.name,
}


def resolve_workload_profile(name_or_alias: Optional[str]) -> WorkloadProfile:
    """
    Resolves a workload profile name or alias to its canonical WorkloadProfile object.
    Defaults to READ_ONLY_SELECT if None or unrecognized.
    """
    if not name_or_alias:
        return READ_ONLY_SELECT

    clean_key = name_or_alias.strip().lower()
    if clean_key in WORKLOAD_PROFILES:
        return WORKLOAD_PROFILES[clean_key]

    if clean_key in PROFILE_ALIASES:
        canonical_name = PROFILE_ALIASES[clean_key]
        return WORKLOAD_PROFILES[canonical_name]

    # Heuristic fallback based on substrings
    if "select" in clean_key or "read_only" in clean_key:
        return READ_ONLY_SELECT
    elif "tpcb" in clean_key or "balanced" in clean_key:
        return BALANCED_OLTP_TPCB
    elif "simple" in clean_key or "ingest" in clean_key or "-n" in clean_key:
        return SIMPLE_WRITE_INGEST

    return READ_ONLY_SELECT
