# CFFI Prototype Plan

## Objective

Validate CFFI integration is viable before committing to full implementation.
Estimated time: 8-16 hours.

## Pre-Flight Checks (Completed)

| Check | Status | Notes |
|-------|--------|-------|
| Recent Python developments | ✅ None found | No new Python bindings exist |
| yugioh-game maintenance | ✅ Active | Last commit: May 2025 |
| Platform | ⚠️ macOS ARM64 | Need `make macosx` for Lua |
| C++ compiler | ✅ Available | Apple Clang 17.0.0 |
| cmake | ❌ Not installed | Not needed (use g++ directly) |
| Lua via brew | ❌ Not installed | Will build from source |

## Success Criteria

- [ ] libygo.so/libygo.dylib builds successfully
- [ ] Can create a duel and load cards
- [ ] Can execute 5 sequential actions
- [ ] Can replay actions with consistent state
- [ ] Performance >100 actions/second

## Failure Criteria (triggers fallback to Lupa)

- Build fails after 4 hours of debugging
- Performance <50 actions/second
- State drift on replay

## Timeline

| Phase | Time | Deliverable |
|-------|------|-------------|
| Phase 1: Build | 4-8 hours | libygo.dylib + CFFI bindings |
| Phase 2: Execute | 4-8 hours | Working duel with replay |
| **Total** | **8-16 hours** | Validated prototype |

---

## Phase 1: Build Infrastructure

### Step 1.1: Set up build environment (1 hour)

```bash
# Create working directory
mkdir -p cffi_prototype
cd cffi_prototype

# Install Python dependencies
pip install cffi

# Clone repositories (already done in /tmp, copy or link)
cp -r /tmp/ygopro-core ./vendor/ygopro-core
cp -r /tmp/yugioh-game ./reference/yugioh-game

# Get ygopro-scripts
git clone --depth 1 https://github.com/Fluorohydride/ygopro-scripts ./vendor/ygopro-scripts
```

### Step 1.2: Compile Lua 5.3 for macOS (1 hour)

```bash
cd cffi_prototype/vendor

# Download Lua 5.3.5
wget https://www.lua.org/ftp/lua-5.3.5.tar.gz
tar xf lua-5.3.5.tar.gz
cd lua-5.3.5

# Build for macOS (ARM64)
# Note: Use 'macosx' target, not 'linux'
make macosx CC=clang CFLAGS='-O2 -fPIC -arch arm64'

# Verify
ls -la src/liblua.a
./src/lua -v
```

**Potential issue:** If `make macosx` fails, try:
```bash
make posix CC=clang CFLAGS='-O2 -fPIC -arch arm64' LDFLAGS='-arch arm64'
```

### Step 1.3: Compile ygopro-core to shared library (2 hours)

```bash
cd cffi_prototype/vendor

# Apply patches from yugioh-game (if any)
# Check reference/yugioh-game/etc/ for patches
ls reference/yugioh-game/etc/*.patch 2>/dev/null

# Compile to shared library
cd ygopro-core
clang++ -shared -fPIC -arch arm64 \
    -o ../libygo.dylib \
    *.cpp \
    -I../lua-5.3.5/src \
    -L../lua-5.3.5/src \
    -llua \
    -std=c++17 \
    -DOCGCORE_EXPORT_FUNCTIONS

# Verify
file ../libygo.dylib
otool -L ../libygo.dylib
```

**Potential issues:**
1. Missing includes: Add `-I/usr/local/include` if needed
2. Link errors: May need to build Lua as dylib instead of static
3. C++17 vs C++14: edo9300 fork requires C++17

### Step 1.4: Generate CFFI bindings (2 hours)

Create `cffi_prototype/duel_build.py`:

