import certifi
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from core.config import settings
from typing import Optional
from core.logger import logger

class MongoDB:
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None

    async def connect_db(self):
        """Initializes the MongoDB connection."""
        uri = settings.MONGO_URI
        db_name = settings.MONGO_DB
        self.client = AsyncIOMotorClient(uri, tlsCAFile=certifi.where())
        self.db = self.client[db_name]
        logger.info(f"Connected to MongoDB: {uri}/{db_name}")

    async def close_db(self):
        """Closes the MongoDB connection."""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed.")

    def get_database(self) -> AsyncIOMotorDatabase:
        """Returns the Motor database instance."""
        if self.db is None:
            msg = "Database not connected. Call connect_db() first."
            raise RuntimeError(msg)
        return self.db

# Instantiate the service (but don't connect yet)
mongodb_service = MongoDB()

# Dependency for FastAPI endpoints
async def get_db() -> AsyncIOMotorDatabase:
    """Dependency that yields the MongoDB database instance."""
    return mongodb_service.get_database()