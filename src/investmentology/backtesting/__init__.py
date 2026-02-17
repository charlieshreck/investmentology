"""Backtesting module for strategy replay against historical data."""

from investmentology.backtesting.runner import BacktestRunner, BacktestResult
from investmentology.backtesting.tearsheet import generate_tearsheet

__all__ = ["BacktestRunner", "BacktestResult", "generate_tearsheet"]
