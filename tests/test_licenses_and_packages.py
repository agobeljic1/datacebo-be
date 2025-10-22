from datetime import datetime, timezone, timedelta

from fastapi.testclient import TestClient

from app.main import app
from app.db.session import Base, engine


def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def register(client: TestClient, email: str, password: str = "secretpass") -> str:
    r = client.post("/auth/register", json={"email": email, "password": password})
    assert r.status_code == 201
    return r.json()["access_token"]


def login(client: TestClient, email: str, password: str = "secretpass") -> str:
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200
    return r.json()["access_token"]


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def promote_user1_to_admin():
    with engine.begin() as conn:
        conn.exec_driver_sql("UPDATE users SET role='admin' WHERE id=1")


def create_base_and_addon(client: TestClient, admin_headers: dict):
    # Create base
    r1 = client.post(
        "/packages/",
        headers=admin_headers,
        json={"name": "baseA", "is_base": True, "price": 100, "is_deprecated": False},
    )
    assert r1.status_code == 201
    base = r1.json()

    # Create add-on
    r2 = client.post(
        "/packages/",
        headers=admin_headers,
        json={"name": "addonX", "is_base": False, "price": 50, "is_deprecated": False},
    )
    assert r2.status_code == 201
    addon = r2.json()

    return base, addon


def test_admin_required_for_package_and_license_creation():
    reset_db()
    client = TestClient(app)

    # Create two users (ids 1 and 2)
    user1_token = register(client, "u1@example.com")
    register(client, "u2@example.com")

    # Non-admin cannot create package
    r_pkg = client.post(
        "/packages/",
        headers=bearer(user1_token),
        json={"name": "baseZ", "is_base": True, "price": 10, "is_deprecated": False},
    )
    assert r_pkg.status_code == 403

    # Non-admin cannot create license
    # Attempt to create license for user id 2 with some fake package id (will fail auth first)
    r_lic = client.post(
        "/licenses/",
        headers=bearer(user1_token),
        json={"user_id": 2, "package_ids": [1]},
    )
    assert r_lic.status_code == 403


def test_license_lifecycle_validate_revoke_and_expire_and_packages_guard():
    reset_db()
    client = TestClient(app)

    # Users
    user1_token = register(client, "admin@example.com")  # id=1
    register(client, "user2@example.com")  # id=2

    # Promote first user to admin and refresh token
    promote_user1_to_admin()
    admin_token = login(client, "admin@example.com")
    admin_headers = bearer(admin_token)

    base, addon = create_base_and_addon(client, admin_headers)

    # Create license for user 2 (base+addon)
    r_create = client.post(
        "/licenses/",
        headers=admin_headers,
        json={"user_id": 2, "package_ids": [base["id"], addon["id"]], "license_days": 30},
    )
    assert r_create.status_code == 201
    lic = r_create.json()

    # Validate returns valid
    r_valid = client.post("/licenses/validate", json={"key": lic["key"]})
    assert r_valid.status_code == 200
    assert r_valid.json()["valid"] is True

    # Revoke
    r_revoke = client.post(
        f"/licenses/{lic['id']}/revoke",
        headers=admin_headers,
        json={"reason": "test"},
    )
    assert r_revoke.status_code == 200
    assert r_revoke.json()["revoked_at"] is not None

    # Validate now invalid with reason
    r_valid2 = client.post("/licenses/validate", json={"key": lic["key"]})
    assert r_valid2.status_code == 200
    v2 = r_valid2.json()
    assert v2["valid"] is False and v2["reason"] == "test"

    # Create another license and force expire it
    r_create2 = client.post(
        "/licenses/",
        headers=admin_headers,
        json={"user_id": 2, "package_ids": [base["id"], addon["id"]], "license_days": 30},
    )
    assert r_create2.status_code == 201
    lic2 = r_create2.json()

    # Set expires_at in the past directly via SQL
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "UPDATE licenses SET expires_at = :past WHERE id = :id",
            {"past": datetime.now(tz=timezone.utc) - timedelta(days=1), "id": lic2["id"]},
        )

    # Validate invalid due to expiration
    r_valid3 = client.post("/licenses/validate", json={"key": lic2["key"]})
    assert r_valid3.status_code == 200
    assert r_valid3.json()["valid"] is False

    # Accessing packages with expired license is forbidden
    r_pkgs = client.get(f"/licenses/{lic2['key']}/packages")
    assert r_pkgs.status_code == 403


def test_package_deprecation_affects_access_and_listing():
    reset_db()
    client = TestClient(app)

    # Setup admin and user
    user1_token = register(client, "admin@example.com")  # id=1
    register(client, "user2@example.com")  # id=2
    promote_user1_to_admin()
    admin_token = login(client, "admin@example.com")
    admin_headers = bearer(admin_token)

    base, addon = create_base_and_addon(client, admin_headers)

    # License for user 2
    r_create = client.post(
        "/licenses/",
        headers=admin_headers,
        json={"user_id": 2, "package_ids": [base["id"], addon["id"]]},
    )
    assert r_create.status_code == 201
    lic = r_create.json()

    # Initially both packages visible
    r_pkgs1 = client.get(f"/licenses/{lic['key']}/packages")
    assert r_pkgs1.status_code == 200
    names1 = r_pkgs1.json()["package_names"]
    assert set(names1) == {"baseA", "addonX"}

    # Deprecate add-on -> only base visible
    r_dep_addon = client.post(f"/packages/{addon['id']}/deprecate", headers=admin_headers)
    assert r_dep_addon.status_code == 200 and r_dep_addon.json()["is_deprecated"] is True
    r_pkgs2 = client.get(f"/licenses/{lic['key']}/packages")
    assert r_pkgs2.status_code == 200
    names2 = r_pkgs2.json()["package_names"]
    assert names2 == ["baseA"]

    # Deprecate base -> neither visible (no base means add-ons are not granted)
    r_dep_base = client.post(f"/packages/{base['id']}/deprecate", headers=admin_headers)
    assert r_dep_base.status_code == 200 and r_dep_base.json()["is_deprecated"] is True
    r_pkgs3 = client.get(f"/licenses/{lic['key']}/packages")
    assert r_pkgs3.status_code == 200
    names3 = r_pkgs3.json()["package_names"]
    assert names3 == []

    # Listing packages excludes deprecated by default
    r_list_default = client.get("/packages/")
    assert r_list_default.status_code == 200
    assert r_list_default.json() == []

    # Including deprecated returns both
    r_list_all = client.get("/packages/?include_deprecated=true")
    assert r_list_all.status_code == 200
    all_names = {p["name"] for p in r_list_all.json()}
    assert all_names == {"baseA", "addonX"}