```python
from cffi import FFI

ffibuilder = FFI()

# Copy and adapt from reference/yugioh-game/duel_build.py
ffibuilder.set_source("_duel",
    r"""
    #include "ocgapi.h"
    // Add minimal helper functions if needed
    """,
    libraries=['ygo'],
    library_dirs=['./vendor'],
    include_dirs=['./vendor/ygopro-core', './vendor/lua-5.3.5/src'],
    extra_compile_args=['-std=c++17'],
    extra_link_args=['-Wl,-rpath,./vendor'],
)

ffibuilder.cdef("""
    // Core functions from ocgapi.h
    typedef void* ptr;
    typedef uint32_t uint32;
    typedef int32_t int32;
    typedef uint8_t uint8;
    typedef uint8_t byte;

    ptr create_duel(uint32 seed);
    void start_duel(ptr pduel, int32 options);
    void end_duel(ptr pduel);
    int32 process(ptr pduel);
    int32 get_message(ptr pduel, byte* buf);
    void set_responsei(ptr pduel, int32 value);
    void set_responseb(ptr pduel, byte* value);
    void new_card(ptr pduel, uint32 code, uint8 owner, uint8 playerid,
                  uint8 location, uint8 sequence, uint8 position);
    void set_player_info(ptr pduel, int32 playerid, int32 lp,
                         int32 startcount, int32 drawcount);

    // Callbacks
    extern "Python" uint32 card_reader_callback(uint32, struct card_data*);
    extern "Python" byte* script_reader_callback(const char*, int*);

    typedef uint32 (*card_reader)(uint32, struct card_data*);
    typedef byte* (*script_reader)(const char*, int*);
    void set_card_reader(card_reader f);
    void set_script_reader(script_reader f);
""")

if __name__ == "__main__":
    ffibuilder.compile(verbose=True)
```

Run and verify:
```bash
cd cffi_prototype
python duel_build.py

# Should create _duel.cpython-*.so
ls _duel*.so
```

---

## Phase 2: Basic Duel Execution

### Step 2.1: Create duel wrapper (1 hour)

Create `cffi_prototype/duel.py`:

```python
from _duel import ffi, lib
import sqlite3

class Duel:
    def __init__(self, seed=12345):
        self.duel = lib.create_duel(seed)
        self.buf = ffi.new('char[]', 4096)

    def load_card_database(self, path):
        """Load card data from CDB."""
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row

    def add_card(self, code, player, location, sequence, position=0x1):
        """Add a card to the duel."""
        lib.new_card(self.duel, code, player, player,
                     location, sequence, position)

    def start(self, options=0x50000):  # MR5
        """Start the duel."""
        lib.start_duel(self.duel, options)

    def process(self):
        """Process one game tick."""
        res = lib.process(self.duel)
        length = lib.get_message(self.duel, ffi.cast('byte*', self.buf))
        data = ffi.unpack(self.buf, length)
        return res, data

    def respond_int(self, value):
        """Send integer response."""
        lib.set_responsei(self.duel, value)

    def end(self):
        """End the duel."""
        lib.end_duel(self.duel)
```

### Step 2.2: Implement minimal message handlers (2 hours)

Create `cffi_prototype/messages.py`:

```python
import struct

MSG_IDLE = 11
MSG_SELECT_CARD = 15
MSG_SELECT_CHAIN = 16
MSG_HINT = 2
MSG_NEW_TURN = 40

def parse_message(data):
    """Parse message type and return (msg_type, payload)."""
    if not data:
        return None, None
    msg_type = data[0]
    payload = data[1:]
    return msg_type, payload

def parse_idle(payload):
    """Parse MSG_IDLE to get legal actions."""
    # Format: player, summonable[], spsummon[], repos[], mset[], sset[], activate[]
    buf = io.BytesIO(payload)
    player = struct.unpack('b', buf.read(1))[0]

    def read_cardlist():
        count = struct.unpack('b', buf.read(1))[0]
        cards = []
        for _ in range(count):
            code = struct.unpack('I', buf.read(4))[0]
            # controller, location, sequence
            ctrl = struct.unpack('b', buf.read(1))[0]
            loc = struct.unpack('b', buf.read(1))[0]
            seq = struct.unpack('b', buf.read(1))[0]
            cards.append({'code': code, 'ctrl': ctrl, 'loc': loc, 'seq': seq})
        return cards

    summonable = read_cardlist()
    spsummon = read_cardlist()
    repos = read_cardlist()
    mset = read_cardlist()
    sset = read_cardlist()

    # activate has extra data field
    count = struct.unpack('b', buf.read(1))[0]
    activate = []
    for _ in range(count):
        code = struct.unpack('I', buf.read(4))[0]
        ctrl = struct.unpack('b', buf.read(1))[0]
        loc = struct.unpack('b', buf.read(1))[0]
        seq = struct.unpack('b', buf.read(1))[0]
        desc = struct.unpack('I', buf.read(4))[0]  # effect description
        activate.append({'code': code, 'ctrl': ctrl, 'loc': loc, 'seq': seq, 'desc': desc})

    to_bp = struct.unpack('b', buf.read(1))[0]
    to_ep = struct.unpack('b', buf.read(1))[0]

    return {
        'player': player,
        'summonable': summonable,
        'spsummon': spsummon,
        'repos': repos,
        'mset': mset,
        'sset': sset,
        'activate': activate,
        'to_bp': to_bp,
        'to_ep': to_ep,
    }
```

