from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    mock_mode: bool = True
    openai_api_key: str = ""
    host: str = "0.0.0.0"
    port: int = 8000

    cost_per_1k_input: float = 0.00015
    cost_per_1k_output: float = 0.00060

    # Cloud Database URL from Neon
    database_url: str = ""

    # Local fallbacks
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "postgres"
    db_user: str = "postgres"
    db_password: str = "postgres"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()