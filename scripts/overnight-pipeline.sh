#!/bin/bash
# Overnight analysis pipeline — runs sequentially, each step feeds the next.
# Runs during sleeping hours (02:00 UTC) to use a different Claude 5h subscription window.
#
# Pipeline: Screen → Post-Screen Analysis → Watchlist Re-Analysis
#
# Screen: Pure Quant Gate math (no agents)
# Post-Screen: Multi-agent analysis of top screened stocks (Warren, Simons, Auditor/Claude CLI, Soros/Gemini CLI)
# Watchlist: Re-analyze existing watchlist with all 4 agents
set -euo pipefail

LOGDIR=/var/log/investmentology
mkdir -p "$LOGDIR"
LOGFILE="$LOGDIR/overnight-pipeline.log"

# Load environment (CLI providers + DB + API keys)
# Temporarily disable nounset (-u) because .env contains bcrypt hashes
# with $2b which bash interprets as positional params
set +u
set -a
source /home/investmentology/.env
set +a
set -u
cd /home/investmentology

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" | tee -a "$LOGFILE"; }

log "=== Overnight pipeline started ==="

# Step 1: Quant Gate screen (pure math, ~30 min)
log "Step 1/3: Quant Gate screen"
if python3 -m investmentology cron weekly-screen 2>&1 | tee -a "$LOGFILE"; then
    log "Step 1/3: Screen complete"
else
    log "Step 1/3: Screen FAILED (exit $?) — continuing to analysis anyway"
fi

# Step 2: Post-screen analysis on top screen results (all 4 agents)
log "Step 2/3: Post-screen analysis (4 agents)"
if python3 -m investmentology cron post-screen-analyze --limit 20 2>&1 | tee -a "$LOGFILE"; then
    log "Step 2/3: Post-screen analysis complete"
else
    log "Step 2/3: Post-screen analysis FAILED (exit $?) — continuing to watchlist"
fi

# Step 3: Watchlist re-analysis (all 4 agents)
log "Step 3/3: Watchlist re-analysis (4 agents)"
if python3 -m investmentology cron daily-watchlist-analyze --limit 30 2>&1 | tee -a "$LOGFILE"; then
    log "Step 3/3: Watchlist re-analysis complete"
else
    log "Step 3/3: Watchlist re-analysis FAILED (exit $?)"
fi

log "=== Overnight pipeline finished ==="
