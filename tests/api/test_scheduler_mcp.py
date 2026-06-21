# Copyright (C) 2025 Comites.ai
# SPDX-License-Identifier: AGPL-3.0-only

"""Scheduler MCP tool-handler tests.

These exercise the handlers directly by setting the per-request ContextVar
(the ASGI layer normally sets it after authenticating the X-API-Key). They
cover the two behaviors from the-forum#9 (unified user resolution so create
and list agree) and #8 (idempotent create), plus the pause/resume tools.
"""
import json

import pytest

from app.api.v1 import scheduler_mcp
from app.models.agent import Agent
from app.models.user import PlatformIdentity, User


@pytest.fixture
def agent(fake_firestore) -> Agent:
    a = Agent(vertex_ai_agent_id="re-1", display_name="Agent", id="agent-1")
    fake_firestore.add_agent(a, agent_id="agent-1")
    return a


@pytest.fixture
def request_ctx(fake_firestore, agent):
    """Bind the authenticated request context the handlers read from."""
    token = scheduler_mcp._request_ctx.set(
        {"agent": agent, "firestore": fake_firestore}
    )
    yield
    scheduler_mcp._request_ctx.reset(token)


async def _seed_user(fake_firestore) -> str:
    """A user whose Slack display name differs from primary_name."""
    return await fake_firestore.create_user(
        User(
            primary_name="Alice Smith",
            identities=[
                PlatformIdentity(
                    platform="slack", platform_user_id="U_001", display_name="alice.s"
                )
            ],
        )
    )


# ---- the-forum#9: create and list resolve to the same user ----


async def test_create_then_list_agree_via_display_name(fake_firestore, request_ctx):
    user_id = await _seed_user(fake_firestore)

    created = json.loads(
        await scheduler_mcp._handle_create(
            {
                "name": "morning check-in",
                "prompt": "what's up?",
                "schedule": "0 9 * * *",
                "user_name": "alice.s",  # platform display name, not primary_name
                "output_platform": "slack",
            }
        )
    )
    assert created["user_id"] == user_id

    listed = json.loads(
        await scheduler_mcp._handle_list({"user_name": "Alice Smith"})  # primary_name
    )
    # Resolving by a different alias still surfaces the same reminder.
    assert [j["id"] for j in listed] == [created["id"]]


async def test_list_unknown_user_raises_clear_error(fake_firestore, request_ctx):
    await _seed_user(fake_firestore)
    with pytest.raises(ValueError, match="No user found"):
        await scheduler_mcp._handle_list({"user_name": "Nobody"})


async def test_list_known_user_no_reminders_returns_empty(fake_firestore, request_ctx):
    await _seed_user(fake_firestore)
    listed = json.loads(await scheduler_mcp._handle_list({"user_name": "alice.s"}))
    assert listed == []


# ---- the-forum#8: create is idempotent through the MCP path ----


async def test_create_twice_yields_one_reminder(fake_firestore, request_ctx):
    await _seed_user(fake_firestore)
    args = {
        "name": "morning check-in",
        "prompt": "v1",
        "schedule": "0 9 * * *",
        "user_name": "alice.s",
        "output_platform": "slack",
    }
    first = json.loads(await scheduler_mcp._handle_create(args))
    second = json.loads(
        await scheduler_mcp._handle_create({**args, "prompt": "v2"})
    )
    assert second["id"] == first["id"]
    assert second["prompt"] == "v2"

    listed = json.loads(await scheduler_mcp._handle_list({"user_name": "alice.s"}))
    assert len(listed) == 1


# ---- pause / resume ----


async def test_pause_then_resume(fake_firestore, request_ctx):
    await _seed_user(fake_firestore)
    created = json.loads(
        await scheduler_mcp._handle_create(
            {
                "name": "daily",
                "prompt": "hi",
                "schedule": "0 9 * * *",
                "user_name": "alice.s",
                "output_platform": "slack",
            }
        )
    )
    job_id = created["id"]

    paused = json.loads(
        await scheduler_mcp._handle_set_enabled({"job_id": job_id}, enabled=False)
    )
    assert paused["enabled"] is False

    resumed = json.loads(
        await scheduler_mcp._handle_set_enabled({"job_id": job_id}, enabled=True)
    )
    assert resumed["enabled"] is True


async def test_pause_rejects_job_owned_by_another_agent(fake_firestore, request_ctx):
    # A job belonging to a different agent must not be pausable.
    other = await fake_firestore.create_scheduled_job(
        {
            "name": "x",
            "prompt": "x",
            "agent_id": "agent-2",
            "user_id": "user-x",
            "output_platform": "slack",
            "schedule": "0 9 * * *",
            "timezone": "UTC",
            "enabled": True,
        }
    )
    with pytest.raises(ValueError, match="not found"):
        await scheduler_mcp._handle_set_enabled({"job_id": other.id}, enabled=False)
