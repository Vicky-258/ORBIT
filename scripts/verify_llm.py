#!/usr/bin/env python3
"""
AADS: Explicit Opt-In Live LLM Connectivity Verification.
Sends a single minimal bounded request to the configured LLM provider
to verify API credentials, network reachability, and structured output extraction.

Usage:
    python scripts/verify_llm.py
    python run_demo.py --verify-llm

Note: This command makes an external API request and may incur minor API charges.
"""
import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aads.agent.provider import verify_live_llm


def main():
    print("=" * 65)
    print("🤖 AADS: Opt-In Live LLM Connectivity Verification")
    print("=" * 65)
    print("  Notice: This command initiates an actual outbound network request")
    print("  to the configured LLM provider and may incur minor token charges.\n")

    result = verify_live_llm()

    status = result.get("status", "UNKNOWN")
    provider = result.get("provider", "Unknown")
    model_name = result.get("model_name", "Unknown")
    latency = result.get("latency_seconds", 0.0)

    print(f"  • Verification Status : {status}")
    print(f"  • Provider / Model    : {provider} / {model_name}")
    print(f"  • Latency             : {latency:.3f}s")

    if result.get("success"):
        print("\n  ✅ SUCCESS: Live LLM connectivity verified successfully!")
        print("  Structured Fields Extracted:")
        for k, v in result.get("extracted_fields", {}).items():
            print(f"    - {k:22s}: {v}")
        if result.get("note"):
            print(f"\n  ℹ Note: {result.get('note')}")
        sys.exit(0)
    else:
        print("\n  ❌ VERIFICATION FAILED:")
        print(f"    • Error Details : {result.get('error_message')}")
        if result.get("instructions"):
            print(f"    • Remediation   : {result.get('instructions')}")
        
        # Exit code convention: 1 for missing credentials, 2 for provider/network error
        exit_code = 1 if status == "MISSING_CREDENTIALS" else 2
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
