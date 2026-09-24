from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Universal Web Agent"
    environment: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    google_api_key: str | None = None
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    primary_model: str = "gemini-3.8-flash"
    planner_model: str = "gemini-3.1-pro-preview"
    default_max_steps: int = 40
    default_max_failures: int = 3
    default_task_budget_usd: float = 0.75
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
