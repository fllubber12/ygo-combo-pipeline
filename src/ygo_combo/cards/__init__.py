"""
Card-specific logic for combo enumeration.

This module provides:
- Card role classification (roles.py)
- Card validation (validator.py)
- Card verification utilities (verification.py)
"""

from .roles import (
    CardRole,
    CardClassification,
    ActionWithRole,
    CardRoleClassifier,
)

from .validator import (
    CardNotVerifiedError,
    CardValidationError,
    CardValidator,
)

__all__ = [
    # Roles
    'CardRole',
    'CardClassification',
    'ActionWithRole',
    'CardRoleClassifier',
    # Validator
    'CardNotVerifiedError',
    'CardValidationError',
    'CardValidator',
]
