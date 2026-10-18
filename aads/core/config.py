"""
Global configuration and externalized constants for AADS.
"""
from pathlib import Path
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent.parent
REGISTRY_DB_PATH = BASE_DIR / "data" / "registry.db"
REGISTRY_FIXTURES_PATH = BASE_DIR / "aads" / "registry" / "fixtures"
RAW_EXPERIMENTS_DIR = BASE_DIR / "data" / "experiments"

class PricingConfig(BaseModel):
    """Cost model pricing per unit (monthly USD)."""
    vcpu_monthly_usd: float = Field(default=24.0, description="Cost per vCPU per month")
    memory_gb_monthly_usd: float = Field(default=4.0, description="Cost per GB RAM per month")
    storage_gb_monthly_usd: float = Field(default=0.10, description="Cost per GB persistent storage per month")
    redis_base_instance_monthly_usd: float = Field(default=15.0, description="Base managed/container cost for Redis")
    postgres_base_instance_monthly_usd: float = Field(default=25.0, description="Base managed/container cost for PostgreSQL")

class BenchmarkConfig(BaseModel):
    """Resource isolation and timeout bounds for benchmarks."""
    default_timeout_seconds: int = 120
    docker_cpu_limit: str = "1.0"
    docker_memory_limit: str = "512m"
    default_replications: int = 3
    warmup_duration_seconds: int = 3

class Settings(BaseModel):
    pricing: PricingConfig = PricingConfig()
    benchmark: BenchmarkConfig = BenchmarkConfig()
    default_p95_target_ms: float = 60.0
    default_min_throughput_rps: float = 400.0
    default_max_budget_usd: float = 200.0
    random_seed: int = 42

settings = Settings()
