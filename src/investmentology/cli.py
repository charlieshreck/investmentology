"""CLI entry point for Investmentology.

Provides commands for running the pipeline stages:
  - screen: Run L1 Quant Gate screening
  - analyze: Run L2-L4 analysis on candidates
  - monitor: Run daily monitoring loop
  - status: Show pipeline and portfolio status
  - migrate: Run database migrations
  - controller: Run the agent-first pipeline controller
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path

from investmentology.config import load_config
from investmentology.registry.db import Database
from investmentology.registry.queries import Registry


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def cmd_screen(args: argparse.Namespace) -> None:
    """Run L1 Quant Gate screening."""
    from investmentology.data.edgar_client import EdgarClient
    from investmentology.data.yfinance_client import YFinanceClient
    from investmentology.quant_gate.screener import QuantGateScreener

    config = load_config()
    db = Database(config.db_dsn)
    db.connect()
    registry = Registry(db)
    yf_client = YFinanceClient()

    edgar_client = None
    if not args.legacy:
        # EDGAR for fundamentals (fast, bulk), yfinance for prices only
        edgar_client = EdgarClient()
        logging.info("Loading SEC EDGAR ticker map...")
        edgar_client.load_ticker_map()
        logging.info("Fetching SEC EDGAR bulk financial data...")
        edgar_client.fetch_bulk_frames()
        logging.info("EDGAR coverage: %s", edgar_client.coverage)
        logging.info("Fetching prior year data for Piotroski YoY...")
        edgar_client.fetch_prior_year()

    screener = QuantGateScreener(registry, yf_client, config, edgar_client=edgar_client)

    logging.info("Starting Quant Gate screen...")
    if args.delta and args.previous_run:
        result = screener.run_delta(args.previous_run)
        print(json.dumps(result, indent=2, default=str))
    else:
        result = screener.run()
        print(f"Run ID: {result.run_id}")
        print(f"Universe: {result.data_quality.universe_size}")
        print(f"Passed: {len(result.top_results)}")
        if result.top_results:
            print("\nTop 10 (sorted by composite score):")
            for i, r in enumerate(result.top_results[:10], 1):
                z = r.get("altman_z_score")
                z_str = f"{z:.1f}" if z else "N/A"
                print(
                    f"  {i:2d}. {r['ticker']:6s} "
                    f"CS={r['composite_score']:.3f} "
                    f"GR=#{r['combined_rank']} "
                    f"F={r['piotroski_score']} "
                    f"Z={z_str}({r.get('altman_zone', '?')})"
                )


def cmd_analyze(args: argparse.Namespace) -> None:
    """Run L2-L4 analysis on candidates."""
    from investmentology.agents.gateway import LLMGateway
    from investmentology.data.enricher import build_enricher
    from investmentology.learning.registry import DecisionLogger
    from investmentology.orchestrator import AnalysisOrchestrator

    config = load_config()
    db = Database(config.db_dsn)
    db.connect()
    registry = Registry(db)
    gateway = LLMGateway.from_config(config)
    decision_logger = DecisionLogger(registry)
    enricher = build_enricher(config)

    orchestrator = AnalysisOrchestrator(registry, gateway, decision_logger, enricher=enricher)

    tickers = args.tickers
    if not tickers:
        # Default: get CANDIDATE state from watchlist
        candidates = registry.get_watchlist_by_state(
            __import__("investmentology.models.lifecycle", fromlist=["WatchlistState"]).WatchlistState.CANDIDATE
        )
        tickers = [c["ticker"] for c in candidates[:args.limit]]

    if not tickers:
        print("No candidates to analyze.")
        return

    print(f"Analyzing {len(tickers)} candidates...")

    async def _run():
        await gateway.start()
        try:
            result = await orchestrator.analyze_candidates(tickers)
            return result
        finally:
            await gateway.close()

    result = asyncio.run(_run())
    print("\nResults:")
    print(f"  Candidates in: {result.candidates_in}")
    print(f"  Passed competence: {result.passed_competence}")
    print(f"  Analyzed: {result.analyzed}")
    print(f"  Conviction buys: {result.conviction_buys}")
    print(f"  Vetoed: {result.vetoed}")

    for r in result.results:
        if r.verdict:
            v = r.verdict
            print(f"  {r.ticker}: {v.verdict.value} (conf={v.confidence:.0%}, consensus={v.consensus_score:+.3f})")
            if v.risk_flags:
                for flag in v.risk_flags[:3]:
                    print(f"    !! {flag}")
            if v.reasoning:
                print(f"    -> {v.reasoning[:120]}")
        elif r.final_action != "NO_ACTION":
            print(f"  {r.ticker}: {r.final_action} (conf={r.final_confidence:.2f})")


def cmd_monitor(args: argparse.Namespace) -> None:
    """Run daily monitoring loop."""
    from investmentology.data.alerts import AlertEngine
    from investmentology.data.monitor import DailyMonitor
    from investmentology.data.yfinance_client import YFinanceClient

    config = load_config()
    db = Database(config.db_dsn)
    db.connect()
    registry = Registry(db)

    monitor = DailyMonitor(registry, YFinanceClient(), AlertEngine())

    if args.premarket:
        print("Running pre-market check...")
        result = monitor.run_premarket()
    else:
        print("Running full daily monitor...")
        result = monitor.run()

    print("\nMonitor result:")
    print(f"  Alerts: {len(result.alerts)}")
    for alert in result.alerts:
        print(f"    [{alert.severity.value}] {alert.alert_type.value}: {alert.message}")


def cmd_status(args: argparse.Namespace) -> None:
    """Show pipeline and portfolio status."""
    from investmentology.learning.lifecycle import StockLifecycleManager
    from investmentology.learning.predictions import PredictionManager
    from investmentology.learning.registry import DecisionLogger

    config = load_config()
    db = Database(config.db_dsn)
    db.connect()
    registry = Registry(db)
    decision_logger = DecisionLogger(registry)
    prediction_mgr = PredictionManager(registry)

    # Pipeline summary
    lifecycle = StockLifecycleManager(registry, decision_logger)
    summary = lifecycle.get_pipeline_summary()
    print("Pipeline Summary:")
    for state, count in sorted(summary.items()):
        if count > 0:
            print(f"  {state}: {count}")

    # Decision count
    total_decisions = decision_logger.get_decision_count()
    print(f"\nTotal decisions logged: {total_decisions}")

    # Recent decisions
    recent = decision_logger.get_recent_decisions(limit=5)
    if recent:
        print("\nRecent decisions:")
        for d in recent:
            print(f"  [{d.decision_type.value}] {d.ticker}: {d.reasoning[:60]}")

    # Open positions
    positions = registry.get_open_positions()
    if positions:
        print(f"\nOpen positions ({len(positions)}):")
        for p in positions:
            pnl = f"{p.pnl_pct:+.1%}" if p.pnl_pct else "N/A"
            print(f"  {p.ticker}: {p.shares} shares @ ${p.entry_price} (PnL: {pnl})")

    # Calibration
    cal = prediction_mgr.get_calibration_data()
    print(f"\nCalibration: {cal['total_settled']} settled predictions")
    if cal["total_settled"] > 0:
        print(f"  ECE: {cal['ece']:.4f}, Brier: {cal['brier']:.4f}")


def cmd_cron(args: argparse.Namespace) -> None:
    """Run a scheduled pipeline job with audit logging."""
    from investmentology.agents.gateway import LLMGateway
    from investmentology.data.enricher import build_enricher
    from investmentology.learning.registry import DecisionLogger
    from investmentology.orchestrator import AnalysisOrchestrator

    config = load_config()
    db = Database(config.db_dsn)
    db.connect()
    registry = Registry(db)

    job = args.job
    limit = args.limit
    cron_id = registry.log_cron_start(job)
    logging.info("Cron job %s started (id=%d)", job, cron_id)

    try:
        if job == "weekly-screen":
            from investmentology.data.edgar_client import EdgarClient
            from investmentology.data.yfinance_client import YFinanceClient
            from investmentology.quant_gate.screener import QuantGateScreener

            yf_client = YFinanceClient()
            edgar_client = EdgarClient()
            edgar_client.load_ticker_map()
            edgar_client.fetch_bulk_frames()
            edgar_client.fetch_prior_year()

            screener = QuantGateScreener(registry, yf_client, config, edgar_client=edgar_client)
            result = screener.run()
            msg = f"Screened {result.data_quality.universe_size}, passed {len(result.top_results)}"
            logging.info(msg)
            print(msg)

        elif job == "post-screen-analyze":
            gateway = LLMGateway.from_config(config)
            decision_logger = DecisionLogger(registry)
            enricher = build_enricher(config)
            orchestrator = AnalysisOrchestrator(registry, gateway, decision_logger, enricher=enricher)

            # Analyze top results from latest screen that aren't on watchlist yet
            latest_run = registry._db.execute(
                "SELECT id FROM invest.quant_gate_runs ORDER BY id DESC LIMIT 1"
            )
            if not latest_run:
                print("No screening runs found.")
                registry.log_cron_finish(cron_id, "skipped", "No screening runs")
                return

            run_id = latest_run[0]["id"]
            threshold = args.threshold if args.threshold is not None else config.post_screen_threshold
            rows = registry._db.execute(
                "SELECT r.ticker FROM invest.quant_gate_results r "
                "WHERE r.run_id = %s AND r.composite_score >= %s "
                "ORDER BY r.composite_score DESC NULLS LAST LIMIT %s",
                (run_id, threshold, limit),
            )
            tickers = [r["ticker"] for r in rows]

            # Filter out tickers with active re-entry blocks
            blocked = registry.get_blocked_tickers()
            if blocked:
                before = len(tickers)
                tickers = [t for t in tickers if t not in blocked]
                skipped = before - len(tickers)
                if skipped:
                    logging.info("Skipped %d blocked tickers in post-screen", skipped)
                    print(f"Skipped {skipped} blocked tickers (re-entry conditions not met)")

            if tickers:
                async def _run():
                    await gateway.start()
                    try:
                        return await orchestrator.analyze_candidates(tickers)
                    finally:
                        await gateway.close()

                result = asyncio.run(_run())
                msg = f"Analyzed {result.analyzed}/{result.candidates_in} (threshold>={threshold}), buys={result.conviction_buys}"
                logging.info(msg)
                print(msg)
            else:
                print("No candidates to analyze.")

        elif job == "daily-watchlist-analyze":
            gateway = LLMGateway.from_config(config)
            decision_logger = DecisionLogger(registry)
            enricher = build_enricher(config)
            orchestrator = AnalysisOrchestrator(registry, gateway, decision_logger, enricher=enricher)

            states = ["CANDIDATE", "ASSESSED", "CONVICTION_BUY", "POSITION_HOLD",
                       "WATCHLIST_EARLY", "WATCHLIST_CATALYST"]

            # Run block-clearing check before building the queue
            try:
                from investmentology.registry.reentry import check_and_clear_blocks
                # Build fundamentals lookup for block clearing
                fund_rows = registry._db.execute(
                    "SELECT DISTINCT ON (ticker) ticker, price, operating_income, "
                    "revenue, net_income, total_debt, total_assets, current_assets, "
                    "current_liabilities, net_ppe "
                    "FROM invest.fundamentals_cache "
                    "ORDER BY ticker, fetched_at DESC"
                )
                fund_by_ticker = {r["ticker"]: r for r in fund_rows}
                cleared = check_and_clear_blocks(registry._db, fund_by_ticker)
                if cleared:
                    print(f"Cleared {cleared} re-entry blocks (conditions satisfied)")
            except Exception:
                logging.debug("Block clearing check skipped (table may not exist)")

            tickers = registry.get_watchlist_tickers_for_reanalysis(
                states, min_hours=args.min_hours,
                min_move_pct=3.0, force_after_hours=168,
            )
            tickers = tickers[:limit]

            if tickers:
                async def _run():
                    await gateway.start()
                    try:
                        return await orchestrator.analyze_candidates(tickers)
                    finally:
                        await gateway.close()

                result = asyncio.run(_run())
                msg = f"Re-analyzed {result.analyzed}/{result.candidates_in}, buys={result.conviction_buys}"
                logging.info(msg)
                print(msg)
            else:
                print("No watchlist tickers need re-analysis.")

        elif job == "daily-monitor":
            from investmentology.data.alerts import AlertEngine
            from investmentology.data.monitor import DailyMonitor
            from investmentology.data.yfinance_client import YFinanceClient

            monitor = DailyMonitor(registry, YFinanceClient(), AlertEngine())

            if args.premarket:
                result = monitor.run_premarket()
                msg = f"Premarket: {len(result.alerts)} alerts"
            else:
                result = monitor.run()
                msg = f"Monitor: {result.positions_updated} prices updated, {result.predictions_settled} settled, {len(result.alerts)} alerts"
            logging.info(msg)
            print(msg)

        elif job == "price-refresh":
            from investmentology.data.yfinance_client import YFinanceClient

            yf_client = YFinanceClient(cache_ttl_hours=0)

            # Collect all tickers: positions + watchlist + recent verdicts
            all_tickers: set[str] = set()

            # Open positions
            positions = registry.get_open_positions()
            pos_tickers = {p.ticker for p in positions}
            all_tickers |= pos_tickers

            # Watchlist
            wl_rows = registry._db.execute(
                "SELECT ticker FROM invest.watchlist WHERE state != 'REJECTED'"
            )
            all_tickers |= {r["ticker"] for r in wl_rows}

            # Recent verdicts (recs)
            verdict_rows = registry._db.execute(
                "SELECT DISTINCT ON (ticker) ticker "
                "FROM invest.verdicts ORDER BY ticker, created_at DESC"
            )
            all_tickers |= {r["ticker"] for r in verdict_rows}

            if not all_tickers:
                print("No tickers to refresh.")
                registry.log_cron_finish(cron_id, "skipped", "No tickers")
                return

            ticker_list = sorted(all_tickers)
            print(f"Refreshing prices for {len(ticker_list)} tickers...")

            # Batch fetch (single yf.download call)
            prices = yf_client.get_prices_batch(ticker_list)
            updated = 0

            # Update fundamentals_cache (used by recs/watchlist queries)
            # Insert a new price-only row carrying forward market_cap from latest entry
            for ticker, price in prices.items():
                try:
                    registry._db.execute(
                        "INSERT INTO invest.fundamentals_cache (ticker, fetched_at, price, market_cap) "
                        "SELECT %s, NOW(), %s, "
                        "  (SELECT fc.market_cap FROM invest.fundamentals_cache fc "
                        "   WHERE fc.ticker = %s ORDER BY fc.fetched_at DESC LIMIT 1) ",
                        (ticker, price, ticker),
                    )
                    updated += 1
                except Exception:
                    pass  # ticker may not exist in invest.stocks

            # Update portfolio positions current_price
            pos_updated = 0
            for p in positions:
                if p.ticker in prices:
                    registry._db.execute(
                        "UPDATE invest.portfolio_positions SET current_price = %s, updated_at = NOW() "
                        "WHERE ticker = %s AND is_closed = false",
                        (prices[p.ticker], p.ticker),
                    )
                    pos_updated += 1

            msg = f"Price refresh: {updated}/{len(ticker_list)} prices fetched, {pos_updated} positions updated"
            logging.info(msg)
            print(msg)

        elif job == "overnight-pipeline":
            _run_overnight_pipeline(db, registry, cron_id)
            return  # cron_id logged inside

        else:
            print(f"Unknown cron job: {job}")
            registry.log_cron_finish(cron_id, "error", f"Unknown job: {job}")
            return

        registry.log_cron_finish(cron_id, "success")
        logging.info("Cron job %s completed successfully", job)

    except Exception as e:
        logging.exception("Cron job %s failed", job)
        registry.log_cron_finish(cron_id, "error", str(e))
        raise


def _run_overnight_pipeline(db: Database, registry: Registry, cron_id: int) -> None:
    """Overnight pipeline coordinator.

    Creates a fresh cycle, populates steps, then polls until the always-running
    controller deployment processes them. Does NOT run the controller itself.

    Flow:
    1. Create cycle → create Phase 1 steps for all selected tickers
    2. Poll every 30s until Phase 1 (screening) completes
    3. Create Phase 2 steps for tickers that passed the gate
    4. Poll every 60s until Phase 2 (agents + synthesis) completes
    5. Log summary and exit
    """
    import time

    from investmentology.pipeline import state
    from investmentology.pipeline.selection import select_tickers
    from investmentology.pipeline.controller import SCREENER_AGENT_NAMES, ANALYSIS_AGENT_NAMES
    from investmentology.registry.reentry import get_blocked_tickers

    # Gather candidates (same logic as controller._get_analysis_tickers)
    candidates: set[str] = set()

    _ANALYSABLE_STATES = [
        "CANDIDATE", "ASSESSED", "CONVICTION_BUY",
        "WATCHLIST_EARLY", "WATCHLIST_CATALYST",
        "CONFLICT_REVIEW", "POSITION_HOLD", "POSITION_TRIM",
    ]

    try:
        wl_rows = db.execute(
            "SELECT ticker FROM invest.watchlist WHERE state = ANY(%s)",
            (_ANALYSABLE_STATES,),
        )
        for r in wl_rows:
            candidates.add(r["ticker"])
    except Exception:
        pass

    try:
        qg_rows = db.execute(
            "SELECT DISTINCT r.ticker FROM invest.quant_gate_results r "
            "WHERE r.run_id = ("
            "  SELECT id FROM invest.quant_gate_runs ORDER BY id DESC LIMIT 1"
            ") AND r.combined_rank <= 100",
        )
        for r in qg_rows:
            candidates.add(r["ticker"])
    except Exception:
        pass

    try:
        pos_rows = db.execute(
            "SELECT ticker FROM invest.portfolio_positions "
            "WHERE is_closed = FALSE",
        )
        for r in pos_rows:
            candidates.add(r["ticker"])
    except Exception:
        pass

    blocked = get_blocked_tickers(db)
    unblocked = sorted(t for t in candidates if t not in blocked)

    if not unblocked:
        logging.info("Overnight pipeline: no candidates found")
        registry.log_cron_finish(cron_id, "skipped", "No candidates")
        return

    # Select tickers (portfolio-first)
    selection = select_tickers(db, unblocked)
    all_tickers = selection.all_tickers
    logging.info(
        "Overnight pipeline: %d portfolio + %d watchlist = %d tickers",
        len(selection.portfolio), len(selection.watchlist), len(all_tickers),
    )

    # Expire old cycles and create fresh one
    state.expire_old_cycles(db)
    cycle_id = state.create_cycle(db, ticker_count=len(all_tickers))
    logging.info("Created overnight cycle %s", cycle_id)

    # Phase 1: Create screening steps
    for ticker in all_tickers:
        state.create_screening_steps(db, cycle_id, ticker, SCREENER_AGENT_NAMES)

    logging.info(
        "Phase 1: created screening steps for %d tickers, waiting for controller...",
        len(all_tickers),
    )

    # Poll Phase 1 completion (controller processes steps)
    phase1_timeout = 3600  # 1 hour max for screening
    phase1_start = time.monotonic()

    while time.monotonic() - phase1_start < phase1_timeout:
        time.sleep(30)
        summary = state.get_cycle_summary(db, cycle_id)
        pending = summary["pending"]
        running = summary["running"]
        completed = summary["completed"]
        failed = summary["failed"]

        # Phase 1 is done when no pending/running steps remain
        if pending == 0 and running == 0:
            logging.info(
                "Phase 1 complete: %d completed, %d failed", completed, failed,
            )
            break

        logging.info(
            "Phase 1 waiting: %d pending, %d running, %d completed, %d failed",
            pending, running, completed, failed,
        )
    else:
        logging.warning("Phase 1 timed out after %ds", phase1_timeout)

    # Phase 2: Check which tickers passed gate, create analysis steps
    passed_tickers = []
    for ticker in all_tickers:
        if state.is_step_completed(db, cycle_id, ticker, state.STEP_GATE_DECISION):
            # Check if analysis steps already exist (controller may have created them)
            progress = state.get_ticker_progress(db, cycle_id, ticker)
            has_agent_steps = any(
                s["step"].startswith("agent:") for s in progress
            )
            if not has_agent_steps:
                state.create_analysis_steps(
                    db, cycle_id, ticker, ANALYSIS_AGENT_NAMES,
                )
            passed_tickers.append(ticker)

    if not passed_tickers:
        logging.info("Overnight pipeline: no tickers passed gate")
        state.complete_cycle(db, cycle_id)
        registry.log_cron_finish(cron_id, "success", "No tickers passed gate")
        return

    logging.info(
        "Phase 2: %d tickers passed gate, waiting for analysis...",
        len(passed_tickers),
    )

    # Poll Phase 2 completion
    phase2_timeout = 14400  # 4 hours max for analysis
    phase2_start = time.monotonic()

    while time.monotonic() - phase2_start < phase2_timeout:
        time.sleep(60)
        summary = state.get_cycle_summary(db, cycle_id)
        pending = summary["pending"]
        running = summary["running"]
        completed = summary["completed"]
        failed = summary["failed"]

        if pending == 0 and running == 0:
            logging.info(
                "Phase 2 complete: %d completed, %d failed", completed, failed,
            )
            break

        logging.info(
            "Phase 2 waiting: %d pending, %d running, %d completed, %d failed",
            pending, running, completed, failed,
        )
    else:
        logging.warning("Phase 2 timed out after %ds", phase2_timeout)

    # Final summary
    state.complete_cycle(db, cycle_id)
    final = state.get_cycle_summary(db, cycle_id)
    total_failed = final["failed"] + final.get("expired", 0)
    total_steps = final["total_steps"]

    msg = (
        f"Overnight pipeline complete: cycle {cycle_id}, "
        f"{len(passed_tickers)}/{len(all_tickers)} passed gate, "
        f"{final['completed']}/{total_steps} steps completed, "
        f"{total_failed} failures"
    )
    logging.info(msg)
    print(msg)

    # Exit code based on failure rate
    status = "success" if total_failed < total_steps * 0.5 else "error"
    registry.log_cron_finish(cron_id, status, msg)

    if status == "error":
        import sys
        sys.exit(1)


def cmd_controller(args: argparse.Namespace) -> None:
    """Run the agent-first pipeline controller.

    Long-running process that polls pipeline_state every 60 seconds,
    dispatches agent work to CLI queues or API calls, and manages
    convergence/debate/synthesis.
    """
    import signal

    from investmentology.agents.gateway import LLMGateway
    from investmentology.pipeline.controller import PipelineController

    config = load_config()
    db = Database(config.db_dsn)
    db.connect()
    gateway = LLMGateway.from_config(config)

    controller = PipelineController(db, gateway)

    async def _run() -> None:
        await controller.start()
        loop = asyncio.get_event_loop()

        # Graceful shutdown on SIGTERM/SIGINT
        stop_event = asyncio.Event()

        def _signal_handler() -> None:
            logging.info("Shutdown signal received")
            stop_event.set()

        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, _signal_handler)

        logging.info("Pipeline controller running (Ctrl+C to stop)")

        # Run controller loop in a task so we can cancel on signal
        loop_task = asyncio.create_task(controller.run_loop())
        await stop_event.wait()

        # Shutdown
        controller._running = False
        loop_task.cancel()
        try:
            await loop_task
        except asyncio.CancelledError:
            pass
        await controller.stop()

    asyncio.run(_run())


def cmd_migrate(args: argparse.Namespace) -> None:
    """Run database migrations."""
    config = load_config()
    db = Database(config.db_dsn)
    db.connect()
    migrations_dir = str(Path(__file__).parent / "registry" / "migrations")
    db.run_migrations(migrations_dir)
    print("Migrations complete.")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="investmentology",
        description="AI-powered institutional-grade investment advisory",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    subs = parser.add_subparsers(dest="command", required=True)

    # screen
    p_screen = subs.add_parser("screen", help="Run L1 Quant Gate screening")
    p_screen.add_argument("--delta", action="store_true", help="Compare to previous run")
    p_screen.add_argument("--previous-run", type=int, help="Previous run ID for delta")
    p_screen.add_argument("--legacy", action="store_true", help="Use yfinance instead of EDGAR")

    # analyze
    p_analyze = subs.add_parser("analyze", help="Run L2-L4 analysis on candidates")
    p_analyze.add_argument("tickers", nargs="*", help="Tickers to analyze (default: watchlist candidates)")
    p_analyze.add_argument("--limit", type=int, default=10, help="Max candidates from watchlist")

    # monitor
    p_monitor = subs.add_parser("monitor", help="Run daily monitoring loop")
    p_monitor.add_argument("--premarket", action="store_true", help="Run pre-market check only")

    # status
    subs.add_parser("status", help="Show pipeline and portfolio status")

    # cron
    p_cron = subs.add_parser("cron", help="Run a scheduled pipeline job")
    p_cron.add_argument("job", choices=[
        "weekly-screen", "post-screen-analyze", "daily-watchlist-analyze",
        "daily-monitor", "price-refresh", "overnight-pipeline",
    ], help="Cron job to run")
    p_cron.add_argument("--limit", type=int, default=20, help="Max tickers to process")
    p_cron.add_argument("--threshold", type=float, default=None,
                        help="Override composite_score threshold for post-screen-analyze")
    p_cron.add_argument("--premarket", action="store_true",
                        help="Run premarket mode (monitor job only)")
    p_cron.add_argument("--min-hours", type=int, default=20,
                        help="Min hours since last analysis (daily-watchlist-analyze)")

    # controller
    subs.add_parser("controller", help="Run agent-first pipeline controller")

    # migrate
    subs.add_parser("migrate", help="Run database migrations")

    args = parser.parse_args(argv)
    setup_logging(args.verbose)

    commands = {
        "screen": cmd_screen,
        "analyze": cmd_analyze,
        "monitor": cmd_monitor,
        "status": cmd_status,
        "cron": cmd_cron,
        "controller": cmd_controller,
        "migrate": cmd_migrate,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
