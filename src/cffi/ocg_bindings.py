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
import platform

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


def _get_lib_extension() -> str:
    """Get platform-appropriate shared library extension."""
    system = platform.system()
    if system == "Darwin":
        return ".dylib"
    elif system == "Windows":
        return ".dll"
    return ".so"  # Linux and others


def load_library():
    """Load the libygo shared library."""
    ext = _get_lib_extension()
    lib_path = Path(__file__).parent / "build" / f"libygo{ext}"
    if not lib_path.exists():
        raise FileNotFoundError(
            f"libygo{ext} not found at {lib_path}. "
            f"Expected extension for {platform.system()}: {ext}"
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

# Duel flags (MR5 = Master Rule 5)
DUEL_FLAGS_MR5 = (5 << 16)

# Message types (from common.h)
MSG_RETRY = 1
MSG_HINT = 2
MSG_START = 4
MSG_WIN = 5
MSG_SELECT_BATTLECMD = 10
MSG_IDLE = 11
MSG_SELECT_CARD = 15
MSG_SELECT_CHAIN = 16
MSG_SELECT_PLACE = 18
MSG_SELECT_POSITION = 19
MSG_SELECT_EFFECTYN = 21
MSG_SELECT_YESNO = 22
MSG_SELECT_OPTION = 23
MSG_SELECT_UNSELECT_CARD = 25
MSG_SHUFFLE_DECK = 32
MSG_NEW_TURN = 40
MSG_NEW_PHASE = 41
MSG_DRAW = 90

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
