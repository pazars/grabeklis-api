from pydantic import BaseModel
from typing import Optional
from google.genai import types


class RunAgentRequest(BaseModel):
    appName: str
    userId: Optional[str]
    sessionId: Optional[str]
    newMessage: types.Content
