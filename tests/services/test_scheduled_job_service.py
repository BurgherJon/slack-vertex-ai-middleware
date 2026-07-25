# Copyright (C) 2025 Comites.ai
# SPDX-License-Identifier: AGPL-3.0-only

"""ScheduledJobService tests against the fake firestore."""
from datetime import datetime, timedelta, UTC

import pytest

from app.core.exceptions import DuplicateScheduledJobError, ScheduledJobReadError
from app.models.agent import Agent
from app.schemas.scheduled_job import ScheduledJobCreate, ScheduledJobUpdate
from app.services.scheduled_job_service import ScheduledJobService


@pytest.fixture
def agent_id_in_firestore(fake_firestore) -> str:
    agent = Agent(vertex_ai_agent_id="re-1", display_name="Agent")
    return fake_firestore.add_agent(agent, agent_id="agent-1")


@pytest.fixture
def service(fake_firestore) -> ScheduledJobService:
    return ScheduledJobService(firestore=fake_firestore)


def _make_create(**overrides) -> ScheduledJobCreate:
    base = dict(
        name="morning brief",
        prompt="summarize",
        agent_id="agent-1",
        user_id="user-1",
        output_platform="slack",
        schedule="0 9 * * 1-5",
        timezone="UTC",
        enabled=True,
    )
    base.update(overrides)
    return ScheduledJobCreate(**base)


# ---- validation ----


def test_validate_cron_accepts_valid(service):
    assert service._validate_cron_expression("0 9 * * 1-5") is True


def test_validate_cron_rejects_invalid(service):
    assert service._validate_cron_expression("not a cron") is False


# ---- create_job ----


async def test_create_job_persists_and_returns(service, agent_id_in_firestore):
    job = await service.create_job(_make_create())
    assert job.id is not None
    assert job.name == "morning brief"


async def test_create_job_rejects_invalid_cron(service, agent_id_in_firestore):
    with pytest.raises(ValueError, match="Invalid cron"):
        await service.create_job(_make_create(schedule="not a cron"))


async def test_create_job_rejects_invalid_timezone(service, agent_id_in_firestore):
    with pytest.raises(ValueError, match="Invalid timezone"):
        await service.create_job(_make_create(timezone="Mars/Olympus_Mons"))


async def test_create_job_rejects_unknown_agent(service):
    with pytest.raises(ValueError, match="Agent not found"):
        await service.create_job(_make_create(agent_id="ghost"))


# ---- list / get / delete / update ----


async def test_list_jobs_filters_by_user(service, agent_id_in_firestore):
    await service.create_job(_make_create(name="job-a", user_id="user-1"))
    await service.create_job(_make_create(name="job-b", user_id="user-2"))
    user1_jobs = await service.list_jobs(user_id="user-1")
    assert {j.name for j in user1_jobs} == {"job-a"}


async def test_get_job_returns_none_when_missing(service):
    assert await service.get_job("nonexistent") is None


async def test_delete_job_removes_it(service, agent_id_in_firestore):
    job = await service.create_job(_make_create())
    assert await service.delete_job(job.id) is True
    assert await service.get_job(job.id) is None


async def test_delete_job_returns_false_when_missing(service):
    assert await service.delete_job("nonexistent") is False


async def test_update_job_changes_fields(service, agent_id_in_firestore):
    job = await service.create_job(_make_create())
    updated = await service.update_job(
        job.id, ScheduledJobUpdate(enabled=False, name="renamed")
    )
    assert updated.enabled is False
    assert updated.name == "renamed"


async def test_update_job_returns_none_when_missing(service):
    assert await service.update_job("nope", ScheduledJobUpdate(enabled=False)) is None


# ---- idempotent upsert (the-forum#8) ----


