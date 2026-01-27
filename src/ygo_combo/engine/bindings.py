"""
CFFI bindings for edo9300 ygopro-core (OCG API v11.0).

Based on ocgapi.h and ocgapi_types.h from:
https://github.com/edo9300/ygopro-core

Usage:
    from src.cffi.ocg_bindings import ffi, lib

    # Get version
    major, minor = ffi.new("int*"), ffi.new("int*")
    lib.OCG_GetVersion(major, minor)
    print(f"OCG Core version: {major[0]}.{minor[0]}")
"""

from cffi import FFI
from pathlib import Path

ffi = FFI()

# Define the C API based on ocgapi.h and ocgapi_types.h
ffi.cdef("""
    /*** ENUMS ***/

    typedef enum OCG_LogTypes {
        OCG_LOG_TYPE_ERROR,
        OCG_LOG_TYPE_FROM_SCRIPT,
        OCG_LOG_TYPE_FOR_DEBUG,
        OCG_LOG_TYPE_UNDEFINED
    } OCG_LogTypes;

    typedef enum OCG_DuelCreationStatus {
        OCG_DUEL_CREATION_SUCCESS,
        OCG_DUEL_CREATION_NO_OUTPUT,
        OCG_DUEL_CREATION_NOT_CREATED,
        OCG_DUEL_CREATION_NULL_DATA_READER,
        OCG_DUEL_CREATION_NULL_SCRIPT_READER,
        OCG_DUEL_CREATION_INCOMPATIBLE_LUA_API,
        OCG_DUEL_CREATION_NULL_RNG_SEED
    } OCG_DuelCreationStatus;

    typedef enum OCG_DuelStatus {
        OCG_DUEL_STATUS_END,
        OCG_DUEL_STATUS_AWAITING,
        OCG_DUEL_STATUS_CONTINUE
    } OCG_DuelStatus;

    /*** TYPES ***/

    typedef void* OCG_Duel;

    typedef struct OCG_CardData {
        uint32_t code;
        uint32_t alias;
        uint16_t* setcodes;
        uint32_t type;
        uint32_t level;
        uint32_t attribute;
        uint64_t race;
        int32_t attack;
        int32_t defense;
        uint32_t lscale;
        uint32_t rscale;
        uint32_t link_marker;
    } OCG_CardData;

    typedef struct OCG_Player {
        uint32_t startingLP;
        uint32_t startingDrawCount;
        uint32_t drawCountPerTurn;
    } OCG_Player;

    // Callback types (we'll use extern "Python" for these)
    typedef void (*OCG_DataReader)(void* payload, uint32_t code, OCG_CardData* data);
    typedef void (*OCG_DataReaderDone)(void* payload, OCG_CardData* data);
    typedef int (*OCG_ScriptReader)(void* payload, OCG_Duel duel, const char* name);
    typedef void (*OCG_LogHandler)(void* payload, const char* string, int type);

    typedef struct OCG_DuelOptions {
        uint64_t seed[4];
        uint64_t flags;
        OCG_Player team1;
        OCG_Player team2;
        OCG_DataReader cardReader;
        void* payload1;
        OCG_ScriptReader scriptReader;
        void* payload2;
        OCG_LogHandler logHandler;
        void* payload3;
        OCG_DataReaderDone cardReaderDone;
        void* payload4;
        uint8_t enableUnsafeLibraries;
    } OCG_DuelOptions;

    typedef struct OCG_NewCardInfo {
        uint8_t team;
        uint8_t duelist;
        uint32_t code;
        uint8_t con;
        uint32_t loc;
        uint32_t seq;
        uint32_t pos;
    } OCG_NewCardInfo;

    typedef struct OCG_QueryInfo {
        uint32_t flags;
        uint8_t con;
        uint32_t loc;
        uint32_t seq;
        uint32_t overlay_seq;
    } OCG_QueryInfo;

    /*** API FUNCTIONS ***/

    // Core information
    void OCG_GetVersion(int* major, int* minor);

    // Duel creation and destruction
    int OCG_CreateDuel(OCG_Duel* out_ocg_duel, const OCG_DuelOptions* options_ptr);
    void OCG_DestroyDuel(OCG_Duel ocg_duel);
    void OCG_DuelNewCard(OCG_Duel ocg_duel, const OCG_NewCardInfo* info_ptr);
    void OCG_StartDuel(OCG_Duel ocg_duel);

    // Duel processing and querying
    int OCG_DuelProcess(OCG_Duel ocg_duel);
    void* OCG_DuelGetMessage(OCG_Duel ocg_duel, uint32_t* length);
    void OCG_DuelSetResponse(OCG_Duel ocg_duel, const void* buffer, uint32_t length);
    int OCG_LoadScript(OCG_Duel ocg_duel, const char* buffer, uint32_t length, const char* name);

    // Query functions
    uint32_t OCG_DuelQueryCount(OCG_Duel ocg_duel, uint8_t team, uint32_t loc);
    void* OCG_DuelQuery(OCG_Duel ocg_duel, uint32_t* length, const OCG_QueryInfo* info_ptr);
    void* OCG_DuelQueryLocation(OCG_Duel ocg_duel, uint32_t* length, const OCG_QueryInfo* info_ptr);
    void* OCG_DuelQueryField(OCG_Duel ocg_duel, uint32_t* length);

    /*** Python callbacks ***/
    extern "Python" void py_card_reader(void* payload, uint32_t code, OCG_CardData* data);
    extern "Python" void py_card_reader_done(void* payload, OCG_CardData* data);
    extern "Python" int py_script_reader(void* payload, OCG_Duel duel, const char* name);
    extern "Python" void py_log_handler(void* payload, const char* string, int type);
""")


