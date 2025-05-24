from fastapi import APIRouter, HTTPException, Path, Query
from services.adk_service import adk_service

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

        # 2. Prompt the Agent
        agent_response = await adk_service.prompt_adk_agent(
            agent_name, username, session_id, prompt
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
