import asyncio
import httpx
from fastapi import HTTPException
from core.config import settings
from schemas.adk_schemas import RunAgentRequest
from google.genai import types
from core.logger import logger


class ADKService:
    def __init__(self):
        self.adk_api_base_url = settings.GOOGLE_ADK_BASE_URL
        self.httpx_client = httpx.AsyncClient(base_url=self.adk_api_base_url)

    async def get_or_create_adk_session(
        self, app_name: str, user_id: str, session_id: str, max_retries: int = 5
    ):
        """
        Attempts to get an ADK session. If not found, tries to create it.
        Retries with exponential backoff if creation fails.
        """
        session_url = f"/apps/{app_name}/users/{user_id}/sessions/{session_id}"

        for attempt in range(max_retries):
            try:
                # Try to GET the session
                resp = await self.httpx_client.get(session_url)
                if resp.status_code == 200:
                    logger.info("Using existing ADK session")
                    return resp.json()
                # If not found, try to create
                else:
                    create_resp = await self.httpx_client.post(session_url, json={})
                    if create_resp.status_code - 200 < 100:
                        logger.info(f"Created new ADK session: {user_id} - {session_id}")
                        return create_resp.json()
            except Exception:
                logger.info(f"Attempt {attempt + 1}: Failed to get or create ADK session.")
                pass  # Ignore and retry

            # Exponential backoff
            await asyncio.sleep(2 ** attempt)

        raise HTTPException(
            status_code=503,
            detail=f"Could not get or create ADK session after {max_retries} attempts.",
        )

    async def prompt_adk_agent(
        self, app_name: str, user_id: str, session_id: str, content: types.Content
    ) -> dict:
        """
        Prompts the ADK agent via the /run endpoint of the adk api_server.
        """
        run_agent_url = "/run"
        run_agent_payload = RunAgentRequest(
            appName=app_name,
            userId=user_id,
            sessionId=session_id,
            newMessage=content,
        ).model_dump(by_alias=True)

        try:
            response = await self.httpx_client.post(
                run_agent_url,
                json=run_agent_payload,
                headers={"Content-Type": "application/json"},
                timeout=600,
            )
            response.raise_for_status()
            logger.info(
                f"ADK api_server run successful. Response status: {response.status_code}"
            )
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                f"ADK api_server run error: {e.response.status_code} - {e.response.text}"
            )
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Failed to prompt ADK agent via api_server: {e.response.text}",
            )
        except httpx.RequestError as e:
            logger.error(
                f"Network error connecting to ADK api_server run endpoint: {e}"
            )
            raise HTTPException(
                status_code=503,
                detail=f"Could not connect to ADK api_server run service at {self.adk_api_base_url}: {e}",
            )


# Instantiate the service
adk_service = ADKService()