def load_library():
    """Load the libygo shared library.

    Uses paths.get_library_path() for platform detection.
    """
    from .paths import get_library_path, get_lib_extension
    lib_path = get_library_path()
    if not lib_path.exists():
        ext = get_lib_extension()
        raise FileNotFoundError(
            f"libygo{ext} not found at {lib_path}. "
            f"Please build the library first."
        )
    return ffi.dlopen(str(lib_path))


# Module-level library instance (lazy loaded)
_lib = None


def get_lib():
    """Get the library instance, loading it if necessary."""
    global _lib
    if _lib is None:
        _lib = load_library()
    return _lib


def __getattr__(name):
    """Module-level lazy loading for 'lib' attribute."""
    if name == "lib":
        return get_lib()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# Location constants (from common.h)
LOCATION_DECK = 0x01
LOCATION_HAND = 0x02
LOCATION_MZONE = 0x04
LOCATION_SZONE = 0x08
LOCATION_GRAVE = 0x10
LOCATION_REMOVED = 0x20
LOCATION_EXTRA = 0x40
LOCATION_OVERLAY = 0x80
LOCATION_ONFIELD = LOCATION_MZONE | LOCATION_SZONE

# Position constants
POS_FACEUP_ATTACK = 0x1
POS_FACEDOWN_ATTACK = 0x2
POS_FACEUP_DEFENSE = 0x4
POS_FACEDOWN_DEFENSE = 0x8
POS_FACEUP = POS_FACEUP_ATTACK | POS_FACEUP_DEFENSE
POS_FACEDOWN = POS_FACEDOWN_ATTACK | POS_FACEDOWN_DEFENSE

# Query flags (for OCG_DuelQueryLocation)
QUERY_CODE = 0x1
QUERY_POSITION = 0x2
QUERY_EQUIP_CARD = 0x10
QUERY_ATTACK = 0x100
QUERY_DEFENSE = 0x200
QUERY_END = 0x80000000

# Duel flags (MR5 = Master Rule 5)
DUEL_FLAGS_MR5 = (5 << 16)

# =============================================================================
# Message Types (from ygopro-core/common.h)
# =============================================================================
# Reference: https://github.com/edo9300/ygopro-core/blob/master/common.h

# Core messages
MSG_RETRY = 1
MSG_HINT = 2
MSG_WAITING = 3
MSG_START = 4
MSG_WIN = 5
MSG_UPDATE_DATA = 6
MSG_UPDATE_CARD = 7

# Selection messages (require player response)
# Values from ygopro-core/ocgapi_constants.h
MSG_SELECT_BATTLECMD = 10
MSG_IDLE = 11  # MSG_SELECT_IDLECMD
MSG_SELECT_EFFECTYN = 12
MSG_SELECT_YESNO = 13
MSG_SELECT_OPTION = 14
MSG_SELECT_CARD = 15
MSG_SELECT_CHAIN = 16
MSG_SELECT_PLACE = 18
MSG_SELECT_POSITION = 19
MSG_SELECT_TRIBUTE = 20
MSG_SELECT_COUNTER = 22
MSG_SELECT_SUM = 23  # CRITICAL: Was wrong (26), fixed to match ygopro-core
MSG_SELECT_DISFIELD = 24
MSG_SORT_CARD = 25
MSG_SELECT_UNSELECT_CARD = 26  # CRITICAL: Was wrong (25), fixed to match ygopro-core

