import json
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Path, Query
from fastapi.responses import JSONResponse
from core.config import settings
from core.database import get_db
from services.adk_service import adk_service
from schemas.agent_schemas import ResponseSchema

router = APIRouter()


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


@router.get("/agent/summary/daily/{agent_name}")
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
):
    """
    Summarizes articles within a date range using the specified agent.
    """
    fmt = "%Y%m%d"
    username = settings.ADK_SYSTEM_USERNAME
    session_id = settings.ADK_SYSTEM_SESSION_ID

    try:
        # 1. Check/Create Google ADK Session
        await adk_service.get_or_create_adk_session(
            agent_name,
            username,
            session_id,
        )
        # Parse the dates

        dt = datetime.strptime(date, fmt)

        # Query MongoDB for articles within the single day
        db = await get_db()
        col = db[settings.MONGO_COLLECTION]

        # Articles of the same day are considered until 3 AM the next day
        start_of_day = dt.replace(hour=0, minute=0, second=0)
        end_of_day = start_of_day + timedelta(days=1, hours=3)

        query = {
            "date": {
                "$gte": start_of_day,
                "$lt": end_of_day,
            }
        }
        
        articles = await col.find(
            query,
            {
                "_id": 0,
                "article": 1,
                "category": 1,
                "url": 1,
            },
        ).to_list(length=100)

        if not articles or len(articles) == 0:
            msg = "No articles found in the specified date range."
            return JSONResponse(
                content={"message": msg},
                status_code=404,
            )

        parts = [{"text": str(article)} for article in articles]

        # Prepare content for the agent
        content = {"role": "user", "parts": parts}

        # Send to the agent for summarization
        res = await adk_service.prompt_adk_agent(
            agent_name, username, session_id, content
        )

        prelim_answer = res[0]["content"]["parts"][0]["text"]
        answer = json.loads(prelim_answer)
        answer = ResponseSchema(**answer)

        return JSONResponse(
            content=answer.model_dump(),
            media_type="application/json; charset=utf-8",
        )

    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error during summarization.",
        )
