"""Portfolio-level risk assessment — LLM-powered analysis of portfolio health.

Runs on-demand (not per-ticker). Analyses the whole portfolio for correlation,
concentration, stress scenarios, liquidity, beta, and regime alignment.
Uses hash-based caching: only re-runs when portfolio composition changes.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime

from fastapi import APIRouter, Depends

from investmentology.api.deps import get_gateway, get_registry
from investmentology.agents.gateway import LLMGateway
from investmentology.registry.queries import Registry

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory cache for risk assessment (survives until pod restart)
_cache: dict[str, dict] = {}


def _portfolio_hash(positions: list, sector_map: dict[str, str], total_value: float) -> str:
    """Compute a hash of portfolio composition.

    Includes tickers, share counts, and allocation percentages rounded to 1%.
    Small price movements don't invalidate the cache; trades and significant
    drift do.
    """
    parts = []
    for p in sorted(positions, key=lambda x: x.ticker):
        mv = float(p.current_price * p.shares)
        alloc_pct = round(mv / total_value * 100) if total_value > 0 else 0
        sector = sector_map.get(p.ticker, "Unknown")
        parts.append(f"{p.ticker}:{int(p.shares)}:{alloc_pct}:{sector}")
    raw = "|".join(parts)
    return hashlib.md5(raw.encode()).hexdigest()[:12]


_SYSTEM_PROMPT = """\
You are a warm, knowledgeable portfolio advisor having a one-on-one conversation \
with the investor about their portfolio. You know their positions intimately.

Your tone: friendly, clear, reassuring but honest. Like a trusted advisor over \
coffee — not a compliance report. Use "your" and "you" naturally. Speak about \
stocks by name like old friends. Be specific with numbers but weave them into \
natural sentences, not tables.

You MUST return valid JSON with this exact structure:
{
  "risk_score": <1-10 integer, 1=very safe, 10=extremely risky>,
  "risk_label": "<LOW|MODERATE|ELEVATED|HIGH|CRITICAL>",
  "overview": "<3-4 warm sentences about overall portfolio health. Start with how things look, then the key thing to know right now>",
  "portfolio_roles": [
    {
      "ticker": "<symbol>",
      "role": "<Growth Engine|Income Generator|Defensive Anchor|Speculative Bet|Turnaround Play|Core Holding|Cash Cow>",
      "comment": "<1 sentence — what this stock does for the portfolio, written warmly. e.g. 'Your biggest winner and the backbone of your tech exposure'>"
    }
  ],
  "what_id_change": "<1-2 sentences. The ONE thing you'd adjust if you could. Be specific. If nothing, say the portfolio looks great as-is>",
  "watch_out_for": ["<2-4 plain-English risks. Not jargon — things like 'If tech sells off, half your portfolio feels it' or 'Your biggest position is getting quite large'>"],
  "stress_scenarios": [
    {"scenario": "<plain English scenario>", "estimated_impact_pct": <number>, "comment": "<1 sentence — what happens and which positions get hit>"}
  ],
  "regime_comment": "<1-2 sentences about whether portfolio positioning fits the current market environment>",
  "suggestions": [
    {"action": "<Trim|Build up|Start a position in|Take some profits on|Consider adding>", "ticker": "<or 'cash' or 'bonds'>", "reason": "<conversational reason — why this helps>"}
  ]
}

