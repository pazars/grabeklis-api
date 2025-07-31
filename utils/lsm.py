from datetime import datetime, timedelta, timezone
from motor.motor_asyncio import AsyncIOMotorCollection
from schemas.lsm_schemas import MongoSummaryDocument, MongoUpdateResult

LSM_SKIP_CATEGORIES = [
    "Vaļasprieki",
    "Virtuve",
    "Laika ziņas",
    "Ceļošana",
    "Cilvēkstāsti",
    "Ikdienai",
    "Ziņas vieglajā valodā",
    "Podkāsti",
    "Vēsture",
    "Sarunas",
    "Skatpunts",
]

DEFAULT_FIND_FILTER = {
    "_id": 0,
    "url": 1,
    "article": 1,
    "category": 1,
}


async def get_articles_by_date(
    col: AsyncIOMotorCollection,
    dt: datetime,
    find: dict = DEFAULT_FIND_FILTER,
):
    # Articles of the same day are considered until 3 AM the next day
    # because close to midnight events can be publised after midnigt.
    start_of_day = dt.replace(hour=0, minute=0, second=0)
    end_of_day = start_of_day + timedelta(days=1, hours=3)

    query = {
        "date": {
            "$gte": start_of_day,
            "$lt": end_of_day,
        },
        "category": {
            "$nin": LSM_SKIP_CATEGORIES,
        },
    }

    articles = await col.find(query, find).to_list()

    return articles


async def upsert_summary(
    col: AsyncIOMotorCollection, data: MongoSummaryDocument
) -> MongoUpdateResult:
    # Convert data.date string (%Y%m%d) to a datetime.date object
    # This will parse 'YYYYMMDD' string into a date object
    summary_date = datetime.strptime(data.date, "%Y%m%d").date()

    # Convert the datetime.date object to a datetime.datetime object
    # Set time to midnight and ensure it's UTC for MongoDB's internal storage consistency
    summary_datetime_utc = datetime(
        summary_date.year,
        summary_date.month,
        summary_date.day,
        0,
        0,
        0,  # Midnight
        tzinfo=timezone.utc,  # Explicitly UTC
    )

    # Get the current timestamp, also as an aware UTC datetime object
    current_timestamp_utc = datetime.now(timezone.utc)

    # Prepare the document to be upserted
    # Start with the dumped data from the Pydantic model
    document_to_upsert = data.model_dump()

    # Add the actual date object (not just the string) and the timestamp
    document_to_upsert["date"] = summary_datetime_utc
    document_to_upsert["updated_at"] = current_timestamp_utc

    # Define the filter to check if a document with this date already exists
    # We compare against the 'date' field in the database which should also be a date object
    query = {"date": summary_datetime_utc}

    # Perform the upsert operation
    # If a document matching the query exists, it will be updated with the new data.
    # If not, a new document will be inserted.
    result = await col.update_one(query, {"$set": document_to_upsert}, upsert=True)

    res = MongoUpdateResult(
        did_upsert=result.did_upsert,
        matched_count=result.matched_count,
        modified_count=result.modified_count,
        upserted_id=result.upserted_id,
    )

    return res


async def get_daily_summary(col: AsyncIOMotorCollection, date: datetime):
    dt = datetime.strptime(date, "%Y%m%d")

    target_date_utc = datetime(dt.year, dt.month, dt.day).replace(
        hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc
    )

    query = {"date": target_date_utc}

    find = {"_id": 0, "date": 1, "summaries": 1}

    # Find a single document that exactly matches the date
    document = await col.find_one(query, find)

    return document
