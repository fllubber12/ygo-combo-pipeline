#!/usr/bin/env python3
"""
Test creating a duel with the edo9300 OCG API.

This test validates that we can:
1. Set up callbacks for card data and script reading
2. Create a duel instance
3. Add cards to the duel
4. Start the duel
5. Process and destroy the duel
"""

import sqlite3
from pathlib import Path

from ocg_bindings import ffi, load_library, LOCATION_DECK, LOCATION_HAND, POS_FACEDOWN_DEFENSE


# Card database path
CDB_PATH = Path(__file__).parents[2] / "locale" / "en" / "cards.cdb"
SCRIPT_PATH = Path("/tmp/ygopro-scripts") if Path("/tmp/ygopro-scripts").exists() else None

# Global state for callbacks
_card_db = None
_script_cache = {}


def init_card_database():
    """Initialize the card database connection."""
    global _card_db
    if CDB_PATH.exists():
        _card_db = sqlite3.connect(str(CDB_PATH))
        _card_db.row_factory = sqlite3.Row
        print(f"✅ Card database loaded: {CDB_PATH}")
        return True
    else:
        print(f"⚠️ Card database not found: {CDB_PATH}")
        return False


@ffi.callback("void(void*, uint32_t, OCG_CardData*)")
def py_card_reader(payload, code, data):
    """Callback to provide card data to the engine."""
    global _card_db

    # Set defaults
    data.code = code
    data.alias = 0
    data.setcodes = ffi.NULL
    data.type = 0
    data.level = 0
    data.attribute = 0
    data.race = 0
    data.attack = 0
    data.defense = 0
    data.lscale = 0
    data.rscale = 0
    data.link_marker = 0

    if _card_db is None:
        return

    try:
        cursor = _card_db.execute(
            "SELECT * FROM datas WHERE id = ?", (code,)
        )
        row = cursor.fetchone()
        if row:
            data.code = row["id"]
            data.alias = row["alias"] or 0
            data.type = row["type"] or 0
            data.level = row["level"] or 0
            data.attribute = row["attribute"] or 0
            data.race = row["race"] or 0
            data.attack = row["atk"] if row["atk"] is not None else 0
            data.defense = row["def"] if row["def"] is not None else 0
            # Note: setcodes requires special handling (array)
    except Exception as e:
        print(f"Card reader error for code {code}: {e}")


@ffi.callback("void(void*, OCG_CardData*)")
def py_card_reader_done(payload, data):
    """Callback when card reading is complete (cleanup)."""
    pass  # No cleanup needed for our simple implementation


@ffi.callback("int(void*, OCG_Duel, const char*)")
def py_script_reader(payload, duel, name):
    """Callback to load Lua scripts for cards."""
    script_name = ffi.string(name).decode("utf-8")

    if SCRIPT_PATH is None:
        return 0  # No scripts available

    # Try to find the script file
    script_file = SCRIPT_PATH / script_name
    if not script_file.exists():
        # Try with .lua extension
        script_file = SCRIPT_PATH / f"{script_name}.lua"

    if script_file.exists():
        try:
            script_content = script_file.read_bytes()
            lib = load_library()
            result = lib.OCG_LoadScript(
                duel,
                script_content,
                len(script_content),
                name
            )
            return 1 if result == 1 else 0
        except Exception as e:
            print(f"Script load error for {script_name}: {e}")
            return 0
    return 0


@ffi.callback("void(void*, const char*, int)")
def py_log_handler(payload, string, log_type):
    """Callback for log messages from the engine."""
    msg = ffi.string(string).decode("utf-8") if string != ffi.NULL else ""
    log_types = ["ERROR", "SCRIPT", "DEBUG", "UNDEFINED"]
    type_name = log_types[log_type] if log_type < len(log_types) else "UNKNOWN"
    print(f"[OCG {type_name}] {msg}")


def test_create_duel():
    """Test creating a basic duel."""
    print("\n" + "="*60)
    print("Testing OCG Duel Creation")
    print("="*60 + "\n")

    # Initialize card database
    has_cdb = init_card_database()

    # Load library
    lib = load_library()
    print("✅ Library loaded")

    # Create duel options
    options = ffi.new("OCG_DuelOptions*")

    # Set seed (4 x uint64)
    options.seed[0] = 12345
    options.seed[1] = 67890
    options.seed[2] = 11111
    options.seed[3] = 22222

    # Set flags (MR5)
    options.flags = (5 << 16)  # Master Rule 5

    # Set player info
    options.team1.startingLP = 8000
    options.team1.startingDrawCount = 5
    options.team1.drawCountPerTurn = 1

    options.team2.startingLP = 8000
    options.team2.startingDrawCount = 5
    options.team2.drawCountPerTurn = 1

    # Set callbacks
    options.cardReader = py_card_reader
    options.payload1 = ffi.NULL
    options.scriptReader = py_script_reader
    options.payload2 = ffi.NULL
    options.logHandler = py_log_handler
    options.payload3 = ffi.NULL
    options.cardReaderDone = py_card_reader_done
    options.payload4 = ffi.NULL
    options.enableUnsafeLibraries = 0

    # Create duel
    duel_ptr = ffi.new("OCG_Duel*")
    result = lib.OCG_CreateDuel(duel_ptr, options)

    if result != 0:  # OCG_DUEL_CREATION_SUCCESS = 0
        error_names = [
            "SUCCESS", "NO_OUTPUT", "NOT_CREATED",
            "NULL_DATA_READER", "NULL_SCRIPT_READER",
            "INCOMPATIBLE_LUA_API", "NULL_RNG_SEED"
        ]
        error_name = error_names[result] if result < len(error_names) else "UNKNOWN"
        print(f"❌ Failed to create duel: {error_name} ({result})")
        return False

    duel = duel_ptr[0]
    print("✅ Duel created successfully")

    # Add some cards (if we have the database)
    if has_cdb:
        # Add Fiendsmith Engraver (60764609) to player 0's deck
        card_info = ffi.new("OCG_NewCardInfo*")
        card_info.team = 0
        card_info.duelist = 0
        card_info.code = 60764609  # Fiendsmith Engraver
        card_info.con = 0
        card_info.loc = LOCATION_DECK
        card_info.seq = 0
        card_info.pos = POS_FACEDOWN_DEFENSE

        lib.OCG_DuelNewCard(duel, card_info)
        print("✅ Added card to deck: Fiendsmith Engraver (60764609)")

    # Start duel
    lib.OCG_StartDuel(duel)
    print("✅ Duel started")

    # Process one tick
    status = lib.OCG_DuelProcess(duel)
    status_names = ["END", "AWAITING", "CONTINUE"]
    status_name = status_names[status] if status < len(status_names) else "UNKNOWN"
    print(f"✅ Duel process result: {status_name} ({status})")

    # Get messages
    msg_len = ffi.new("uint32_t*")
    msg_ptr = lib.OCG_DuelGetMessage(duel, msg_len)
    print(f"✅ Got message buffer: {msg_len[0]} bytes")

    # Destroy duel
    lib.OCG_DestroyDuel(duel)
    print("✅ Duel destroyed")

    print("\n" + "="*60)
    print("✅ All duel creation tests passed!")
    print("="*60)
    return True


if __name__ == "__main__":
    success = test_create_duel()
    exit(0 if success else 1)
