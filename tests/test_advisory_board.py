"""Tests for the Advisory Board (L5.5) and CIO Synthesis (L6).

Tests cover:
  - Dataclass construction (AdvisorOpinion, BoardNarrative, BoardResult)
  - Pair response parsing (valid JSON, markdown fences, malformed, missing keys)
  - Vote synthesis (8 approve, 5 adjust up, 3 veto, mixed)
  - Verdict shift up/down and boundary conditions
  - CIO narrative generation
  - Full convene() with mocked gateway
  - Graceful degradation (pair failures)
"""

from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from investmentology.advisory.board import (
    BOARD_MEMBERS,
    PAIR_CONFIG,
    AdvisoryBoard,
    _build_system_prompt,
    _build_user_prompt,
    _parse_pair_response,
    _shift_verdict,
    _synthesize_votes,
    _verdict_index,
)
from investmentology.advisory.cio import (
    CIOSynthesizer,
    _build_cio_system_prompt,
    _build_cio_user_prompt,
    _fallback_narrative,
    _parse_cio_response,
)
from investmentology.advisory.models import (
    AdvisorOpinion,
    BoardNarrative,
    BoardResult,
    BoardVote,
)
from investmentology.agents.gateway import LLMResponse
from investmentology.verdict import AgentStance, Verdict, VerdictResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_verdict(verdict: str = "BUY", confidence: float = 0.7, score: float = 0.4) -> VerdictResult:
    return VerdictResult(
        verdict=Verdict(verdict),
        confidence=Decimal(str(confidence)),
        reasoning="Test reasoning",
        consensus_score=score,
        agent_stances=[
            AgentStance(name="warren", sentiment=0.6, confidence=Decimal("0.8"),
                        key_signals=["UNDERVALUED (strong)"], summary="Good value"),
            AgentStance(name="soros", sentiment=0.3, confidence=Decimal("0.7"),
                        key_signals=["REGIME_BULL (moderate)"], summary="Macro ok"),
        ],
    )


def _make_opinion(
    name: str = "dalio",
    display: str = "Ray Dalio",
    vote: BoardVote = BoardVote.APPROVE,
    confidence: float = 0.75,
) -> AdvisorOpinion:
    return AdvisorOpinion(
        advisor_name=name,
        display_name=display,
        vote=vote,
        confidence=Decimal(str(confidence)),
        assessment="Test assessment",
        key_concern="Some concern",
        key_endorsement="Some positive",
        reasoning="Test reasoning from this advisor",
    )


def _make_llm_response(content: str, model: str = "test-model") -> LLMResponse:
    return LLMResponse(
        content=content,
        model=model,
        provider="test",
        token_usage={},
        latency_ms=1000,
    )


# ---------------------------------------------------------------------------
# Test BoardVote Enum
# ---------------------------------------------------------------------------

class TestBoardVote:
    def test_all_values(self) -> None:
        assert set(BoardVote) == {
            BoardVote.APPROVE, BoardVote.ADJUST_UP,
            BoardVote.ADJUST_DOWN, BoardVote.VETO,
        }

    def test_is_str_enum(self) -> None:
        assert BoardVote.APPROVE == "APPROVE"
        assert str(BoardVote.VETO) == "VETO"


# ---------------------------------------------------------------------------
# Test AdvisorOpinion Dataclass
# ---------------------------------------------------------------------------

class TestAdvisorOpinion:
    def test_construction(self) -> None:
        op = _make_opinion()
        assert op.advisor_name == "dalio"
        assert op.vote == BoardVote.APPROVE
        assert op.confidence == Decimal("0.75")

    def test_defaults(self) -> None:
        op = AdvisorOpinion(
            advisor_name="test", display_name="Test", vote=BoardVote.APPROVE,
            confidence=Decimal("0.5"), assessment="ok",
        )
        assert op.reasoning == ""
        assert op.specific_numbers == {}
        assert op.model == ""
        assert op.latency_ms == 0


# ---------------------------------------------------------------------------
# Test BoardNarrative Dataclass
# ---------------------------------------------------------------------------

class TestBoardNarrative:
    def test_construction(self) -> None:
        bn = BoardNarrative(
            headline="BUY with caution",
            narrative="Paragraph text",
            risk_summary="Macro risk",
            pre_mortem="If wrong because...",
            conflict_resolution="Reconciled by...",
        )
        assert bn.headline == "BUY with caution"
        assert bn.verdict_adjustment == 0
        assert bn.adjusted_verdict is None

    def test_with_adjustment(self) -> None:
        bn = BoardNarrative(
            headline="h", narrative="n", risk_summary="r",
            pre_mortem="p", conflict_resolution="c",
            verdict_adjustment=-1, adjusted_verdict="ACCUMULATE",
        )
        assert bn.verdict_adjustment == -1
        assert bn.adjusted_verdict == "ACCUMULATE"


