"""
Unit Tests for AADS Workload Parser & Ambiguity Ranking Engine (Phase 5.3C.1).
Verifies DAU/MAU to RPS conversions, threshold-based ambiguity evaluation,
bounded clarification dialogue, and strict isolation of user facts from agent assumptions.
"""
import pytest
from aads.agent.architecture_agent import (
    ArchitectureAgent,
    parse_natural_traffic,
    rank_and_evaluate_ambiguity,
)


class TestNaturalTrafficParsing:
    def test_parse_200k_dau(self):
        text = "photo sharing app targeting around 200K active daily users"
        res = parse_natural_traffic(text)
        assert res is not None
        avg_rps, peak_rps, explanation = res
        assert avg_rps == pytest.approx(57.9, abs=0.5)
        assert peak_rps == pytest.approx(173.7, abs=1.0)
        assert "200,000 active daily users" in explanation

    def test_parse_50k_daily_active_users(self):
        text = "backend for 50,000 daily active users"
        res = parse_natural_traffic(text)
        assert res is not None
        avg_rps, peak_rps, _ = res
        assert avg_rps == pytest.approx(14.5, abs=0.5)
        assert peak_rps == pytest.approx(43.4, abs=1.0)

    def test_parse_1m_mau(self):
        text = "system expected to handle 1M MAU"
        res = parse_natural_traffic(text)
        assert res is not None
        avg_rps, peak_rps, explanation = res
        # 1M MAU * 20% stickiness = 200K DAU equivalent
        assert avg_rps == pytest.approx(57.9, abs=0.5)
        assert "assuming 20% DAU/MAU stickiness" in explanation

    def test_returns_none_when_no_traffic_mentioned(self):
        text = "build a secure api gateway"
        assert parse_natural_traffic(text) is None


class TestAmbiguityRankingAndThreshold:
    def test_vague_prompt_triggers_ranked_questions(self):
        score, questions = rank_and_evaluate_ambiguity(
            has_throughput=False,
            has_latency=False,
            has_budget=False,
            has_read_write=False,
            threshold=0.50,
        )
        assert score == 1.0
        assert len(questions) == 3
        # Rank 1 must be Throughput (0.40)
        assert "throughput" in questions[0].lower() or "user volume" in questions[0].lower()
        # Rank 2 must be Latency (0.30)
        assert "latency" in questions[1].lower() or "sla" in questions[1].lower()
        # Rank 3 must be Budget (0.20)
        assert "budget" in questions[2].lower()

    def test_fully_specified_prompt_has_zero_questions(self):
        score, questions = rank_and_evaluate_ambiguity(
            has_throughput=True,
            has_latency=True,
            has_budget=True,
            has_read_write=True,
            threshold=0.50,
        )
        assert score == 0.0
        assert len(questions) == 0

    def test_photo_app_200k_dau_ranks_sla_and_budget(self):
        # Throughput is derived (True), Read/Write is feed domain (True)
        # Missing Latency (0.30) + Budget (0.20) = 0.50
        score, questions = rank_and_evaluate_ambiguity(
            has_throughput=True,
            has_latency=False,
            has_budget=False,
            has_read_write=True,
            threshold=0.50,
        )
        assert score == 0.50
        assert len(questions) == 2
        assert "latency" in questions[0].lower()
        assert "budget" in questions[1].lower()


class TestArchitectureAgentFallbackParse:
    @pytest.fixture
    def agent(self):
        return ArchitectureAgent()

    def test_user_facts_never_contain_agent_assumptions(self, agent):
        """Zero Assumption Leakage: user_facts property must only return verified facts."""
        prompt = "I want a photo sharing backend"
        res = agent.fallback_parse(prompt, already_clarified=True)
        
        # When clarified, default assumptions are used
        assert res.request_rate_rps == 500.0
        assert res.p95_latency_target_ms == 50.0
        assert res.max_monthly_budget_usd == 250.0

        # But user_facts must NOT claim the user provided these numbers!
        assert "request_rate_rps" not in res.user_facts
        assert "p95_latency_target_ms" not in res.user_facts
        assert "max_monthly_budget_usd" not in res.user_facts

        # Instead, they must be recorded in agent_assumptions
        assump_text = " ".join(res.agent_assumptions)
        assert "Default load assumed: 500.0 RPS" in assump_text
        assert "Default p95 latency target assumed: 50.0 ms" in assump_text

    def test_photo_app_200k_dau_end_to_end_clarification(self, agent):
        prompt = (
            "I want a backend for a photo sharing app that targets around 200K active daily users, "
            "where people share photos with a wide range of followers with features to like comment "
            "share those images, people also have option to have feed and follow each other"
        )
        res = agent.fallback_parse(prompt, already_clarified=False)
        
        # Throughput was derived from 200K DAU
        assert res.request_rate_rps == pytest.approx(57.9, abs=0.5)
        assert "request_rate_rps" in res.user_facts
        
        # Ambiguity threshold (0.50) was reached: asked for SLA and budget
        assert len(res.clarification_questions) == 2
        assert "latency" in res.clarification_questions[0].lower()
        assert "budget" in res.clarification_questions[1].lower()

    def test_bounded_dialogue_prevents_infinite_clarification_loop(self, agent):
        prompt = "I want a photo sharing backend with 200K active daily users"
        
        # Turn 1: asks clarification
        turn1 = agent.fallback_parse(prompt, already_clarified=False)
        assert len(turn1.clarification_questions) == 2

        # Turn 2: user proceeded without answering SLA/budget -> already_clarified=True
        turn2 = agent.fallback_parse(prompt, already_clarified=True)
        # Must not ask again!
        assert len(turn2.clarification_questions) == 0
        assert turn2.p95_latency_target_ms == 50.0
        assert turn2.max_monthly_budget_usd == 250.0
        assert "Default p95 latency target assumed" in " ".join(turn2.agent_assumptions)


class TestDynamicDomainAndArchetypeClassification:
    @pytest.fixture
    def agent(self):
        return ArchitectureAgent()

    def test_hotel_rating_app_with_maps(self, agent):
        prompt = "I want a backend for a hotel rating app with maps that targets around 50K users"
        res = agent.fallback_parse(prompt, already_clarified=True)

        assert res.app_type == "hotel_rating_app_with_maps"
        assert res.read_ratio == 0.90
        assert res.write_ratio == 0.10
        assumptions = " ".join(res.agent_assumptions)
        assert "READ_HEAVY_INTERACTIVE" in assumptions

    def test_education_platform_with_ai_video(self, agent):
        prompt = "building an education platform with user generated AI videos that targets 10K students"
        res = agent.fallback_parse(prompt, already_clarified=True)

        assert res.app_type == "education_platform_with_user_generated_ai_videos"
        assert res.read_ratio == 0.20
        assert res.write_ratio == 0.80
        assumptions = " ".join(res.agent_assumptions)
        assert "DECOUPLED_ASYNC_COMPUTE" in assumptions

    def test_banking_ledger_transactional(self, agent):
        prompt = "Write-heavy transactional workload with 150 RPS for banking payments"
        res = agent.fallback_parse(prompt, already_clarified=True)

        assert res.app_type == "transactional"
        assert res.read_ratio == 0.40
        assert res.write_ratio == 0.60
        assumptions = " ".join(res.agent_assumptions)
        assert "TRANSACTIONAL_OLTP" in assumptions
