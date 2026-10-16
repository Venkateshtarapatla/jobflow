import os

os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg2://jobflow:jobflow@localhost:5432/jobflow_test",
)

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.main import app

assert engine.url.database.endswith("_test"), "Tests must run against a *_test database"


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def delay_mock():
    """Replaces Celery's .delay() so tests never need Redis."""
    with patch("app.routers.jobs.process_job.delay") as mocked:
        yield mocked
