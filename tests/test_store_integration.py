from fastapi.testclient import TestClient

from app.main import app
from app.db.session import Base, engine


def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def bearer(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


def test_store_purchase_end_to_end():
    reset_db()
    client = TestClient(app)

    # Register admin (id=1) and make admin
    r_admin = client.post("/auth/register", json={"email": "admin@x.com", "password": "secretpass"})
    assert r_admin.status_code == 201
    with engine.begin() as conn:
        conn.exec_driver_sql("UPDATE users SET role='admin' WHERE id=1")
    # Refresh token to include role
    r_admin_login = client.post("/auth/login", json={"email": "admin@x.com", "password": "secretpass"})
    assert r_admin_login.status_code == 200
    admin_headers = bearer(r_admin_login.json()["access_token"]) 

    # Register a user
    r_user = client.post("/auth/register", json={"email": "user@x.com", "password": "secretpass"})
    assert r_user.status_code == 201
    user_headers = bearer(r_user.json()["access_token"]) 

    # Create base and addon packages
    r_base = client.post(
        "/packages/",
        headers=admin_headers,
        json={"name": "baseA", "is_base": True, "price": 100, "is_deprecated": False},
    )
    r_addon = client.post(
        "/packages/",
        headers=admin_headers,
        json={"name": "addonX", "is_base": False, "price": 50, "is_deprecated": False},
    )
    assert r_base.status_code == 201 and r_addon.status_code == 201
    base = r_base.json()
    addon = r_addon.json()

    # Fund user balance
    r_inc = client.post("/balance/increase", headers=user_headers, json={"amount": 1000})
    assert r_inc.status_code == 200

    # Purchase 1 base + 1 addon for 5 days
    r_purchase = client.post(
        "/store/purchase",
        headers=user_headers,
        json={
            "items": [
                {"base_package_id": base["id"], "addon_package_ids": [addon["id"]]},
            ],
            "license_days": 5,
        },
    )
    assert r_purchase.status_code == 201
    created = r_purchase.json()
    assert len(created) == 1
    lic_key = created[0]["key"]

    # License should validate as valid
    r_valid = client.post("/licenses/validate", json={"key": lic_key})
    assert r_valid.status_code == 200 and r_valid.json()["valid"] is True

    # License packages should show both names
    r_pkgs = client.get(f"/licenses/{lic_key}/packages")
    assert r_pkgs.status_code == 200
    assert set(r_pkgs.json()["package_names"]) == {"baseA", "addonX"}
