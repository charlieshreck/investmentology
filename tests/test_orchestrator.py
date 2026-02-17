from __future__ import annotations

import asyncio
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from investmentology.adversarial.munger import AdversarialResult, MungerVerdict
from investmentology.agents.base import AnalysisRequest, AnalysisResponse
from investmentology.agents.gateway import LLMGateway, LLMResponse
from investmentology.compatibility.matrix import CompatibilityResult
from investmentology.compatibility.patterns import CONVICTION_BUY
from investmentology.competence.circle import CompetenceResult
from investmentology.competence.moat import MoatAssessment
from investmentology.learning.registry import DecisionLogger
from investmentology.models.signal import AgentSignalSet, Signal, SignalSet, SignalTag
from investmentology.models.stock import FundamentalsSnapshot, Stock
from investmentology.orchestrator import (
    AnalysisOrchestrator,
    CandidateAnalysis,
    PipelineResult,
)
from investmentology.registry.queries import Registry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_snapshot(ticker: str = "AAPL") -> FundamentalsSnapshot:
    return FundamentalsSnapshot(
        ticker=ticker,
        fetched_at=datetime(2026, 2, 10),
        operating_income=Decimal("120e9"),
        market_cap=Decimal("3000e9"),
        total_debt=Decimal("100e9"),
        cash=Decimal("60e9"),
        current_assets=Decimal("150e9"),
        current_liabilities=Decimal("120e9"),
        net_ppe=Decimal("40e9"),
        revenue=Decimal("400e9"),
        net_income=Decimal("100e9"),
        total_assets=Decimal("350e9"),
        total_liabilities=Decimal("250e9"),
        shares_outstanding=15000000000,
        price=Decimal("200"),
    )


def _make_signal_set(agent_name: str, tags: list[SignalTag] | None = None) -> AgentSignalSet:
    if tags is None:
        tags = [SignalTag.UNDERVALUED]
    return AgentSignalSet(
        agent_name=agent_name,
        model="test-model",
        signals=SignalSet(
            signals=[Signal(tag=t, strength="moderate", detail="test") for t in tags]
        ),
        confidence=Decimal("0.75"),
        reasoning="Test reasoning",
    )


def _make_response(agent_name: str, ticker: str = "AAPL") -> AnalysisResponse:
    return AnalysisResponse(
        agent_name=agent_name,
        model="test-model",
        ticker=ticker,
        signal_set=_make_signal_set(agent_name),
        summary=f"{agent_name} analysis summary",
        latency_ms=500,
        token_usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    )


@pytest.fixture
def mock_registry() -> MagicMock:
    reg = MagicMock(spec=Registry)
    reg.get_latest_fundamentals.return_value = _make_snapshot()
    reg.get_active_stocks.return_value = [
        Stock(ticker="AAPL", name="Apple", sector="Technology",
              industry="Consumer Electronics", market_cap=Decimal("3000e9"), exchange="NASDAQ"),
    ]
    reg.insert_agent_signals.return_value = 1
    reg.get_latest_verdict.return_value = None
    reg._db = MagicMock()
    reg._db.execute.return_value = [
        {"combined_rank": 5, "piotroski_score": 8, "altman_z_score": Decimal("3.5")}
    ]
    return reg


@pytest.fixture
def mock_gateway() -> MagicMock:
    from investmentology.agents.gateway import ProviderConfig

    gw = MagicMock(spec=LLMGateway)
    gw.call = AsyncMock(return_value=LLMResponse(
        content='{"in_circle": true, "confidence": 0.8, "reasoning": "clear business", "sector_familiarity": "high"}',
        model="test", provider="test",
        token_usage={}, latency_ms=100,
    ))
    # Agent constructors check these dicts to resolve their provider
    gw._cli_providers = {}
    gw._providers = {
        "deepseek": ProviderConfig(name="deepseek", base_url="http://test", api_key="test", default_model="deepseek-reasoner"),
        "groq": ProviderConfig(name="groq", base_url="http://test", api_key="test", default_model="llama-3.3-70b-versatile"),
        "xai": ProviderConfig(name="xai", base_url="http://test", api_key="test", default_model="grok-3"),
        "anthropic": ProviderConfig(name="anthropic", base_url="http://test", api_key="test", default_model="claude-sonnet-4-5-20250929"),
    }
    return gw


@pytest.fixture
def mock_decision_logger() -> MagicMock:
    return MagicMock(spec=DecisionLogger)


