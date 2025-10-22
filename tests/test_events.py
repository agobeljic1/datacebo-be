from fastapi.testclient import TestClient

from app.main import app
from app.db.session import Base, engine


def auth_headers(client: TestClient, email: str, password: str) -> dict:
    r = client.post("/auth/register", json={"email": email, "password": password})
    assert r.status_code == 201
    return {"Authorization": f"Bearer {r.json()["access_token"]}"}


def make_admin(client: TestClient, headers: dict) -> None:
    # Create a second user; first user has id=1, second id=2. Promote id=1 to admin using id=1 itself not possible via API without admin.
    # Workaround: directly update DB for test simplicity.
    with engine.begin() as conn:
        conn.exec_driver_sql("UPDATE users SET role='admin' WHERE id=1")


def test_log_event_and_list_as_admin():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    client = TestClient(app)

    headers = auth_headers(client, "user@example.com", "secretpass")
    make_admin(client, headers)

    # Log an event anonymously
    payload = {
        "package_name": "pkgA",
        "package_version": "1.0.0",
        "license_key": None,
    }
    r = client.post("/events", json=payload)
    assert r.status_code == 201
    data = r.json()
    assert data["package_name"] == "pkgA"
    assert data["valid_at_log_time"] is False

    # List events as admin
    # Refresh login to get latest admin role into access token
    rlogin = client.post("/auth/login", json={"email": "user@example.com", "password": "secretpass"})
    assert rlogin.status_code == 200
    admin_headers = {"Authorization": f"Bearer {rlogin.json()['access_token']}"}
    r2 = client.get("/events", headers=admin_headers)
    assert r2.status_code == 200
    items = r2.json()
    assert len(items) == 1
    assert items[0]["package_name"] == "pkgA"


