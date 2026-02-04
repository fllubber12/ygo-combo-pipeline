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

# Project root is three directories up from src/ygo_combo/engine/
PROJECT_ROOT = Path(__file__).parents[3]

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

# Build directory is at src/ygo_combo/build/ (one level up from engine/)
BUILD_DIR = Path(__file__).parent.parent / "build"


def get_lib_extension() -> str:
    """Get platform-appropriate shared library extension.

    Returns:
        Library extension including the dot (.dylib, .dll, or .so).
    """
    import platform
    system = platform.system()
    if system == "Darwin":
        return ".dylib"
    elif system == "Windows":
        return ".dll"
    return ".so"  # Linux and others


def get_library_path() -> Path:
    """Get platform-appropriate path to libygo shared library."""
    return BUILD_DIR / f"libygo{get_lib_extension()}"


# =============================================================================
# SCRIPT PATHS
# =============================================================================

def get_scripts_path() -> Path:
    """Get ygopro-core scripts directory from environment or Windows fallback.

    Checks YGOPRO_SCRIPTS_PATH environment variable first.
    On Windows, falls back to known default location if env var not set
    (helps with multiprocessing workers that may not inherit env vars).

    Raises:
        EnvironmentError: If YGOPRO_SCRIPTS_PATH is not set and no fallback exists.
    """
    env_path = os.environ.get("YGOPRO_SCRIPTS_PATH")
    if env_path:
        return Path(env_path)

    # Windows fallback: check common location for this machine
    # This helps multiprocessing workers on Windows that may not inherit env vars
    import platform
    if platform.system() == "Windows":
        windows_fallback = Path(r"C:\Users\19259\edopro_temp\ProjectIgnis\script")
        if windows_fallback.exists():
            return windows_fallback

    raise EnvironmentError(
        "YGOPRO_SCRIPTS_PATH environment variable must be set.\n"
        "Example: export YGOPRO_SCRIPTS_PATH=/path/to/ygopro-core/script\n"
        "This should point to the directory containing utility.lua and card scripts."
    )


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
