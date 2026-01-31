"""Sentry error monitoring configuration."""

import os
import sentry_sdk
from dotenv import load_dotenv


def init_sentry() -> bool:
    """Initialize Sentry error monitoring.

    Returns:
        True if Sentry was initialized, False if DSN not configured.
    """
    load_dotenv()

    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        return False

    environment = os.getenv("ENVIRONMENT", "development")

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        send_default_pii=True,
        traces_sample_rate=0.1,
        attach_stacktrace=True,
    )

    return True


def capture_exception(exception: Exception = None):
    """Capture an exception and send to Sentry.

    Args:
        exception: The exception to capture. If None, captures the current exception.
    """
    sentry_sdk.capture_exception(exception)


def capture_message(message: str, level: str = "info"):
    """Send a message to Sentry.

    Args:
        message: The message to send.
        level: Log level (debug, info, warning, error, fatal).
    """
    sentry_sdk.capture_message(message, level=level)
