from fastapi import APIRouter, HTTPException, Path, Query
from core.logger import logger
from core.config import settings
from datetime import datetime
from fastapi.responses import JSONResponse
from typing import Literal
from core.database import get_db
from services.adk_service import adk_service


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
    col = db[settings.LSM_COLLECTION]

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


@router.post("/agent/{agent_name}")
async def chat_with_agent_endpoint(
    agent_name: str = Path(
        ...,
        title="Agent Name",
        description="Name of the agent to interact with.",
    ),
    prompt: str = Query(
        ...,
        title="Prompt",
        description="Prompt to send to the agent.",
    ),
    username: str = Query(
        ...,
        title="Username",
        description="Username for the session.",
    ),
    session_id: str = Query(
        ...,
        title="Session ID",
        description="Session identifier.",
    ),
):
    """
    Handles interaction with a Google ADK agent.
    Checks for an existing session and prompts the agent.
    """
    try:
        # 1. Check/Create Google ADK Session
        await adk_service.get_or_create_adk_session(
            agent_name,
            username,
            session_id,
        )

        content = {"role": "user", "parts": [{"text": prompt}]}

        # 2. Prompt the Agent
        agent_response = await adk_service.prompt_adk_agent(
            agent_name, username, session_id, content
        )

        return agent_response

    except HTTPException as e:
        raise e  # Re-raise FastAPI HTTPExceptions
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error during agent interaction.",
        )