from fastapi import FastAPI, Path
from loguru import logger
from contextlib import asynccontextmanager
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection
from settings import settings
from datetime import datetime
from fastapi.responses import JSONResponse


collections: dict[str, AsyncIOMotorCollection] = {
    "collection": None,
}

category_mapping: dict[str, str | None] = {
    "c0": None,
    "c1": "Latvijā",
    "c2": "Pasaulē", 
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # MongoDB connection setup using settings
    client = AsyncIOMotorClient(settings.MONGO_URI)
    db = client[settings.MONGO_DB]
    collections["collection"] = db[settings.MONGO_COLLECTION]
    yield
    client.close()


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Hello"}


# About page route
@app.get("/about")
async def about() -> dict[str, str]:
    return {"message": "This is the about page."}


def parse_date(date: str) -> datetime:
    """
    Parses a date string in the format YYYYMMDD into a datetime object.
    """
    try:
        return datetime.strptime(date, "%Y%m%d")
    except ValueError:
        raise ValueError("Invalid date format. Use YYYYMMDD.")


async def fetch_titles(filter_date: datetime, category: str = None) -> list[str]:
    """
    Fetches titles from MongoDB filtered by date and optionally by category.
    """
    col = collections["collection"]

    # Build the query
    query = {
        "date": {
            "$gte": filter_date,
            "$lt": filter_date.replace(day=filter_date.day + 1),
        }
    }
    if category:
        query["category"] = category

    # Query MongoDB
    posts = await col.find(query, {"_id": 0, "title": 1}).to_list(length=100)

    # Extract titles
    return [entry["title"] for entry in posts]


@app.get("/titles/{date}")
async def get_titles_by_date(date: str = Path(..., regex=r"^\d{8}$")) -> JSONResponse:
    """
    Filters posts by a specific date (YYYYMMDD) and returns their titles.
    """
    try:
        filter_date = parse_date(date)
    except ValueError as e:
        return JSONResponse(content={"error": str(e)}, status_code=400)

    titles = await fetch_titles(filter_date)
    logger.debug(f"Found {len(titles)} posts for date {date}")

    return JSONResponse(content={"titles": titles}, media_type="application/json; charset=utf-8")


@app.get("/titles/{category_key}/{date}")
async def get_titles_by_category_and_date(
    category_key: str, date: str = Path(..., regex=r"^\d{8}$")
) -> JSONResponse:
    """
    Filters posts by a specific category and date (YYYYMMDD) and returns their titles.
    """
    try:
        filter_date = parse_date(date)
    except ValueError as e:
        return JSONResponse(content={"error": str(e)}, status_code=400)

    category = category_mapping.get(category_key)
    titles = await fetch_titles(filter_date, category)
    logger.debug(f"Found {len(titles)} posts for category '{category}' and date {date}")

    return JSONResponse(content={"titles": titles}, media_type="application/json; charset=utf-8")
