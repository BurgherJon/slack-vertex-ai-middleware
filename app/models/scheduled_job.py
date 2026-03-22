"""Scheduled job configuration model."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ScheduledJob(BaseModel):
    """
    Scheduled job configuration stored in Firestore.

    Represents a recurring job that sends a prompt to a Vertex AI agent
    and delivers the response to a Slack user.
    """

    id: Optional[str] = Field(default=None, description="Firestore document ID")
    name: str = Field(..., description="Human-readable job name")
    prompt: str = Field(..., description="Prompt to send to the agent")
    agent_id: str = Field(..., description="Agent ID from agents collection")
    slack_user_id: str = Field(..., description="Slack user ID to receive responses (U...)")

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

    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")

    model_config = {"frozen": False}  # Mutable for updates
