import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

os.environ["DATABASE_URL"] = "sqlite:///./unused-test-only.db"
os.environ["SESSION_SECRET"] = "test-only-session-secret-with-more-than-32-bytes"
os.environ["SESSION_EXPIRE_HOURS"] = "168"
os.environ["COOKIE_SECURE"] = "false"
os.environ["COOKIE_SAMESITE"] = "lax"
os.environ["FRONTEND_ORIGIN"] = "http://localhost:5173"
os.environ["ENVIRONMENT"] = "test"

from app.db.base import Base
from app.db.session import get_db
from app.main import app


@pytest.fixture
def client() -> Generator[tuple[TestClient, object], None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    def override_get_db() -> Generator[Session, None, None]:
        with Session(engine, autoflush=False, expire_on_commit=False) as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client, engine
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()
