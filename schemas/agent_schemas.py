from pydantic import BaseModel
from typing import Optional
from google.genai import types


class RunAgentRequest(BaseModel):
    appName: str
    userId: Optional[str]
    sessionId: Optional[str]
    newMessage: types.Content

class Article(BaseModel):
    title: str
    url: str
    summary: str

class Summary(BaseModel):
    category: str
    articles: list[Article]

class ResponseSchema(BaseModel):
    category_summary: list[Summary]