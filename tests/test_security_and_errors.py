from fastapi.testclient import TestClient

from app.main import app
from app.db.session import Base, engine


def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def register(client: TestClient, email: str, password: str = "secretpass") -> str:
    r = client.post("/auth/register", json={"email": email, "password": password})
    assert r.status_code == 201
    return r.json()["access_token"]


def promote_first_user_to_admin():
    with engine.begin() as conn:
        conn.exec_driver_sql("UPDATE users SET role='admin' WHERE id=1")


def test_non_admin_cannot_deprecate_or_undeprecate_or_list_licenses():
    reset_db()
    client = TestClient(app)

    # Create admin (id=1) and a normal user (id=2)
    admin_access = register(client, "admin@example.com")
    user_access = register(client, "user@example.com")

    # Promote first user to admin and refresh access token with new role
    promote_first_user_to_admin()
    admin_login = client.post("/auth/login", json={"email": "admin@example.com", "password": "secretpass"})
    assert admin_login.status_code == 200
    admin_headers = bearer(admin_login.json()["access_token"]) 

    # Create a package as admin
    r_pkg = client.post(
        "/packages/",
        headers=admin_headers,
        json={"name": "baseZ", "is_base": True, "price": 10, "is_deprecated": False},
    )
    assert r_pkg.status_code == 201
    pkg_id = r_pkg.json()["id"]

    # Non-admin cannot deprecate
    assert client.post(f"/packages/{pkg_id}/deprecate", headers=bearer(user_access)).status_code == 403
    # Non-admin cannot undeprecate
    assert client.post(f"/packages/{pkg_id}/undeprecate", headers=bearer(user_access)).status_code == 403
    # Non-admin cannot list licenses
    assert client.get("/licenses/", headers=bearer(user_access)).status_code == 403


def test_events_list_requires_admin_and_filters_work():
    reset_db()
    client = TestClient(app)

    # Create user and promote to admin
    register(client, "admin@example.com")  # id=1
    promote_first_user_to_admin()
    login = client.post("/auth/login", json={"email": "admin@example.com", "password": "secretpass"})
    assert login.status_code == 200
    admin_headers = bearer(login.json()["access_token"]) 

    # Log events (anonymous allowed)
    client.post("/events", json={"package_name": "pkgA", "package_version": "1.0.0", "license_key": None})
    client.post("/events", json={"package_name": "pkgB", "package_version": "2.0.0", "license_key": "ABC"})

    # Non-admin cannot list
    user_access = register(client, "user@example.com")
    assert client.get("/events", headers=bearer(user_access)).status_code == 403

    # Admin can list and filter
    r_all = client.get("/events", headers=admin_headers)
    assert r_all.status_code == 200 and len(r_all.json()) == 2

    r_pkgB = client.get("/events?package_name=pkgB", headers=admin_headers)
    assert r_pkgB.status_code == 200
    assert all(e["package_name"] == "pkgB" for e in r_pkgB.json())

    r_by_key = client.get("/events?license_key=ABC", headers=admin_headers)
    assert r_by_key.status_code == 200
    assert all(e["license_key"] == "ABC" for e in r_by_key.json())


def test_license_packages_unknown_key_404():
    reset_db()
    client = TestClient(app)

    r = client.get("/licenses/does-not-exist/packages")
    assert r.status_code == 404
