from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    MONGO_URI: str
    MONGO_DB: str
    MONGO_COLLECTION: str

    class Config:
        # Load .env file in development mode
        env_file = ".env" if os.getenv("ENVIRONMENT") == "dev" else None

settings = Settings()