# Deck/hand operations
MSG_CONFIRM_DECKTOP = 30
MSG_CONFIRM_CARDS = 31
MSG_SHUFFLE_DECK = 32
MSG_SHUFFLE_HAND = 33
MSG_REFRESH_DECK = 34
MSG_SWAP_GRAVE_DECK = 35
MSG_SHUFFLE_SET_CARD = 36
MSG_REVERSE_DECK = 37
MSG_DECK_TOP = 38
MSG_SHUFFLE_EXTRA = 39

# Turn/phase messages
MSG_NEW_TURN = 40
MSG_NEW_PHASE = 41
MSG_CONFIRM_EXTRATOP = 42

# Card movement
MSG_MOVE = 50
MSG_POS_CHANGE = 53
MSG_SET = 54
MSG_SWAP = 55
MSG_FIELD_DISABLED = 56

# Summoning messages
MSG_SUMMONING = 60
MSG_SUMMONED = 61
MSG_SPSUMMONING = 62
MSG_SPSUMMONED = 63
MSG_FLIPSUMMONING = 64
MSG_FLIPSUMMONED = 65

# Chain messages
MSG_CHAINING = 70
MSG_CHAINED = 71
MSG_CHAIN_SOLVING = 72
MSG_CHAIN_SOLVED = 73
MSG_CHAIN_END = 74
MSG_CHAIN_NEGATED = 75
MSG_CHAIN_DISABLED = 76

# Selection feedback
MSG_CARD_SELECTED = 80
MSG_RANDOM_SELECTED = 81
MSG_BECOME_TARGET = 83

# LP and damage
MSG_DRAW = 90
MSG_DAMAGE = 91
MSG_RECOVER = 92
MSG_EQUIP = 93
MSG_LPUPDATE = 94
MSG_UNEQUIP = 95
MSG_CARD_TARGET = 96
MSG_CANCEL_TARGET = 97
MSG_PAY_LPCOST = 100
MSG_ADD_COUNTER = 101
MSG_REMOVE_COUNTER = 102

# Battle
MSG_ATTACK = 110
MSG_BATTLE = 111
MSG_ATTACK_DISABLED = 112
MSG_DAMAGE_STEP_START = 113
MSG_DAMAGE_STEP_END = 114

# Effect messages
MSG_MISSED_EFFECT = 120
MSG_BE_CHAIN_TARGET = 121
MSG_CREATE_RELATION = 122
MSG_RELEASE_RELATION = 123

# Random events
MSG_TOSS_COIN = 130
MSG_TOSS_DICE = 131
MSG_ROCK_PAPER_SCISSORS = 132
MSG_HAND_RES = 133

# Announcements
MSG_ANNOUNCE_RACE = 140
MSG_ANNOUNCE_ATTRIB = 141
MSG_ANNOUNCE_CARD = 142
MSG_ANNOUNCE_NUMBER = 143

# Hints and UI
MSG_CARD_HINT = 160
MSG_TAG_SWAP = 161
MSG_RELOAD_FIELD = 162
MSG_AI_NAME = 163
MSG_SHOW_HINT = 164
MSG_PLAYER_HINT = 165
MSG_MATCH_KILL = 170
MSG_CUSTOM_MSG = 180
MSG_REMOVE_CARDS = 190

# Card type flags
TYPE_MONSTER = 0x1
TYPE_SPELL = 0x2
TYPE_TRAP = 0x4
TYPE_FUSION = 0x40
TYPE_SYNCHRO = 0x2000
TYPE_XYZ = 0x800000
TYPE_LINK = 0x4000000


if __name__ == "__main__":
    # Quick test
    lib = load_library()
    major = ffi.new("int*")
    minor = ffi.new("int*")
    lib.OCG_GetVersion(major, minor)
    print(f"OCG Core version: {major[0]}.{minor[0]}")
    print("CFFI bindings loaded successfully!")
