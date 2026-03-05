"""AI Research Report generator — assembles data from multiple DB sources into a structured report."""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal

from investmentology.api.routes.shared import consensus_tier
from investmentology.registry.queries import Registry

logger = logging.getLogger(__name__)


def _safe_float(v: Decimal | None) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except Exception:
        return None


class ReportService:
    """Generates structured research reports from existing DB data (no LLM calls)."""

    def __init__(self, registry: Registry) -> None:
        self._reg = registry

    def generate(self, ticker: str) -> dict | None:
        """Build a full research report for a ticker.

        Returns None if insufficient data exists.
        """
        ticker = ticker.upper()
        reg = self._reg

        # Fundamentals (optional — report still works without)
        fundamentals = reg.get_latest_fundamentals(ticker)

        # Stock info
        stock_rows = reg._db.execute(
            "SELECT name, sector, industry, market_cap FROM invest.stocks WHERE ticker = %s",
            (ticker,),
        )
        stock = stock_rows[0] if stock_rows else {}

        # Quant gate results
        qg_rows = reg._db.execute(
            "SELECT combined_rank, piotroski_score, altman_z_score, altman_zone, "
            "momentum_score, composite_score, earnings_yield, roic "
            "FROM invest.quant_gate_results WHERE ticker = %s "
            "ORDER BY id DESC LIMIT 1",
            (ticker,),
        )
        quant_gate = qg_rows[0] if qg_rows else None

        # Agent signals
        signal_rows = reg._db.execute(
            "SELECT agent_name, confidence, target_price, reasoning, created_at "
            "FROM invest.agent_signals WHERE ticker = %s "
            "ORDER BY created_at DESC LIMIT 20",
            (ticker,),
        )

        # Verdict
        verdict_rows = reg._db.execute(
            "SELECT verdict, confidence, reasoning, target_price, created_at "
            "FROM invest.verdicts WHERE ticker = %s "
            "ORDER BY created_at DESC LIMIT 1",
            (ticker,),
        )
        verdict = verdict_rows[0] if verdict_rows else None

        # Adversarial content
        adversarial_rows = reg._db.execute(
            "SELECT content_type, content FROM invest.adversarial_content "
            "WHERE ticker = %s ORDER BY created_at DESC LIMIT 5",
            (ticker,),
        )

        # Position info (if held)
        position_rows = reg._db.execute(
            "SELECT entry_price, shares, current_price, entry_date, position_type, thesis "
            "FROM invest.portfolio_positions WHERE ticker = %s AND exit_date IS NULL "
            "LIMIT 1",
            (ticker,),
        )
        position = position_rows[0] if position_rows else None

        # Decisions history
        decision_rows = reg._db.execute(
            "SELECT decision_type, confidence, reasoning, created_at "
            "FROM invest.decisions WHERE ticker = %s "
            "ORDER BY created_at DESC LIMIT 5",
            (ticker,),
        )

        # Need at least some data to build a report
        has_data = fundamentals or verdict or signal_rows or quant_gate or position
        if not has_data and not stock:
            return None

        # Build report sections
        sections = []

        # 1. Executive Summary
        if fundamentals:
            sections.append(self._executive_summary(ticker, stock, verdict, fundamentals))
        elif verdict:
            content = f"**{stock.get('name', ticker)}** ({ticker})"
            if stock.get("sector"):
                content += f" — {stock['sector']}"
            content += f"\n\n**Verdict**: {verdict['verdict']} (confidence: {float(verdict['confidence']):.0%})"
            sections.append({"title": "Executive Summary", "content": content})

        # 2. Investment Thesis
        sections.append(self._investment_thesis(ticker, position, verdict, decision_rows))

        # 3. Financial Overview
        if fundamentals:
            sections.append(self._financial_overview(fundamentals))

        # 4. Quantitative Gate
        if quant_gate:
            sections.append(self._quant_gate_section(quant_gate))

        # 5. Agent Consensus
        if signal_rows:
            sections.append(self._agent_consensus(signal_rows))

        # 6. Risk Assessment
        if adversarial_rows:
            sections.append(self._risk_assessment(adversarial_rows))

        # 7. Portfolio Context
        if position and fundamentals:
            sections.append(self._portfolio_context(position, fundamentals))

        # 8. Recommendation
        if verdict:
            sections.append(self._recommendation(verdict))

        if not sections:
            return None

        return {
            "ticker": ticker,
            "name": stock.get("name", ticker),
            "sector": stock.get("sector", ""),
            "industry": stock.get("industry", ""),
            "generated_at": datetime.utcnow().isoformat(),
            "sections": sections,
        }

    def _executive_summary(self, ticker: str, stock: dict, verdict: dict | None, fund) -> dict:
        price = _safe_float(fund.price) or 0
        mcap = _safe_float(fund.market_cap) or 0
        mcap_str = f"${mcap / 1e9:.1f}B" if mcap >= 1e9 else f"${mcap / 1e6:.0f}M"

        summary = f"**{stock.get('name', ticker)}** ({ticker}) is a {stock.get('sector', 'N/A')} "
        summary += f"company in the {stock.get('industry', 'N/A')} industry. "
        summary += f"Current price: ${price:.2f}. Market cap: {mcap_str}."

        if verdict:
            summary += f"\n\n**Verdict**: {verdict['verdict']} "
            summary += f"(confidence: {float(verdict['confidence']):.0%})"
            if verdict.get("target_price"):
                tp = float(verdict["target_price"])
                upside = ((tp - price) / price * 100) if price > 0 else 0
                summary += f". Target: ${tp:.2f} ({upside:+.1f}%)"

        return {"title": "Executive Summary", "content": summary}

    def _investment_thesis(self, ticker: str, position, verdict, decisions) -> dict:
        parts = []
        if position and position.get("thesis"):
            parts.append(f"**Active Position Thesis**: {position['thesis']}")

        if verdict and verdict.get("reasoning"):
            parts.append(f"**Latest Verdict Reasoning**: {verdict['reasoning']}")

        if decisions:
            parts.append("\n**Recent Decision History**:")
            for d in decisions[:3]:
                parts.append(
                    f"- {d['decision_type']} ({d['created_at'].strftime('%Y-%m-%d')}): "
                    f"{d['reasoning'][:200]}..."
                    if len(d.get("reasoning", "")) > 200
                    else f"- {d['decision_type']} ({d['created_at'].strftime('%Y-%m-%d')}): "
                    f"{d.get('reasoning', 'N/A')}"
                )

        return {
            "title": "Investment Thesis",
            "content": "\n\n".join(parts) if parts else "No thesis data available.",
        }

    def _financial_overview(self, fund) -> dict:
        rows = [
            ("Revenue", _safe_float(fund.revenue)),
            ("Net Income", _safe_float(fund.net_income)),
            ("Operating Income", _safe_float(fund.operating_income)),
            ("Market Cap", _safe_float(fund.market_cap)),
            ("Enterprise Value", _safe_float(fund.enterprise_value)),
            ("Total Debt", _safe_float(fund.total_debt)),
            ("Cash", _safe_float(fund.cash)),
            ("Shares Outstanding", fund.shares_outstanding),
        ]

        def fmt(v):
            if v is None:
                return "N/A"
            if isinstance(v, int):
                return f"{v:,}"
            if abs(v) >= 1e9:
                return f"${v / 1e9:.2f}B"
            if abs(v) >= 1e6:
                return f"${v / 1e6:.1f}M"
            return f"${v:,.2f}"

        table = "| Metric | Value |\n|--------|-------|\n"
        for label, val in rows:
            table += f"| {label} | {fmt(val)} |\n"

        ey = _safe_float(fund.earnings_yield) if hasattr(fund, "earnings_yield") else None
        roic = _safe_float(fund.roic) if hasattr(fund, "roic") else None
        if ey or roic:
            table += f"| Earnings Yield | {ey:.1%} |\n" if ey else ""
            table += f"| ROIC | {roic:.1%} |\n" if roic else ""

        return {"title": "Financial Overview", "content": table}

    def _quant_gate_section(self, qg: dict) -> dict:
        parts = [
            f"**Greenblatt Rank**: #{qg['combined_rank']}",
            f"**Composite Score**: {float(qg['composite_score']):.2f}" if qg.get("composite_score") else None,
            f"**Piotroski F-Score**: {qg['piotroski_score']}/9" if qg.get("piotroski_score") is not None else None,
            f"**Altman Z-Score**: {float(qg['altman_z_score']):.2f} ({qg.get('altman_zone', 'N/A')})" if qg.get("altman_z_score") else None,
            f"**Momentum**: {float(qg['momentum_score']):.2f}" if qg.get("momentum_score") is not None else None,
        ]
        return {
            "title": "Quantitative Gate",
            "content": "\n".join(p for p in parts if p),
        }

    def _agent_consensus(self, signals: list[dict]) -> dict:
        # Deduplicate to latest per agent
        seen = set()
        unique = []
        for s in signals:
            if s["agent_name"] not in seen:
                seen.add(s["agent_name"])
                unique.append(s)

        table = "| Agent | Confidence | Target | Summary |\n"
        table += "|-------|-----------|--------|--------|\n"
        for s in unique:
            conf = f"{float(s['confidence']):.0%}" if s.get("confidence") else "N/A"
            tp = f"${float(s['target_price']):.2f}" if s.get("target_price") else "—"
            reason = (s.get("reasoning") or "")[:100]
            table += f"| {s['agent_name']} | {conf} | {tp} | {reason} |\n"

        # Consensus tier
        confidences = [float(s["confidence"]) for s in unique if s.get("confidence")]
        if confidences:
            avg_conf = sum(confidences) / len(confidences)
            tier = consensus_tier(avg_conf)
            table += f"\n**Consensus**: {tier} (avg confidence: {avg_conf:.0%})"

        return {"title": "Agent Consensus", "content": table}

    def _risk_assessment(self, adversarial: list[dict]) -> dict:
        parts = []
        for row in adversarial:
            ct = row.get("content_type", "unknown")
            content = row.get("content", "")
            if isinstance(content, dict):
                content = content.get("summary", str(content)[:500])
            parts.append(f"**{ct}**: {str(content)[:500]}")

        return {
            "title": "Risk Assessment",
            "content": "\n\n".join(parts) if parts else "No adversarial review data.",
        }

    def _portfolio_context(self, position: dict, fund) -> dict:
        entry = float(position.get("entry_price", 0))
        current = float(fund.price) if fund.price else 0
        shares = float(position.get("shares", 0))
        pnl_pct = ((current - entry) / entry * 100) if entry > 0 else 0
        value = current * shares

        content = (
            f"**Position Type**: {position.get('position_type', 'N/A')}\n"
            f"**Entry**: ${entry:.2f} on {position.get('entry_date', 'N/A')}\n"
            f"**Current**: ${current:.2f} ({pnl_pct:+.1f}%)\n"
            f"**Shares**: {shares:,.0f}\n"
            f"**Position Value**: ${value:,.2f}"
        )
        return {"title": "Portfolio Context", "content": content}

    def _recommendation(self, verdict: dict) -> dict:
        content = f"**Verdict**: {verdict['verdict']}\n"
        content += f"**Confidence**: {float(verdict['confidence']):.0%}\n"
        if verdict.get("target_price"):
            content += f"**Target Price**: ${float(verdict['target_price']):.2f}\n"
        if verdict.get("reasoning"):
            content += f"\n{verdict['reasoning']}"
        return {"title": "Recommendation", "content": content}
