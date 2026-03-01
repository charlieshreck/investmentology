from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from investmentology.adversarial.biases import BiasResult, check_biases_in_reasoning
from investmentology.adversarial.kill_company import (
    KillScenario,
    build_kill_company_prompt,
    parse_kill_scenarios,
)
from investmentology.adversarial.premortem import (
    PreMortemResult,
    build_premortem_prompt,
    parse_premortem,
)
from investmentology.agents.gateway import LLMGateway
from investmentology.models.signal import AgentSignalSet, SignalTag

logger = logging.getLogger(__name__)

# Confidence threshold above which we consider an agent "highly confident"
HIGH_CONFIDENCE_THRESHOLD = Decimal("0.80")

# Patterns that trigger adversarial review
PATTERN_UNANIMITY = "suspicious_unanimity"
PATTERN_DANGEROUS_DISAGREEMENT = "dangerous_disagreement"
PATTERN_CONVICTION_BUY = "conviction_buy"


class MungerVerdict(StrEnum):
    PROCEED = "PROCEED"
    CAUTION = "CAUTION"
    VETO = "VETO"


@dataclass
class AdversarialResult:
    verdict: MungerVerdict
    bias_flags: list[BiasResult]
    kill_scenarios: list[KillScenario]
    premortem: PreMortemResult | None
    reasoning: str


