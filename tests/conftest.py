import httpx
import pytest

from boundary_agent import config
from boundary_agent.utils import grant_store


def _up(url: str) -> bool:
    try:
        return httpx.get(url, timeout=3.0).status_code == 200
    except httpx.HTTPError:
        return False


@pytest.fixture(scope="session", autouse=True)
def require_stack():
    missing = [u for u in (f"{config.DMN_BASE_URL}/actuator/health", f"{config.CRM_BASE_URL}/health") if not _up(u)]
    if missing:
        pytest.fail(f"Stack not running (docker compose up -d): {missing}")


@pytest.fixture(autouse=True)
def clean_stores():
    grant_store.clear()
    yield
    grant_store.clear()
