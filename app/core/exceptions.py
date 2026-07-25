# Copyright (C) 2025 Comites.ai
# SPDX-License-Identifier: AGPL-3.0-only

"""Custom exceptions for the middleware."""


class MiddlewareException(Exception):
    """Base exception for middleware errors."""

    pass


class AgentNotFoundError(MiddlewareException):
    """Agent configuration not found in Firestore."""

    pass


class SessionError(MiddlewareException):
    """Error creating or retrieving session."""

    pass


class VertexAIError(MiddlewareException):
    """Error communicating with Vertex AI."""

    pass


class SlackAPIError(MiddlewareException):
    """Error communicating with Slack API."""

    pass


class ResourceExhaustedError(MiddlewareException):
    """Google API rate limit exceeded (429 RESOURCE_EXHAUSTED)."""

    pass


class FileDownloadError(MiddlewareException):
    """Failed to download a user-uploaded file from the source platform."""

    pass


class FileTooLargeError(MiddlewareException):
    """User-uploaded file exceeds the configured size limit."""

    pass


class UnsupportedImageTypeError(MiddlewareException):
    """User-uploaded image MIME type is not in the configured allowlist."""

    pass


class GcsUploadError(MiddlewareException):
    """Failed to upload a file to Google Cloud Storage."""

    pass


class AgentStreamError(MiddlewareException):
    """Vertex AI streaming response broke mid-flight (not a clean empty result)."""

    pass


class ScheduledJobReadError(MiddlewareException):
    """
    Could not read the scheduled_jobs collection completely.

    Distinct from "no jobs matched". Callers that decide whether to *write*
    based on a read (the create_job upsert lookup) must fail closed on this
    rather than treating an unreadable collection as an empty one — that
    conflation is what let duplicate jobs accumulate (#14).
    """

    pass


class DuplicateScheduledJobError(MiddlewareException):
    """
    A scheduled job with the same (agent_id, user_id, name) identity exists.

    Raised by the write-time uniqueness guard, which is deliberately the last
    line of defense: it re-checks at insert time without parsing any stored
    document, so it still holds when a malformed document would defeat the
    model-level lookup.
    """

    pass
