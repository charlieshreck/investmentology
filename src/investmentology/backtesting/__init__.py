"""Backtesting module for strategy replay and historical factor analysis."""

from investmentology.backtesting.runner import BacktestRunner, BacktestResult
from investmentology.backtesting.tearsheet import generate_tearsheet
from investmentology.backtesting.quant_historical import HistoricalQuantBacktest

__all__ = [
    "BacktestRunner",
    "BacktestResult",
    "generate_tearsheet",
    "HistoricalQuantBacktest",
]