# ---------------------------------------------------------------------------
# Test BoardResult Dataclass
# ---------------------------------------------------------------------------

class TestBoardResult:
    def test_defaults(self) -> None:
        br = BoardResult()
        assert br.opinions == []
        assert br.narrative is None
        assert br.original_verdict == ""
        assert not br.verdict_changed

    def test_verdict_changed(self) -> None:
        br = BoardResult(original_verdict="BUY", adjusted_verdict="ACCUMULATE")
        assert br.verdict_changed

    def test_verdict_not_changed_when_same(self) -> None:
        br = BoardResult(original_verdict="BUY", adjusted_verdict="BUY")
        assert not br.verdict_changed

    def test_verdict_not_changed_when_none(self) -> None:
        br = BoardResult(original_verdict="BUY", adjusted_verdict=None)
        assert not br.verdict_changed


# ---------------------------------------------------------------------------
# Test Board Members Configuration
# ---------------------------------------------------------------------------

class TestBoardMembers:
    def test_eight_members(self) -> None:
        assert len(BOARD_MEMBERS) == 8

    def test_all_have_required_fields(self) -> None:
        for key, spec in BOARD_MEMBERS.items():
            assert spec.key == key
            assert spec.display_name
            assert spec.philosophy
            assert spec.data_focus
            assert spec.evaluation_criteria
            assert spec.bias_warning
            assert spec.vote_tendency
            assert spec.signature_question

    def test_expected_members(self) -> None:
        expected = {"dalio", "lynch", "druckenmiller", "klarman", "munger", "williams", "soros", "simons"}
        assert set(BOARD_MEMBERS.keys()) == expected


# ---------------------------------------------------------------------------
# Test Pair Configuration
# ---------------------------------------------------------------------------

class TestPairConfig:
    def test_four_pairs(self) -> None:
        assert len(PAIR_CONFIG) == 4

    def test_all_members_covered(self) -> None:
        all_members = set()
        for pair in PAIR_CONFIG:
            all_members.update(pair["members"])
        assert all_members == set(BOARD_MEMBERS.keys())

    def test_no_duplicate_members(self) -> None:
        seen = set()
        for pair in PAIR_CONFIG:
            for m in pair["members"]:
                assert m not in seen, f"{m} appears in multiple pairs"
                seen.add(m)

    def test_each_pair_has_providers(self) -> None:
        for pair in PAIR_CONFIG:
            assert len(pair["providers"]) >= 1


# ---------------------------------------------------------------------------
# Test Prompt Builders
# ---------------------------------------------------------------------------

class TestPromptBuilders:
    def test_system_prompt_contains_both_members(self) -> None:
        prompt = _build_system_prompt(
            BOARD_MEMBERS["soros"], BOARD_MEMBERS["druckenmiller"], "Macro",
        )
        assert "George Soros" in prompt
        assert "Stanley Druckenmiller" in prompt
        assert "soros" in prompt
        assert "druckenmiller" in prompt

    def test_system_prompt_contains_json_format(self) -> None:
        prompt = _build_system_prompt(
            BOARD_MEMBERS["munger"], BOARD_MEMBERS["klarman"], "Value",
        )
        assert "APPROVE" in prompt
        assert "VETO" in prompt

    def test_user_prompt_contains_verdict(self) -> None:
        verdict = _make_verdict("BUY")
        prompt = _build_user_prompt(verdict, verdict.agent_stances, None, MagicMock(ticker="AAPL"), None)
        assert "BUY" in prompt
        assert "Warren" in prompt or "warren" in prompt

    def test_user_prompt_with_adversarial(self) -> None:
        verdict = _make_verdict()
        adv = MagicMock()
        adv.verdict = MagicMock(value="CAUTION")
        adv.bias_flags = []
        adv.reasoning = "Some concerns"
        prompt = _build_user_prompt(verdict, verdict.agent_stances, adv, MagicMock(ticker="AAPL"), None)
        assert "Adversarial" in prompt


# ---------------------------------------------------------------------------
# Test Response Parsing
# ---------------------------------------------------------------------------

