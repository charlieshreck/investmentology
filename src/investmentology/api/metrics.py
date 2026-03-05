"""Prometheus metrics for the Investmentology API."""

from __future__ import annotations

import re

from prometheus_client import Counter, Gauge, Histogram, Info

# ---------------------------------------------------------------------------
# API metrics
# ---------------------------------------------------------------------------

api_request_duration = Histogram(
    "investmentology_api_request_duration_seconds",
    "API request duration in seconds",
    ["method", "path_template", "status"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

api_requests_total = Counter(
    "investmentology_api_requests_total",
    "Total API requests",
    ["method", "path_template", "status"],
)

# ---------------------------------------------------------------------------
# Pipeline metrics
# ---------------------------------------------------------------------------

pipeline_cycle_duration = Histogram(
    "investmentology_pipeline_cycle_seconds",
    "Pipeline cycle (tick) duration in seconds",
    ["status"],
)

pipeline_cycles_total = Counter(
    "investmentology_pipeline_cycles_total",
    "Pipeline cycle completions",
    ["status"],
)

# ---------------------------------------------------------------------------
# Agent metrics
# ---------------------------------------------------------------------------

agent_analysis_duration = Histogram(
    "investmentology_agent_analysis_seconds",
    "Agent analysis call duration",
    ["agent_name", "provider"],
)

agent_analysis_total = Counter(
    "investmentology_agent_analysis_total",
    "Agent analysis completions",
    ["agent_name", "status"],
)

# ---------------------------------------------------------------------------
# Quant Gate metrics
# ---------------------------------------------------------------------------

quant_gate_runs_total = Counter(
    "investmentology_quant_gate_runs_total",
    "Quant gate screening runs",
)

quant_gate_stocks_scored = Gauge(
    "investmentology_quant_gate_stocks_scored",
    "Number of stocks scored in last quant gate run",
)

# ---------------------------------------------------------------------------
# Portfolio metrics
# ---------------------------------------------------------------------------

position_count = Gauge(
    "investmentology_position_count",
    "Number of open positions",
)

portfolio_value_usd = Gauge(
    "investmentology_portfolio_value_usd",
    "Total portfolio value in USD",
)

# ---------------------------------------------------------------------------
# DB pool metrics
# ---------------------------------------------------------------------------

db_pool_size = Gauge(
    "investmentology_db_pool_connections",
    "Database connection pool size",
    ["state"],
)

# ---------------------------------------------------------------------------
# Build info
# ---------------------------------------------------------------------------

build_info = Info(
    "investmentology",
    "Application build information",
)

# ---------------------------------------------------------------------------
# Path templating — avoids label cardinality explosion
# ---------------------------------------------------------------------------

# Patterns to normalize dynamic path segments
_PATH_PATTERNS = [
    (re.compile(r"/stock/[A-Z0-9.-]+"), "/stock/{ticker}"),
    (re.compile(r"/positions/\d+"), "/positions/{id}"),
    (re.compile(r"/results/\d+"), "/results/{id}"),
    (re.compile(r"/sizing/[A-Z0-9.-]+"), "/sizing/{ticker}"),
    (re.compile(r"/report/[A-Z0-9.-]+"), "/report/{ticker}"),
]


def template_path(path: str) -> str:
    """Normalize a request path to a template for metric labels."""
    for pattern, replacement in _PATH_PATTERNS:
        path = pattern.sub(replacement, path)
    return path
