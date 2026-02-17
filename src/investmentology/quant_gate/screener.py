from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from investmentology.config import AppConfig
from investmentology.data.edgar_client import EdgarClient
from investmentology.data.universe import load_full_universe
from investmentology.data.yfinance_client import YFinanceClient
from investmentology.models.decision import Decision, DecisionType
from investmentology.models.lifecycle import WatchlistState
from investmentology.models.stock import FundamentalsSnapshot, Stock
from investmentology.quant_gate.altman import calculate_altman
from investmentology.quant_gate.composite import composite_score
from investmentology.quant_gate.greenblatt import rank_by_greenblatt
from investmentology.quant_gate.piotroski import calculate_piotroski
from investmentology.registry.queries import Registry

logger = logging.getLogger(__name__)


@dataclass
class DataQualityReport:
    universe_size: int
    after_exclusions: int
    scored: int
    missing_ebit_pct: float
    stale_pct: float
    circuit_breaker_healthy: bool
    exclusion_reasons: dict[str, int] = field(default_factory=dict)


@dataclass
class ScreenerResult:
    run_id: int
    top_results: list[dict]  # Combined Greenblatt + Piotroski + Altman
    data_quality: DataQualityReport


def _dict_to_snapshot(d: dict) -> FundamentalsSnapshot | None:
    """Convert yfinance result dict to FundamentalsSnapshot.

    Returns None if critical fields are missing.
    """
    try:
        # EDGAR provides net_ppe directly; yfinance uses net_tangible_assets as proxy
        net_ppe = d.get("net_ppe") or d.get("net_tangible_assets") or Decimal(0)
        return FundamentalsSnapshot(
            ticker=d["ticker"],
            fetched_at=datetime.fromisoformat(d["fetched_at"]) if isinstance(d["fetched_at"], str) else d["fetched_at"],
            operating_income=d.get("operating_income") or Decimal(0),
            market_cap=d.get("market_cap") or Decimal(0),
            total_debt=d.get("total_debt") or Decimal(0),
            cash=d.get("cash") or Decimal(0),
            current_assets=d.get("current_assets") or Decimal(0),
            current_liabilities=d.get("current_liabilities") or Decimal(0),
            net_ppe=net_ppe,
            revenue=d.get("revenue") or Decimal(0),
            net_income=d.get("net_income") or Decimal(0),
            total_assets=d.get("total_assets") or Decimal(0),
            total_liabilities=d.get("total_liabilities") or Decimal(0),
            shares_outstanding=int(d["shares_outstanding"]) if d.get("shares_outstanding") else 0,
            price=d.get("price") or Decimal(0),
        )
    except (KeyError, TypeError, ValueError):
        logger.debug("Failed to convert dict to snapshot for %s", d.get("ticker"))
        return None


def _dict_to_stock(d: dict) -> Stock:
    """Convert universe dict to Stock model."""
    return Stock(
        ticker=d["ticker"],
        name=d.get("name", ""),
        sector=d.get("sector", ""),
        industry=d.get("industry", ""),
        market_cap=Decimal(str(d.get("market_cap", 0))),
        exchange=d.get("exchange", ""),
    )


