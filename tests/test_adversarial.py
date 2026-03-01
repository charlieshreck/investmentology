from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from investmentology.adversarial.biases import (
    COGNITIVE_BIASES,
    BiasCheck,
    check_biases_in_reasoning,
)
from investmentology.adversarial.kill_company import (
    KillScenario,
    build_kill_company_prompt,
    parse_kill_scenarios,
)
from investmentology.adversarial.munger import (
    AdversarialResult,
    MungerOrchestrator,
    MungerVerdict,
    PATTERN_CONVICTION_BUY,
)
from investmentology.adversarial.premortem import (
    PreMortemResult,
    build_premortem_prompt,
    parse_premortem,
)
from investmentology.agents.gateway import LLMGateway, LLMResponse
from investmentology.competence.circle import CompetenceFilter, CompetenceResult
from investmentology.competence.moat import MoatAnalyzer, MoatAssessment
from investmentology.models.signal import AgentSignalSet, Signal, SignalSet, SignalTag
from investmentology.models.stock import FundamentalsSnapshot


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_snapshot(**overrides) -> FundamentalsSnapshot:
    defaults = dict(
        ticker="AAPL",
        fetched_at=datetime(2025, 1, 15, 12, 0, 0),
        operating_income=Decimal("100000"),
        market_cap=Decimal("500000"),
        total_debt=Decimal("50000"),
        cash=Decimal("30000"),
        current_assets=Decimal("80000"),
        current_liabilities=Decimal("40000"),
        net_ppe=Decimal("60000"),
        revenue=Decimal("400000"),
        net_income=Decimal("80000"),
        total_assets=Decimal("300000"),
        total_liabilities=Decimal("150000"),
        shares_outstanding=1000,
        price=Decimal("500"),
    )
    defaults.update(overrides)
    return FundamentalsSnapshot(**defaults)


def _make_signal_set(
    agent_name: str = "test_agent",
    confidence: str = "0.80",
    tags: list[SignalTag] | None = None,
    reasoning: str = "Test reasoning",
) -> AgentSignalSet:
    if tags is None:
        tags = [SignalTag.UNDERVALUED]
    signals = [Signal(tag=t, strength="strong", detail="test") for t in tags]
    return AgentSignalSet(
        agent_name=agent_name,
        model="test-model",
        signals=SignalSet(signals=signals),
        confidence=Decimal(confidence),
        reasoning=reasoning,
    )


def _mock_llm_response(content: str) -> LLMResponse:
    return LLMResponse(
        content=content,
        model="test-model",
        provider="test",
        token_usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        latency_ms=500,
    )


def _mock_gateway() -> LLMGateway:
    gw = MagicMock(spec=LLMGateway)
    gw.call = AsyncMock()
    return gw


# ---------------------------------------------------------------------------
# BiasCheck: at least 15 biases defined
# ---------------------------------------------------------------------------


class TestBiasChecks:
    def test_at_least_15_biases_defined(self):
        assert len(COGNITIVE_BIASES) >= 15

    def test_all_biases_have_required_fields(self):
        for bias in COGNITIVE_BIASES:
            assert isinstance(bias, BiasCheck)
            assert bias.name
            assert bias.description
            assert bias.check_question
            assert isinstance(bias.red_flag_keywords, list)
            assert len(bias.red_flag_keywords) > 0

    def test_bias_names_unique(self):
        names = [b.name for b in COGNITIVE_BIASES]
        assert len(names) == len(set(names)), "Bias names must be unique"


# ---------------------------------------------------------------------------
# check_biases_in_reasoning: detects confirmation bias keywords
# ---------------------------------------------------------------------------


