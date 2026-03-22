"""API v1 routes aggregation."""
from fastapi import APIRouter

from app.api.v1 import slack_events, scheduled_jobs

router = APIRouter()

# Include all v1 endpoints
router.include_router(slack_events.router)
router.include_router(scheduled_jobs.router)
