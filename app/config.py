import os
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def _bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    database_url: str = field(default_factory=lambda: os.environ.get("DATABASE_URL", ""))
    log_level: str = field(default_factory=lambda: os.environ.get("LOG_LEVEL", "INFO"))

    google_client_id: str = field(
        default_factory=lambda: os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
    )
    google_client_secret: str = field(
        default_factory=lambda: os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")
    )

    session_secret: str = field(default_factory=lambda: os.environ.get("SESSION_SECRET", ""))
    cookie_domain: str = field(default_factory=lambda: os.environ.get("COOKIE_DOMAIN", ""))
    cookie_secure: bool = field(default_factory=lambda: _bool("COOKIE_SECURE", False))

    default_post_login_url: str = field(
        default_factory=lambda: os.environ.get("DEFAULT_POST_LOGIN_URL", "/")
    )
    allowed_redirect_origins: str = field(
        default_factory=lambda: os.environ.get("ALLOWED_REDIRECT_ORIGINS", "")
    )

    anthropic_api_key: str = field(
        default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY", "")
    )
    openai_api_key: str = field(
        default_factory=lambda: os.environ.get("OPENAI_API_KEY", "")
    )

    media_root: str = field(
        default_factory=lambda: os.environ.get("MEDIA_ROOT", "/var/lib/jesse/media")
    )


settings = Settings()
