"""Root conftest.py — loads .env before any tests run."""
import pytest
from dotenv import load_dotenv

load_dotenv()


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    """Clear the lru_cache on get_settings so monkeypatch.setenv takes effect."""
    from config.settings import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