async def test_create_job_is_idempotent_on_identity(service, agent_id_in_firestore):
    first = await service.create_job(_make_create(name="morning check-in"))
    second = await service.create_job(
        _make_create(name="morning check-in", prompt="updated prompt", schedule="0 8 * * *")
    )
    # Same job, updated in place — not a duplicate.
    assert second.id == first.id
    assert second.prompt == "updated prompt"
    assert second.schedule == "0 8 * * *"
    all_jobs = await service.list_jobs(agent_id="agent-1", user_id="user-1")
    assert len(all_jobs) == 1


async def test_upsert_identity_is_case_and_whitespace_insensitive(service, agent_id_in_firestore):
    first = await service.create_job(_make_create(name="Morning Check-In"))
    second = await service.create_job(_make_create(name="  morning check-in  "))
    assert second.id == first.id
    assert len(await service.list_jobs(agent_id="agent-1", user_id="user-1")) == 1


async def test_upsert_reenables_a_paused_job(service, agent_id_in_firestore):
    job = await service.create_job(_make_create(name="daily"))
    await service.update_job(job.id, ScheduledJobUpdate(enabled=False))
    revived = await service.create_job(_make_create(name="daily"))
    assert revived.id == job.id
    assert revived.enabled is True


async def test_upsert_scopes_identity_by_user_and_agent(service, agent_id_in_firestore):
    # Same name, different user => distinct jobs.
    await service.create_job(_make_create(name="check-in", user_id="user-1"))
    await service.create_job(_make_create(name="check-in", user_id="user-2"))
    assert len(await service.list_jobs(user_id="user-1")) == 1
    assert len(await service.list_jobs(user_id="user-2")) == 1


# ---- read failures must not defeat the upsert (#14) ----


def _poison_doc(**overrides) -> dict:
    """
    A stored document that ScheduledJob cannot parse.

    Uses a null prompt rather than a null name: name is now coerced (see
    test_null_name_document_does_not_hide_sibling_jobs), so prompt is what
    still produces the ValidationError this bug hinged on.
    """
    data = dict(
        name="poison",
        prompt=None,
        agent_id="agent-1",
        user_id="user-1",
        schedule="0 3 * * *",
        enabled=True,
    )
    data.update(overrides)
    return data


async def test_null_name_document_does_not_hide_sibling_jobs(
    service, fake_firestore, agent_id_in_firestore
):
    """The original incident: one name:null doc blanked the whole list."""
    existing = await service.create_job(_make_create(name="morning-readiness-check"))
    fake_firestore.scheduled_jobs["poison"] = {
        "name": None,
        "prompt": "whatever",
        "agent_id": "agent-1",
        "user_id": "user-1",
        "schedule": "0 3 * * *",
        "enabled": True,
    }

    # The re-create must still find the existing job and update it in place.
    again = await service.create_job(
        _make_create(name="morning-readiness-check", prompt="updated")
    )

    assert again.id == existing.id, "upsert inserted a duplicate instead of updating"
    real_jobs = [
        j
        for j in await service.list_jobs(agent_id="agent-1", user_id="user-1")
        if j.id != "poison"
    ]
    assert len(real_jobs) == 1


async def test_nameless_document_never_matches_an_upsert_target(
    service, fake_firestore, agent_id_in_firestore
):
    """A coerced empty name must not become a wildcard that swallows creates."""
    fake_firestore.scheduled_jobs["nameless"] = {
        "name": None,
        "prompt": "whatever",
        "agent_id": "agent-1",
        "user_id": "user-1",
        "schedule": "0 3 * * *",
        "enabled": True,
    }

    created = await service.create_job(_make_create(name="a real job"))

    assert created.id != "nameless"


async def test_create_fails_closed_when_a_document_cannot_be_parsed(
    service, fake_firestore, agent_id_in_firestore
):
    """
    An unparseable doc must not read as "no existing job".

    Skipping it silently is exactly how a duplicate gets inserted, so the
    upsert lookup refuses to answer from a partial list.
    """
    fake_firestore.scheduled_jobs["poison"] = _poison_doc()

    with pytest.raises(ScheduledJobReadError):
        await service.create_job(_make_create(name="morning brief"))

    # Nothing was written.
    assert set(fake_firestore.scheduled_jobs) == {"poison"}


