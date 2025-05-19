from fastapi import FastAPI, Path
from loguru import logger
from contextlib import asynccontextmanager
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection
from settings import settings
from datetime import datetime
from fastapi.responses import JSONResponse
from typing import Literal
from google import genai
from google.genai import types


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


async def fetch_article(
    filter_date: datetime,
    article_part: Literal["title", "summary", "article"],
    category: str = None,
) -> list[str]:
    """
    Fetches chosen article part from MongoDB filtered by date and optionally by category.
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
    posts = await col.find(query, {"_id": 0, article_part: 1}).to_list(length=100)

    # Extract titles
    return [entry[article_part] for entry in posts]


@app.get("/articles/{date}")
async def get_articles_by_date(date: str = Path(..., regex=r"^\d{8}$")) -> JSONResponse:
    """
    Filters posts by a specific date (YYYYMMDD) and returns their articles.
    """
    try:
        filter_date = parse_date(date)
    except ValueError as e:
        return JSONResponse(content={"error": str(e)}, status_code=400)

    articles = await fetch_article(filter_date, "article")
    logger.debug(f"Found {len(articles)} posts for date {date}")

    return JSONResponse(
        content={"articles": articles}, media_type="application/json; charset=utf-8"
    )


@app.get("/titles/{date}")
async def get_titles_by_date(date: str = Path(..., regex=r"^\d{8}$")) -> JSONResponse:
    """
    Filters posts by a specific date (YYYYMMDD) and returns their titles.
    """
    try:
        filter_date = parse_date(date)
    except ValueError as e:
        return JSONResponse(content={"error": str(e)}, status_code=400)

    titles = await fetch_article(filter_date, "title")
    logger.debug(f"Found {len(titles)} posts for date {date}")

    return JSONResponse(
        content={"titles": titles}, media_type="application/json; charset=utf-8"
    )


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
    titles = await fetch_article(filter_date, "title", category)
    logger.debug(f"Found {len(titles)} posts for category '{category}' and date {date}")

    return JSONResponse(
        content={"titles": titles}, media_type="application/json; charset=utf-8"
    )


@app.get("/summarise/{date}")
async def summarise_articles_for_date(
    date: str = Path(..., regex=r"^\d{8}$"),
) -> JSONResponse:
    client = genai.Client(
        vertexai=True,
        project=settings.GCP_PROJECT_ID,
        location=settings.VERTEXAI_REGION,
    )

    dt = parse_date(date)
    db_response = await fetch_article(dt, "article")
    articles = types.Part.from_text(text=" ".join(db_response))

    model = "gemini-2.0-flash-001"
    contents = [
        types.Content(role="user", parts=[articles]),
    ]

    generate_content_config = types.GenerateContentConfig(
        temperature=1,
        top_p=1,
        max_output_tokens=8192,
        safety_settings=[
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
            types.SafetySetting(
                category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"
            ),
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF"),
        ],
        system_instruction=[types.Part.from_text(text=settings.SUMMARY_SYSTEM_PROMPT)],
    )

    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=generate_content_config,
    )

    return JSONResponse(
        content={"summary": response.text},
        media_type="application/json; charset=utf-8",
    )
