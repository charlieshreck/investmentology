"""DataEnricher: enriches AnalysisRequest with external data sources.

Orchestrates FRED (macro) and Finnhub (news/earnings/insider/sentiment)
providers to populate context fields on AnalysisRequest before agents run.
"""

from __future__ import annotations

import logging

from investmentology.agents.base import AnalysisRequest
from investmentology.data.edgar_tools import EdgarToolsProvider
from investmentology.data.finnhub_provider import FinnhubProvider
from investmentology.data.fred_provider import FredProvider

if __import__("typing").TYPE_CHECKING:
    from investmentology.config import AppConfig

logger = logging.getLogger(__name__)


def build_enricher(config: AppConfig) -> DataEnricher | None:
    """Build a DataEnricher from app config. Returns None if no providers available."""
    fred = FredProvider(config.fred_api_key) if config.fred_api_key else None
    finnhub = FinnhubProvider(config.finnhub_api_key) if config.finnhub_api_key else None
    edgar = EdgarToolsProvider()  # No API key needed (SEC is free)
    if fred or finnhub or edgar:
        return DataEnricher(fred=fred, finnhub=finnhub, edgar=edgar)
    return None


class DataEnricher:
    """Enriches AnalysisRequest with data from external providers."""

    def __init__(
        self,
        fred: FredProvider | None = None,
        finnhub: FinnhubProvider | None = None,
        edgar: EdgarToolsProvider | None = None,
    ) -> None:
        self._fred = fred
        self._finnhub = finnhub
        self._edgar = edgar
        self._macro_cache: dict | None = None

    def enrich(self, request: AnalysisRequest) -> AnalysisRequest:
        """Populate context fields on the request. Modifies in place and returns it.

        Failures in any provider are logged and silently skipped — enrichment
        is best-effort and must never block analysis.
        """
        self._enrich_macro(request)
        self._enrich_news(request)
        self._enrich_earnings(request)
        self._enrich_insider(request)
        self._enrich_social(request)
        self._enrich_filings(request)
        self._enrich_holders(request)
        self._enrich_technical(request)
        self._enrich_analyst_ratings(request)
        self._enrich_short_interest(request)
        self._enrich_sector_performance(request)
        return request

    def _enrich_macro(self, request: AnalysisRequest) -> None:
        """Add FRED macro context + pendulum reading (shared across all tickers in a batch).

        Falls back to market_snapshot data (VIX, yields) when FRED is unavailable.
        """
        macro_data: dict = {}

        # Primary source: FRED economic data
        if self._fred:
            try:
                if self._macro_cache is None:
                    self._macro_cache = self._fred.get_macro_context()
                    # Inject pendulum reading into macro context
                    try:
                        from investmentology.data.pendulum_feeds import auto_pendulum_reading
                        reading = auto_pendulum_reading()
                        if reading:
                            self._macro_cache["pendulum_score"] = int(reading.score)
                            self._macro_cache["pendulum_label"] = reading.label
                            self._macro_cache["pendulum_sizing_multiplier"] = str(reading.sizing_multiplier)
                            # Include component scores for deeper analysis
                            if reading.components:
                                for comp_name, comp_val in reading.components.items():
                                    self._macro_cache[f"pendulum_{comp_name}"] = str(comp_val)
                    except Exception:
                        logger.debug("Pendulum enrichment failed, continuing without")
                macro_data = dict(self._macro_cache)
            except Exception:
                logger.warning("FRED enrichment failed for %s", request.ticker)

        # Fallback: extract macro data from market_snapshot when FRED is unavailable
        if not macro_data and request.market_snapshot:
            snap = request.market_snapshot
            if snap.get("vix") is not None:
                macro_data["vix"] = float(snap["vix"])
            if snap.get("ten_year_yield") is not None:
                macro_data["treasury_10y"] = float(snap["ten_year_yield"])
            if snap.get("three_month_yield") is not None:
                macro_data["treasury_3m"] = float(snap["three_month_yield"])
            if snap.get("yield_spread") is not None:
                macro_data["yield_curve_spread"] = float(snap["yield_spread"])
                macro_data["yield_curve_inverted"] = float(snap["yield_spread"]) < 0
            if macro_data:
                macro_data["_source"] = "market_snapshot_fallback"
                logger.info("Using market snapshot fallback for macro context (%d indicators)", len(macro_data) - 1)

        if not macro_data:
            return

        # Merge with any existing macro_context (e.g. manually passed)
        if request.macro_context:
            merged = dict(macro_data)
            merged.update(request.macro_context)
            request.macro_context = merged
        else:
            request.macro_context = macro_data

    def _enrich_news(self, request: AnalysisRequest) -> None:
        if not self._finnhub or request.news_context is not None:
            return
        try:
            request.news_context = self._finnhub.get_news(request.ticker)
        except Exception:
            logger.warning("News enrichment failed for %s", request.ticker)
            request.news_context = []

    def _enrich_earnings(self, request: AnalysisRequest) -> None:
        if not self._finnhub or request.earnings_context is not None:
            return
        try:
            request.earnings_context = self._finnhub.get_earnings(request.ticker)
        except Exception:
            logger.warning("Earnings enrichment failed for %s", request.ticker)

    def _enrich_insider(self, request: AnalysisRequest) -> None:
        if not self._finnhub or request.insider_context is not None:
            return
        try:
            request.insider_context = self._finnhub.get_insider_transactions(request.ticker)
        except Exception:
            logger.warning("Insider enrichment failed for %s", request.ticker)
            request.insider_context = []

    def _enrich_social(self, request: AnalysisRequest) -> None:
        if not self._finnhub or request.social_sentiment is not None:
            return
        try:
            request.social_sentiment = self._finnhub.get_social_sentiment(request.ticker)
        except Exception:
            logger.warning("Social sentiment enrichment failed for %s", request.ticker)

    def _enrich_filings(self, request: AnalysisRequest) -> None:
        if not self._edgar or request.filing_context is not None:
            return
        try:
            request.filing_context = self._edgar.get_filing_text(request.ticker)
        except Exception:
            logger.warning("Filing enrichment failed for %s", request.ticker)

    def _enrich_holders(self, request: AnalysisRequest) -> None:
        if not self._edgar or request.institutional_context is not None:
            return
        try:
            result = self._edgar.get_institutional_holders(request.ticker)
            # edgar returns {"holders": [...], ...} — agents expect a flat list
            if isinstance(result, dict):
                request.institutional_context = result.get("holders", [])
            else:
                request.institutional_context = result or []
        except Exception:
            logger.warning("Institutional holders enrichment failed for %s", request.ticker)
            request.institutional_context = []

    def _enrich_analyst_ratings(self, request: AnalysisRequest) -> None:
        if not self._finnhub or request.analyst_ratings is not None:
            return
        try:
            request.analyst_ratings = self._finnhub.get_analyst_ratings(request.ticker)
        except Exception:
            logger.warning("Analyst ratings enrichment failed for %s", request.ticker)

    def _enrich_short_interest(self, request: AnalysisRequest) -> None:
        if not self._finnhub or request.short_interest is not None:
            return
        try:
            request.short_interest = self._finnhub.get_short_interest(request.ticker)
        except Exception:
            logger.warning("Short interest enrichment failed for %s", request.ticker)

    def _enrich_sector_performance(self, request: AnalysisRequest) -> None:
        """Add sector ETF performance data (shared across all tickers in a batch)."""
        if request.sector_performance is not None:
            return
        try:
            from investmentology.data.snapshots import fetch_sector_performance

            if not hasattr(self, "_sector_perf_cache"):
                self._sector_perf_cache = None
            if self._sector_perf_cache is None:
                raw = fetch_sector_performance(period="1mo")
                self._sector_perf_cache = {k: float(v) for k, v in raw.items()} if raw else {}
            if self._sector_perf_cache:
                request.sector_performance = dict(self._sector_perf_cache)
        except Exception:
            logger.warning("Sector performance enrichment failed for %s", request.ticker)

    def _enrich_technical(self, request: AnalysisRequest) -> None:
        """Compute technical indicators for Simons agent."""
        if request.technical_indicators is not None:
            return
        try:
            from investmentology.data.technical_indicators import compute_technical_indicators
            request.technical_indicators = compute_technical_indicators(request.ticker)
        except Exception:
            logger.warning("Technical indicator enrichment failed for %s", request.ticker)