class MungerOrchestrator:
    """Adversarial review orchestrator -- Charlie Munger's checklist.

    Triggers:
    - Suspicious unanimity (all agents agree strongly)
    - Dangerous disagreement (Warren vs Auditor on risk)
    - All CONVICTION_BUY decisions (standard review)
    """

    # Provider and model to use for adversarial LLM calls
    PROVIDER = "deepseek"
    MODEL = "deepseek-chat"

    def __init__(self, gateway: LLMGateway, registry: object | None = None) -> None:
        self._gateway = gateway
        self._registry = registry  # Registry for base rate queries

    def should_trigger(
        self,
        agent_signals: list[AgentSignalSet],
        pattern_name: str | None = None,
    ) -> bool:
        """Check if adversarial review is needed.

        Returns True if any trigger condition is met.
        """
        if pattern_name == PATTERN_CONVICTION_BUY:
            return True

        # Check for suspicious unanimity: all agents high confidence, same buy direction
        if self._check_unanimity(agent_signals):
            return True

        # Check for dangerous disagreement: Warren bullish but Auditor flags risk
        if self._check_dangerous_disagreement(agent_signals):
            return True

        return False

    def _check_unanimity(self, agent_signals: list[AgentSignalSet]) -> bool:
        """All agents agree strongly (high confidence, same direction)."""
        if len(agent_signals) < 2:
            return False

        all_high_confidence = all(
            s.confidence >= HIGH_CONFIDENCE_THRESHOLD for s in agent_signals
        )
        if not all_high_confidence:
            return False

        buy_tags = {SignalTag.BUY_NEW, SignalTag.BUY_ADD}
        all_bullish = all(
            any(sig.tag in buy_tags for sig in s.signals.signals)
            for s in agent_signals
        )
        return all_bullish

    def _check_dangerous_disagreement(self, agent_signals: list[AgentSignalSet]) -> bool:
        """Warren is bullish but Auditor flags risk."""
        warren_signals = None
        auditor_signals = None

        for s in agent_signals:
            if s.agent_name == "warren":
                warren_signals = s
            elif s.agent_name == "auditor":
                auditor_signals = s

        if warren_signals is None or auditor_signals is None:
            return False

        buy_tags = {SignalTag.BUY_NEW, SignalTag.BUY_ADD}
        warren_bullish = any(
            sig.tag in buy_tags for sig in warren_signals.signals.signals
        )

        risk_tags = {
            SignalTag.ACCOUNTING_RED_FLAG,
            SignalTag.GOVERNANCE_CONCERN,
            SignalTag.LEVERAGE_HIGH,
            SignalTag.DRAWDOWN_RISK,
        }
        auditor_risk = any(
            sig.tag in risk_tags for sig in auditor_signals.signals.signals
        )

        return warren_bullish and auditor_risk

    async def review(
        self,
        ticker: str,
        fundamentals_summary: str,
        thesis: str,
        agent_signals: list[AgentSignalSet],
        sector: str = "",
    ) -> AdversarialResult:
        """Run full adversarial review.

        1. Check biases in agent reasoning
        2. Run Kill the Company exercise via LLM
        3. Run Pre-Mortem if conviction is high
        4. Determine verdict: PROCEED / CAUTION / VETO
        """
        # 1. Check biases across all agent reasoning
        combined_reasoning = " ".join(s.reasoning for s in agent_signals)
        bias_flags = check_biases_in_reasoning(combined_reasoning, {})

        # 2. Kill the Company
        kill_prompt = build_kill_company_prompt(ticker, "Unknown", fundamentals_summary)
        kill_response = await self._gateway.call(
            provider=self.PROVIDER,
            system_prompt="You are a ruthless business analyst. Your job is to find fatal flaws.",
            user_prompt=kill_prompt,
            model=self.MODEL,
        )
        kill_scenarios = parse_kill_scenarios(kill_response.content)

        # 3. Pre-Mortem (if any agent has high conviction)
        premortem: PreMortemResult | None = None
        max_confidence = max((s.confidence for s in agent_signals), default=Decimal("0"))
        if max_confidence >= HIGH_CONFIDENCE_THRESHOLD:
            # Get historical base rates for this sector
            base_rate_context = self._get_base_rates(sector)

            premortem_prompt = build_premortem_prompt(
                ticker=ticker,
                thesis=thesis,
                entry_price="current",
            )
            # Inject base rates into the prompt
            if base_rate_context:
                premortem_prompt += f"\n\nHistorical base rates for {sector} sector:\n{base_rate_context}"

            premortem_response = await self._gateway.call(
                provider=self.PROVIDER,
                system_prompt="You are a pessimistic investment analyst conducting a pre-mortem.",
                user_prompt=premortem_prompt,
                model=self.MODEL,
            )
            premortem = parse_premortem(premortem_response.content)
            if premortem and base_rate_context:
                premortem.base_rates = base_rate_context

        # 4. Determine verdict
        verdict = self._determine_verdict(bias_flags, kill_scenarios, premortem)

        flagged_biases = [b for b in bias_flags if b.is_flagged]
        reasoning_parts: list[str] = []
        if flagged_biases:
            bias_names = ", ".join(b.bias_name for b in flagged_biases)
            reasoning_parts.append(f"Biases detected: {bias_names}")
        if kill_scenarios:
            fatal = [s for s in kill_scenarios if s.impact == "fatal"]
            if fatal:
                reasoning_parts.append(f"{len(fatal)} fatal kill scenarios identified")
            reasoning_parts.append(f"{len(kill_scenarios)} total kill scenarios")
        if premortem:
            reasoning_parts.append(
                f"Pre-mortem probability: {premortem.probability_estimate}"
            )

        return AdversarialResult(
            verdict=verdict,
            bias_flags=bias_flags,
            kill_scenarios=kill_scenarios,
            premortem=premortem,
            reasoning=f"Munger review for {ticker}: "
            + "; ".join(reasoning_parts)
            if reasoning_parts
            else f"Munger review for {ticker}: No significant concerns.",
        )

    def _get_base_rates(self, sector: str) -> str:
        """Get historical base rate context for a sector."""
        if not self._registry or not sector:
            return ""
        try:
            outcomes = self._registry.get_sector_outcomes(sector)
            failures = self._registry.get_failure_modes(sector)

            if not outcomes:
                return ""

            parts = []
            rate = outcomes.get("success_rate", 0)
            total = outcomes.get("total", 0)
            if total > 0:
                parts.append(
                    f"- {sector} picks succeed {rate * 100:.0f}% of the time "
                    f"(based on {total} settled decisions)"
                )
            if failures:
                parts.append("- Common failure reasons:")
                for f in failures[:3]:
                    parts.append(f"  * {f}")
            return "\n".join(parts)
        except Exception:
            logger.debug("Base rate lookup failed for %s", sector)
            return ""

    def _determine_verdict(
        self,
        bias_flags: list[BiasResult],
        kill_scenarios: list[KillScenario],
        premortem: PreMortemResult | None,
    ) -> MungerVerdict:
        """Determine the overall verdict based on adversarial findings."""
        veto_score = 0

        # Count flagged biases
        flagged_count = sum(1 for b in bias_flags if b.is_flagged)
        if flagged_count >= 5:
            veto_score += 2
        elif flagged_count >= 3:
            veto_score += 1

        # Count fatal/high-likelihood kill scenarios
        fatal_high = [
            s
            for s in kill_scenarios
            if s.impact == "fatal" and s.likelihood == "high"
        ]
        fatal_any = [s for s in kill_scenarios if s.impact == "fatal"]
        if fatal_high:
            veto_score += 3
        elif fatal_any:
            veto_score += 1

        # Pre-mortem assessment
        if premortem:
            if premortem.probability_estimate == "likely":
                veto_score += 3
            elif premortem.probability_estimate == "plausible":
                veto_score += 1

        # Verdict thresholds
        if veto_score >= 4:
            return MungerVerdict.VETO
        elif veto_score >= 2:
            return MungerVerdict.CAUTION
        else:
            return MungerVerdict.PROCEED
