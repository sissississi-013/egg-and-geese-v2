"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Central settings for all API keys and connection strings."""

    # --- Databases ---
    database_url: str = Field(
        default="postgresql+asyncpg://egggeese:egggeese2024@localhost:5432/egggeese",
        alias="DATABASE_URL",
    )
    neo4j_uri: str = Field(
        default="neo4j+s://f32c51a6.databases.neo4j.io", alias="NEO4J_URI"
    )
    neo4j_user: str = Field(default="neo4j", alias="NEO4J_USER")
    neo4j_password: str = Field(default="", alias="NEO4J_PASSWORD")
    neo4j_database: str = Field(default="neo4j", alias="NEO4J_DATABASE")

    # --- GLiNER (local model, Pioneer-deployed endpoint, or Fastino hosted) ---
    # Mode: "local"   → loads model from HuggingFace into memory
    #        "pioneer" → calls a Pioneer-deployed inference endpoint
    #        "fastino" → calls Fastino's hosted /gliner-2 endpoint
    gliner_mode: str = Field(default="fastino", alias="GLINER_MODE")
    gliner_model_id: str = Field(
        default="gliner-community/gliner_medium-v2.5",
        alias="GLINER_MODEL_ID",
    )
    # Pioneer endpoint URL (only used when GLINER_MODE=pioneer)
    pioneer_endpoint_url: str = Field(default="", alias="PIONEER_ENDPOINT_URL")
    pioneer_api_key: str = Field(default="", alias="PIONEER_API_KEY")
    # Fastino hosted endpoint (only used when GLINER_MODE=fastino)
    fastino_base_url: str = Field(
        default="https://api.pioneer.ai", alias="FASTINO_BASE_URL"
    )
    # NER confidence threshold
    gliner_threshold: float = Field(default=0.3, alias="GLINER_THRESHOLD")

    # --- Yutori (web agents: scouting, research, browsing) ---
    yutori_api_key: str = Field(default="", alias="YUTORI_API_KEY")
    yutori_base_url: str = Field(
        default="https://api.yutori.com", alias="YUTORI_BASE_URL"
    )

    # --- Reka Vision ---
    reka_api_key: str = Field(default="", alias="REKA_API_KEY")
    reka_base_url: str = Field(
        default="https://api.reka.ai", alias="REKA_BASE_URL"
    )

    # --- Senso ---
    senso_api_key: str = Field(default="", alias="SENSO_API_KEY")
    senso_base_url: str = Field(
        default="https://api.senso.ai/v1", alias="SENSO_BASE_URL"
    )

    # --- Anthropic ---
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")

    # --- OpenClaw Gateway ---
    openclaw_gateway_url: str = Field(
        default="http://localhost:3001", alias="OPENCLAW_GATEWAY_URL"
    )

    # --- App ---
    app_env: str = Field(default="development", alias="APP_ENV")
    metrics_poll_interval_minutes: int = Field(
        default=30, alias="METRICS_POLL_INTERVAL_MINUTES"
    )

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
