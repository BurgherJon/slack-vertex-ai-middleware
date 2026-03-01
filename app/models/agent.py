"""Agent configuration model."""
from typing import Optional
from pydantic import BaseModel, Field


class Agent(BaseModel):
    """
    Agent configuration stored in Firestore.

    Represents a Slack bot and its corresponding Vertex AI agent.
    """

    id: Optional[str] = Field(default=None, description="Firestore document ID")
    slack_bot_token: str = Field(..., description="Slack Bot User OAuth Token (xoxb-...)")
    slack_bot_id: str = Field(..., description="Slack bot user ID (B...)")
    vertex_ai_agent_id: str = Field(..., description="Vertex AI agent resource name")
    display_name: str = Field(..., description="Human-readable agent name")

    model_config = {"frozen": True}  # Immutable after creation