class TestParsePairResponse:
    def test_valid_json(self) -> None:
        content = json.dumps({
            "soros": {
                "vote": "APPROVE",
                "confidence": 0.8,
                "assessment": "Macro supportive",
                "key_concern": "Late cycle",
                "key_endorsement": "Strong momentum",
                "reasoning": "Reflexive dynamics favor the bull case."
            },
            "druckenmiller": {
                "vote": "ADJUST_UP",
                "confidence": 0.85,
                "assessment": "Asymmetric risk/reward",
                "key_concern": None,
                "key_endorsement": "3:1 upside",
                "reasoning": "Catalyst imminent, size up."
            }
        })
        resp = _make_llm_response(content)
        opinions = _parse_pair_response(resp, BOARD_MEMBERS["soros"], BOARD_MEMBERS["druckenmiller"])
        assert len(opinions) == 2
        assert opinions[0].advisor_name == "soros"
        assert opinions[0].vote == BoardVote.APPROVE
        assert opinions[1].advisor_name == "druckenmiller"
        assert opinions[1].vote == BoardVote.ADJUST_UP

    def test_markdown_fences(self) -> None:
        inner = json.dumps({
            "munger": {"vote": "VETO", "confidence": 0.9, "assessment": "Fatal flaw",
                       "key_concern": "Bias", "key_endorsement": None, "reasoning": "Inversion fails."},
            "klarman": {"vote": "ADJUST_DOWN", "confidence": 0.7, "assessment": "Thin margin",
                        "key_concern": "Downside", "key_endorsement": None, "reasoning": "Need 30%."},
        })
        content = f"```json\n{inner}\n```"
        resp = _make_llm_response(content)
        opinions = _parse_pair_response(resp, BOARD_MEMBERS["munger"], BOARD_MEMBERS["klarman"])
        assert len(opinions) == 2
        assert opinions[0].vote == BoardVote.VETO

    def test_malformed_json(self) -> None:
        resp = _make_llm_response("This is not JSON at all")
        opinions = _parse_pair_response(resp, BOARD_MEMBERS["dalio"], BOARD_MEMBERS["williams"])
        assert opinions == []

    def test_missing_member_key(self) -> None:
        content = json.dumps({
            "dalio": {"vote": "APPROVE", "confidence": 0.7, "assessment": "ok",
                      "key_concern": None, "key_endorsement": None, "reasoning": "ok"},
            # williams is missing
        })
        resp = _make_llm_response(content)
        opinions = _parse_pair_response(resp, BOARD_MEMBERS["dalio"], BOARD_MEMBERS["williams"])
        assert len(opinions) == 1
        assert opinions[0].advisor_name == "dalio"

    def test_invalid_vote_defaults_to_approve(self) -> None:
        content = json.dumps({
            "lynch": {"vote": "MAYBE", "confidence": 0.5, "assessment": "Unsure",
                      "key_concern": None, "key_endorsement": None, "reasoning": "Hmm."},
            "simons": {"vote": "APPROVE", "confidence": 0.6, "assessment": "Data ok",
                       "key_concern": None, "key_endorsement": None, "reasoning": "Stats fine."},
        })
        resp = _make_llm_response(content)
        opinions = _parse_pair_response(resp, BOARD_MEMBERS["lynch"], BOARD_MEMBERS["simons"])
        assert len(opinions) == 2
        assert opinions[0].vote == BoardVote.APPROVE  # "MAYBE" → default APPROVE

    def test_confidence_clamped(self) -> None:
        content = json.dumps({
            "dalio": {"vote": "APPROVE", "confidence": 1.5, "assessment": "Over-confident",
                      "key_concern": None, "key_endorsement": None, "reasoning": "Too sure."},
            "williams": {"vote": "APPROVE", "confidence": -0.3, "assessment": "Under",
                         "key_concern": None, "key_endorsement": None, "reasoning": "Unsure."},
        })
        resp = _make_llm_response(content)
        opinions = _parse_pair_response(resp, BOARD_MEMBERS["dalio"], BOARD_MEMBERS["williams"])
        assert opinions[0].confidence == Decimal("1")
        assert opinions[1].confidence == Decimal("0")


# ---------------------------------------------------------------------------
# Test Vote Synthesis
# ---------------------------------------------------------------------------

