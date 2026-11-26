import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from shortener.config import Settings
from shortener.db import Base
from shortener.main import create_app


@pytest.fixture
def database_url(tmp_path: Path) -> Iterator[str]:
    """Use PostgreSQL when TEST_DATABASE_URL is set (CI), SQLite otherwise."""
    url = os.environ.get("TEST_DATABASE_URL")
    if url is None:
        yield f"sqlite:///{tmp_path / 'test.db'}"
        return

    yield url
    # Leave a clean schema for the next test.
    engine = create_engine(url)
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(database_url: str) -> Iterator[TestClient]:
    settings = Settings(database_url=database_url, base_url="https://sho.rt")
    app = create_app(settings)
    with TestClient(app, follow_redirects=False) as test_client:
        yield test_client
