import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from mvp.backend.database import Base, get_db


def _make_test_db():
    return "sqlite:///" + tempfile.mktemp(suffix=".db")


def _init_test_db(db_url):
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return engine, SessionLocal


@pytest.fixture
def client(monkeypatch):
    import mvp.backend.database as db_module
    import mvp.backend.main as main_module

    db_url = _make_test_db()
    test_engine, TestSessionLocal = _init_test_db(db_url)

    original_engine = db_module.engine
    original_main_engine = main_module.engine
    original_SessionLocal = db_module.SessionLocal
    db_module.engine = test_engine
    main_module.engine = test_engine
    db_module.SessionLocal = TestSessionLocal

    def override_get_db():
        d = TestSessionLocal()
        try:
            yield d
        finally:
            d.close()

    main_module.app.dependency_overrides[get_db] = override_get_db
    import mvp.backend.config as config_module
    monkeypatch.setattr(config_module.settings, "jwt_secret", "test-secret-" + "x" * 40)
    monkeypatch.setattr(config_module.settings, "rate_limit_fail_closed", False)
    monkeypatch.setattr(config_module.settings, "allow_unsigned_license_response", True)
    from fastapi.testclient import TestClient

    with TestClient(main_module.app) as c:
        # No real Redis in tests: rate limiter is fail-open; idempotency is fail-closed.
        main_module.redis_client = None
        yield c

    main_module.app.dependency_overrides.clear()
    db_module.engine = original_engine
    main_module.engine = original_main_engine
    db_module.SessionLocal = original_SessionLocal


@pytest.fixture
def db_session(client):
    import mvp.backend.database as db_module
    db = db_module.SessionLocal()
    try:
        yield db
    finally:
        db.close()
