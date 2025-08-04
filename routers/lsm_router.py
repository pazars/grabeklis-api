import json
import traceback
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from core.config import settings
from core.logger import logger
from core.database import get_db
from schemas import lsm_schemas
from google import genai
from google.genai import types
from utils import lsm

router = APIRouter()


@router.post("/lsm/summary/daily", response_model=lsm_schemas.MongoUpdateResult)
async def summarise_agent_articles(
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

    try:
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
            logger.info(f"Article limit: {limit}")
            articles = articles[:limit]

        parts, index = [], {}
        for article in articles:
            # LLMs copy URLs better than UUIDs
            index[article["url"]] = article
            for_request = {
                "uuid": article["url"],
                "category": article["category"],
                "article": article["article"],
            }

            parts.append(types.Part.from_text(text=str(for_request)))

        # Prepare content for the agent
        content = {"role": "user", "parts": parts}

        client = genai.Client(
            vertexai=True,
            project=settings.GCP_PROJECT_ID,
            location=settings.GCP_REGION,
        )
        tokens: types.CountTokensResponse = client.models.count_tokens(
            model="gemini-2.5-flash", contents=content
        )

        total_tokens = tokens.total_tokens
        logger.info(f"Input tokens: {total_tokens}")
        token_limit = 0.2e6
        if total_tokens > token_limit:
            msg = f"Token count {total_tokens} > {token_limit} limit"
            logger.error(msg)
            raise Exception(msg)

        config = types.GenerateContentConfig(
            system_instruction=settings.SUMMARY_SYSTEM_PROMPT,
            response_schema=lsm_schemas.AgentResponseSchema,
            response_mime_type="application/json",
            safety_settings=[
                types.SafetySetting(
                    category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"
                ),
                types.SafetySetting(
                    category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"
                ),
                types.SafetySetting(
                    category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"
                ),
                types.SafetySetting(
                    category="HARM_CATEGORY_HARASSMENT", threshold="OFF"
                ),
            ],
            thinking_config=types.ThinkingConfig(
                thinking_budget=15000,
            ),
        )

        res = client.models.generate_content(
            model=settings.GCP_MODEL_ID, contents=content, config=config
        )

        log_col = db[settings.REQUEST_LOG_COLLECTION]
        log_col.insert_one(res.model_dump())

        answer = res.candidates[0].content.parts[0].text

        try:
            summaries = json.loads(answer)
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

        logger.info("Adding summary to DB")
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