@pytest.fixture
def orchestrator(
    mock_registry: MagicMock,
    mock_gateway: MagicMock,
    mock_decision_logger: MagicMock,
) -> AnalysisOrchestrator:
    return AnalysisOrchestrator(
        registry=mock_registry,
        gateway=mock_gateway,
        decision_logger=mock_decision_logger,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCandidateAnalysis:
    def test_defaults(self) -> None:
        ca = CandidateAnalysis(ticker="AAPL")
        assert ca.ticker == "AAPL"
        assert ca.final_action == "NO_ACTION"
        assert ca.final_confidence == Decimal("0")
        assert ca.agent_responses == []
        assert ca.passed_competence is False

    def test_with_fields(self) -> None:
        ca = CandidateAnalysis(
            ticker="MSFT",
            passed_competence=True,
            final_action="CONVICTION_BUY",
            final_confidence=Decimal("0.85"),
        )
        assert ca.passed_competence is True
        assert ca.final_action == "CONVICTION_BUY"


class TestPipelineResult:
    def test_defaults(self) -> None:
        pr = PipelineResult(candidates_in=10, passed_competence=0,
                           analyzed=0, conviction_buys=0, vetoed=0)
        assert pr.candidates_in == 10
        assert pr.results == []


class TestVerdictToAction:
    @pytest.mark.parametrize(
        "verdict_value, expected_action",
        [
            ("STRONG_BUY", "CONVICTION_BUY"),
            ("BUY", "CONVICTION_BUY"),
            ("ACCUMULATE", "WATCHLIST_EARLY"),
            ("HOLD", "HOLD"),
            ("WATCHLIST", "WATCHLIST_CATALYST"),
            ("REDUCE", "SELL"),
            ("SELL", "SELL"),
            ("AVOID", "REJECTED"),
            ("DISCARD", "HARD_REJECT"),
        ],
    )
    def test_verdict_maps_to_action(
        self, verdict_value: str, expected_action: str,
    ) -> None:
        from investmentology.verdict import Verdict, VerdictResult

        vr = VerdictResult(
            verdict=Verdict(verdict_value),
            confidence=Decimal("0.5"),
            reasoning="test",
        )
        assert AnalysisOrchestrator._verdict_to_action(vr) == expected_action


class TestActionToDecisionType:
    @pytest.mark.parametrize(
        "action, expected",
        [
            ("CONVICTION_BUY", "BUY"),
            ("BUY", "BUY"),
            ("REJECTED", "REJECT"),
            ("HARD_REJECT", "REJECT"),
            ("WATCHLIST_EARLY", "WATCHLIST"),
            ("NO_ACTION", "HOLD"),
            ("MANUAL_REVIEW", "AGENT_ANALYSIS"),
            ("UNKNOWN", "AGENT_ANALYSIS"),
        ],
    )
    def test_mapping(self, action: str, expected: str) -> None:
        dt = AnalysisOrchestrator._action_to_decision_type(action)
        assert dt.value == expected


class TestAnalyzeSingle:
    def test_no_fundamentals_returns_early(
        self, orchestrator: AnalysisOrchestrator, mock_registry: MagicMock,
    ) -> None:
        mock_registry.get_latest_fundamentals.return_value = None

        async def _run():
            result = await orchestrator._analyze_single("UNKNOWN", None, None, None)
            return result

        result = asyncio.run(_run())
        assert result.ticker == "UNKNOWN"
        assert result.final_action == "NO_ACTION"
        assert not result.passed_competence

    def test_competence_fail_continues_pipeline(
        self,
        orchestrator: AnalysisOrchestrator,
        mock_registry: MagicMock,
        mock_decision_logger: MagicMock,
    ) -> None:
        # Competence fail should NOT stop the pipeline — agents still run
        with patch.object(
            orchestrator._competence, "assess",
            new=AsyncMock(return_value=CompetenceResult(
                in_circle=False, confidence=Decimal("0.3"),
                reasoning="Too complex", sector_familiarity="low",
            )),
        ), patch.object(
            orchestrator._moat, "analyze",
            new=AsyncMock(return_value=MoatAssessment(
                moat_type="none", sources=[], trajectory="stable",
                durability_years=0, confidence=Decimal("0.3"), reasoning="n/a",
            )),
        ), patch.object(
            orchestrator._warren, "analyze",
            new=AsyncMock(return_value=_make_response("warren")),
        ), patch.object(
            orchestrator._soros, "analyze",
            new=AsyncMock(return_value=_make_response("soros")),
        ), patch.object(
            orchestrator._simons, "analyze",
            new=AsyncMock(return_value=_make_response("simons")),
        ), patch.object(
            orchestrator._auditor, "analyze",
            new=AsyncMock(return_value=_make_response("auditor")),
        ):
            result = asyncio.run(orchestrator._analyze_single("AAPL", None, None, None))

        assert result.passed_competence is False
        # Agents still ran despite competence fail
        assert len(result.agent_responses) == 4
        assert result.verdict is not None
        # Competence concern added as risk flag
        assert any("Outside Circle" in f for f in result.verdict.risk_flags)
        mock_decision_logger.log_competence_decision.assert_called_once()
        call_kwargs = mock_decision_logger.log_competence_decision.call_args.kwargs
        assert call_kwargs["passed"] is False
        assert call_kwargs["signals"]["in_circle"] is False

    def test_full_pipeline_with_agents(
        self,
        orchestrator: AnalysisOrchestrator,
        mock_registry: MagicMock,
        mock_decision_logger: MagicMock,
    ) -> None:
        # Mock competence to pass
        with patch.object(
            orchestrator._competence, "assess",
            new=AsyncMock(return_value=CompetenceResult(
                in_circle=True, confidence=Decimal("0.85"),
                reasoning="Clear business model", sector_familiarity="high",
            )),
        ), patch.object(
            orchestrator._moat, "analyze",
            new=AsyncMock(return_value=MoatAssessment(
                moat_type="wide", sources=["brand", "switching_costs"],
                trajectory="widening", durability_years=15,
                confidence=Decimal("0.8"), reasoning="Strong moat",
            )),
        ), patch.object(
            orchestrator._warren, "analyze",
            new=AsyncMock(return_value=_make_response("warren")),
        ), patch.object(
            orchestrator._soros, "analyze",
            new=AsyncMock(return_value=_make_response("soros")),
        ), patch.object(
            orchestrator._simons, "analyze",
            new=AsyncMock(return_value=_make_response("simons")),
        ), patch.object(
            orchestrator._auditor, "analyze",
            new=AsyncMock(return_value=_make_response("auditor")),
        ):
            result = asyncio.run(orchestrator._analyze_single("AAPL", None, None, None))

        assert result.passed_competence is True
        assert len(result.agent_responses) == 4
        assert len(result.agent_signal_sets) == 4
        assert result.compatibility is not None
        # Competence pass + analysis decisions should be logged
        assert mock_decision_logger.log_competence_decision.call_count == 1
        assert mock_decision_logger.log_analysis_decision.call_count >= 2  # L3 + L4


class TestAnalyzeCandidates:
    def test_batch_analysis(
        self,
        orchestrator: AnalysisOrchestrator,
        mock_registry: MagicMock,
    ) -> None:
        # Batch loop with competence fail — agents still run
        with patch.object(
            orchestrator._competence, "assess",
            new=AsyncMock(return_value=CompetenceResult(
                in_circle=False, confidence=Decimal("0.3"),
                reasoning="Out of circle", sector_familiarity="low",
            )),
        ), patch.object(
            orchestrator._moat, "analyze",
            new=AsyncMock(return_value=MoatAssessment(
                moat_type="none", sources=[], trajectory="stable",
                durability_years=0, confidence=Decimal("0.3"), reasoning="n/a",
            )),
        ), patch.object(
            orchestrator._warren, "analyze",
            new=AsyncMock(return_value=_make_response("warren")),
        ), patch.object(
            orchestrator._soros, "analyze",
            new=AsyncMock(return_value=_make_response("soros")),
        ), patch.object(
            orchestrator._simons, "analyze",
            new=AsyncMock(return_value=_make_response("simons")),
        ), patch.object(
            orchestrator._auditor, "analyze",
            new=AsyncMock(return_value=_make_response("auditor")),
        ):
            result = asyncio.run(
                orchestrator.analyze_candidates(["AAPL", "MSFT"])
            )

        assert result.candidates_in == 2
        assert len(result.results) == 2
        assert result.passed_competence == 0
        # All candidates get full analysis despite competence fail
        assert result.analyzed == 2

    def test_agent_failure_is_handled(
        self,
        orchestrator: AnalysisOrchestrator,
        mock_registry: MagicMock,
    ) -> None:
        with patch.object(
            orchestrator._competence, "assess",
            new=AsyncMock(return_value=CompetenceResult(
                in_circle=True, confidence=Decimal("0.85"),
                reasoning="Clear", sector_familiarity="high",
            )),
        ), patch.object(
            orchestrator._moat, "analyze",
            new=AsyncMock(return_value=MoatAssessment(
                moat_type="wide", sources=["brand"],
                trajectory="stable", durability_years=10,
                confidence=Decimal("0.7"), reasoning="ok",
            )),
        ), patch.object(
            orchestrator._warren, "analyze",
            new=AsyncMock(side_effect=RuntimeError("LLM timeout")),
        ), patch.object(
            orchestrator._soros, "analyze",
            new=AsyncMock(return_value=_make_response("soros")),
        ), patch.object(
            orchestrator._simons, "analyze",
            new=AsyncMock(side_effect=RuntimeError("Rate limited")),
        ), patch.object(
            orchestrator._auditor, "analyze",
            new=AsyncMock(return_value=_make_response("auditor")),
        ):
            result = asyncio.run(
                orchestrator.analyze_candidates(["AAPL"])
            )

        assert result.analyzed == 1
        # Only 2 of 4 agents succeeded
        assert len(result.results[0].agent_responses) == 2
