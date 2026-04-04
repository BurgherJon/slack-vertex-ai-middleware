"""API v1 routes aggregation."""
from fastapi import APIRouter

from app.api.v1 import slack_events_v2, scheduled_jobs

router = APIRouter()

# Include all v1 endpoints
router.include_router(slack_events_v2.router)  # Using v2 (multi-platform architecture)
router.include_router(scheduled_jobs.router)
