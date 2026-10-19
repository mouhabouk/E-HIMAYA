import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("AI_SERVICE_TOKEN", "test-service-token-test-service-token")
os.environ.setdefault("AI_MODELS_DIR", "/nonexistent-models")
os.environ.setdefault("AI_OLLAMA_URL", "http://ollama.test")

from app.main import app

AUTH = {"Authorization": f"Bearer {os.environ['AI_SERVICE_TOKEN']}"}


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
