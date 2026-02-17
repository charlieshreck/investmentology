from __future__ import annotations

import os
from unittest.mock import patch

from investmentology.config import AppConfig, DatabaseConfig, load_config


class TestDatabaseConfig:
    def test_dsn_property(self) -> None:
        cfg = DatabaseConfig(
            host="localhost", port=5432, database="testdb", user="u", password="p"
        )
        assert cfg.dsn == "postgresql://u:p@localhost:5432/testdb"

    def test_frozen(self) -> None:
        cfg = DatabaseConfig(
            host="localhost", port=5432, database="testdb", user="u", password="p"
        )
        try:
            cfg.host = "other"  # type: ignore[misc]
            assert False, "Should be frozen"
        except AttributeError:
            pass


class TestLoadConfig:
    def test_loads_from_env(self) -> None:
        env = {
            "DATABASE_URL": "postgresql://u:p@host:5432/db",
            "DEEPSEEK_API_KEY": "dk-123",
            "GROK_API_KEY": "gk-456",
            "GROQ_API_KEY": "gq-789",
            "ANTHROPIC_API_KEY": "ak-abc",
            "QUANT_GATE_TOP_N": "50",
            "MIN_MARKET_CAP": "500000000",
            "MIN_HOLD_HOURS": "72",
        }
        with patch.dict(os.environ, env, clear=False):
            cfg = load_config()

        assert cfg.db_dsn == "postgresql://u:p@host:5432/db"
        assert cfg.deepseek_api_key == "dk-123"
        assert cfg.grok_api_key == "gk-456"
        assert cfg.groq_api_key == "gq-789"
        assert cfg.anthropic_api_key == "ak-abc"
        assert cfg.quant_gate_top_n == 50
        assert cfg.universe_min_market_cap == 500_000_000
        assert cfg.min_hold_hours == 72

    def test_defaults(self) -> None:
        env = {
            "DATABASE_URL": "",
            "DEEPSEEK_API_KEY": "",
            "GROK_API_KEY": "",
            "GROQ_API_KEY": "",
            "ANTHROPIC_API_KEY": "",
        }
        # Remove keys that might exist
        clean_env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("QUANT_GATE_TOP_N", "MIN_MARKET_CAP", "MIN_HOLD_HOURS")
        }
        clean_env.update(env)
        with patch.dict(os.environ, clean_env, clear=True):
            cfg = load_config()

        assert cfg.quant_gate_top_n == 100
        assert cfg.universe_min_market_cap == 200_000_000
        assert cfg.min_hold_hours == 48

    def test_app_config_frozen(self) -> None:
        cfg = AppConfig(db_dsn="", deepseek_api_key="", grok_api_key="", groq_api_key="", anthropic_api_key="")
        try:
            cfg.db_dsn = "x"  # type: ignore[misc]
            assert False, "Should be frozen"
        except AttributeError:
            pass
