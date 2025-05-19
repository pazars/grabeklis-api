from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    # MongoDB
    MONGO_URI: str
    MONGO_DB: str
    MONGO_COLLECTION: str

    # Google Cloud Platform (GCP)
    GCP_PROJECT_ID: str
    VERTEXAI_REGION: str

    SUMMARY_SYSTEM_PROMPT: str

    class Config:
        # Load .env file in development mode
        env_file = ".env" if os.getenv("ENVIRONMENT") == "dev" else None

settings = Settings()