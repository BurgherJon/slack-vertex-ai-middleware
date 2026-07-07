# Copyright (C) 2025 Comites.ai
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin user administration via the rendered admin UI."""
from app.models.user import User, PlatformIdentity


def _login(client):
    client.get("/admin/auth/callback?code=t&state=t", follow_redirects=False)


def _seed_user(fake_firestore, **overrides):
    fields = {
        "primary_name": "Jonathan",
        "email": "jonathan@example.com",
        "identities": [
            PlatformIdentity(
                platform="slack",
                platform_user_id="U_123",
                display_name="Jonathan",
            )
        ],
    }
    fields.update(overrides)
    return fake_firestore.add_user(User(**fields), user_id="user-1")


def test_users_list_renders_empty_state(admin_client):
    _login(admin_client)
    response = admin_client.get("/admin/users")
    assert response.status_code == 200
    assert "No users yet" in response.text


def test_users_list_shows_user_and_timezone(admin_client, fake_firestore):
    _seed_user(fake_firestore, default_timezone="America/New_York")
    _login(admin_client)
    response = admin_client.get("/admin/users")
    assert response.status_code == 200
    assert "Jonathan" in response.text
    assert "America/New_York" in response.text


def test_users_list_requires_auth(admin_client):
    response = admin_client.get("/admin/users", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"


def test_edit_user_updates_fields(admin_client, fake_firestore):
    user_id = _seed_user(fake_firestore)
    _login(admin_client)
    response = admin_client.post(
        f"/admin/users/{user_id}/edit",
        data={
            "primary_name": "Jon",
            "email": "jon@example.com",
            "default_timezone": "Europe/London",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/users"

    stored = fake_firestore.users[user_id]
    assert stored["primary_name"] == "Jon"
    assert stored["email"] == "jon@example.com"
    assert stored["default_timezone"] == "Europe/London"


def test_edit_user_can_unset_timezone_and_email(admin_client, fake_firestore):
    user_id = _seed_user(fake_firestore, default_timezone="Europe/London")
    _login(admin_client)
    response = admin_client.post(
        f"/admin/users/{user_id}/edit",
        data={"primary_name": "Jonathan", "email": "", "default_timezone": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303

    stored = fake_firestore.users[user_id]
    assert stored["email"] is None
    assert stored["default_timezone"] is None


def test_edit_user_rejects_unknown_timezone(admin_client, fake_firestore):
    user_id = _seed_user(fake_firestore)
    _login(admin_client)
    response = admin_client.post(
        f"/admin/users/{user_id}/edit",
        data={
            "primary_name": "Jonathan",
            "email": "",
            "default_timezone": "Mars/Olympus_Mons",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "Unknown timezone" in response.text
    # Nothing persisted
    assert fake_firestore.users[user_id].get("default_timezone") is None


def test_edit_user_rejects_blank_name(admin_client, fake_firestore):
    user_id = _seed_user(fake_firestore)
    _login(admin_client)
    response = admin_client.post(
        f"/admin/users/{user_id}/edit",
        data={"primary_name": "   ", "email": "", "default_timezone": ""},
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "Primary name is required" in response.text
    assert fake_firestore.users[user_id]["primary_name"] == "Jonathan"


def test_edit_missing_user_404s(admin_client):
    _login(admin_client)
    response = admin_client.get("/admin/users/ghost/edit")
    assert response.status_code == 404
