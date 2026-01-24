#!/usr/bin/env python3
"""
Smoke test for edo9300 ygopro-core API.
Tests that the library loads and all expected symbols are available.
"""

import ctypes
from pathlib import Path


def main():
    # Load the library
    lib_path = Path(__file__).parent / "libygo.dylib"

    if not lib_path.exists():
        print(f"❌ Library not found: {lib_path}")
        return False

    try:
        lib = ctypes.CDLL(str(lib_path))
        print(f"✅ Library loaded: {lib_path}")
    except OSError as e:
        print(f"❌ Failed to load library: {e}")
        return False

    # Check for edo9300 API functions (from ocgapi.h)
    required_functions = [
        # Core info
        "OCG_GetVersion",
        # Duel creation/destruction
        "OCG_CreateDuel",
        "OCG_DestroyDuel",
        "OCG_DuelNewCard",
        "OCG_StartDuel",
        # Duel processing
        "OCG_DuelProcess",
        "OCG_DuelGetMessage",
        "OCG_DuelSetResponse",
        "OCG_LoadScript",
        # Querying
        "OCG_DuelQueryCount",
        "OCG_DuelQuery",
        "OCG_DuelQueryLocation",
        "OCG_DuelQueryField",
    ]

    print("\nChecking API functions:")
    missing = []
    found = []

    for func_name in required_functions:
        try:
            func = getattr(lib, func_name)
            print(f"  ✅ {func_name}")
            found.append(func_name)
        except AttributeError:
            print(f"  ❌ {func_name} - NOT FOUND")
            missing.append(func_name)

    print(f"\n{'='*50}")
    print(f"Found: {len(found)}/{len(required_functions)} functions")

    if missing:
        print(f"❌ Missing {len(missing)} functions: {missing}")
        return False

    # Quick functional test: Get version
    print("\n" + "="*50)
    print("Functional tests:")

    try:
        major = ctypes.c_int()
        minor = ctypes.c_int()
        lib.OCG_GetVersion(ctypes.byref(major), ctypes.byref(minor))
        print(f"  ✅ OCG_GetVersion: {major.value}.{minor.value}")
    except Exception as e:
        print(f"  ❌ OCG_GetVersion failed: {e}")
        return False

    print("\n" + "="*50)
    print("✅ All smoke tests passed!")
    return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