class TestCheckBiases:
    def test_detects_confirmation_bias(self):
        reasoning = "The data confirms our thesis that AAPL is undervalued."
        results = check_biases_in_reasoning(reasoning, {})

        confirmation_results = [r for r in results if r.bias_name == "Confirmation Bias"]
        assert len(confirmation_results) == 1
        assert confirmation_results[0].is_flagged is True
        assert "confirms" in confirmation_results[0].detail.lower()

    def test_detects_overconfidence(self):
        reasoning = "This is a guaranteed winner, can't lose on this one."
        results = check_biases_in_reasoning(reasoning, {})

        overconf = [r for r in results if r.bias_name == "Overconfidence"]
        assert len(overconf) == 1
        assert overconf[0].is_flagged is True

    def test_no_biases_in_clean_reasoning(self):
        reasoning = "The company has strong fundamentals with growing revenue and healthy margins."
        results = check_biases_in_reasoning(reasoning, {})

        flagged = [r for r in results if r.is_flagged]
        assert len(flagged) == 0

    def test_returns_result_for_every_bias(self):
        results = check_biases_in_reasoning("some text", {})
        assert len(results) == len(COGNITIVE_BIASES)

    def test_case_insensitive_matching(self):
        reasoning = "CONFIRMS our thesis. GUARANTEED returns."
        results = check_biases_in_reasoning(reasoning, {})

        flagged_names = {r.bias_name for r in results if r.is_flagged}
        assert "Confirmation Bias" in flagged_names
        assert "Overconfidence" in flagged_names

    def test_multiple_biases_detected(self):
        reasoning = (
            "Everyone is buying this stock and it confirms our thesis. "
            "The analyst says it's a guaranteed 10x potential."
        )
        results = check_biases_in_reasoning(reasoning, {})
        flagged = [r for r in results if r.is_flagged]
        assert len(flagged) >= 3  # Social proof, confirmation, overconfidence, authority, denominator


# ---------------------------------------------------------------------------
# Kill Company
# ---------------------------------------------------------------------------


class TestKillCompany:
    def test_prompt_includes_ticker_and_sector(self):
        prompt = build_kill_company_prompt("AAPL", "Technology", "Strong financials")
        assert "AAPL" in prompt
        assert "Technology" in prompt
        assert "Strong financials" in prompt

    def test_prompt_asks_for_5_scenarios(self):
        prompt = build_kill_company_prompt("MSFT", "Technology", "summary")
        assert "5" in prompt

    def test_parse_kill_scenarios_valid_json(self):
        raw = json.dumps([
            {
                "scenario": "Apple loses iPhone market share to Chinese competitors",
                "likelihood": "medium",
                "impact": "severe",
                "timeframe": "3-5 years",
            },
            {
                "scenario": "Antitrust regulation forces App Store changes",
                "likelihood": "high",
                "impact": "moderate",
                "timeframe": "1-2 years",
            },
        ])
        scenarios = parse_kill_scenarios(raw)
        assert len(scenarios) == 2
        assert isinstance(scenarios[0], KillScenario)
        assert scenarios[0].likelihood == "medium"
        assert scenarios[0].impact == "severe"
        assert scenarios[1].likelihood == "high"

    def test_parse_kill_scenarios_with_markdown_wrapper(self):
        raw = """Here are the scenarios:
```json
[
  {"scenario": "Competition", "likelihood": "high", "impact": "fatal", "timeframe": "3-5 years"}
]
```
"""
        scenarios = parse_kill_scenarios(raw)
        assert len(scenarios) == 1
        assert scenarios[0].impact == "fatal"

    def test_parse_kill_scenarios_invalid_json(self):
        scenarios = parse_kill_scenarios("This is not JSON at all.")
        assert scenarios == []

    def test_parse_kill_scenarios_defaults(self):
        raw = json.dumps([{"scenario": "Generic risk"}])
        scenarios = parse_kill_scenarios(raw)
        assert len(scenarios) == 1
        assert scenarios[0].likelihood == "medium"
        assert scenarios[0].impact == "moderate"
        assert scenarios[0].timeframe == "3-5 years"


# ---------------------------------------------------------------------------
# Pre-Mortem
# ---------------------------------------------------------------------------


