from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://zerobalance:zerobalance@db:5432/zerobalance"
    groq_api_key: str = ""
    qdrant_url: str = "http://qdrant:6333"


settings = Settings()
