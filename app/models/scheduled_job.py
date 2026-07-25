# Copyright (C) 2025 Comites.ai
# SPDX-License-Identifier: AGPL-3.0-only

"""Scheduled job configuration model."""
import logging
from datetime import datetime, UTC
from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)


def normalize_job_name(name: Optional[str]) -> str:
    """
    Identity key used for upsert dedup: trimmed + case-folded.

    Returns "" for a missing/blank name. An empty result is never a valid
    identity — see job_identity_key.
    """
    if not name:
        return ""
    return name.strip().casefold()


def job_identity_key(agent_id: str, user_id: str, name: Optional[str]) -> Optional[str]:
    """
    Stable identity for a scheduled job: (agent_id, user_id, normalized name).

    Stored on the document so the write-time uniqueness guard can match on a
    plain equality query, without deserializing candidate documents into
    ScheduledJob. Returns None when any component is missing, meaning "this
    job has no enforceable identity" — such jobs are never dedup candidates.
    """
    normalized = normalize_job_name(name)
    if not agent_id or not user_id or not normalized:
        return None
    return f"{agent_id}|{user_id}|{normalized}"


class ScheduledJob(BaseModel):
    """
    Scheduled job configuration stored in Firestore.

    Represents a recurring job that sends a prompt to a Vertex AI agent
    and delivers the response to a user on any platform (Slack, Google Chat,
    Telegram, Discord).
    """

    id: Optional[str] = Field(default=None, description="Firestore document ID")
    # Defaulted rather than required: a single document with name: null used
    # to raise ValidationError here, which the caller turned into "no jobs
    # exist" and then into duplicate inserts (#14). A nameless job
    # now parses so it stays visible and manageable; normalize_job_name()
    # renders it "" so it can never match an upsert target.
    name: str = Field(default="", description="Human-readable job name")
    prompt: str = Field(..., description="Prompt to send to the agent")
    agent_id: str = Field(..., description="Agent ID from agents collection")

    # Multi-platform fields
    user_id: str = Field(..., description="Unified user ID from users collection")
    output_platform: str = Field(
        default="slack",
        description="Platform to deliver responses to (slack, google_chat, telegram, discord)"
    )

    schedule: str = Field(..., description="Cron expression (e.g., '0 9 * * 1-5')")
    timezone: str = Field(default="UTC", description="IANA timezone (e.g., 'America/New_York')")

    enabled: bool = Field(default=True, description="Whether job is active")
    cloud_scheduler_job_name: Optional[str] = Field(
        default=None, description="Full Cloud Scheduler job resource name"
    )

    last_execution_at: Optional[datetime] = Field(
        default=None, description="Last successful execution timestamp"
    )
    last_execution_id: Optional[str] = Field(
        default=None, description="Unique ID of last execution attempt"
    )
    execution_started_at: Optional[datetime] = Field(
        default=None, description="Execution lock timestamp (set when job starts)"
    )
    last_error: Optional[str] = Field(
        default=None, description="Last error message if execution failed"
    )
    consecutive_failures: int = Field(
        default=0, description="Number of consecutive failed executions"
    )

    retry_at: Optional[datetime] = Field(
        default=None, description="One-time retry scheduled for this datetime"
    )
    retry_reason: Optional[str] = Field(
        default=None, description="Reason for scheduling a retry (e.g., 'rate_limit_429')"
    )

    identity_key: Optional[str] = Field(
        default=None,
        description="agent_id|user_id|normalized name; backs the write-time uniqueness guard",
    )

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Creation timestamp")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Last update timestamp")

    model_config = {"frozen": False}  # Mutable for updates

    @field_validator("name", mode="before")
    @classmethod
    def _tolerate_missing_name(cls, value):
        """
        Coerce a null/absent name to "" instead of failing the whole document.

        Logged at WARNING so the malformed document is discoverable rather
        than silently normalized.
        """
        if value is None:
            logger.warning(
                "Scheduled job document has a null name; coercing to empty string"
            )
            return ""
        return value