def test_user_can_see_accessible_packages_me_and_validate_packages_endpoint():
    reset_db()
    client = TestClient(app)

    # Setup admin and user
    user1_token = register(client, "admin@example.com")  # id=1
    user2_token = register(client, "user2@example.com")  # id=2
    promote_user1_to_admin()
    admin_token = login(client, "admin@example.com")
    admin_headers = bearer(admin_token)

    base, addon = create_base_and_addon(client, admin_headers)

    # Create license for user 2
    r_create = client.post(
        "/licenses/",
        headers=admin_headers,
        json={"user_id": 2, "package_ids": [base["id"], addon["id"]]},
    )
    assert r_create.status_code == 201
    lic = r_create.json()

    # /me/licenses shows user's packages (non-deprecated)
    r_me = client.get("/me/licenses", headers=bearer(user2_token))
    assert r_me.status_code == 200
    items = r_me.json()
    assert len(items) == 1
    assert set(items[0]["package_names"]) == {"baseA", "addonX"}

    # Deprecate add-on and verify /me/licenses filters it out
    client.post(f"/packages/{addon['id']}/deprecate", headers=admin_headers)
    r_me2 = client.get("/me/licenses", headers=bearer(user2_token))
    assert r_me2.status_code == 200
    items2 = r_me2.json()
    assert items2[0]["package_names"] == ["baseA"]

    # Validate license packages via POST body endpoint
    r_lp = client.post("/licenses/packages", json={"key": lic["key"]})
    assert r_lp.status_code == 200
    assert r_lp.json()["package_names"] == ["baseA"]


def test_license_extend_updates_expiry():
    reset_db()
    client = TestClient(app)

    # Setup admin and user
    register(client, "admin@example.com")  # id=1
    register(client, "user2@example.com")  # id=2
    promote_user1_to_admin()
    admin_token = login(client, "admin@example.com")
    admin_headers = bearer(admin_token)

    # Packages
    base, addon = create_base_and_addon(client, admin_headers)

    # Create license
    r_create = client.post(
        "/licenses/",
        headers=admin_headers,
        json={"user_id": 2, "package_ids": [base["id"], addon["id"]], "license_days": 5},
    )
    assert r_create.status_code == 201
    lic = r_create.json()
    orig_expires = datetime.fromisoformat(lic["expires_at"])  # iso format expected

    # Extend by 10 days
    r_ext = client.post(f"/licenses/{lic['id']}/extend", headers=admin_headers, json={"extra_days": 10})
    assert r_ext.status_code == 200
    new_expires = datetime.fromisoformat(r_ext.json()["expires_at"]).replace(tzinfo=orig_expires.tzinfo)
    # Allow a small delta; exact timedelta of 10 days
    assert (new_expires - orig_expires).days == 10


def test_license_requires_exactly_one_base_on_create():
    reset_db()
    client = TestClient(app)

    # Setup admin and user
    register(client, "admin@example.com")  # id=1
    register(client, "user2@example.com")  # id=2
    promote_user1_to_admin()
    admin_token = login(client, "admin@example.com")
    admin_headers = bearer(admin_token)

    # Create two base packages
    r1 = client.post(
        "/packages/",
        headers=admin_headers,
        json={"name": "base1", "is_base": True, "price": 10, "is_deprecated": False},
    )
    r2 = client.post(
        "/packages/",
        headers=admin_headers,
        json={"name": "base2", "is_base": True, "price": 20, "is_deprecated": False},
    )
    assert r1.status_code == 201 and r2.status_code == 201
    b1, b2 = r1.json(), r2.json()

    # Attempt to create license with two bases -> 400
    r_create = client.post(
        "/licenses/",
        headers=admin_headers,
        json={"user_id": 2, "package_ids": [b1["id"], b2["id"]]},
    )
    assert r_create.status_code == 400


def test_cannot_create_license_with_deprecated_package():
    reset_db()
    client = TestClient(app)

    # Setup admin and user
    register(client, "admin@example.com")  # id=1
    register(client, "user2@example.com")  # id=2
    promote_user1_to_admin()
    admin_token = login(client, "admin@example.com")
    admin_headers = bearer(admin_token)

    # Create base and addon, then deprecate addon
    base, addon = create_base_and_addon(client, admin_headers)
    r_dep = client.post(f"/packages/{addon['id']}/deprecate", headers=admin_headers)
    assert r_dep.status_code == 200

    # Attempt to create license should fail because addon is deprecated
    r_create = client.post(
        "/licenses/",
        headers=admin_headers,
        json={"user_id": 2, "package_ids": [base["id"], addon["id"]]},
    )
    assert r_create.status_code == 400


