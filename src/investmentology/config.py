from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    port: int
    database: str
    user: str
    password: str

    @property
    def dsn(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


@dataclass(frozen=True)
class AppConfig:
    db_dsn: str
    deepseek_api_key: str
    grok_api_key: str
    groq_api_key: str
    anthropic_api_key: str
    use_claude_cli: bool = False
    use_gemini_cli: bool = False
    use_edgar: bool = True
    quant_gate_top_n: int = 100
    universe_min_market_cap: int = 200_000_000
    min_hold_hours: int = 48
    post_screen_threshold: float = 0.70
    fred_api_key: str = ""
    finnhub_api_key: str = ""
    enable_debate: bool = True
    auth_password_hash: str = ""
    auth_secret_key: str = ""
    auth_token_expiry_hours: int = 168
    internal_api_token: str = ""


def load_config() -> AppConfig:
    """Load application config from environment variables.

    Loads .env file if present in the current directory or project root.
    """
    # Try loading .env from cwd or project root
    env_path = Path(".env")
    if env_path.exists():
        load_dotenv(env_path)

    return AppConfig(
        db_dsn=os.environ.get("DATABASE_URL", ""),
        deepseek_api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
        grok_api_key=os.environ.get("GROK_API_KEY", ""),
        groq_api_key=os.environ.get("GROQ_API_KEY", ""),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        use_claude_cli=os.environ.get("USE_CLAUDE_CLI", "").lower() in ("1", "true", "yes"),
        use_gemini_cli=os.environ.get("USE_GEMINI_CLI", "").lower() in ("1", "true", "yes"),
        use_edgar=os.environ.get("USE_EDGAR", "true").lower() in ("1", "true", "yes"),
        quant_gate_top_n=int(os.environ.get("QUANT_GATE_TOP_N", "100")),
        universe_min_market_cap=int(os.environ.get("MIN_MARKET_CAP", "200000000")),
        min_hold_hours=int(os.environ.get("MIN_HOLD_HOURS", "48")),
        post_screen_threshold=float(os.environ.get("POST_SCREEN_THRESHOLD", "0.70")),
        fred_api_key=os.environ.get("FRED_API_KEY", ""),
        finnhub_api_key=os.environ.get("FINNHUB_API_KEY", ""),
        enable_debate=os.environ.get("ENABLE_DEBATE", "true").lower() in ("1", "true", "yes"),
        auth_password_hash=os.environ.get("AUTH_PASSWORD_HASH", ""),
        auth_secret_key=os.environ.get("AUTH_SECRET_KEY", ""),
        auth_token_expiry_hours=int(os.environ.get("AUTH_TOKEN_EXPIRY_HOURS", "168")),
        internal_api_token=os.environ.get("INTERNAL_API_TOKEN", ""),
    )
