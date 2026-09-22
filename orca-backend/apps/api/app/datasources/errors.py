# Typed errors for the marine data acquisition layer.
class SourceError(Exception):
    """Base error for marine data source failures."""


class SourceNotConfiguredError(SourceError):
    """Raised when a source profile has no credentials/endpoint configured.

    This is a permanent, explicit failure - NEVER fall back to mock data.
    """


class SourceUnavailableError(SourceError):
    """Upstream fetch failure (transport, HTTP 5xx, HTTP 4xx, ...)."""

    def __init__(self, message: str, transient: bool = True):
        # transient=True      retryable (timeout, 5xx, connection errors)
        # transient=False     permanent (404/410, rejected request)
        super().__init__(message)
        self.transient = transient


class SourceRateLimitError(SourceError):
    """Upstream responded HTTP 429 (may carry Retry-After)."""

    def __init__(self, message: str, retry_after: float = 2.0):
        super().__init__(message)
        self.retry_after = retry_after


class SourceInvalidDataError(SourceError):
    """Payload could not be parsed or does not match the expected contract."""