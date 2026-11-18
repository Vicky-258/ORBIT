"""
Global configuration and externalized constants for ORBIT.
"""
import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent.parent

def _load_env_file():
    env_file = BASE_DIR / ".env"
    if env_file.is_file():
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'").strip('"')
                        if k and k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass

_load_env_file()
REGISTRY_DB_PATH = BASE_DIR / "data" / "registry.db"
REGISTRY_FIXTURES_PATH = BASE_DIR / "orbit" / "registry" / "fixtures"
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
    docker_cpu_limit: str = "2.0"
    docker_memory_limit: str = "2g"
    default_replications: int = 3
    warmup_duration_seconds: int = 3

class LLMConfig(BaseModel):
    """LLM provider configuration for Architecture Agent (supports OpenAI and Groq)."""
    openai_api_key: Optional[str] = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY") or os.getenv("GROQ_API_KEY"))
    openai_model_name: str = Field(default_factory=lambda: (
        os.getenv("OPENAI_MODEL_NAME") or (
            os.getenv("GROQ_MODEL_NAME") or os.getenv("OPENAI_MODEL_NAME") or ("openai/gpt-oss-120b" if (os.getenv("GROQ_API_KEY") or (os.getenv("OPENAI_API_KEY") or "").startswith("gsk_")) else "gpt-4o-mini")
        )
    ))
    openai_api_base: Optional[str] = Field(default_factory=lambda: (
        os.getenv("OPENAI_API_BASE") or (
            "https://api.groq.com/openai/v1" if (os.getenv("GROQ_API_KEY") or (os.getenv("OPENAI_API_KEY") or "").startswith("gsk_")) else None
        )
    ))
    temperature: float = Field(default=0.0, ge=0.0, le=1.0)
    timeout_seconds: float = Field(default=30.0, gt=0.0)
    max_retries: int = Field(default=2, ge=0)
    force_fallback: bool = Field(default_factory=lambda: os.getenv("AADS_FORCE_FALLBACK", "false").lower() in ("true", "1"))

class Settings(BaseModel):
    pricing: PricingConfig = PricingConfig()
    benchmark: BenchmarkConfig = BenchmarkConfig()
    llm: LLMConfig = LLMConfig()
    default_p95_target_ms: float = 60.0
    default_min_throughput_rps: float = 400.0
    default_max_budget_usd: float = 200.0
    random_seed: int = 42

settings = Settings()
