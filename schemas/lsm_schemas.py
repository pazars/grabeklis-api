from bson import ObjectId
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class Article(BaseModel):
    title: str
    url: str
    ai_summary: str


class Summary(BaseModel):
    category: str
    articles: list[Article]


# What is received from LLM
class AgentResponseSchema(BaseModel):
    summaries: list[Summary]


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
        json_encoders={datetime: lambda dt: dt.strftime("%Y%m%d")},
    )
