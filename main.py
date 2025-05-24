from fastapi import FastAPI
from contextlib import asynccontextmanager
from routers import agent_router, general_router
from services.mongodb_service import mongodb_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    # MongoDB connection
    await mongodb_service.connect_db()
    yield
    await mongodb_service.close_db()


app = FastAPI(lifespan=lifespan)

# Include your routers
app.include_router(agent_router.router, prefix="/api", tags=["Agent chat"])
app.include_router(general_router.router, prefix="/api", tags=["General"])


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Hello"}


# About page route
@app.get("/about")
async def about() -> dict[str, str]:
    return {"message": "This is the about page."}
