"""Session mapping model."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class Session(BaseModel):
    """
    Session mapping stored in Firestore.

    Maps a (Slack user + agent) combination to a Vertex AI session.
    Document ID format: {slack_user_id}_{agent_id}
    """

    id: Optional[str] = Field(default=None, description="Firestore document ID")
    slack_user_id: str = Field(..., description="Slack user ID (U...)")
    agent_id: str = Field(..., description="Agent ID from agents collection")
    vertex_ai_session_id: str = Field(..., description="Vertex AI session ID")
    created_at: datetime = Field(..., description="Session creation timestamp")
    last_activity_at: datetime = Field(..., description="Last message timestamp")

    model_config = {"frozen": True}  # Immutable after creation
