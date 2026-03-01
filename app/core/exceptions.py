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
