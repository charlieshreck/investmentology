"""Generic AgentRunner — replaces individual agent classes.

Uses AgentSkill definitions to build prompts, route to providers,
parse responses, and apply post-processing rules.  A single class
handles all investment persona agents (Warren, Soros, Simons, etc.)
as well as the Data Analyst validator.
"""

from __future__ import annotations

import json
import logging
from decimal import Decimal

from investmentology.agents.base import AnalysisRequest, AnalysisResponse
from investmentology.agents.gateway import LLMGateway
from investmentology.agents.skills import AgentSkill
from investmentology.compatibility.taxonomy import ALL_DOMAIN_TAGS, resolve_tag
from investmentology.models.signal import AgentSignalSet, Signal, SignalSet, SignalTag

logger = logging.getLogger(__name__)

_VALID_TAGS = ALL_DOMAIN_TAGS

# Position-type-aware guidance injected into user prompts per (agent, type)
_TYPE_GUIDANCE: dict[tuple[str, str], str] = {
    # Warren
    ("warren", "permanent"): "This is a PERMANENT holding — a decades-long compounder. Focus on durable competitive advantages, management succession depth, and whether the business model will survive 20+ years of disruption. Higher bar for quality; lower bar for current valuation.",
    ("warren", "core"): "This is a CORE holding — a multi-year competitive advantage play. Evaluate sustainable ROIC above cost of capital, reinvestment runway, and 3-5 year earnings power.",
    ("warren", "tactical"): "This is a TACTICAL position — a 3-12 month catalyst trade. Focus on specific catalysts, risk/reward asymmetry, and clear exit criteria. Your role: confirm the business isn't fundamentally broken.",
    # Auditor
    ("auditor", "permanent"): "PERMANENT position — survival risk assessment is paramount. Focus on existential threats: secular disruption, regulatory capture, governance decay, balance sheet fortress quality.",
    ("auditor", "core"): "CORE position — standard forensic review. Evaluate accounting quality, governance, and balance sheet for 3-5 year holding period.",
    ("auditor", "tactical"): "TACTICAL position — focus on near-term risk events. Earnings manipulation, short-seller reports, pending litigation, debt maturities within 12 months.",
    # Klarman
    ("klarman", "permanent"): "PERMANENT position — evaluate whether the current price offers a margin of safety for DECADES of compounding. Bear case should assume prolonged low-growth periods.",
    ("klarman", "core"): "CORE position — standard margin-of-safety analysis. Demand 30% discount to conservative intrinsic value.",
    ("klarman", "tactical"): "TACTICAL position — evaluate special situation dynamics. Catalyst path, structural discount, forced-selling opportunity, defined exit.",
    # Soros
    ("soros", "permanent"): "PERMANENT position — assess long-term reflexivity risks. Can the narrative around this company sustain itself for decades, or is there a hidden feedback loop that will unwind?",
    ("soros", "core"): "CORE position — identify the dominant narrative driving this stock over 2-5 years. Where are we in the reflexive cycle?",
    ("soros", "tactical"): "TACTICAL position — narrative momentum is everything. Is the market's self-reinforcing belief strengthening or about to break? Define the bust trigger.",
    # Druckenmiller
    ("druckenmiller", "permanent"): "PERMANENT position — sizing and entry timing matter less. Focus on: is this the RIGHT time to add/trim? Macro headwinds that could create better entry?",
    ("druckenmiller", "core"): "CORE position — evaluate catalyst calendar and asymmetric risk/reward over 2-5 year horizon.",
    ("druckenmiller", "tactical"): "TACTICAL position — this is your core domain. Define the catalyst, the timeline, the risk/reward ratio, and the stop-loss. Be precise on sizing conviction.",
    # Dalio
    ("dalio", "permanent"): "PERMANENT position — evaluate through all 4 economic quadrants. Will this company compound through rising rates, falling growth, stagflation? All-weather resilience is the test.",
    ("dalio", "core"): "CORE position — which quadrant are we in, and does this position benefit? Evaluate regime alignment over 2-5 years.",
    ("dalio", "tactical"): "TACTICAL position — regime timing is critical. Is the current macro regime favorable for this trade? When does the regime shift invalidate the thesis?",
    # Simons
    ("simons", "permanent"): "PERMANENT position — long-term technical trends. Multi-year uptrend? Volume patterns suggesting institutional accumulation.",
    ("simons", "core"): "CORE position — medium-term technical analysis. Trend strength, support/resistance levels, momentum indicators.",
    ("simons", "tactical"): "TACTICAL position — short-term technical signals are paramount. Entry timing, pattern recognition, volume confirmation.",
    # Lynch
    ("lynch", "permanent"): "PERMANENT position — GARP: likely Stalwart or Slow Grower. Focus on consistent earnings growth, fair PEG ratio, and whether growth rate justifies decades of holding.",
    ("lynch", "core"): "CORE position — GARP classification critical. Fast Grower or Stalwart most appropriate. PEG ratio, earnings acceleration, institutional neglect.",
    ("lynch", "tactical"): "TACTICAL position — likely Cyclical or Turnaround. Focus on cycle timing, sector rotation signals, and whether the growth inflection is near.",
}