class TestVoteSynthesis:
    def test_all_approve(self) -> None:
        opinions = [_make_opinion(name=f"adv{i}", vote=BoardVote.APPROVE) for i in range(8)]
        result = _synthesize_votes("BUY", opinions, 5000)
        assert result.original_verdict == "BUY"
        assert result.adjusted_verdict is None
        assert not result.verdict_changed
        assert result.vote_counts["APPROVE"] == 8

    def test_three_vetos_caps_to_watchlist(self) -> None:
        opinions = [_make_opinion(name=f"v{i}", vote=BoardVote.VETO) for i in range(3)]
        opinions += [_make_opinion(name=f"a{i}", vote=BoardVote.APPROVE) for i in range(5)]
        result = _synthesize_votes("BUY", opinions, 5000)
        assert result.adjusted_verdict == "WATCHLIST"
        assert result.veto_count == 3

    def test_three_vetos_no_change_if_already_below_watchlist(self) -> None:
        opinions = [_make_opinion(name=f"v{i}", vote=BoardVote.VETO) for i in range(3)]
        opinions += [_make_opinion(name=f"a{i}", vote=BoardVote.APPROVE) for i in range(5)]
        result = _synthesize_votes("REDUCE", opinions, 5000)
        # REDUCE is below WATCHLIST on the ladder, so no adjustment
        assert result.adjusted_verdict is None

    def test_five_adjust_up(self) -> None:
        opinions = [_make_opinion(name=f"u{i}", vote=BoardVote.ADJUST_UP) for i in range(5)]
        opinions += [_make_opinion(name=f"a{i}", vote=BoardVote.APPROVE) for i in range(3)]
        result = _synthesize_votes("BUY", opinions, 5000)
        assert result.adjusted_verdict == "STRONG_BUY"

    def test_five_adjust_down(self) -> None:
        opinions = [_make_opinion(name=f"d{i}", vote=BoardVote.ADJUST_DOWN) for i in range(5)]
        opinions += [_make_opinion(name=f"a{i}", vote=BoardVote.APPROVE) for i in range(3)]
        result = _synthesize_votes("BUY", opinions, 5000)
        assert result.adjusted_verdict == "ACCUMULATE"

    def test_mixed_no_majority(self) -> None:
        opinions = [
            _make_opinion(name="a1", vote=BoardVote.APPROVE),
            _make_opinion(name="a2", vote=BoardVote.APPROVE),
            _make_opinion(name="u1", vote=BoardVote.ADJUST_UP),
            _make_opinion(name="u2", vote=BoardVote.ADJUST_UP),
            _make_opinion(name="d1", vote=BoardVote.ADJUST_DOWN),
            _make_opinion(name="d2", vote=BoardVote.ADJUST_DOWN),
            _make_opinion(name="v1", vote=BoardVote.VETO),
            _make_opinion(name="v2", vote=BoardVote.VETO),
        ]
        result = _synthesize_votes("BUY", opinions, 5000)
        assert result.adjusted_verdict is None  # No majority

    def test_veto_takes_priority_over_adjust(self) -> None:
        opinions = [_make_opinion(name=f"v{i}", vote=BoardVote.VETO) for i in range(3)]
        opinions += [_make_opinion(name=f"u{i}", vote=BoardVote.ADJUST_UP) for i in range(5)]
        result = _synthesize_votes("BUY", opinions, 5000)
        # Veto check comes first
        assert result.adjusted_verdict == "WATCHLIST"

    def test_empty_opinions(self) -> None:
        result = _synthesize_votes("BUY", [], 0)
        assert result.adjusted_verdict is None
        assert result.veto_count == 0

    def test_latency_recorded(self) -> None:
        result = _synthesize_votes("BUY", [], 12345)
        assert result.total_latency_ms == 12345


# ---------------------------------------------------------------------------
# Test Verdict Shifting
# ---------------------------------------------------------------------------

class TestVerdictShift:
    def test_shift_up(self) -> None:
        assert _shift_verdict("BUY", +1) == "STRONG_BUY"
        assert _shift_verdict("HOLD", +1) == "ACCUMULATE"
        assert _shift_verdict("SELL", +1) == "REDUCE"

    def test_shift_down(self) -> None:
        assert _shift_verdict("BUY", -1) == "ACCUMULATE"
        assert _shift_verdict("HOLD", -1) == "WATCHLIST"
        assert _shift_verdict("STRONG_BUY", -1) == "BUY"

    def test_boundary_up(self) -> None:
        assert _shift_verdict("STRONG_BUY", +1) is None

    def test_boundary_down(self) -> None:
        assert _shift_verdict("AVOID", -1) is None

    def test_verdict_index(self) -> None:
        assert _verdict_index("AVOID") == 0
        assert _verdict_index("STRONG_BUY") == 8
        assert _verdict_index("HOLD") == 5


