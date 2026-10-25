import pytest
from fastapi.testclient import TestClient

import app as app_module


@pytest.fixture(autouse=True)
def _fresh_limiter():
    app_module.limiter.reset()


@pytest.fixture
def client():
    return TestClient(app_module.app)