class AgentRunner:
    """Generic agent that builds prompts and routes calls via AgentSkill."""

    def __init__(self, skill: AgentSkill, gateway: LLMGateway) -> None:
        self.skill = skill
        self.gateway = gateway

    # Compatibility properties for DebateOrchestrator (expects BaseAgent interface)
    @property
    def name(self) -> str:
        return self.skill.name

    @property
    def model(self) -> str:
        return self.skill.default_model

    # ------------------------------------------------------------------
    # System prompt
    # ------------------------------------------------------------------

    def build_system_prompt(self, *, request: AnalysisRequest | None = None) -> str:
        """Assemble the system prompt from skill fields.

        If a request is provided, sector-specific overlays are appended
        when the ticker's sector matches a defined overlay.
        """
        parts = [
            f"You are {self.skill.display_name}.",
            "",
            self.skill.philosophy,
            "",
            self.skill.methodology,
            "",
        ]

        # Critical rules
        if self.skill.critical_rules:
            parts.append("CRITICAL RULES:")
            for i, rule in enumerate(self.skill.critical_rules, 1):
                parts.append(f"{i}. {rule}")
            parts.append("")

        # Allowed tags — list them so the LLM knows what to use
        if self.skill.allowed_tags:
            parts.append(f"Allowed signal tags: {', '.join(self.skill.allowed_tags)}")
            parts.append("")

        # Sector-specific methodology overlay
        if request and hasattr(self.skill, "sector_overlays") and self.skill.sector_overlays:
            sector = request.sector or ""
            overlay = self.skill.sector_overlays.get(sector)
            if overlay:
                parts.append(f"## Sector-Specific Methodology ({sector})")
                parts.append(overlay)
                parts.append("")

        # Output format
        parts.append(self.skill.output_format)

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # User prompt — built from AnalysisRequest + skill data requirements
    # ------------------------------------------------------------------

    def build_user_prompt(self, request: AnalysisRequest) -> str:
        """Build the user prompt from the skill's data requirements."""
        parts: list[str] = []

        # Opening line
        opener = self.skill.prompt_opener.format(
            ticker=request.ticker,
            sector=request.sector,
            industry=request.industry,
        )
        parts.append(opener)

        # Fundamentals — always included (in required_data for all skills)
        parts.extend(self._fmt_fundamentals(request))

        # Optional context sections — include only those listed in optional_data
        opt = set(self.skill.optional_data)

        if "quant_gate_rank" in opt and request.quant_gate_rank is not None:
            parts.append(f"  Quant Gate Rank: {request.quant_gate_rank}")
        if "piotroski_score" in opt and request.piotroski_score is not None:
            parts.append(f"  Piotroski F-Score: {request.piotroski_score}")
        if "altman_z_score" in opt and request.altman_z_score is not None:
            parts.append(f"  Altman Z-Score: {request.altman_z_score}")

        if "earnings_context" in opt and request.earnings_context:
            parts.extend(self._fmt_earnings(request.earnings_context))

        if "news_context" in opt and request.news_context:
            parts.extend(self._fmt_news(request.news_context))

        if "insider_context" in opt and request.insider_context:
            parts.extend(self._fmt_insider(request.insider_context))

        if "filing_context" in opt and request.filing_context:
            parts.extend(self._fmt_filing(request.filing_context))

        if "institutional_context" in opt and request.institutional_context:
            parts.extend(self._fmt_institutional(request.institutional_context))

        if "social_sentiment" in opt and request.social_sentiment:
            parts.extend(self._fmt_social(request))

        if "analyst_ratings" in opt and request.analyst_ratings:
            parts.extend(self._fmt_analyst_ratings(request.analyst_ratings))

        if "short_interest" in opt and request.short_interest:
            parts.extend(self._fmt_short_interest(request.short_interest))

        if "research_briefing" in opt and request.research_briefing:
            parts.extend(self._fmt_research_briefing(request.research_briefing))

        if "macro_context" in opt and request.macro_context:
            parts.extend(self._fmt_macro(request.macro_context))

        if "market_snapshot" in opt and request.market_snapshot:
            parts.extend(self._fmt_market_snapshot(request.market_snapshot))

        if request.sector_performance:
            parts.extend(self._fmt_sector_performance(request.sector_performance, request.sector))

        if "technical_indicators" in opt:
            parts.extend(self._fmt_technical(request))

        if "portfolio_context" in opt and request.portfolio_context:
            parts.extend(self._fmt_portfolio(request))

        # Thesis lifecycle context
        if "position_thesis" in opt and request.position_thesis:
            parts.extend(self._fmt_thesis(request))

        # Position-type-aware guidance
        if "position_type" in opt and request.position_type:
            guidance = _TYPE_GUIDANCE.get((self.skill.name, request.position_type))
            if guidance:
                parts.append("")
                parts.append(f"POSITION TYPE GUIDANCE: {guidance}")

        # Similar past situations (Qdrant semantic memory)
        if request.similar_situations:
            parts.extend(self._fmt_similar_situations(request.similar_situations))

        # Previous verdict
        if "previous_verdict" in opt and request.previous_verdict:
            parts.extend(self._fmt_previous_verdict(request.previous_verdict))

        # Entry price / P&L context
        if "entry_price" in opt and request.entry_price is not None:
            parts.append("")
            parts.append("POSITION METRICS:")
            parts.append(f"  Entry price: ${request.entry_price:.2f}")
            if request.pnl_pct is not None:
                parts.append(f"  Unrealized P&L: {request.pnl_pct:+.1f}%")

        # Signature question (closing line)
        if self.skill.signature_question:
            parts.append("")
            parts.append(self.skill.signature_question)

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    def parse_response(self, raw: str, request: AnalysisRequest) -> AgentSignalSet:
        """Parse LLM JSON response into an AgentSignalSet."""
        data = self._extract_json(raw)
        if data is None:
            logger.warning(
                "%s: failed to parse JSON for %s",
                self.skill.display_name, request.ticker,
            )
            return self._empty_signal_set()

        # Data Analyst has a different output schema
        if self.skill.role == "validator":
            return self._parse_validator_response(data)

        return self._parse_standard_response(data, request)

    def _parse_standard_response(
        self, data: dict, request: AnalysisRequest,
    ) -> AgentSignalSet:
        """Parse the standard investment agent JSON response."""
        signals: list[Signal] = []
        for s in data.get("signals", []):
            tag_str = resolve_tag(s.get("tag", ""))
            try:
                tag = SignalTag(tag_str)
            except ValueError:
                logger.warning(
                    "%s: unknown signal tag %r, skipping",
                    self.skill.display_name, tag_str,
                )
                continue
            if tag not in _VALID_TAGS:
                logger.warning(
                    "%s: tag %s not in valid set, skipping",
                    self.skill.display_name, tag,
                )
                continue
            strength = s.get("strength", "moderate")
            if strength not in ("strong", "moderate", "weak"):
                strength = "moderate"
            signals.append(Signal(tag=tag, strength=strength, detail=s.get("detail", "")))

        try:
            confidence = Decimal(str(data.get("confidence", 0.5)))
            confidence = max(Decimal("0"), min(Decimal("1"), confidence))
        except Exception:
            confidence = Decimal("0.5")

        target_price = data.get("target_price")
        if target_price is not None:
            try:
                target_price = Decimal(str(target_price))
            except Exception:
                target_price = None

        # Post-processing: Simons data gate
        if self.skill.name == "simons" and not request.technical_indicators:
            confidence = min(confidence, Decimal("0.15"))
            if not any(s.tag == SignalTag.NO_ACTION for s in signals):
                signals.append(Signal(
                    tag=SignalTag.NO_ACTION,
                    strength="strong",
                    detail="No technical indicators available — cannot assess",
                ))

        # Data gate: macro-dependent agents capped at 0.20 without macro_context
        _MACRO_REQUIRED_AGENTS = {"soros", "druckenmiller", "dalio"}
        if self.skill.name in _MACRO_REQUIRED_AGENTS and not request.macro_context:
            confidence = min(confidence, Decimal("0.20"))

        # Confidence cap: non-held positions max 0.90, held max 0.95
        is_held = request.entry_price is not None
        if is_held:
            confidence = min(confidence, Decimal("0.95"))
        else:
            confidence = min(confidence, Decimal("0.90"))

        # Extract agent-specific structured fields
        metadata: dict = {}
        if self.skill.name == "dalio" and data.get("regime_quadrant"):
            metadata["regime_quadrant"] = data["regime_quadrant"]
        elif self.skill.name == "soros" and data.get("reflexivity_phase"):
            metadata["reflexivity_phase"] = data["reflexivity_phase"]
        elif self.skill.name == "lynch" and data.get("garp_classification"):
            metadata["garp_classification"] = data["garp_classification"]

        return AgentSignalSet(
            agent_name=self.skill.name,
            model=self.skill.default_model,
            signals=SignalSet(signals=signals),
            confidence=confidence,
            reasoning=data.get("reasoning", data.get("summary", "")),
            target_price=target_price,
            metadata=metadata,
        )

    def _parse_validator_response(self, data: dict) -> AgentSignalSet:
        """Parse a Data Analyst validation response."""
        status = data.get("status", "REJECTED")
        issues = data.get("issues", [])
        summary = data.get("summary", "")

        try:
            confidence = Decimal(str(data.get("confidence", 0.5)))
            confidence = max(Decimal("0"), min(Decimal("1"), confidence))
        except Exception:
            confidence = Decimal("0.5")

        # Map status to a pseudo-signal for pipeline consumption
        tag_map = {
            "VALIDATED": "DATA_VALIDATED",
            "SUSPICIOUS": "DATA_SUSPICIOUS",
            "REJECTED": "DATA_REJECTED",
        }
        tag_str = tag_map.get(status, "DATA_REJECTED")

        detail_parts = []
        for issue in issues[:5]:
            detail_parts.append(
                f"{issue.get('field', '?')}: {issue.get('detail', '')}"
            )
        detail_str = "; ".join(detail_parts) if detail_parts else status

        # DATA_VALIDATED etc. are not in SignalTag enum — use reasoning field
        return AgentSignalSet(
            agent_name=self.skill.name,
            model=self.skill.default_model,
            signals=SignalSet(signals=[]),
            confidence=confidence,
            reasoning=f"[{tag_str}] {summary} — {detail_str}",
        )

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def analyze(self, request: AnalysisRequest) -> AnalysisResponse:
        """Run analysis using the skill's provider preference."""
        import time as _time

        from investmentology.api.metrics import agent_analysis_duration, agent_analysis_total

        system_prompt = self.build_system_prompt(request=request)
        user_prompt = self.build_user_prompt(request)

        provider = self._resolve_provider()
        model = self.skill.default_model

        start = _time.monotonic()
        status = "success"
        try:
            llm_response = await self.gateway.call(
                provider=provider,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=model,
            )
        except Exception:
            status = "error"
            agent_analysis_total.labels(agent_name=self.skill.name, status=status).inc()
            agent_analysis_duration.labels(
                agent_name=self.skill.name, provider=provider,
            ).observe(_time.monotonic() - start)
            raise

        agent_analysis_duration.labels(
            agent_name=self.skill.name, provider=provider,
        ).observe(_time.monotonic() - start)
        agent_analysis_total.labels(agent_name=self.skill.name, status=status).inc()

        signal_set = self.parse_response(llm_response.content, request)
        signal_set.token_usage = llm_response.token_usage
        signal_set.latency_ms = llm_response.latency_ms

        return AnalysisResponse(
            agent_name=self.skill.name,
            model=llm_response.model or model,
            ticker=request.ticker,
            signal_set=signal_set,
            summary=signal_set.reasoning,
            target_price=signal_set.target_price,
            token_usage=llm_response.token_usage,
            latency_ms=llm_response.latency_ms,
        )

    # ------------------------------------------------------------------
    # Provider resolution
    # ------------------------------------------------------------------

    def _resolve_provider(self) -> str:
        """Pick the first available provider from the skill's preference list."""
        all_providers = (
            set(self.gateway._providers)
            | set(self.gateway._cli_providers)
            | set(self.gateway._remote_cli_providers)
        )
        for candidate in self.skill.provider_preference:
            if candidate in all_providers:
                return candidate

        raise RuntimeError(
            f"No available provider for {self.skill.name}. "
            f"Tried: {self.skill.provider_preference}. "
            f"Available: {sorted(all_providers)}"
        )

    # ------------------------------------------------------------------
    # JSON extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_json(raw: str) -> dict | None:
        """Extract JSON from raw LLM output, handling code fences and wrapper text.

        Gemini sometimes wraps JSON in conversational text or markdown.
        This method tries multiple extraction strategies.
        """
        # 1. Direct parse
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        stripped = raw.strip()

        # 2. Try extracting from code fences
        if "```" in stripped:
            lines = stripped.split("\n")
            json_lines: list[str] = []
            inside = False
            for line in lines:
                if line.strip().startswith("```"):
                    inside = not inside
                    continue
                if inside:
                    json_lines.append(line)
            try:
                return json.loads("\n".join(json_lines))
            except json.JSONDecodeError:
                pass

        # 3. Find the first top-level JSON object in the text (handles
        #    conversational wrapper text that Gemini sometimes adds)
        first_brace = stripped.find("{")
        if first_brace >= 0:
            # Walk from the first { and find its matching }
            depth = 0
            in_string = False
            escape_next = False
            for i in range(first_brace, len(stripped)):
                c = stripped[i]
                if escape_next:
                    escape_next = False
                    continue
                if c == "\\":
                    escape_next = True
                    continue
                if c == '"' and not escape_next:
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        candidate = stripped[first_brace: i + 1]
                        try:
                            return json.loads(candidate)
                        except json.JSONDecodeError:
                            break  # Malformed even with matched braces

        return None

    def _empty_signal_set(self) -> AgentSignalSet:
        return AgentSignalSet(
            agent_name=self.skill.name,
            model=self.skill.default_model,
            signals=SignalSet(signals=[]),
            confidence=Decimal("0"),
            reasoning="Failed to parse LLM response",
            parse_failed=True,
        )

    # ------------------------------------------------------------------
    # Prompt section formatters
    # ------------------------------------------------------------------

    @staticmethod
    def _fmt_fundamentals(request: AnalysisRequest) -> list[str]:
        """Format the fundamentals section."""
        f = request.fundamentals
        parts = [
            "",
            "FUNDAMENTALS:",
            f"  Price: ${f.price}",
            f"  Market Cap: ${float(f.market_cap):,.0f}",
        ]
        if f.enterprise_value:
            parts.append(f"  Enterprise Value: ${float(f.enterprise_value):,.0f}")
        parts.extend([
            f"  Revenue: ${float(f.revenue):,.0f}",
            f"  Net Income: ${float(f.net_income):,.0f}",
        ])
        if f.operating_income:
            parts.append(f"  Operating Income: ${float(f.operating_income):,.0f}")
        if f.earnings_yield:
            parts.append(f"  Earnings Yield: {float(f.earnings_yield):.1%}")
        if f.roic:
            parts.append(f"  ROIC: {float(f.roic):.1%}")
        parts.extend([
            f"  Total Debt: ${float(f.total_debt):,.0f}",
            f"  Cash: ${float(f.cash):,.0f}",
        ])
        if f.total_assets:
            parts.append(f"  Total Assets: ${float(f.total_assets):,.0f}")
        if f.total_liabilities:
            parts.append(f"  Total Liabilities: ${float(f.total_liabilities):,.0f}")
        return parts

    @staticmethod
    def _fmt_earnings(ec: dict) -> list[str]:
        parts = ["", "EARNINGS CONTEXT:"]
        if ec.get("upcoming"):
            u = ec["upcoming"]
            parts.append(f"  Next earnings: {u.get('date', 'TBD')}")
            if u.get("eps_estimate"):
                parts.append(f"  EPS estimate: {u['eps_estimate']}")
        beat = ec.get("beat_count", 0)
        miss = ec.get("miss_count", 0)
        if beat or miss:
            parts.append(f"  Last 4 quarters: {beat} beat, {miss} miss")
        return parts

    @staticmethod
    def _fmt_news(news: list[dict]) -> list[str]:
        parts = ["", "RECENT NEWS:"]
        for item in news[:5]:
            headline = item.get("headline", "")[:100]
            dt = item.get("datetime", "")[:10]
            parts.append(f"  [{dt}] {headline}")
        return parts

    @staticmethod
    def _fmt_insider(insider: list[dict]) -> list[str]:
        buys = sum(1 for t in insider if t.get("transaction_type") == "buy")
        sells = sum(1 for t in insider if t.get("transaction_type") == "sell")
        if not buys and not sells:
            return []
        return ["", f"INSIDER ACTIVITY (recent): {buys} buys, {sells} sells"]

    @staticmethod
    def _fmt_filing(fc: dict) -> list[str]:
        parts: list[str] = []
        if fc.get("risk_factors"):
            parts.extend([
                "",
                f"10-K RISK FACTORS ({fc.get('filing_date', 'recent')}):",
                f"  {fc['risk_factors'][:1500]}",
            ])
        if fc.get("mda"):
            parts.extend([
                "",
                "MANAGEMENT DISCUSSION & ANALYSIS:",
                f"  {fc['mda'][:1500]}",
            ])
        return parts

    @staticmethod
    def _fmt_institutional(holders: list[dict]) -> list[str]:
        parts = ["", "TOP INSTITUTIONAL HOLDERS (13F):"]
        for h in holders[:10]:
            name = h.get("name", "Unknown")[:40]
            shares = h.get("shares", 0)
            parts.append(f"  {name}: {shares:,} shares")
        return parts

    @staticmethod
    def _fmt_social(request: AnalysisRequest) -> list[str]:
        agg = request.social_sentiment.get("aggregate", {}) if request.social_sentiment else {}
        if not agg:
            return []
        parts = ["", "SOCIAL SENTIMENT:"]
        bias = agg.get("bias", "unknown")
        pos_ratio = agg.get("positive_ratio", "N/A")
        mentions = agg.get("total_mentions", 0)
        parts.append(f"  Bias: {bias}")
        parts.append(f"  Positive ratio: {pos_ratio}")
        parts.append(f"  Total mentions: {mentions}")
        # Contrarian notes
        if bias == "bullish" and pos_ratio and float(pos_ratio) > 0.8:
            parts.append("  NOTE: Extreme social bullishness — contrarian caution warranted")
        elif bias == "bearish" and pos_ratio and float(pos_ratio) < 0.3:
            parts.append("  NOTE: Social bearishness — potential value opportunity if fundamentals strong")
        return parts

    @staticmethod
    def _fmt_analyst_ratings(ratings: dict) -> list[str]:
        """Format analyst consensus ratings."""
        parts = ["", "ANALYST RATINGS:"]
        if ratings.get("price_target"):
            pt = ratings["price_target"]
            parts.append(
                f"  Price targets: Low ${pt.get('low', '?')} | "
                f"Mean ${pt.get('mean', '?')} | High ${pt.get('high', '?')}"
            )
        if ratings.get("trends"):
            latest = ratings["trends"][0]
            total = sum(latest.get(k, 0) for k in ("strong_buy", "buy", "hold", "sell", "strong_sell"))
            if total:
                parts.append(
                    f"  Consensus ({latest.get('period', 'recent')}): "
                    f"{latest.get('strong_buy', 0)} Strong Buy, "
                    f"{latest.get('buy', 0)} Buy, "
                    f"{latest.get('hold', 0)} Hold, "
                    f"{latest.get('sell', 0)} Sell, "
                    f"{latest.get('strong_sell', 0)} Strong Sell"
                )
        if ratings.get("recent_changes"):
            parts.append("  Recent changes:")
            for c in ratings["recent_changes"][:3]:
                parts.append(
                    f"    {c.get('firm', '?')}: {c.get('action', '?')} "
                    f"({c.get('from_grade', '?')} → {c.get('to_grade', '?')})"
                )
        return parts

    @staticmethod
    def _fmt_short_interest(si: dict) -> list[str]:
        """Format short interest data."""
        parts = ["", "SHORT INTEREST:"]
        shares = si.get("short_interest", 0)
        if shares:
            parts.append(f"  Short shares: {shares:,}")
        if si.get("change_pct") is not None:
            direction = "up" if si["change_pct"] > 0 else "down"
            parts.append(f"  Change: {direction} {abs(si['change_pct'])}% from prior period")
            if si["change_pct"] > 20:
                parts.append("  NOTE: Significant increase in short interest — bearish signal")
            elif si["change_pct"] < -20:
                parts.append("  NOTE: Significant short covering — potential squeeze/bullish")
        if si.get("settlement_date"):
            parts.append(f"  As of: {si['settlement_date']}")
        return parts

    @staticmethod
    def _fmt_research_briefing(briefing: str) -> list[str]:
        """Format the Gemini-synthesized research briefing."""
        return [
            "",
            "=" * 60,
            "DEEP RESEARCH BRIEFING (synthesized from news, social media, analyst reports):",
            "=" * 60,
            briefing,
            "=" * 60,
        ]

    @staticmethod
    def _fmt_macro(macro: dict) -> list[str]:
        parts = ["", "MACRO ENVIRONMENT:"]
        for k, v in macro.items():
            parts.append(f"  {k}: {v}")
        return parts

    @staticmethod
    def _fmt_market_snapshot(snap: dict) -> list[str]:
        parts = ["", "MARKET SNAPSHOT:"]
        for k, v in snap.items():
            parts.append(f"  {k}: {v}")
        return parts

    @staticmethod
    def _fmt_sector_performance(perf: dict, ticker_sector: str) -> list[str]:
        """Format sector ETF 1-month performance for sector rotation context."""
        # Map sector names to ETF tickers
        etf_to_sector = {
            "XLK": "Technology", "XLV": "Healthcare", "XLF": "Financials",
            "XLI": "Industrials", "XLC": "Communication", "XLY": "Consumer Cyclical",
            "XLP": "Consumer Defensive", "XLE": "Energy", "XLU": "Utilities",
            "XLB": "Basic Materials", "XLRE": "Real Estate",
        }
        parts = ["", "SECTOR ETF PERFORMANCE (1-month):"]
        for etf, pct in sorted(perf.items(), key=lambda x: x[1], reverse=True):
            name = etf_to_sector.get(etf, etf)
            marker = " ← THIS SECTOR" if name == ticker_sector else ""
            parts.append(f"  {name} ({etf}): {pct:+.1f}%{marker}")
        return parts

    @staticmethod
    def _fmt_technical(request: AnalysisRequest) -> list[str]:
        """Format technical indicators with interpretation hints."""
        if not request.technical_indicators:
            return [
                "",
                "WARNING: No pre-computed technical indicators available.",
                "Without technical data, you CANNOT perform meaningful technical analysis.",
                "Set confidence to 0.0-0.15 and use NO_ACTION tag.",
            ]

        ti = request.technical_indicators
        parts = ["", "PRE-COMPUTED TECHNICAL INDICATORS:"]
        for k, v in ti.items():
            parts.append(f"  {k}: {v}")

        # Interpretation hints
        hints: list[str] = []
        if ti.get("rsi_14"):
            rsi = float(ti["rsi_14"])
            if rsi > 70:
                hints.append(f"  - RSI is {rsi:.1f} (ABOVE 70 = OVERBOUGHT territory)")
            elif rsi < 30:
                hints.append(f"  - RSI is {rsi:.1f} (BELOW 30 = OVERSOLD territory)")
        if ti.get("macd_histogram"):
            macd_h = float(ti["macd_histogram"])
            if macd_h < 0:
                hints.append(f"  - MACD histogram is NEGATIVE ({macd_h:.4f}) = bearish momentum")
        if ti.get("price_vs_sma200") == "below":
            hints.append("  - Price is BELOW 200-day SMA = bearish trend")
        if ti.get("pct_from_52w_high"):
            pct = float(ti["pct_from_52w_high"])
            if pct < -20:
                hints.append(f"  - Stock is {abs(pct):.1f}% below 52-week high = significant drawdown")

        if hints:
            parts.append("")
            parts.append("Key thresholds to evaluate:")
            parts.extend(hints)

        return parts

    def _fmt_portfolio(self, request: AnalysisRequest) -> list[str]:
        """Format portfolio context."""
        pc = request.portfolio_context
        if not pc:
            return []

        parts = ["", "PORTFOLIO CONTEXT:"]
        parts.append(f"  Total value: ${pc.get('total_value', 0):,.0f}")
        parts.append(f"  Positions: {pc.get('position_count', 0)}")

        held = pc.get("held_tickers", [])
        if request.ticker in held:
            parts.append(f"  NOTE: Already hold {request.ticker}")
            for pos in pc.get("positions", []):
                if pos.get("ticker") == request.ticker:
                    parts.append(f"    Current weight: {pos.get('weight_pct', 0):.1f}%")
                    pnl = pos.get("pnl_pct", 0)
                    parts.append(f"    P&L: {pnl:+.1f}%")
                    break
        else:
            parts.append("  This would be a NEW position")

        # Sector exposure
        se = pc.get("sector_exposure", {})
        if se:
            sector_pct = se.get(request.sector, 0)
            if sector_pct > 25:
                parts.append(f"  WARNING: {request.sector} already at {sector_pct:.0f}% of portfolio")
            elif sector_pct > 0:
                parts.append(f"  {request.sector} exposure: {sector_pct:.0f}%")
            else:
                parts.append(f"  {request.sector} is a NEW sector — adds diversification")

        return parts

    @staticmethod
    def _fmt_thesis(request: AnalysisRequest) -> list[str]:
        parts = ["", "THESIS CONTEXT:"]
        parts.append(f"  Original buy thesis: {request.position_thesis[:300]}")
        if request.position_type:
            parts.append(f"  Position type: {request.position_type}")
        if request.days_held is not None:
            parts.append(f"  Held for: {request.days_held} days")
        if request.thesis_health:
            parts.append(f"  Thesis health: {request.thesis_health}")
        parts.append("  CRITICAL: Evaluate whether this thesis remains INTACT.")
        parts.append("  Do NOT recommend selling just because of short-term noise.")
        parts.append("  Only recommend selling if the fundamental thesis is BROKEN.")
        return parts

    @staticmethod
    def _fmt_previous_verdict(pv: dict) -> list[str]:
        parts = [
            "",
            "PREVIOUS ANALYSIS:",
            f"  Last verdict: {pv.get('verdict')} on {pv.get('date', 'unknown date')}",
            f"  Confidence: {pv.get('confidence')}, Consensus: {pv.get('consensus_score')}",
        ]
        if pv.get("reasoning"):
            parts.append(f"  Reasoning: {pv['reasoning'][:200]}")
        # Verdict chain from Neo4j (historical verdicts for this ticker)
        chain = pv.get("verdict_chain")
        if chain:
            parts.append("  VERDICT HISTORY (most recent first):")
            for entry in chain[:5]:
                v = entry.get("verdict", "?")
                c = entry.get("confidence", "?")
                d = entry.get("date", "?")
                parts.append(f"    {d}: {v} (conf: {c})")
        parts.append("  Consider: Has anything materially changed since the last analysis?")
        return parts

    @staticmethod
    def _fmt_similar_situations(situations: list[dict]) -> list[str]:
        """Format similar past situations from Qdrant semantic memory."""
        parts = ["", "SIMILAR PAST SITUATIONS (from institutional memory):"]
        for i, s in enumerate(situations[:3], 1):
            sim_pct = int(s.get("similarity", 0) * 100)
            verdict = s.get("verdict", "?")
            ticker = s.get("ticker", "?")
            conf = s.get("confidence", 0)
            date = s.get("date", "?")[:10] if s.get("date") else "?"
            outcome = s.get("outcome")
            reasoning = s.get("reasoning", "")[:150]

            parts.append(f"  {i}. {ticker} ({date}, {sim_pct}% similar): {verdict} conf={conf:.0%}")
            if reasoning:
                parts.append(f"     Context: {reasoning}")
            if outcome:
                parts.append(f"     OUTCOME: {outcome}")
            else:
                parts.append("     Outcome: pending")
        parts.append("  Use these patterns to inform — but do not blindly follow — your verdict.")
        return parts