# ---------------------------------------------------------------------------
# Test CIO Prompt Builder
# ---------------------------------------------------------------------------

class TestCIOPrompts:
    def test_system_prompt_has_conflict_patterns(self) -> None:
        prompt = _build_cio_system_prompt()
        assert "Value Trap" in prompt
        assert "Growth Mispriced" in prompt
        assert "Forensic Veto" in prompt

    def test_user_prompt_has_opinions(self) -> None:
        verdict = _make_verdict()
        board_result = BoardResult(
            opinions=[_make_opinion()],
            original_verdict="BUY",
            vote_counts={"APPROVE": 1},
        )
        prompt = _build_cio_user_prompt(verdict, board_result, verdict.agent_stances, None)
        assert "Ray Dalio" in prompt
        assert "APPROVE" in prompt


# ---------------------------------------------------------------------------
# Test CIO Response Parsing
# ---------------------------------------------------------------------------

class TestCIOParsing:
    def test_valid_json(self) -> None:
        content = json.dumps({
            "headline": "BUY with conviction",
            "narrative": "Strong thesis...",
            "risk_summary": "Late cycle risk",
            "pre_mortem": "If wrong, because of macro",
            "conflict_resolution": "Resolved by weighting value over momentum",
            "verdict_adjustment": 0,
            "adjusted_verdict": None,
        })
        resp = _make_llm_response(content)
        board_result = BoardResult(
            opinions=[_make_opinion()],
            original_verdict="BUY",
        )
        narrative = _parse_cio_response(resp, _make_verdict(), board_result, 3000)
        assert narrative.headline == "BUY with conviction"
        assert narrative.verdict_adjustment == 0
        assert narrative.latency_ms == 3000

    def test_fallback_on_invalid_json(self) -> None:
        resp = _make_llm_response("Not JSON!")
        board_result = BoardResult(
            opinions=[_make_opinion()],
            original_verdict="BUY",
        )
        narrative = _parse_cio_response(resp, _make_verdict(), board_result, 2000)
        # Should produce fallback narrative, not crash
        assert narrative.model == "fallback"

    def test_veto_blocks_cio_adjustment(self) -> None:
        content = json.dumps({
            "headline": "Should upgrade",
            "narrative": "n",
            "risk_summary": "r",
            "pre_mortem": "p",
            "conflict_resolution": "c",
            "verdict_adjustment": 1,
            "adjusted_verdict": "STRONG_BUY",
        })
        resp = _make_llm_response(content)
        board_result = BoardResult(
            opinions=[_make_opinion(name=f"v{i}", vote=BoardVote.VETO) for i in range(3)],
            original_verdict="BUY",
            veto_count=3,
        )
        narrative = _parse_cio_response(resp, _make_verdict(), board_result, 1000)
        # CIO adjustment blocked because 3+ vetoes
        assert narrative.verdict_adjustment == 0
        assert narrative.adjusted_verdict is None


# ---------------------------------------------------------------------------
# Test Fallback Narrative
# ---------------------------------------------------------------------------

class TestFallbackNarrative:
    def test_basic(self) -> None:
        verdict = _make_verdict("BUY")
        board_result = BoardResult(
            opinions=[
                _make_opinion(name="a1", vote=BoardVote.APPROVE),
                _make_opinion(name="v1", vote=BoardVote.VETO),
            ],
            original_verdict="BUY",
            veto_count=1,
        )
        narrative = _fallback_narrative(verdict, board_result, 500)
        assert "1/2" in narrative.headline
        assert "1 veto" in narrative.headline
        assert narrative.model == "fallback"


# ---------------------------------------------------------------------------
# Test Full Convene (mocked gateway)
# ---------------------------------------------------------------------------

