"""Historical quant gate backtest engine.

Runs the full quant gate screening pipeline on historical EDGAR data
(FY2020-2023, screen dates Jan 2021-2024), computes forward returns,
and measures factor IC, quintile performance, and top-N vs SPY.

Usage:
    from investmentology.backtesting.quant_historical import HistoricalQuantBacktest
    bt = HistoricalQuantBacktest(screen_years=[2021, 2022, 2023, 2024])
    result = bt.run()
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

import numpy as np

from investmentology.backtesting.ic_calculator import (
    FactorICResult,
    QuintileResult,
    TopNResult,
    compute_all_factor_ics,
    compute_quintile_returns,
    compute_top_n_vs_spy,
    ic_results_to_dict,
    quintile_results_to_dict,
    top_n_results_to_dict,
)
from investmentology.backtesting.regime_tagger import (
    compute_regime_ic_table,
    format_calibration_context,
    regime_ic_to_dict,
)
from investmentology.data.edgar_client import EdgarClient
from investmentology.data.universe import load_full_universe
from investmentology.quant_gate.altman import calculate_altman
from investmentology.quant_gate.beneish import calculate_beneish
from investmentology.quant_gate.composite import composite_score
from investmentology.quant_gate.greenblatt import rank_by_greenblatt
from investmentology.quant_gate.piotroski import calculate_piotroski
from investmentology.quant_gate.screener import _dict_to_snapshot, _rank_to_percentile

logger = logging.getLogger(__name__)

# ── Screen Configuration ─────────────────────────────────────────────────────

SCREEN_DATES: list[tuple[int, date]] = [
    (2021, date(2021, 1, 15)),
    (2022, date(2022, 1, 15)),
    (2023, date(2023, 1, 15)),
    (2024, date(2024, 1, 15)),
]

HORIZONS = [6, 12]  # months


# ── Data Structures ──────────────────────────────────────────────────────────

@dataclass
class YearScreenResult:
    """Complete screening + IC results for one screen year."""

    screen_year: int
    screen_date: date
    n_snapshots: int
    n_ranked: int
    n_scored: int
    scored_results: list[dict]
    forward_returns: dict[int, dict[str, float]]  # horizon → ticker → return
    spy_returns: dict[int, float]                  # horizon → SPY return
    ic_results: list[FactorICResult] = field(default_factory=list)
    quintile_results: list[QuintileResult] = field(default_factory=list)
    top_n_results: list[TopNResult] = field(default_factory=list)


# ── Main Engine ──────────────────────────────────────────────────────────────

class HistoricalQuantBacktest:
    """Runs the quant gate on historical EDGAR data and computes factor analytics.

    Data flow per screen year:
    1. EdgarClient(fiscal_year=YYYY-1) → fetch bulk frames + prior year
    2. enrich_with_prices(yfinance historical prices at screen date)
    3. Convert to FundamentalsSnapshot, run Greenblatt ranking
    4. Score top-N with Piotroski, Altman, Beneish, composite
    5. Fetch forward returns at 6m and 12m
    6. Compute factor IC, quintile returns, top-N vs SPY
    """

    def __init__(
        self,
        screen_years: list[int] | None = None,
        top_n: int = 100,
        db: object | None = None,
    ) -> None:
        self._screen_years = screen_years or [2021, 2022, 2023, 2024]
        self._top_n = top_n
        self._db = db
        self._universe: list[dict] | None = None
        self._sectors: dict[str, str] = {}

    def run(self) -> dict:
        """Run the full historical backtest across all screen years.

        Returns a dict matching the invest.quant_backtest_runs columns.
        If db is provided, also inserts the result.
        """
        logger.info(
            "Starting historical quant backtest: years=%s, top_n=%d",
            self._screen_years, self._top_n,
        )

        # Load universe once (sectors are sticky enough over 4 years)
        self._load_universe()

        all_ic: list[FactorICResult] = []
        all_quintile: list[QuintileResult] = []
        all_top_n: list[TopNResult] = []
        all_scored: list[dict] = []
        year_results: list[YearScreenResult] = []

        for screen_year in self._screen_years:
            screen_date = self._get_screen_date(screen_year)
            logger.info("=" * 60)
            logger.info("Screening year %d (date=%s)", screen_year, screen_date)
            try:
                yr = self._screen_year(screen_year, screen_date)
                year_results.append(yr)
                all_ic.extend(yr.ic_results)
                all_quintile.extend(yr.quintile_results)
                all_top_n.extend(yr.top_n_results)
                # Keep top-500 scored results for ticker_details
                for r in yr.scored_results[:500]:
                    r["screen_year"] = screen_year
                    all_scored.append(r)
            except Exception:
                logger.exception("Failed to screen year %d", screen_year)

        # Regime analysis
        regime_ics = compute_regime_ic_table(all_ic)
        regime_dict = regime_ic_to_dict(regime_ics)

        # Summary
        ic_12m = [r for r in all_ic if r.horizon_months == 12]
        composite_ics = [r for r in ic_12m if r.factor_name == "composite_score"]
        top20_12m = [r for r in all_top_n if r.horizon_months == 12 and r.n <= 20]

        summary = {
            "screen_years": self._screen_years,
            "total_ic_observations": len(all_ic),
            "mean_composite_ic_12m": (
                round(sum(r.ic for r in composite_ics) / len(composite_ics), 4)
                if composite_ics else None
            ),
            "mean_alpha_top20_12m": (
                round(sum(r.alpha for r in top20_12m) / len(top20_12m), 4)
                if top20_12m else None
            ),
            "years_with_positive_alpha": sum(1 for r in top20_12m if r.alpha > 0),
            "calibration_context": format_calibration_context(regime_ics),
        }

        result = {
            "run_mode": "post_fix",
            "screen_years": self._screen_years,
            "ic_data": ic_results_to_dict(all_ic),
            "quintile_data": quintile_results_to_dict(all_quintile),
            "top_n_data": top_n_results_to_dict(all_top_n),
            "regime_data": regime_dict,
            "ticker_details": _serialize_ticker_details(all_scored),
            "summary": summary,
        }

        # Persist if DB available
        if self._db is not None:
            self._save_result(result)

        logger.info("Backtest complete. Summary: %s", json.dumps(summary, indent=2))
        return result

    # ── Per-Year Screening ───────────────────────────────────────────────────

    def _screen_year(self, screen_year: int, screen_date: date) -> YearScreenResult:
        """Run the full quant gate pipeline for one historical screen year."""
        fiscal_year = screen_year - 1

        # 1. Fetch EDGAR fundamentals
        edgar = EdgarClient(fiscal_year=fiscal_year)
        edgar.load_ticker_map()
        logger.info("Fetching EDGAR FY%d frames...", fiscal_year)
        edgar.fetch_bulk_frames()
        logger.info("Fetching EDGAR FY%d frames (prior year for Piotroski)...", fiscal_year - 1)
        edgar.fetch_prior_year()

        # Get fundamentals for all tickers in our universe
        universe_tickers = [s["ticker"] for s in self._universe] if self._universe else []
        raw_fundamentals = edgar.get_fundamentals_batch(universe_tickers)
        logger.info("EDGAR returned fundamentals for %d tickers", len(raw_fundamentals))

        # 2. Fetch historical prices at screen date
        prices = self._fetch_prices_at_date(
            [f["ticker"] for f in raw_fundamentals],
            screen_date,
        )
        logger.info("Got prices for %d tickers at %s", len(prices), screen_date)

        # Enrich with prices
        edgar.enrich_with_prices(raw_fundamentals, prices)
        edgar.enrich_with_sectors(raw_fundamentals, self._sectors)

        # 3. Convert to snapshots
        snapshots = []
        for raw in raw_fundamentals:
            snap = _dict_to_snapshot(raw)
            if snap is not None:
                snapshots.append(snap)
        logger.info("Converted %d valid snapshots", len(snapshots))

        # 4. Greenblatt ranking
        ranked = rank_by_greenblatt(snapshots, sectors=self._sectors)
        logger.info("Greenblatt ranking: %d eligible stocks", len(ranked))

        if not ranked:
            return YearScreenResult(
                screen_year=screen_year,
                screen_date=screen_date,
                n_snapshots=len(snapshots),
                n_ranked=0,
                n_scored=0,
                scored_results=[],
                forward_returns={},
                spy_returns={},
            )

        top_ranked = ranked[:self._top_n]
        snap_by_ticker = {s.ticker: s for s in snapshots}
        total_ranked = len(ranked)

        # 5. Prior-year snapshots for Piotroski
        prior_tickers = [gr.ticker for gr in top_ranked]
        prior_raws = edgar.get_prior_fundamentals_batch(prior_tickers)
        prior_by_ticker = {}
        for raw in prior_raws:
            prior_snap = _dict_to_snapshot(raw)
            if prior_snap is not None:
                prior_by_ticker[prior_snap.ticker] = prior_snap

        # 6. Momentum at screen date
        momentum_scores = self._compute_historical_momentum(
            [gr.ticker for gr in top_ranked],
            screen_date,
        )

        # 7. O'Shaughnessy factors
        gp_raw: dict[str, float] = {}
        sy_raw: dict[str, float] = {}
        for gr in top_ranked:
            snap = snap_by_ticker.get(gr.ticker)
            if snap is None:
                continue
            if snap.total_assets > 0 and snap.gross_profit > 0:
                gp_raw[gr.ticker] = float(snap.gross_profit / snap.total_assets)
            if snap.market_cap > 0:
                total_return = float(snap.dividends_paid + snap.shares_repurchased)
                if total_return > 0:
                    sy_raw[gr.ticker] = total_return / float(snap.market_cap)
        gp_scores = _rank_to_percentile(gp_raw)
        sy_scores = _rank_to_percentile(sy_raw)

        # 8. Score top-N
        scored_results: list[dict] = []
        for ordinal, gr in enumerate(top_ranked, start=1):
            snap = snap_by_ticker.get(gr.ticker)
            if snap is None:
                continue

            prior_snap = prior_by_ticker.get(gr.ticker)
            beneish = calculate_beneish(snap, prior_snap)
            if beneish and beneish.data_sufficient and beneish.is_manipulator:
                continue

            piotroski = calculate_piotroski(snap, previous=prior_snap)
            altman = calculate_altman(snap, sector=self._sectors.get(gr.ticker, ""))
            mom = momentum_scores.get(gr.ticker)

            score = composite_score(
                greenblatt_rank=ordinal,
                total_ranked=total_ranked,
                piotroski_score=piotroski.score,
                has_prior_year=prior_snap is not None,
                altman_zone=altman.zone if altman else None,
                momentum_score=mom,
                gross_profitability=gp_scores.get(gr.ticker),
                shareholder_yield=sy_scores.get(gr.ticker),
            )

            scored_results.append({
                "ticker": gr.ticker,
                "earnings_yield": float(gr.earnings_yield) if gr.earnings_yield else None,
                "roic": float(gr.roic) if gr.roic else None,
                "combined_rank": gr.combined_rank,
                "piotroski_score": piotroski.score,
                "altman_z_score": float(altman.z_score) if altman else None,
                "altman_zone": altman.zone if altman else None,
                "momentum_score": mom,
                "gross_profitability": gp_scores.get(gr.ticker),
                "shareholder_yield": sy_scores.get(gr.ticker),
                "composite_score": float(score),
            })

        scored_results.sort(key=lambda r: r.get("composite_score", 0), reverse=True)
        logger.info("Scored %d stocks for %d", len(scored_results), screen_year)

        # 9. Forward returns
        scored_tickers = [r["ticker"] for r in scored_results]
        forward_returns: dict[int, dict[str, float]] = {}
        spy_returns: dict[int, float] = {}

        for horizon in HORIZONS:
            end_date = _add_months(screen_date, horizon)
            fwd, spy_ret = self._fetch_forward_returns(
                scored_tickers, screen_date, end_date,
            )
            forward_returns[horizon] = fwd
            spy_returns[horizon] = spy_ret
            logger.info(
                "Forward returns (%dm): %d tickers, SPY=%.2f%%",
                horizon, len(fwd), spy_ret * 100,
            )

        # 10. Compute IC, quintiles, top-N
        all_ic: list[FactorICResult] = []
        all_quintile: list[QuintileResult] = []
        all_top_n: list[TopNResult] = []

        for horizon in HORIZONS:
            fwd = forward_returns.get(horizon, {})
            spy_ret = spy_returns.get(horizon, 0.0)

            ics = compute_all_factor_ics(scored_results, fwd, screen_year, horizon)
            all_ic.extend(ics)

            quintiles = compute_quintile_returns(scored_results, fwd, spy_ret, screen_year, horizon)
            all_quintile.extend(quintiles)

            for n in (20, 50):
                top_n = compute_top_n_vs_spy(scored_results, fwd, spy_ret, screen_year, horizon, n)
                if top_n:
                    all_top_n.append(top_n)

        # Log key results
        for ic in all_ic:
            if ic.factor_name == "composite_score" and ic.horizon_months == 12:
                logger.info(
                    "Year %d composite IC (12m): %.4f (n=%d, p=%.4f)",
                    screen_year, ic.ic, ic.n_stocks, ic.p_value,
                )

        return YearScreenResult(
            screen_year=screen_year,
            screen_date=screen_date,
            n_snapshots=len(snapshots),
            n_ranked=len(ranked),
            n_scored=len(scored_results),
            scored_results=scored_results,
            forward_returns=forward_returns,
            spy_returns=spy_returns,
            ic_results=all_ic,
            quintile_results=all_quintile,
            top_n_results=all_top_n,
        )

    # ── Data Helpers ─────────────────────────────────────────────────────────

    def _load_universe(self) -> None:
        """Load the stock universe for sector data."""
        logger.info("Loading stock universe for sector data...")
        self._universe = load_full_universe()
        self._sectors = {s["ticker"]: s.get("sector", "") for s in self._universe}
        logger.info("Universe loaded: %d stocks, %d sectors", len(self._universe), len(self._sectors))

    def _get_screen_date(self, screen_year: int) -> date:
        """Get the screen date for a given year."""
        for year, d in SCREEN_DATES:
            if year == screen_year:
                return d
        return date(screen_year, 1, 15)

    @staticmethod
    def _yf_download_with_retry(tickers, start, end, max_retries=3):
        """Download yfinance data with rate-limit retry and backoff."""
        import yfinance as yf

        for attempt in range(max_retries):
            try:
                data = yf.download(
                    tickers, start=str(start), end=str(end),
                    progress=False, threads=True,
                )
                return data
            except Exception as e:
                if "Rate" in str(e) or "429" in str(e) or attempt < max_retries - 1:
                    wait = 30 * (attempt + 1)
                    logger.warning("yfinance rate limited, waiting %ds (attempt %d/%d)", wait, attempt + 1, max_retries)
                    time.sleep(wait)
                else:
                    raise
        return None

    def _fetch_prices_at_date(
        self,
        tickers: list[str],
        as_of: date,
    ) -> dict[str, Decimal]:
        """Fetch closing prices at a specific historical date using yfinance."""
        prices: dict[str, Decimal] = {}
        chunk_size = 50  # Smaller chunks to avoid rate limits
        for i in range(0, len(tickers), chunk_size):
            chunk = tickers[i : i + chunk_size]
            try:
                start = as_of - timedelta(days=7)
                data = self._yf_download_with_retry(
                    chunk, start, as_of + timedelta(days=1),
                )
                if data is None or data.empty:
                    continue

                close = data["Close"]
                if isinstance(close, np.ndarray) or not hasattr(close, "columns"):
                    if len(chunk) == 1 and not close.empty:
                        prices[chunk[0]] = Decimal(str(float(close.iloc[-1])))
                else:
                    for ticker in chunk:
                        if ticker in close.columns:
                            series = close[ticker].dropna()
                            if not series.empty:
                                prices[ticker] = Decimal(str(float(series.iloc[-1])))
            except Exception:
                logger.warning("Price fetch failed for chunk %d-%d at %s", i, i + len(chunk), as_of)
            time.sleep(2)

        return prices

    def _fetch_forward_returns(
        self,
        tickers: list[str],
        start_date: date,
        end_date: date,
    ) -> tuple[dict[str, float], float]:
        """Fetch forward returns from start_date to end_date.

        Returns:
            (ticker_returns, spy_return) — both as decimal fractions (0.10 = 10%).
        """
        all_tickers = list(set(tickers + ["SPY"]))
        returns: dict[str, float] = {}
        spy_return = 0.0

        chunk_size = 50
        for i in range(0, len(all_tickers), chunk_size):
            chunk = all_tickers[i : i + chunk_size]
            try:
                data = self._yf_download_with_retry(
                    chunk,
                    start_date - timedelta(days=5),
                    end_date + timedelta(days=5),
                )
                if data is None or data.empty:
                    continue

                close = data["Close"]
                for ticker in chunk:
                    try:
                        col = ticker if len(chunk) > 1 else close
                        if len(chunk) > 1:
                            if ticker not in close.columns:
                                continue
                            col = close[ticker]
                        series = col.dropna()
                        if len(series) < 2:
                            continue

                        # Get price nearest to start and end
                        start_price = float(series.iloc[0])
                        end_price = float(series.iloc[-1])
                        if start_price > 0:
                            ret = (end_price - start_price) / start_price
                            if ticker == "SPY":
                                spy_return = ret
                            else:
                                returns[ticker] = ret
                    except Exception:
                        continue
            except Exception:
                logger.warning("Forward return fetch failed for chunk %d", i)
            time.sleep(2)

        return returns, spy_return

    def _compute_historical_momentum(
        self,
        tickers: list[str],
        as_of: date,
    ) -> dict[str, float]:
        """Compute J-T 12-1 month momentum at a historical date.

        Downloads 13 months of price history ending at as_of, computes
        price(T-1m) / price(T-12m) - 1, then converts to cross-sectional percentile.
        """
        start = as_of - timedelta(days=400)  # ~13 months
        momentum_raw: dict[str, float] = {}

        chunk_size = 50
        for i in range(0, len(tickers), chunk_size):
            chunk = tickers[i : i + chunk_size]
            try:
                data = self._yf_download_with_retry(
                    chunk, start, as_of + timedelta(days=1),
                )
                if data is None or data.empty:
                    continue

                close = data["Close"]
                for ticker in chunk:
                    try:
                        col = ticker if len(chunk) > 1 else close
                        if len(chunk) > 1:
                            if ticker not in close.columns:
                                continue
                            col = close[ticker]
                        series = col.dropna()
                        if len(series) < 200:
                            continue
                        # J-T skip-month: price(T-1m) / price(T-12m) - 1
                        momentum_raw[ticker] = float(
                            (series.iloc[-22] / series.iloc[0]) - 1
                        )
                    except Exception:
                        continue
            except Exception:
                logger.warning("Momentum fetch failed for chunk %d at %s", i, as_of)
            time.sleep(2)

        return _rank_to_percentile(momentum_raw)

    def _save_result(self, result: dict) -> None:
        """Persist result to invest.quant_backtest_runs."""
        try:
            self._db.execute(
                """INSERT INTO invest.quant_backtest_runs
                   (run_mode, screen_years, ic_data, quintile_data,
                    top_n_data, regime_data, ticker_details, summary)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    result["run_mode"],
                    result["screen_years"],
                    json.dumps(result["ic_data"]),
                    json.dumps(result["quintile_data"]),
                    json.dumps(result["top_n_data"]),
                    json.dumps(result["regime_data"]),
                    json.dumps(result["ticker_details"]),
                    json.dumps(result["summary"]),
                ),
            )
            logger.info("Backtest result saved to database")
        except Exception:
            logger.exception("Failed to save backtest result to database")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _add_months(d: date, months: int) -> date:
    """Add months to a date."""
    month = d.month + months
    year = d.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    day = min(d.day, 28)  # Safe for all months
    return date(year, month, day)


def _serialize_ticker_details(scored: list[dict]) -> list[dict]:
    """Ensure all values are JSON-serializable (convert Decimal to float)."""
    out = []
    for r in scored:
        row = {}
        for k, v in r.items():
            if isinstance(v, Decimal):
                row[k] = float(v)
            else:
                row[k] = v
        out.append(row)
    return out
