#!/usr/bin/env python3
"""
Centralized path definitions for ygo-combo-pipeline.

All file paths should be imported from this module to ensure consistency
across the codebase.
"""

import os
from pathlib import Path

# =============================================================================
# PROJECT ROOT
# =============================================================================

# Project root is two directories up from src/cffi/
PROJECT_ROOT = Path(__file__).parents[2]

# =============================================================================
# CONFIGURATION FILES
# =============================================================================

CONFIG_DIR = PROJECT_ROOT / "config"
LOCKED_LIBRARY_PATH = CONFIG_DIR / "locked_library.json"
EVALUATION_CONFIG_PATH = CONFIG_DIR / "evaluation_config.json"

# =============================================================================
# DATA FILES
# =============================================================================

# Card database (sqlite)
CDB_PATH = PROJECT_ROOT / "cards.cdb"

# =============================================================================
# BUILD ARTIFACTS
# =============================================================================

BUILD_DIR = Path(__file__).parent / "build"


def get_library_path() -> Path:
    """Get platform-appropriate path to libygo shared library."""
    import platform
    system = platform.system()
    if system == "Darwin":
        ext = ".dylib"
    elif system == "Windows":
        ext = ".dll"
    else:
        ext = ".so"
    return BUILD_DIR / f"libygo{ext}"


# =============================================================================
# SCRIPT PATHS
# =============================================================================

def get_scripts_path() -> Path:
    """Get ygopro-core scripts directory from environment or default.

    Set YGOPRO_SCRIPTS_PATH environment variable to override.
    """
    env_path = os.environ.get("YGOPRO_SCRIPTS_PATH")
    if env_path:
        return Path(env_path)
    # Default fallback
    return Path("/tmp/ygopro-scripts")


def verify_scripts_path() -> bool:
    """Check if scripts directory exists and contains expected files.

    Returns True if valid, raises FileNotFoundError with helpful message if not.
    """
    scripts_path = get_scripts_path()
    if not scripts_path.exists():
        raise FileNotFoundError(
            f"ygopro-core scripts directory not found: {scripts_path}\n"
            f"Set YGOPRO_SCRIPTS_PATH environment variable to the correct location.\n"
            f"Example: export YGOPRO_SCRIPTS_PATH=/path/to/ygopro-core/script"
        )

    # Check for expected utility files
    utility_lua = scripts_path / "utility.lua"
    if not utility_lua.exists():
        raise FileNotFoundError(
            f"utility.lua not found in scripts directory: {scripts_path}\n"
            f"Ensure YGOPRO_SCRIPTS_PATH points to a valid ygopro-core script directory."
        )

    return True


# =============================================================================
# OUTPUT PATHS
# =============================================================================

REPORTS_DIR = PROJECT_ROOT / "reports"
HANDOFFS_DIR = PROJECT_ROOT / "handoffs"


if __name__ == "__main__":
    # Quick test of path resolution
    print(f"PROJECT_ROOT: {PROJECT_ROOT}")
    print(f"CDB_PATH: {CDB_PATH} (exists: {CDB_PATH.exists()})")
    print(f"LOCKED_LIBRARY_PATH: {LOCKED_LIBRARY_PATH} (exists: {LOCKED_LIBRARY_PATH.exists()})")
    print(f"Library path: {get_library_path()} (exists: {get_library_path().exists()})")
    print(f"Scripts path: {get_scripts_path()}")