class TestConvene:
    @pytest.mark.asyncio
    async def test_full_convene_success(self) -> None:
        """All 4 pairs succeed — should get 8 opinions."""
        gateway = MagicMock()

        # Each pair returns valid JSON for its 2 members
        pair_responses = []
        for pair_cfg in PAIR_CONFIG:
            a, b = pair_cfg["members"]
            content = json.dumps({
                a: {"vote": "APPROVE", "confidence": 0.7, "assessment": f"{a} approves",
                    "key_concern": None, "key_endorsement": "Good thesis", "reasoning": "Solid."},
                b: {"vote": "APPROVE", "confidence": 0.75, "assessment": f"{b} approves",
                    "key_concern": "Minor risk", "key_endorsement": "Strong moat", "reasoning": "Agree."},
            })
            pair_responses.append(_make_llm_response(content))

        # gateway.call returns responses in order
        call_idx = 0
        async def mock_call(**kwargs):
            nonlocal call_idx
            resp = pair_responses[call_idx]
            call_idx += 1
            return resp

        gateway.call = mock_call

        board = AdvisoryBoard(gateway)
        verdict = _make_verdict("BUY")
        request = MagicMock(ticker="AAPL")

        result = await board.convene(verdict, verdict.agent_stances, None, request)

        assert len(result.opinions) == 8
        assert result.original_verdict == "BUY"
        assert all(op.vote == BoardVote.APPROVE for op in result.opinions)

    @pytest.mark.asyncio
    async def test_one_pair_failure(self) -> None:
        """One pair fails — should get 6 opinions, not crash."""
        gateway = MagicMock()

        # Build responses for all 4 pairs; the mock will track which
        # system_prompt belongs to which pair via the theme keyword.
        pair_responses: dict[str, str] = {}
        for pair_cfg in PAIR_CONFIG:
            a, b = pair_cfg["members"]
            content = json.dumps({
                a: {"vote": "APPROVE", "confidence": 0.7, "assessment": "ok",
                    "key_concern": None, "key_endorsement": None, "reasoning": "ok"},
                b: {"vote": "APPROVE", "confidence": 0.7, "assessment": "ok",
                    "key_concern": None, "key_endorsement": None, "reasoning": "ok"},
            })
            pair_responses[pair_cfg["theme"]] = content

        fail_theme = PAIR_CONFIG[0]["theme"]  # "Macro Conviction"

        async def mock_call(**kwargs):
            sp = kwargs.get("system_prompt", "")
            if fail_theme in sp:
                raise RuntimeError("Provider unavailable")
            for theme, content in pair_responses.items():
                if theme in sp:
                    return _make_llm_response(content)
            return _make_llm_response("{}")

        gateway.call = mock_call

        board = AdvisoryBoard(gateway)
        verdict = _make_verdict()
        request = MagicMock(ticker="AAPL")

        result = await board.convene(verdict, verdict.agent_stances, None, request)

        # First pair failed, 3 pairs × 2 = 6 opinions
        assert len(result.opinions) == 6

    @pytest.mark.asyncio
    async def test_all_pairs_fail(self) -> None:
        """All pairs fail — should return empty result, not crash."""
        gateway = MagicMock()

        async def mock_call(**kwargs):
            raise RuntimeError("All down")

        gateway.call = mock_call

        board = AdvisoryBoard(gateway)
        verdict = _make_verdict()
        request = MagicMock(ticker="AAPL")

        result = await board.convene(verdict, verdict.agent_stances, None, request)

        assert len(result.opinions) == 0
        assert result.adjusted_verdict is None


# ---------------------------------------------------------------------------
# Test CIO Synthesizer (mocked gateway)
# ---------------------------------------------------------------------------

class TestCIOSynthesizer:
    @pytest.mark.asyncio
    async def test_synthesize_success(self) -> None:
        gateway = MagicMock()

        content = json.dumps({
            "headline": "BUY — strong consensus with manageable risks",
            "narrative": "The board unanimously approved...",
            "risk_summary": "Late-cycle macro headwinds",
            "pre_mortem": "If wrong, due to rate hikes",
            "conflict_resolution": "Value and momentum aligned",
            "verdict_adjustment": 0,
            "adjusted_verdict": None,
        })

        async def mock_call(**kwargs):
            return _make_llm_response(content)

        gateway.call = mock_call

        cio = CIOSynthesizer(gateway)
        verdict = _make_verdict()
        board_result = BoardResult(
            opinions=[_make_opinion()],
            original_verdict="BUY",
        )

        narrative = await cio.synthesize(verdict, board_result, verdict.agent_stances)

        assert narrative.headline == "BUY — strong consensus with manageable risks"
        assert narrative.verdict_adjustment == 0

    @pytest.mark.asyncio
    async def test_synthesize_all_providers_fail(self) -> None:
        gateway = MagicMock()

        async def mock_call(**kwargs):
            raise RuntimeError("Dead")

        gateway.call = mock_call

        cio = CIOSynthesizer(gateway)
        verdict = _make_verdict()
        board_result = BoardResult(
            opinions=[_make_opinion()],
            original_verdict="BUY",
        )

        narrative = await cio.synthesize(verdict, board_result, verdict.agent_stances)

        assert narrative.model == "fallback"
        assert "1/1" in narrative.headline
