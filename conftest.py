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


@pytest.fixture()
def fresh_db(tmp_path, monkeypatch):
    """Provide each test with an isolated SQLite database."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("SQLITE_DB_PATH", db_path)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from persistence.models import Base
    import persistence.database as db_mod

    test_engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(test_engine)
    db_mod.engine = test_engine
    db_mod.SessionLocal = sessionmaker(
        bind=test_engine, autocommit=False, autoflush=False
    )

    yield

    Base.metadata.drop_all(test_engine)
