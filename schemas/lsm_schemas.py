from bson import ObjectId
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Optional
from google.genai import types


class RunAgentRequest(BaseModel):
    appName: str
    userId: Optional[str]
    sessionId: Optional[str]
    newMessage: types.Content


# This is what is received from the agent
class AgentArticle(BaseModel):
    uuid: str
    summary: str
    title: str = None
    url: str = None


class AgentSummary(BaseModel):
    category: str
    articles: list[AgentArticle]


class AgentResponseSchema(BaseModel):
    summaries: list[AgentSummary]


# This is what is saved in db
class Article(BaseModel):
    article_id: ObjectId
    title: str
    url: str
    ai_summary: str

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )


class Summary(BaseModel):
    category: str
    articles: list[Article]


# What is stored in the summary collection
class MongoSummaryDocument(BaseModel):
    date: str
    summaries: list[Summary]

# Daily summary post response (upsert to mongo)
class MongoUpdateResult(BaseModel):
    did_upsert: bool
    matched_count: int
    modified_count: int
    upserted_id: ObjectId | None

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )


class ArticleNoID(BaseModel):
    title: str
    url: str
    ai_summary: str

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )


class SummaryNoID(BaseModel):
    category: str
    articles: list[ArticleNoID]


# Daily summary get response (website)
class DailySummarySchema(BaseModel):
    date: datetime
    summaries: list[SummaryNoID]

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={datetime: lambda dt: dt.strftime('%Y%m%d')}
    )