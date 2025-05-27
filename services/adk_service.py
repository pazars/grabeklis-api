import httpx
from fastapi import HTTPException
from core.config import settings
from schemas.agent_schemas import RunAgentRequest
from google.genai import types
from core.logger import logger


class ADKService:
    def __init__(self):
        self.adk_api_base_url = settings.GOOGLE_ADK_BASE_URL
        self.httpx_client = httpx.AsyncClient(base_url=self.adk_api_base_url)

    async def get_or_create_adk_session(
        self, app_name: str, user_id: str, session_id: str
    ):
        """
        Attempts to get an ADK session. If not found (404), creates a new one.
        Returns the session details or raises an HTTPException.
        """
        session_base_url = f"/apps/{app_name}/users/{user_id}/sessions/{session_id}"
        logger.debug(f"Attempting to get ADK session: {session_base_url}")

        # 1. First, attempt to GET the session
        try:
            get_response = await self.httpx_client.get(session_base_url)
            get_response.raise_for_status()

            # If GET is successful (200 OK), session already exists
            logger.info(
                f"ADK api_server: Session '{session_id}' for user '{user_id}' and app '{app_name}' already exists."
            )
            return get_response.json()  # Return existing session details

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # Session not found, proceed to create it
                logger.info(
                    f"ADK api_server: Session '{session_id}' not found (404). Attempting to create..."
                )
            else:
                # Other HTTP errors during GET (e.g., 500)
                logger.error(
                    f"ADK api_server: Error during GET session ({e.response.status_code}): {e.response.text}"
                )
                raise HTTPException(
                    status_code=e.response.status_code,
                    detail=f"Failed to check ADK session via api_server: {e.response.text}",
                )
        except httpx.RequestError as e:
            # Network error during GET attempt
            logger.error(
                f"Network error trying to connect to ADK api_server session endpoint (GET): {e}"
            )
            raise HTTPException(
                status_code=503,
                detail=f"Could not connect to ADK api_server session service at {self.adk_api_base_url}: {e}",
            )

        # 2. If session was not found (404 from GET), attempt to POST (create) it
        try:
            # A POST with an empty body is used to create the session.
            post_response = await self.httpx_client.post(session_base_url, json={})
            post_response.raise_for_status()  # Raises for 4xx/5xx

            logger.info(
                f"ADK api_server: Session '{session_id}' for user '{user_id}' and app '{app_name}' created successfully."
            )
            return post_response.json()  # Return newly created session details

        except httpx.HTTPStatusError as e:
            # This should ideally not happen if 404 was handled above,
            # but it's good to keep defensive checks.
            logger.error(
                f"ADK api_server: Error during POST session ({e.response.status_code}): {e.response.text}"
            )
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Failed to create ADK session via api_server: {e.response.text}",
            )
        except httpx.RequestError as e:
            # Network error during POST attempt
            logger.error(
                f"Network error trying to connect to ADK api_server session endpoint (POST): {e}"
            )
            raise HTTPException(
                status_code=503,
                detail=f"Could not connect to ADK api_server session service at {self.adk_api_base_url}: {e}",
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
                timeout=60,
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