async def test_create_fails_closed_when_the_query_fails(
    service, fake_firestore, agent_id_in_firestore
):
    """Permissions/transient/index failures must not read as an empty collection."""
    fake_firestore.scheduled_jobs_query_error = RuntimeError("firestore unavailable")

    with pytest.raises(RuntimeError, match="firestore unavailable"):
        await service.create_job(_make_create())

    assert fake_firestore.scheduled_jobs == {}


async def test_dispatcher_still_runs_other_jobs_despite_a_bad_document(
    service, fake_firestore, agent_id_in_firestore
):
    """
    The dispatcher takes the opposite trade-off from the upsert lookup.

    One unparseable document must not stop every other agent's jobs; it is
    skipped and logged rather than raising.
    """
    healthy = await service.create_job(
        _make_create(name="healthy", schedule="* * * * *")
    )
    # Backdate the last run so the cron is actually due this tick.
    fake_firestore.scheduled_jobs[healthy.id]["last_execution_at"] = datetime.now(
        UTC
    ) - timedelta(days=1)
    fake_firestore.scheduled_jobs["poison"] = _poison_doc()

    due = await service.get_due_jobs()

    assert [j.name for j in due] == ["healthy"]


async def test_blank_name_is_rejected(service, agent_id_in_firestore):
    """Whitespace passes the schema's min_length but has no dedup identity."""
    with pytest.raises(ValueError, match="blank"):
        await service.create_job(_make_create(name="   "))


# ---- write-time uniqueness guard ----


async def test_write_guard_blocks_a_duplicate_the_lookup_missed(
    service, fake_firestore, agent_id_in_firestore
):
    """
    Last line of defense: even if the lookup wrongly reports no match, the
    insert itself is refused. Simulated by bypassing the lookup entirely.
    """
    await service.create_job(_make_create(name="nightly"))

    with pytest.raises(DuplicateScheduledJobError):
        await fake_firestore.create_scheduled_job(
            {
                "name": "nightly",
                "prompt": "dupe",
                "agent_id": "agent-1",
                "user_id": "user-1",
                "schedule": "0 3 * * *",
                "enabled": True,
            }
        )


async def test_write_guard_matches_normalized_names(
    service, fake_firestore, agent_id_in_firestore
):
    await service.create_job(_make_create(name="Nightly Sync"))

    with pytest.raises(DuplicateScheduledJobError):
        await fake_firestore.create_scheduled_job(
            {
                "name": "  nightly sync  ",
                "prompt": "dupe",
                "agent_id": "agent-1",
                "user_id": "user-1",
                "schedule": "0 3 * * *",
                "enabled": True,
            }
        )


async def test_write_guard_scopes_identity_by_user(
    service, fake_firestore, agent_id_in_firestore
):
    await service.create_job(_make_create(name="check-in", user_id="user-1"))
    # Same name, different user — not a duplicate.
    other = await service.create_job(_make_create(name="check-in", user_id="user-2"))
    assert other.id is not None


async def test_rename_moves_the_identity_so_the_old_name_is_free(
    service, agent_id_in_firestore
):
    """
    A stale identity_key would both block a legitimate re-create of the old
    name and stop matching real duplicates of the new one.
    """
    job = await service.create_job(_make_create(name="old name"))
    await service.update_job(job.id, ScheduledJobUpdate(name="new name"))

    # Old name is free again...
    recreated = await service.create_job(_make_create(name="old name"))
    assert recreated.id != job.id

    # ...and the new name now dedups against the renamed job.
    again = await service.create_job(_make_create(name="new name"))
    assert again.id == job.id


async def test_cron_error_message_is_actionable(service, agent_id_in_firestore):
    with pytest.raises(ValueError, match="5-field"):
        await service.create_job(_make_create(schedule="not a cron"))


async def test_timezone_error_message_is_actionable(service, agent_id_in_firestore):
    with pytest.raises(ValueError, match="IANA"):
        await service.create_job(_make_create(timezone="Mars/Olympus_Mons"))