class QuantGateScreener:
    """Orchestrates the full Greenblatt Magic Formula screening pipeline."""

    def __init__(
        self,
        registry: Registry,
        yf_client: YFinanceClient,
        config: AppConfig,
        edgar_client: EdgarClient | None = None,
    ) -> None:
        self._registry = registry
        self._yf = yf_client
        self._edgar = edgar_client
        self._config = config

    def run(self) -> ScreenerResult:
        """Full screening pipeline:
        1. Fetch universe via load_full_universe()
        2. Upsert stocks to DB via registry
        3. Fetch fundamentals batch via yf_client
        4. Insert fundamentals to DB
        5. Apply Greenblatt exclusions + ranking
        6. Calculate Piotroski + Altman for top N
        7. Create quant gate run in DB
        8. Insert results to DB
        9. Log SCREEN decision for the batch
        10. Add top N to watchlist as CANDIDATE
        11. Return ScreenerResult
        """
        top_n = self._config.quant_gate_top_n

        # 1. Load universe
        logger.info("Loading stock universe...")
        universe = load_full_universe(
            min_market_cap=self._config.universe_min_market_cap,
        )
        universe_size = len(universe)
        logger.info("Universe loaded: %d tickers", universe_size)

        if not universe:
            logger.error("Empty universe, aborting screen")
            return self._empty_result(universe_size=0)

        # 2. Upsert stocks to DB
        stocks = [_dict_to_stock(u) for u in universe]
        self._registry.upsert_stocks(stocks)
        logger.info("Upserted %d stocks", len(stocks))

        # Build sector/industry lookups
        sectors: dict[str, str] = {u["ticker"]: u.get("sector", "") for u in universe}
        industries: dict[str, str] = {u["ticker"]: u.get("industry", "") for u in universe}

        # 3. Fetch fundamentals
        tickers = [u["ticker"] for u in universe]
        logger.info("Fetching fundamentals for %d tickers...", len(tickers))

        if self._edgar is not None:
            # EDGAR path: bulk frames (fast, ~7s for all companies)
            raw_fundamentals = self._edgar.get_fundamentals_batch(tickers)
            # Enrich with sector/industry from universe
            self._edgar.enrich_with_sectors(raw_fundamentals, sectors, industries)
            # Fetch prices via yfinance in chunks to avoid rate limiting
            logger.info("Fetching prices for %d tickers via yfinance...", len(tickers))
            all_prices: dict[str, Decimal] = {}
            chunk_size = 100
            total_chunks = (len(tickers) + chunk_size - 1) // chunk_size
            failed_chunks: list[list[str]] = []
            for i in range(0, len(tickers), chunk_size):
                chunk = tickers[i : i + chunk_size]
                chunk_prices = self._yf.get_prices_batch(chunk)
                all_prices.update(chunk_prices)
                chunk_num = i // chunk_size + 1
                logger.info(
                    "Price chunk %d/%d: got %d prices (%d total)",
                    chunk_num, total_chunks, len(chunk_prices), len(all_prices),
                )
                if not chunk_prices:
                    failed_chunks.append(chunk)
                time.sleep(1)  # 1s pause between chunks to avoid rate limiting
            # Retry any failed chunks once after a longer pause
            if failed_chunks:
                logger.info("Retrying %d failed price chunks after 10s pause...", len(failed_chunks))
                time.sleep(10)
                for chunk in failed_chunks:
                    chunk_prices = self._yf.get_prices_batch(chunk)
                    all_prices.update(chunk_prices)
                    logger.info("Retry got %d prices (%d total)", len(chunk_prices), len(all_prices))
                    time.sleep(2)
            logger.info("Got prices for %d/%d tickers", len(all_prices), len(tickers))
            self._edgar.enrich_with_prices(raw_fundamentals, all_prices)
        else:
            # Legacy yfinance path (slow, rate-limited)
            raw_fundamentals = self._yf.get_fundamentals_batch(tickers)

        logger.info("Got fundamentals for %d tickers", len(raw_fundamentals))

        # Convert to snapshots
        snapshots: list[FundamentalsSnapshot] = []
        missing_ebit = 0
        for raw in raw_fundamentals:
            snap = _dict_to_snapshot(raw)
            if snap is None:
                continue
            if not snap.operating_income or snap.operating_income <= 0:
                missing_ebit += 1
            snapshots.append(snap)

        # 4. Insert fundamentals to DB
        if snapshots:
            self._registry.insert_fundamentals(snapshots)
            logger.info("Inserted %d fundamentals snapshots", len(snapshots))

        # 5. Apply Greenblatt ranking
        ranked = rank_by_greenblatt(snapshots, sectors=sectors)
        logger.info("Greenblatt ranking: %d eligible stocks", len(ranked))

        if not ranked:
            return self._empty_result(universe_size=universe_size)

        # Take top N
        top_ranked = ranked[:top_n]

        # Build snapshot lookup for enrichment
        snap_by_ticker: dict[str, FundamentalsSnapshot] = {s.ticker: s for s in snapshots}

        # Build prior-year snapshot lookup for Piotroski YoY comparisons
        prior_by_ticker: dict[str, FundamentalsSnapshot] = {}
        has_prior = False
        if self._edgar is not None:
            prior_tickers = [gr.ticker for gr in top_ranked]
            prior_raws = self._edgar.get_prior_fundamentals_batch(prior_tickers)
            for raw in prior_raws:
                prior_snap = _dict_to_snapshot(raw)
                if prior_snap is not None:
                    prior_by_ticker[prior_snap.ticker] = prior_snap
            has_prior = len(prior_by_ticker) > 0
            logger.info("Prior-year data: %d/%d top stocks", len(prior_by_ticker), len(prior_tickers))

        total_ranked = len(ranked)

        # 6. Calculate Piotroski + Altman + Composite for top N
        top_results: list[dict] = []
        for gr in top_ranked:
            snap = snap_by_ticker.get(gr.ticker)
            if snap is None:
                continue

            prior_snap = prior_by_ticker.get(gr.ticker)
            piotroski = calculate_piotroski(snap, previous=prior_snap)
            altman = calculate_altman(snap)

            score = composite_score(
                greenblatt_rank=gr.combined_rank,
                total_ranked=total_ranked,
                piotroski_score=piotroski.score,
                has_prior_year=prior_snap is not None,
                altman_zone=altman.zone if altman else None,
            )

            top_results.append({
                "ticker": gr.ticker,
                "earnings_yield": gr.earnings_yield,
                "roic": gr.roic,
                "ey_rank": gr.ey_rank,
                "roic_rank": gr.roic_rank,
                "combined_rank": gr.combined_rank,
                "piotroski_score": piotroski.score,
                "altman_z_score": altman.z_score if altman else None,
                "altman_zone": altman.zone if altman else None,
                "composite_score": score,
            })

        # Sort by composite score descending (highest = best)
        top_results.sort(key=lambda r: r["composite_score"], reverse=True)

        # 7. Data quality report
        missing_ebit_pct = (missing_ebit / len(snapshots) * 100) if snapshots else 0.0
        data_quality = DataQualityReport(
            universe_size=universe_size,
            after_exclusions=len(ranked),
            scored=len(top_results),
            missing_ebit_pct=round(missing_ebit_pct, 2),
            stale_pct=0.0,  # Could be computed if we track fetched_at freshness
            circuit_breaker_healthy=self._yf.is_healthy,
        )

        # 8. Create quant gate run in DB
        run_id = self._registry.create_quant_gate_run(
            universe_size=universe_size,
            passed_count=len(top_results),
            config={
                "top_n": top_n,
                "min_market_cap": self._config.universe_min_market_cap,
            },
            data_quality={
                "universe_size": data_quality.universe_size,
                "after_exclusions": data_quality.after_exclusions,
                "scored": data_quality.scored,
                "missing_ebit_pct": data_quality.missing_ebit_pct,
                "circuit_breaker_healthy": data_quality.circuit_breaker_healthy,
            },
        )

        # 9. Insert results to DB
        if top_results:
            self._registry.insert_quant_gate_results(run_id, top_results)
            logger.info("Inserted %d quant gate results for run %d", len(top_results), run_id)

        # 10. Log SCREEN decision
        self._registry.log_decision(Decision(
            ticker="BATCH",
            decision_type=DecisionType.SCREEN,
            layer_source="quant_gate",
            confidence=None,
            reasoning=f"Greenblatt Magic Formula screen: {universe_size} universe -> {len(top_results)} passed",
            signals={
                "run_id": run_id,
                "universe_size": universe_size,
                "passed_count": len(top_results),
            },
        ))

        # 11. Add top N to watchlist as CANDIDATE
        for result in top_results:
            try:
                self._registry.add_to_watchlist(
                    ticker=result["ticker"],
                    state=WatchlistState.CANDIDATE,
                    source_run_id=run_id,
                    notes=f"Greenblatt rank #{result['combined_rank']}",
                )
            except Exception:
                # Duplicate or constraint violation is expected on re-runs
                logger.debug("Could not add %s to watchlist (may already exist)", result["ticker"])

        return ScreenerResult(
            run_id=run_id,
            top_results=top_results,
            data_quality=data_quality,
        )

    def run_delta(self, previous_run_id: int) -> dict:
        """Compare current run to previous: new entries, dropped, rank changes >20."""
        current = self.run()

        # Get previous results from DB
        # We need the previous run's results for comparison
        prev_rows = self._registry._db.execute(
            "SELECT ticker, combined_rank FROM invest.quant_gate_results WHERE run_id = %s",
            (previous_run_id,),
        )
        prev_by_ticker: dict[str, int] = {
            r["ticker"]: r["combined_rank"] for r in prev_rows
        }

        curr_by_ticker: dict[str, int] = {
            r["ticker"]: r["combined_rank"] for r in current.top_results
        }

        prev_set = set(prev_by_ticker.keys())
        curr_set = set(curr_by_ticker.keys())

        new_entries = sorted(curr_set - prev_set)
        dropped = sorted(prev_set - curr_set)

        # Rank changes > 20 positions
        significant_changes: list[dict] = []
        for ticker in curr_set & prev_set:
            old_rank = prev_by_ticker[ticker]
            new_rank = curr_by_ticker[ticker]
            change = old_rank - new_rank  # positive = improved
            if abs(change) > 20:
                significant_changes.append({
                    "ticker": ticker,
                    "old_rank": old_rank,
                    "new_rank": new_rank,
                    "change": change,
                })

        significant_changes.sort(key=lambda x: abs(x["change"]), reverse=True)

        return {
            "current_run_id": current.run_id,
            "previous_run_id": previous_run_id,
            "new_entries": new_entries,
            "dropped": dropped,
            "significant_rank_changes": significant_changes,
            "data_quality": current.data_quality,
        }

    def _empty_result(self, universe_size: int) -> ScreenerResult:
        """Return an empty result for edge cases."""
        return ScreenerResult(
            run_id=0,
            top_results=[],
            data_quality=DataQualityReport(
                universe_size=universe_size,
                after_exclusions=0,
                scored=0,
                missing_ebit_pct=0.0,
                stale_pct=0.0,
                circuit_breaker_healthy=self._yf.is_healthy,
            ),
        )
