#!/usr/bin/env python3
"""
Diagnostic script to trace Lua script loading issue.

This script creates a minimal duel and traces exactly what happens
when card scripts are loaded via the py_script_reader callback.
"""

import sys
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global counter to track callback invocations
callback_count = 0
loaded_scripts = []
ocg_errors = []
ocg_logs = []

def main():
    """Run diagnostic tests."""
    global callback_count, loaded_scripts

    logger.info("=" * 60)
    logger.info("DIAGNOSTIC: Lua Script Loading Issue")
    logger.info("=" * 60)

    # Import engine modules
    from ygo_combo.engine.bindings import ffi, load_library, LOCATION_HAND, LOCATION_DECK, POS_FACEUP_ATTACK
    from ygo_combo.engine.interface import (
        init_card_database, close_card_database, get_scripts_path,
        py_card_reader, py_card_reader_done, set_lib
    )

    # Create a diagnostic log handler that captures all messages
    @ffi.callback("void(void*, const char*, int)")
    def diagnostic_log_handler(payload, string, log_type):
        global ocg_errors, ocg_logs
        msg = ffi.string(string).decode("utf-8") if string != ffi.NULL else ""
        log_types = {0: "ERROR", 1: "SCRIPT", 2: "DEBUG", 3: "UNDEFINED"}
        type_name = log_types.get(log_type, f"UNKNOWN({log_type})")

        full_msg = f"[OCG {type_name}] {msg}"
        ocg_logs.append(full_msg)

        if log_type == 0:  # ERROR
            ocg_errors.append(msg)
            logger.error(full_msg)
        else:
            logger.debug(full_msg)

    # Load the library
    logger.info("Step 1: Loading libocgcore...")
    lib = load_library()
    set_lib(lib)

    # Get version
    major = ffi.new("int*")
    minor = ffi.new("int*")
    lib.OCG_GetVersion(major, minor)
    logger.info(f"  OCG version: {major[0]}.{minor[0]}")

    # Initialize card database
    logger.info("Step 2: Initializing card database...")
    if not init_card_database():
        logger.error("  Failed to initialize card database!")
        return
    logger.info("  Card database initialized")

    # Get scripts path
    script_path = get_scripts_path()
    logger.info(f"Step 3: Script path = {script_path}")

    # Create a DIAGNOSTIC script reader that logs everything
    @ffi.callback("int(void*, OCG_Duel, const char*)")
    def diagnostic_script_reader(payload, duel, name):
        """Diagnostic script reader with detailed logging."""
        global callback_count, loaded_scripts
        callback_count += 1

        script_name = ffi.string(name).decode("utf-8")
        logger.info(f"  [CALLBACK #{callback_count}] Script requested: {script_name}")

        # Search for the script
        search_paths = [
            script_path / "official" / script_name,
            script_path / "official" / f"{script_name}.lua",
            script_path / script_name,
            script_path / f"{script_name}.lua",
        ]

        script_file = None
        for p in search_paths:
            if p.exists():
                script_file = p
                break

        if script_file is None:
            logger.warning(f"    Script not found in any search path")
            return 0

        logger.info(f"    Found: {script_file}")

        # Read content
        try:
            content = script_file.read_bytes()
            logger.info(f"    Size: {len(content)} bytes")

            # Show first few lines for card scripts
            if script_name.startswith("c") and script_name.endswith(".lua"):
                lines = content.decode('utf-8', errors='replace').split('\n')[:5]
                logger.info(f"    First lines:")
                for i, line in enumerate(lines, 1):
                    logger.info(f"      {i}: {line[:80]}")

            # Call OCG_LoadScript
            logger.info(f"    Calling OCG_LoadScript...")
            result = lib.OCG_LoadScript(duel, content, len(content), name)
            logger.info(f"    OCG_LoadScript returned: {result}")

            if result == 1:
                loaded_scripts.append(script_name)
                return 1
            else:
                logger.error(f"    FAILED to load {script_name}")
                return 0

        except Exception as e:
            logger.exception(f"    Exception loading {script_name}: {e}")
            return 0

    # Create duel options
    logger.info("Step 4: Creating duel...")
    options = ffi.new("OCG_DuelOptions*")
    options.seed[0] = 12345
    options.seed[1] = 67890
    options.seed[2] = 11111
    options.seed[3] = 22222
    options.flags = (5 << 16)  # MR5
    options.team1.startingLP = 8000
    options.team1.startingDrawCount = 0
    options.team1.drawCountPerTurn = 0
    options.team2.startingLP = 8000
    options.team2.startingDrawCount = 0
    options.team2.drawCountPerTurn = 0
    options.cardReader = py_card_reader
    options.scriptReader = diagnostic_script_reader
    options.logHandler = diagnostic_log_handler
    options.cardReaderDone = py_card_reader_done

    duel_ptr = ffi.new("OCG_Duel*")
    result = lib.OCG_CreateDuel(duel_ptr, options)

    if result != 0:
        logger.error(f"  Failed to create duel: {result}")
        return

    duel = duel_ptr[0]
    logger.info(f"  Duel created successfully")

    # Pre-load utility scripts manually
    logger.info("Step 5: Pre-loading utility scripts...")
    utility_scripts = ["constant.lua", "utility.lua"]

    for script_name in utility_scripts:
        full_path = script_path / script_name
        if full_path.exists():
            content = full_path.read_bytes()
            result = lib.OCG_LoadScript(duel, content, len(content), script_name.encode())
            logger.info(f"  {script_name}: {'OK' if result == 1 else 'FAILED'}")
        else:
            logger.warning(f"  {script_name}: NOT FOUND")

    # Now add a single card and see what happens
    logger.info("Step 6: Adding a card (this should trigger py_script_reader for the card script)...")

    callback_count = 0  # Reset counter
    loaded_scripts = []

    card_info = ffi.new("OCG_NewCardInfo*")
    card_info.team = 0
    card_info.duelist = 0
    card_info.code = 60764609  # Fiendsmith Engraver
    card_info.con = 0
    card_info.loc = LOCATION_HAND
    card_info.seq = 0
    card_info.pos = POS_FACEUP_ATTACK

    logger.info(f"  Calling OCG_DuelNewCard for card code {card_info.code}...")
    lib.OCG_DuelNewCard(duel, card_info)

    logger.info(f"  Card added. Callback was invoked {callback_count} time(s).")
    logger.info(f"  Scripts loaded: {loaded_scripts}")

    # Step 7: Start the duel and process to see if card effects work
    logger.info("Step 7: Starting duel and processing messages...")
    lib.OCG_StartDuel(duel)

    # Process a few times
    for i in range(3):
        status = lib.OCG_DuelProcess(duel)
        logger.info(f"  Process #{i+1}: status = {status}")

        # Get messages
        msg_len = ffi.new("uint32_t*")
        msg_ptr = lib.OCG_DuelGetMessage(duel, msg_len)

        if msg_len[0] > 0:
            logger.info(f"    Message length: {msg_len[0]} bytes")
        else:
            logger.info(f"    No messages")

        if status == 0:  # OCG_DUEL_STATUS_END
            logger.info("  Duel ended")
            break

    # Summary
    logger.info("=" * 60)
    logger.info("DIAGNOSTIC SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total callback invocations: {callback_count}")
    logger.info(f"Scripts loaded via callback: {loaded_scripts}")
    logger.info(f"Total OCG logs: {len(ocg_logs)}")
    logger.info(f"OCG errors: {len(ocg_errors)}")

    if ocg_errors:
        logger.error("=" * 60)
        logger.error("OCG ERRORS:")
        logger.error("=" * 60)
        for err in ocg_errors:
            logger.error(f"  {err}")

    # Cleanup
    logger.info("Cleaning up...")
    lib.OCG_DestroyDuel(duel)
    close_card_database()

    logger.info("Done.")


if __name__ == "__main__":
    main()
