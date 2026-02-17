"""Dependency injection for the FastAPI application."""

from __future__ import annotations

from investmentology.agents.gateway import LLMGateway
from investmentology.config import AppConfig
from investmentology.learning.calibration import CalibrationEngine
from investmentology.learning.predictions import PredictionManager
from investmentology.learning.registry import DecisionLogger
from investmentology.orchestrator import AnalysisOrchestrator
from investmentology.registry.db import Database
from investmentology.registry.queries import Registry


class AppState:
    """Holds shared application state initialised during lifespan."""

    def __init__(self) -> None:
        self.config: AppConfig | None = None
        self.db: Database | None = None
        self.registry: Registry | None = None
        self.gateway: LLMGateway | None = None
        self.decision_logger: DecisionLogger | None = None
        self.prediction_manager: PredictionManager | None = None
        self.calibration_engine: CalibrationEngine | None = None
        self.orchestrator: AnalysisOrchestrator | None = None


# Singleton shared across the app
app_state = AppState()


def get_registry() -> Registry:
    if app_state.registry is None:
        raise RuntimeError("Registry not initialised")
    return app_state.registry


def get_gateway() -> LLMGateway:
    if app_state.gateway is None:
        raise RuntimeError("LLMGateway not initialised")
    return app_state.gateway


def get_decision_logger() -> DecisionLogger:
    if app_state.decision_logger is None:
        raise RuntimeError("DecisionLogger not initialised")
    return app_state.decision_logger


def get_prediction_manager() -> PredictionManager:
    if app_state.prediction_manager is None:
        raise RuntimeError("PredictionManager not initialised")
    return app_state.prediction_manager


def get_calibration_engine() -> CalibrationEngine:
    if app_state.calibration_engine is None:
        raise RuntimeError("CalibrationEngine not initialised")
    return app_state.calibration_engine


def get_orchestrator() -> AnalysisOrchestrator:
    if app_state.orchestrator is None:
        raise RuntimeError("AnalysisOrchestrator not initialised")
    return app_state.orchestrator