class TestPreMortem:
    def test_prompt_includes_ticker_and_thesis(self):
        prompt = build_premortem_prompt("AAPL", "Undervalued with strong moat", "150.00")
        assert "AAPL" in prompt
        assert "Undervalued with strong moat" in prompt
        assert "150.00" in prompt

    def test_parse_premortem_valid(self):
        raw = json.dumps({
            "narrative": "It's 2028 and AAPL lost 50% due to China ban.",
            "key_risks": ["China ban", "iPhone commoditization", "Services slowdown"],
            "probability_estimate": "possible",
        })
        result = parse_premortem(raw)
        assert isinstance(result, PreMortemResult)
        assert "2028" in result.narrative
        assert len(result.key_risks) == 3
        assert result.probability_estimate == "possible"

    def test_parse_premortem_invalid_json(self):
        result = parse_premortem("Just a plain text response with no JSON.")
        assert isinstance(result, PreMortemResult)
        assert result.narrative != ""
        assert result.key_risks == []
        assert result.probability_estimate == "unknown"


# ---------------------------------------------------------------------------
# MungerOrchestrator.should_trigger
# ---------------------------------------------------------------------------


class TestMungerShouldTrigger:
    def test_triggers_on_conviction_buy_pattern(self):
        gw = _mock_gateway()
        orch = MungerOrchestrator(gw)

        signals = [_make_signal_set()]
        assert orch.should_trigger(signals, pattern_name=PATTERN_CONVICTION_BUY) is True

    def test_triggers_on_unanimity(self):
        """All agents high confidence + all bullish = suspicious unanimity."""
        gw = _mock_gateway()
        orch = MungerOrchestrator(gw)

        signals = [
            _make_signal_set("warren", "0.90", [SignalTag.BUY_NEW]),
            _make_signal_set("soros", "0.85", [SignalTag.BUY_NEW]),
            _make_signal_set("simons", "0.88", [SignalTag.BUY_ADD]),
            _make_signal_set("auditor", "0.82", [SignalTag.BUY_NEW]),
        ]
        assert orch.should_trigger(signals) is True

    def test_no_trigger_on_mixed_signals(self):
        """Agents disagree on direction -- no unanimity trigger."""
        gw = _mock_gateway()
        orch = MungerOrchestrator(gw)

        signals = [
            _make_signal_set("warren", "0.90", [SignalTag.BUY_NEW]),
            _make_signal_set("soros", "0.50", [SignalTag.HOLD]),
            _make_signal_set("simons", "0.60", [SignalTag.SELL_FULL]),
        ]
        assert orch.should_trigger(signals) is False

    def test_no_trigger_on_low_confidence(self):
        """All agree but low confidence -- no trigger."""
        gw = _mock_gateway()
        orch = MungerOrchestrator(gw)

        signals = [
            _make_signal_set("warren", "0.50", [SignalTag.BUY_NEW]),
            _make_signal_set("soros", "0.55", [SignalTag.BUY_NEW]),
        ]
        assert orch.should_trigger(signals) is False

    def test_triggers_on_dangerous_disagreement(self):
        """Warren bullish but Auditor flags risk."""
        gw = _mock_gateway()
        orch = MungerOrchestrator(gw)

        signals = [
            _make_signal_set("warren", "0.90", [SignalTag.BUY_NEW]),
            _make_signal_set("auditor", "0.70", [SignalTag.ACCOUNTING_RED_FLAG]),
        ]
        assert orch.should_trigger(signals) is True

    def test_dangerous_disagreement_warren_sell_no_trigger(self):
        """Warren is selling, Auditor flags risk -- not dangerous disagreement."""
        gw = _mock_gateway()
        orch = MungerOrchestrator(gw)

        signals = [
            _make_signal_set("warren", "0.90", [SignalTag.SELL_FULL]),
            _make_signal_set("auditor", "0.70", [SignalTag.ACCOUNTING_RED_FLAG]),
        ]
        # No unanimity (not all BUY), no conviction_buy pattern, no dangerous disagreement (warren not bullish)
        assert orch.should_trigger(signals) is False

    def test_single_agent_no_trigger(self):
        gw = _mock_gateway()
        orch = MungerOrchestrator(gw)
        signals = [_make_signal_set("warren", "0.95", [SignalTag.BUY_NEW])]
        # Can't have unanimity with single agent
        assert orch.should_trigger(signals) is False


# ---------------------------------------------------------------------------
# MungerOrchestrator.review: returns AdversarialResult (mock gateway)
# ---------------------------------------------------------------------------