### Step 2.3: Test basic duel execution (1 hour)

Create `cffi_prototype/test_basic.py`:

```python
from duel import Duel
from messages import parse_message, parse_idle, MSG_IDLE

def test_create_duel():
    """Test creating and starting a duel."""
    d = Duel(seed=12345)

    # Add some cards (use real card codes)
    # Fiendsmith Engraver: 60764609
    d.add_card(60764609, 0, 0x02, 0)  # Hand

    d.start()
    res, data = d.process()

    print(f"Process result: {res}")
    print(f"Message length: {len(data)}")

    d.end()
    print("Duel created and ended successfully!")

if __name__ == "__main__":
    test_create_duel()
```

### Step 2.4: Validate replay consistency (2 hours)

Create `cffi_prototype/test_replay.py`:

```python
import time
from duel import Duel

def execute_actions(duel, action_sequence):
    """Execute a sequence of actions and return final state."""
    for action in action_sequence:
        duel.respond_int(action)
        duel.process()
    # Return some representation of state
    return get_state_hash(duel)

def test_replay_consistency():
    """Test that replaying same actions gives same result."""
    actions = [0, 5, 0, 5, 0]  # Example action sequence

    # First run
    d1 = Duel(seed=12345)
    setup_test_deck(d1)
    d1.start()
    d1.process()
    state1 = execute_actions(d1, actions)
    d1.end()

    # Second run (replay)
    d2 = Duel(seed=12345)  # Same seed
    setup_test_deck(d2)
    d2.start()
    d2.process()
    state2 = execute_actions(d2, actions)
    d2.end()

    assert state1 == state2, "State drift detected!"
    print("Replay consistency verified!")

def test_performance():
    """Benchmark action execution speed."""
    actions = [0, 5, 0, 5, 0]
    iterations = 100

    start = time.time()
    for _ in range(iterations):
        d = Duel(seed=12345)
        setup_test_deck(d)
        d.start()
        d.process()
        execute_actions(d, actions)
        d.end()
    elapsed = time.time() - start

    total_actions = iterations * len(actions)
    actions_per_sec = total_actions / elapsed

    print(f"Performance: {actions_per_sec:.1f} actions/second")
    assert actions_per_sec > 100, f"Too slow! Need >100, got {actions_per_sec}"
    print("Performance test passed!")
```

---

## Files to Create

| File | Purpose |
|------|---------|
| `cffi_prototype/duel_build.py` | CFFI build script |
| `cffi_prototype/duel.py` | Duel wrapper class |
| `cffi_prototype/messages.py` | Message parsers |
| `cffi_prototype/test_basic.py` | Basic functionality test |
| `cffi_prototype/test_replay.py` | Replay and performance tests |

---

## Fallback Plan

If prototype fails:

1. **Build fails:** Try Docker container with known-good Linux environment
2. **Performance too slow:** Profile to find bottleneck, consider Cython
3. **State drift:** Investigate message handling, compare with yugioh-game
4. **All else fails:** Proceed with Lupa extension (accept 90% correctness)

---

## Decision Point

After completing prototype:

| Outcome | Next Step |
|---------|-----------|
| All criteria pass | Proceed to full CFFI integration (30-40h) |
| Performance marginal (50-100/sec) | Add caching, proceed cautiously |
| Build fails | Try Docker, then fallback |
| State drift | Debug or fallback |

---

## References

- [yugioh-game duel_build.py](/tmp/yugioh-game/duel_build.py)
- [yugioh-game duel.py](/tmp/yugioh-game/ygo/duel.py)
- [yugioh-game message_handlers/](/tmp/yugioh-game/ygo/message_handlers/)
- [ocgcore ocgapi.h](/tmp/ygopro-core/ocgapi.h)
