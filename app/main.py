from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import Base, engine
from app.routers import dead_letter, jobs


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)  # fine for now; switch to Alembic later
    yield


app = FastAPI(title="JobFlow", lifespan=lifespan)
app.include_router(jobs.router)
app.include_router(dead_letter.router)
