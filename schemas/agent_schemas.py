from pydantic import BaseModel
from typing import Optional

class Message(BaseModel):
    role: str
    parts: list[dict]

class RunAgentRequest(BaseModel):
    appName: str
    userId: Optional[str]
    sessionId: Optional[str]
    newMessage: Message