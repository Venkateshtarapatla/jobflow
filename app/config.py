from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://jobflow:jobflow@localhost:5432/jobflow"
    redis_url: str = "redis://localhost:6379/0"
    max_retries: int = 3

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
