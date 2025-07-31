import json
import uuid
import traceback
from datetime import datetime
from fastapi import APIRouter, HTTPException, Path, Query
from fastapi.responses import JSONResponse
from core.config import settings
from core.logger import logger
from core.database import get_db
from services.adk_service import adk_service
from schemas import lsm_schemas
from google.genai import types
from utils import lsm

router = APIRouter()


@router.post(
    "/lsm/summary/daily/{agent_name}", response_model=lsm_schemas.MongoUpdateResult
)
async def summarise_agent_articles(
    agent_name: str = Path(
        ...,
        title="Agent Name",
        description="Name of the agent to interact with for summarization.",
    ),
    date: str = Query(
        ...,
        title="Date",
        description="Date in YYYYMMDD format.",
        regex=r"^\d{8}$",
    ),
    limit: int = Query(
        default=None,
        title="Article count limit",
        description="Limit the summary to a number of articles.",
    ),
):
    """
    Summarizes articles within a date range using the specified agent.
    """
    fmt = "%Y%m%d"
    username = settings.ADK_SYSTEM_USERNAME
    session_id = settings.ADK_SYSTEM_SESSION_ID

    try:
        # Check/Create Google ADK Session
        await adk_service.get_or_create_adk_session(
            agent_name,
            username,
            session_id,
        )

        # Query MongoDB for articles within the single day
        db = await get_db()
        col = db[settings.LSM_COLLECTION]

        dt = datetime.strptime(date, fmt)

        find = {
            "_id": 1,
            "url": 1,
            "article": 1,
            "category": 1,
            "title": 1,
        }

        articles = await lsm.get_articles_by_date(col, dt, find)

        if not articles or len(articles) == 0:
            msg = "No articles found in the specified date range."
            return JSONResponse(
                content={"message": msg},
                status_code=404,
            )

        if limit:
            logger.info(f"Limiting number of articles to: {limit}")
            articles = articles[:limit]

        parts, index = [], {}
        for article in articles:
            # Don't send actual database IDs
            new_id = str(uuid.uuid4())
            index[new_id] = article

            for_request = {
                "uuid": new_id,
                "category": article["category"],
                "article": article["article"],
            }

            parts.append(types.Part.from_text(text=str(for_request)))

        # Prepare content for the agent
        content = {"role": "user", "parts": parts}

        # Send to the agent for summarization
        res = await adk_service.prompt_adk_agent(
            agent_name, username, session_id, content
        )

        prelim_answer = res[0]["content"]["parts"][0]["text"]

        try:
            summaries = json.loads(prelim_answer)
            summaries = lsm_schemas.AgentResponseSchema(**summaries)
        except Exception as e:
            logger.error(f"Error parsing agent response: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to parse agent response.",
            )

        response_summaries: list[lsm_schemas.Summary] = []
        # Map back to database IDs and add metadata
        for summary in summaries.summaries:
            response_articles: list[lsm_schemas.Article] = []

            for article in summary.articles:
                data = index[article.uuid]
                response_article = lsm_schemas.Article(
                    article_id=data["_id"],
                    title=data["title"],
                    url=data["url"],
                    ai_summary=article.summary,
                )
                response_articles.append(response_article)

            response_summary = lsm_schemas.Summary(
                category=summary.category,
                articles=response_articles,
            )

            response_summaries.append(response_summary)

        res = lsm_schemas.MongoSummaryDocument(
            **{
                "date": dt.strftime("%Y%m%d"),
                "summaries": response_summaries,
            }
        )

        db = await get_db()
        col = db[settings.LSM_SUMMARY_COLLECTION]
        result = await lsm.upsert_summary(col, res)

        return result

    except HTTPException as e:
        raise e
    except Exception:
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail="Unexpected exception occured",
        )


@router.get("/lsm/summary/daily", response_model=lsm_schemas.DailySummarySchema)
async def get_daily_summary(
    date: str = Query(
        ...,
        title="Date",
        description="Date in YYYYMMDD format.",
        regex=r"^\d{8}$",
    ),
):
    db = await get_db()
    col = db[settings.LSM_SUMMARY_COLLECTION]
    document = await lsm.get_daily_summary(col, date)

    res = lsm_schemas.DailySummarySchema(**document)
    return res