class TestMungerReview:
    @pytest.mark.asyncio
    async def test_review_returns_adversarial_result(self):
        gw = _mock_gateway()

        kill_json = json.dumps([
            {
                "scenario": "Competition destroys margins",
                "likelihood": "medium",
                "impact": "severe",
                "timeframe": "3-5 years",
            }
        ])
        premortem_json = json.dumps({
            "narrative": "AAPL lost 50% due to margin compression",
            "key_risks": ["margin pressure", "China risk"],
            "probability_estimate": "possible",
        })

        gw.call.side_effect = [
            _mock_llm_response(kill_json),
            _mock_llm_response(premortem_json),
        ]

        orch = MungerOrchestrator(gw)
        signals = [
            _make_signal_set("warren", "0.90", [SignalTag.BUY_NEW]),
        ]

        result = await orch.review(
            ticker="AAPL",
            fundamentals_summary="Strong financials",
            thesis="Undervalued with wide moat",
            agent_signals=signals,
        )

        assert isinstance(result, AdversarialResult)
        assert result.verdict in list(MungerVerdict)
        assert isinstance(result.bias_flags, list)
        assert isinstance(result.kill_scenarios, list)
        assert len(result.kill_scenarios) == 1
        assert result.premortem is not None
        assert result.reasoning

    @pytest.mark.asyncio
    async def test_review_no_premortem_on_low_confidence(self):
        gw = _mock_gateway()

        kill_json = json.dumps([
            {"scenario": "Minor risk", "likelihood": "low", "impact": "moderate", "timeframe": "5+ years"}
        ])

        gw.call.return_value = _mock_llm_response(kill_json)

        orch = MungerOrchestrator(gw)
        signals = [
            _make_signal_set("warren", "0.50", [SignalTag.HOLD]),
        ]

        result = await orch.review(
            ticker="AAPL",
            fundamentals_summary="OK financials",
            thesis="Neutral outlook",
            agent_signals=signals,
        )

        assert isinstance(result, AdversarialResult)
        assert result.premortem is None
        # Only 1 call (kill company), no premortem
        assert gw.call.call_count == 1

    @pytest.mark.asyncio
    async def test_review_veto_on_severe_findings(self):
        gw = _mock_gateway()

        kill_json = json.dumps([
            {"scenario": "Fatal flaw", "likelihood": "high", "impact": "fatal", "timeframe": "1-2 years"},
        ])
        premortem_json = json.dumps({
            "narrative": "Total disaster",
            "key_risks": ["fatal flaw"],
            "probability_estimate": "likely",
        })

        gw.call.side_effect = [
            _mock_llm_response(kill_json),
            _mock_llm_response(premortem_json),
        ]

        orch = MungerOrchestrator(gw)
        # Use reasoning with many bias triggers
        signals = [
            _make_signal_set(
                "warren", "0.95", [SignalTag.BUY_NEW],
                reasoning=(
                    "This confirms our thesis. Everyone is buying. "
                    "Guaranteed returns. Can't lose. The analyst says "
                    "10x potential. It's a sure thing."
                ),
            ),
        ]

        result = await orch.review(
            ticker="AAPL",
            fundamentals_summary="Weak",
            thesis="Speculative",
            agent_signals=signals,
        )

        assert result.verdict == MungerVerdict.VETO


# ---------------------------------------------------------------------------
# MungerVerdict enum
# ---------------------------------------------------------------------------


class TestMungerVerdict:
    def test_values(self):
        assert MungerVerdict.PROCEED == "PROCEED"
        assert MungerVerdict.CAUTION == "CAUTION"
        assert MungerVerdict.VETO == "VETO"


# ---------------------------------------------------------------------------
# CompetenceFilter: returns CompetenceResult (mock gateway)
# ---------------------------------------------------------------------------


