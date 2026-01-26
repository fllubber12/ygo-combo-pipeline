# Implementation Roadmap

Based on the research report, here's a prioritized action plan for improving the combo enumeration pipeline.

---

## Priority Matrix

| Priority | Change | Effort | Impact | Rationale |
|----------|--------|--------|--------|-----------|
| **P0** | Zobrist hashing for transposition table | Medium | High | O(1) incremental updates vs. full state comparison |
| **P1** | Parallel search by starting hand | Medium | High | 658K hands are embarrassingly parallel |
| **P2** | Card role classification | Low | Medium | Better pruning: starter → extender → payoff |
| **P3** | Iterative deepening wrapper | Low | Medium | Find shortest combos first, anytime behavior |
| **P4** | Adopt ygo-agent state encoding | Medium | Medium | Future ML compatibility |

---

## P0: Zobrist Hashing (High Priority)

**Location**: New file `src/cffi/zobrist.py`

**Design**:
```python
class ZobristHasher:
    """Incremental state hashing for YuGiOh game states."""

    def __init__(self, seed=42):
        self.rng = random.Random(seed)
        # Generate random 64-bit numbers for each (card_id, location, zone, owner) tuple
        self.card_keys = {}  # Lazily populated
        self.opt_keys = {}   # For OPT tracking
        self.resource_keys = {
            'normal_summon_used': self.rng.getrandbits(64),
            'battle_phase_available': self.rng.getrandbits(64),
            # ... etc
        }

    def hash_state(self, state) -> int:
        """Full hash computation (used once at start)."""
        h = 0
        for card in state.all_cards:
            h ^= self._get_card_key(card)
        for opt in state.used_opts:
            h ^= self._get_opt_key(opt)
        # ... resources
        return h

    def update_hash(self, old_hash, old_card_state, new_card_state) -> int:
        """Incremental update - O(1) for single card move."""
        return old_hash ^ self._get_card_key(old_card_state) ^ self._get_card_key(new_card_state)
```

**Components to Hash**:
- Card ID × Location (Hand/Field/GY/Banished/Deck/Extra)
- Card position (ATK/DEF/Face-down)
- Card owner (Player 1/2)
- Zone index (which monster zone, which S/T zone)
- Normal summon used this turn
- Battle phase availability
- OPT effects used (bitmap)

**Integration**:
- Replace MD5 hashing in `state_representation.py`
- Update `BoardSignature.hash()` to use Zobrist
- Keep MD5 as fallback for debugging

---

## P1: Parallel Search Architecture

**Location**: New file `src/cffi/parallel_search.py`

**Design**:
```python
from multiprocessing import Pool
from itertools import combinations

def enumerate_combos_parallel(deck: List[int], num_workers: int = None):
    """Parallel combo enumeration across starting hands."""
    all_hands = list(combinations(deck, 5))

    with Pool(num_workers) as pool:
        results = pool.map(enumerate_from_hand, all_hands)

    # Merge results
    return merge_combo_results(results)

def enumerate_from_hand(hand: Tuple[int, ...]) -> List[ComboResult]:
    """Worker function - enumerate all combos from single hand."""
    # Existing DFS logic, but starting from specific hand
    ...
```

**Parallelism Stats**:
- 40-card deck → C(40,5) = 658,008 unique hands
- Each hand is independent (embarrassingly parallel)
- Linear speedup expected with worker count

**Implementation Steps**:
1. Extract `enumerate_from_hand()` from `EnumerationEngine`
2. Make card database read-only shared memory
3. Write results to separate files per worker
4. Merge results in main process

---

## P2: Card Role Classification

**Location**: New file `src/cffi/card_roles.py`

**Design**:
```python
class CardRole(Enum):
    STARTER = 1      # Initiates combos (1-card starters)
    EXTENDER = 2     # Continues combos (requires setup)
    PAYOFF = 3       # End goal (boss monsters, negates)
    UTILITY = 4      # Hand traps, removal
    BRICK = 5        # Garnets, unsearchable requirements

def classify_card(card_id: int, deck_context: DeckContext) -> CardRole:
    """Classify card role based on effect analysis."""
    # Could use heuristics or ML later
    ...

def prioritize_actions(actions: List[Action], roles: Dict[int, CardRole]) -> List[Action]:
    """Order actions by card role priority."""
    # Starters first, then extenders, then payoffs
    ...
```

**Move Ordering Priority**:
1. Starters (initiate combos)
2. Extenders (continue combos)
3. Payoffs (end goals)
4. Utility (disruption, protection)
5. Pass action (last resort)

**Integration**:
- Add role classification to `locked_library.json`
- Use in `_handle_idle()` to order actions
- Better pruning: if no starters activated, skip extenders

---

## P3: Iterative Deepening Wrapper

**Location**: Add to `src/cffi/combo_enumeration.py`

**Design**:
```python
def enumerate_iterative(engine: EnumerationEngine, max_depth: int):
    """Find combos using iterative deepening."""
    all_results = []

    for depth in range(1, max_depth + 1):
        print(f"Searching depth {depth}...")
        engine.config.max_depth = depth
        results = engine.enumerate()

        # Only keep new combos found at this depth
        new_combos = [r for r in results if r.depth == depth]
        all_results.extend(new_combos)

        # Early termination if we found what we want
        if has_target_board(new_combos):
            break

    return all_results
```

**Benefits**:
- Find shortest combos first
- Anytime behavior (can stop early with partial results)
- Better for "find ANY combo" vs "find ALL combos"

---

## P4: ygo-agent State Encoding

**Location**: New file `src/cffi/ml_encoding.py`

**Design** (from ygo-agent):
```python
@dataclass
class CardFeatures:
    """41 features per card (ygo-agent compatible)."""
    card_id: int          # 2 bytes → embedding
    location: int         # Categorical (6 values)
    owner: int            # Binary (0/1)
    position: int         # Categorical (4 values)
    attribute: int        # Categorical (7 values)
    race: int             # Categorical (25 values)
    level: int            # 1-12
    atk: int              # Binned (16-bit float)
    defense: int          # Binned (16-bit float)
    counters: int         # Integer
    negated: bool         # Binary

@dataclass
class GlobalFeatures:
    """23 global state features."""
    turn_count: int
    phase: int
    lp_player0: int
    lp_player1: int
    cards_in_hand_p0: int
    cards_in_deck_p0: int
    # ... etc
```

**Benefits**:
- Future ML model compatibility
- Standardized representation for combo clustering
- Could train board evaluation model

---

## Integration Order

```
Phase 1 (Foundation):
├── P2: Card role classification (enables better pruning)
└── P3: Iterative deepening (quick wins first)

Phase 2 (Performance):
├── P0: Zobrist hashing (transposition speedup)
└── P1: Parallel search (horizontal scaling)

Phase 3 (ML Preparation):
└── P4: ygo-agent encoding (future-proofing)
```

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| States/second | ~1000 | ~10,000 |
| Memory per state | ~500B | ~100B |
| Transposition hit rate | 39% | 60%+ |
| Time to first combo | Unknown | <1 second |
| Full enumeration (26 cards) | Hours | Minutes |

---

## Dependencies

**P0 (Zobrist)**:
- No external dependencies
- Replaces existing hash function

**P1 (Parallel)**:
- Python `multiprocessing` (stdlib)
- May need process-safe transposition table

**P2 (Card Roles)**:
- No dependencies
- Could integrate with `locked_library.json`

**P3 (Iterative Deepening)**:
- No dependencies
- Wrapper around existing engine

**P4 (ML Encoding)**:
- Optional: numpy for efficient arrays
- Optional: torch for future ML integration
