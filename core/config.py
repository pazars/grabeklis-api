from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    # MongoDB
    MONGO_URI: str
    MONGO_DB: str
    LSM_COLLECTION: str
    LSM_SUMMARY_COLLECTION: str

    # Google Cloud Platform (GCP)
    GCP_PROJECT_ID: str
    VERTEXAI_REGION: str

    # Google ADK
    GOOGLE_ADK_BASE_URL: str
    ADK_SYSTEM_USERNAME: str
    ADK_SYSTEM_SESSION_ID: str

    class Config:
        # Load .env file in development mode
        env_file = ".env" if os.getenv("ENVIRONMENT") == "dev" else None

settings = Settings()