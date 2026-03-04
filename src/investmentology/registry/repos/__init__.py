"""Domain-specific repository classes that decompose the monolithic Registry."""

from investmentology.registry.repos.stock_repo import StockRepo
from investmentology.registry.repos.fundamentals_repo import FundamentalsRepo
from investmentology.registry.repos.quant_gate_repo import QuantGateRepo
from investmentology.registry.repos.decision_repo import DecisionRepo
from investmentology.registry.repos.prediction_repo import PredictionRepo
from investmentology.registry.repos.watchlist_repo import WatchlistRepo
from investmentology.registry.repos.position_repo import PositionRepo
from investmentology.registry.repos.signal_repo import SignalRepo
from investmentology.registry.repos.verdict_repo import VerdictRepo
from investmentology.registry.repos.enriched_repo import EnrichedRepo
from investmentology.registry.repos.cron_repo import CronRepo
from investmentology.registry.repos.learning_repo import LearningRepo

__all__ = [
    "StockRepo", "FundamentalsRepo", "QuantGateRepo",
    "DecisionRepo", "PredictionRepo", "WatchlistRepo",
    "PositionRepo", "SignalRepo", "VerdictRepo",
    "EnrichedRepo", "CronRepo", "LearningRepo",
]
