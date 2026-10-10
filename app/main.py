from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import Base, engine
from app.routers import jobs


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)   # fine for now; switch to Alembic later
    yield


app = FastAPI(title="JobFlow", lifespan=lifespan)
app.include_router(jobs.router)