Rules:
- Classify EVERY position into a portfolio role. The investor wants to understand what each stock does for them.
- Be honest but not alarmist. If the portfolio is solid, celebrate that.
- Use actual numbers from the data — percentages, dollar values, P&L figures.
- "watch_out_for" should be things a friend would flag, not a risk committee. Plain English.
- Stress scenarios: pick 2-3 realistic ones. Say which stocks get hurt.
- Suggestions should feel like advice, not orders. "You might want to..." not "TRIM IMMEDIATELY."
- If the portfolio is well-balanced, say so warmly. Don't manufacture problems.
"""


@router.get("/portfolio/risk-assessment")
async def get_risk_assessment(
    registry: Registry = Depends(get_registry),
    gateway: LLMGateway = Depends(get_gateway),
) -> dict:
    """LLM-powered portfolio risk assessment with hash-based caching."""
    start = time.time()

    # 1. Gather portfolio data
    positions = registry.get_open_positions()
    if not positions:
        return {
            "assessment": None,
            "cached": False,
            "reason": "no_positions",
        }

    total_value = float(sum(p.current_price * p.shares for p in positions))
    if total_value <= 0:
        return {
            "assessment": None,
            "cached": False,
            "reason": "zero_value",
        }

    # Build sector map
    stocks = registry.get_active_stocks()
    stock_map = {s.ticker: s for s in stocks}
    sector_map = {
        p.ticker: (stock_map[p.ticker].sector if p.ticker in stock_map else "Unknown")
        for p in positions
    }

    # 2. Check cache
    phash = _portfolio_hash(positions, sector_map, total_value)
    if phash in _cache:
        cached = _cache[phash]
        cached["cached"] = True
        cached["portfolio_hash"] = phash
        return cached

    # 3. Build portfolio context for LLM
    context_parts = []
    context_parts.append(f"PORTFOLIO SUMMARY: {len(positions)} positions, "
                         f"total value ${total_value:,.0f}")

    # Cash
    try:
        budget = registry._db.execute(
            "SELECT total_budget, cash_available FROM invest.portfolio_budget "
            "ORDER BY updated_at DESC LIMIT 1"
        )
        if budget:
            cash = float(budget[0]["cash_available"])
            total_budget = float(budget[0]["total_budget"])
            cash_pct = cash / total_budget * 100 if total_budget > 0 else 0
            context_parts.append(f"CASH: ${cash:,.0f} ({cash_pct:.1f}% of budget)")
    except Exception:
        pass

    # Positions detail
    context_parts.append("\nPOSITIONS:")
    sector_values: dict[str, float] = {}
    for p in sorted(positions, key=lambda x: float(x.current_price * x.shares), reverse=True):
        mv = float(p.current_price * p.shares)
        alloc = mv / total_value * 100
        pnl_pct = ((float(p.current_price) / float(p.entry_price)) - 1) * 100 if p.entry_price else 0
        sector = sector_map.get(p.ticker, "Unknown")
        industry = stock_map[p.ticker].industry if p.ticker in stock_map else "Unknown"
        ptype = p.position_type or "core"

        sector_values[sector] = sector_values.get(sector, 0) + mv
        context_parts.append(
            f"  {p.ticker}: ${mv:,.0f} ({alloc:.1f}%), sector={sector}, "
            f"industry={industry}, type={ptype}, P&L={pnl_pct:+.1f}%"
        )

    # Sector summary
    context_parts.append("\nSECTOR ALLOCATION:")
    for sector, val in sorted(sector_values.items(), key=lambda x: -x[1]):
        pct = val / total_value * 100
        context_parts.append(f"  {sector}: {pct:.1f}%")

    # Macro regime
    try:
        regime = registry._db.execute(
            "SELECT data_value FROM invest.pipeline_data_cache "
            "WHERE data_key = 'macro_regime' "
            "ORDER BY created_at DESC LIMIT 1"
        )
        if regime:
            val = regime[0]["data_value"]
            rd = val if isinstance(val, dict) else json.loads(val)
            context_parts.append(
                f"\nMACRO REGIME: {rd.get('regime', 'unknown')} "
                f"(stance: {rd.get('stance', 'N/A')})"
            )
    except Exception:
        pass

    # Recent alerts
    try:
        alerts = registry._db.execute(
            "SELECT ticker, alert_type, severity, message "
            "FROM invest.portfolio_alerts WHERE resolved_at IS NULL "
            "ORDER BY created_at DESC LIMIT 5"
        )
        if alerts:
            context_parts.append("\nACTIVE ALERTS:")
            for a in alerts:
                context_parts.append(f"  [{a['severity']}] {a['ticker']}: {a['message']}")
    except Exception:
        pass

    portfolio_context = "\n".join(context_parts)

    # 4. Call LLM
    provider = "deepseek"
    model = "deepseek-chat"
    if "deepseek" not in gateway._providers:
        provider = "groq"
        model = "llama-3.3-70b-versatile"

    assessment = None
    try:
        response = await gateway.call(
            provider=provider,
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=f"Analyse this portfolio for risk:\n\n{portfolio_context}",
            model=model,
            max_tokens=2048,
            temperature=0.2,
        )

        # Parse JSON from response
        content = response.content.strip()
        # Handle markdown code blocks
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

        assessment = json.loads(content)
    except json.JSONDecodeError:
        logger.warning("Risk assessment LLM returned non-JSON: %s", response.content[:200])
        assessment = {
            "risk_score": 5,
            "risk_label": "UNKNOWN",
            "summary": response.content[:500] if response else "Failed to parse risk assessment",
            "concentration_analysis": {"flags": []},
            "stress_scenarios": [],
            "regime_alignment": {"alignment": "UNKNOWN", "comment": "Parse failed"},
            "rebalancing_suggestions": [],
            "key_risks": ["Risk assessment parse failed — review manually"],
        }
    except Exception as e:
        logger.exception("Risk assessment LLM call failed")
        return {
            "assessment": None,
            "cached": False,
            "error": str(e)[:200],
        }

    latency_ms = int((time.time() - start) * 1000)

    result = {
        "assessment": assessment,
        "cached": False,
        "portfolio_hash": phash,
        "assessed_at": datetime.utcnow().isoformat(),
        "position_count": len(positions),
        "total_value": total_value,
        "latency_ms": latency_ms,
    }

    # 5. Cache result
    _cache[phash] = result

    return result


@router.post("/portfolio/risk-assessment/refresh")
async def force_risk_assessment(
    registry: Registry = Depends(get_registry),
    gateway: LLMGateway = Depends(get_gateway),
) -> dict:
    """Force re-run risk assessment, ignoring cache."""
    global _cache
    _cache = {}
    return await get_risk_assessment(registry=registry, gateway=gateway)
