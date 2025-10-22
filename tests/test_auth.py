import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import Base, engine


@pytest.fixture(autouse=True, scope="module")
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_register_and_login_and_refresh_and_logout():
    client = TestClient(app)

    # Register
    reg_payload = {
        "email": "user@example.com",
        "password": "secretpass",
    }
    r = client.post("/auth/register", json=reg_payload)
    assert r.status_code == 201
    assert "access_token" in r.json()
    # Refresh cookie set
    assert "refresh_token=" in r.headers.get("set-cookie", "")

    # Login
    login_payload = {"email": "user@example.com", "password": "secretpass"}
    r2 = client.post("/auth/login", json=login_payload)
    assert r2.status_code == 200
    assert "access_token" in r2.json()
    assert "refresh_token=" in r2.headers.get("set-cookie", "")

    # Refresh (reads cookie automatically)
    r3 = client.post("/auth/refresh")
    assert r3.status_code == 200
    assert "access_token" in r3.json()

    # Logout (delete cookie)
    r4 = client.post("/auth/logout")
    assert r4.status_code == 204
    # Further refresh should fail
    r5 = client.post("/auth/refresh")
    assert r5.status_code in (401, 403)
