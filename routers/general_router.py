from fastapi import APIRouter, Path
from core.logger import logger
from core.config import settings
from datetime import datetime
from fastapi.responses import JSONResponse
from typing import Literal
from google import genai
from google.genai import types
from core.database import get_db


category_mapping: dict[str, str | None] = {
    "c0": None,
    "c1": "Latvijā",
    "c2": "Pasaulē",
}

router = APIRouter()


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

    db = await get_db()
    col = db[settings.MONGO_COLLECTION]

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


@router.get("/articles/{date}")
async def get_articles_by_date(date: str = Path(..., regex=r"^\d{8}$")) -> JSONResponse:
    """
    Filters posts by a specific date (YYYYMMDD) and returns their articles.
    """
    try:
        filter_date = parse_date(date)
    except ValueError as e:
        return JSONResponse(content={"error": str(e)}, status_code=400)

    articles = await fetch_article(filter_date, "article")
    logger.info(f"Found {len(articles)} posts for date {date}")

    return JSONResponse(
        content={"articles": articles}, media_type="application/json; charset=utf-8"
    )


@router.get("/titles/{date}")
async def get_titles_by_date(date: str = Path(..., regex=r"^\d{8}$")) -> JSONResponse:
    """
    Filters posts by a specific date (YYYYMMDD) and returns their titles.
    """
    try:
        filter_date = parse_date(date)
        logger.info(f"Parsed date: {filter_date}")
    except ValueError as e:
        return JSONResponse(content={"error": str(e)}, status_code=400)

    titles = await fetch_article(filter_date, "title")
    logger.info(f"Found {len(titles)} posts for date {date}")

    return JSONResponse(
        content={"titles": titles}, media_type="application/json; charset=utf-8"
    )


@router.get("/titles/{category_key}/{date}")
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
    logger.info(f"Found {len(titles)} posts for category '{category}' and date {date}")

    return JSONResponse(
        content={"titles": titles}, media_type="application/json; charset=utf-8"
    )


@router.get("/summarise/{date}")
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
