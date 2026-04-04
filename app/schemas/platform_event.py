"""Platform-agnostic event models for unified message processing."""
from typing import Optional, Any
from pydantic import BaseModel, Field


class PlatformEvent(BaseModel):
    """
    Unified event model that abstracts platform-specific message events.

    This model normalizes events from different platforms (Slack, Google Chat, etc.)
    into a common format for processing.
    """
    platform: str = Field(
        ...,
        description="Platform name (slack, google_chat)"
    )
    user_id: str = Field(
        ...,
        description="Platform-specific user identifier"
    )
    user_email: Optional[str] = Field(
        default=None,
        description="User's email (if available, used for auto-linking)"
    )
    message_text: str = Field(
        ...,
        description="Message text content"
    )
    space_id: str = Field(
        ...,
        description="Conversation/channel/space identifier"
    )
    files: list[dict[str, Any]] = Field(
        default_factory=list,
        description="File attachments in platform-specific format"
    )
    raw_event: dict[str, Any] = Field(
        ...,
        description="Original platform event data for reference"
    )

    model_config = {"frozen": True}  # Immutable after creation
