#!/usr/bin/env python3
"""Test Sentry integration."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from ygo_combo.sentry_config import init_sentry, capture_message, capture_exception


def main():
    print("Testing Sentry integration...")

    if init_sentry():
        print("Sentry initialized successfully")
    else:
        print("ERROR: SENTRY_DSN not found in environment")
        sys.exit(1)

    # Send test message
    print("Sending test message...")
    capture_message("Test from YGO Combo Pipeline", level="info")
    print("Test message sent")

    # Trigger test exception
    print("Triggering test exception...")
    try:
        1 / 0
    except ZeroDivisionError as e:
        capture_exception(e)
        print("Test exception captured")

    print("\nSentry test complete! Check your Sentry dashboard for:")
    print("  - Message: 'Test from YGO Combo Pipeline'")
    print("  - Exception: ZeroDivisionError")


if __name__ == "__main__":
    main()
