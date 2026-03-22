"""FastAPI dependencies for dependency injection."""
from fastapi import Request

from app.services.message_processor import MessageProcessor
from app.services.firestore_service import FirestoreService
from app.services.vertex_ai_service import VertexAIService
from app.services.slack_service import SlackService
from app.services.scheduled_job_service import ScheduledJobService
from app.services.scheduled_job_executor import ScheduledJobExecutor


def get_message_processor(request: Request) -> MessageProcessor:
    """
    Get MessageProcessor instance from app state.

    Args:
        request: FastAPI request object

    Returns:
        MessageProcessor instance
    """
    return MessageProcessor(
        firestore=request.app.state.firestore,
        vertex_ai=request.app.state.vertex_ai,
        slack=request.app.state.slack,
    )


def get_firestore_service(request: Request) -> FirestoreService:
    """
    Get FirestoreService instance from app state.

    Args:
        request: FastAPI request object

    Returns:
        FirestoreService instance
    """
    return request.app.state.firestore


def get_vertex_ai_service(request: Request) -> VertexAIService:
    """
    Get VertexAIService instance from app state.

    Args:
        request: FastAPI request object

    Returns:
        VertexAIService instance
    """
    return request.app.state.vertex_ai


def get_slack_service(request: Request) -> SlackService:
    """
    Get SlackService instance from app state.

    Args:
        request: FastAPI request object

    Returns:
        SlackService instance
    """
    return request.app.state.slack


def get_scheduled_job_service(request: Request) -> ScheduledJobService:
    """
    Get ScheduledJobService instance from app state.

    Args:
        request: FastAPI request object

    Returns:
        ScheduledJobService instance
    """
    return request.app.state.scheduled_job_service


def get_scheduled_job_executor(request: Request) -> ScheduledJobExecutor:
    """
    Get ScheduledJobExecutor instance.

    Args:
        request: FastAPI request object

    Returns:
        ScheduledJobExecutor instance
    """
    return ScheduledJobExecutor(
        firestore=request.app.state.firestore,
        vertex_ai=request.app.state.vertex_ai,
        slack=request.app.state.slack,
    )
