"""API v1 routes aggregation."""
from fastapi import APIRouter

from app.api.v1 import slack_events

router = APIRouter()

# Include all v1 endpoints
router.include_router(slack_events.router)