class TestCompetenceFilter:
    @pytest.mark.asyncio
    async def test_assess_returns_competence_result(self):
        gw = _mock_gateway()
        response_json = json.dumps({
            "in_circle": True,
            "confidence": 0.85,
            "reasoning": "Consumer electronics is well understood",
            "sector_familiarity": "high",
        })
        gw.call.return_value = _mock_llm_response(response_json)

        filt = CompetenceFilter(gw)
        result = await filt.assess(
            ticker="AAPL",
            sector="Technology",
            industry="Consumer Electronics",
            business_description="Designs and sells consumer electronics and services.",
        )

        assert isinstance(result, CompetenceResult)
        assert result.in_circle is True
        assert result.confidence == Decimal("0.85")
        assert result.sector_familiarity == "high"
        assert result.reasoning

    @pytest.mark.asyncio
    async def test_assess_out_of_circle(self):
        gw = _mock_gateway()
        response_json = json.dumps({
            "in_circle": False,
            "confidence": 0.4,
            "reasoning": "Biotech drug development is too complex to predict",
            "sector_familiarity": "low",
        })
        gw.call.return_value = _mock_llm_response(response_json)

        filt = CompetenceFilter(gw)
        result = await filt.assess(
            ticker="MRNA",
            sector="Healthcare",
            industry="Biotechnology",
            business_description="Develops mRNA therapeutics and vaccines.",
        )

        assert result.in_circle is False
        assert result.sector_familiarity == "low"

    @pytest.mark.asyncio
    async def test_assess_handles_bad_response(self):
        gw = _mock_gateway()
        gw.call.return_value = _mock_llm_response("Not valid JSON at all")

        filt = CompetenceFilter(gw)
        result = await filt.assess(
            ticker="XYZ",
            sector="Unknown",
            industry="Unknown",
            business_description="Unclear business",
        )

        assert isinstance(result, CompetenceResult)
        assert result.in_circle is False
        assert result.sector_familiarity == "low"


# ---------------------------------------------------------------------------
# MoatAnalyzer: returns MoatAssessment (mock gateway)
# ---------------------------------------------------------------------------


class TestMoatAnalyzer:
    @pytest.mark.asyncio
    async def test_analyze_returns_moat_assessment(self):
        gw = _mock_gateway()
        response_json = json.dumps({
            "moat_type": "wide",
            "sources": ["brand", "switching_costs", "network_effects"],
            "trajectory": "stable",
            "durability_years": 15,
            "confidence": 0.8,
            "reasoning": "Apple ecosystem creates strong switching costs",
        })
        gw.call.return_value = _mock_llm_response(response_json)

        analyzer = MoatAnalyzer(gw)
        snap = _make_snapshot()
        result = await analyzer.analyze(
            ticker="AAPL",
            sector="Technology",
            fundamentals=snap,
        )

        assert isinstance(result, MoatAssessment)
        assert result.moat_type == "wide"
        assert "brand" in result.sources
        assert "switching_costs" in result.sources
        assert result.trajectory == "stable"
        assert result.durability_years == 15
        assert result.confidence == Decimal("0.8")
        assert result.reasoning

    @pytest.mark.asyncio
    async def test_analyze_narrow_moat(self):
        gw = _mock_gateway()
        response_json = json.dumps({
            "moat_type": "narrow",
            "sources": ["cost_advantages"],
            "trajectory": "narrowing",
            "durability_years": 5,
            "confidence": 0.6,
            "reasoning": "Cost advantages being eroded by competition",
        })
        gw.call.return_value = _mock_llm_response(response_json)

        analyzer = MoatAnalyzer(gw)
        snap = _make_snapshot()
        result = await analyzer.analyze(
            ticker="WMT",
            sector="Consumer Staples",
            fundamentals=snap,
        )

        assert result.moat_type == "narrow"
        assert result.trajectory == "narrowing"

    @pytest.mark.asyncio
    async def test_analyze_handles_bad_response(self):
        gw = _mock_gateway()
        gw.call.return_value = _mock_llm_response("Unable to process request")

        analyzer = MoatAnalyzer(gw)
        snap = _make_snapshot()
        result = await analyzer.analyze(
            ticker="XYZ",
            sector="Unknown",
            fundamentals=snap,
        )

        assert isinstance(result, MoatAssessment)
        assert result.moat_type == "none"
        assert result.sources == []
