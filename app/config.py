import os
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


@dataclass(frozen=True)
class Settings:
    bearer_token: str = field(default_factory=lambda: os.environ.get("BEARER_TOKEN", ""))
    database_url: str = field(default_factory=lambda: os.environ.get("DATABASE_URL", ""))
    log_level: str = field(default_factory=lambda: os.environ.get("LOG_LEVEL", "INFO"))


settings = Settings()
