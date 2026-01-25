# Combo Pipeline Roadmap

> Last Updated: 2026-01-25
> Status: Phase 1 Complete, Phase 2 In Progress

---

## Quick Reference (TL;DR)

| Key | Value |
|-----|-------|
| **Current Phase** | 2.1 (Search Strategy Decision) |
| **Blocking On** | State space analysis to choose exhaustive vs MCTS |
| **Next Action** | Run depth 30/35/40 measurements |
| **Last Verified** | 2026-01-25 |

### Key Numbers to Remember

```
Library:        26 cards (9 main + 17 extra)
Trans. Hit:     39.3% (excellent deduplication)
Caesar depth:   23 actions (found)
Target depth:   35-40 actions (estimated)
Best found:     S:P Little Knight at depth 22
Target board:   Caesar + A Bao A Qu + Rextremende + Kyrie
```

### Environment Variables

```bash
# Required: Path to ygopro-scripts directory (Lua card scripts)
export YGOPRO_SCRIPTS_PATH=/path/to/ygopro-scripts
```

### Quick Commands

```bash
# Verify everything works
python3 -m pytest tests/ -v                                   # All tests
python3 src/cffi/combo_enumeration.py --max-depth 15 --max-paths 100  # Quick test

# Run verification
python3 src/cffi/combo_enumeration.py --max-depth 25 --max-paths 1000 --output verify.json
```

---

## 1. Project Vision & Goals

### Ultimate Goal
Build a system that can analyze Yu-Gi-Oh! combo decks to answer:
1. **Given a specific hand, what's the optimal play sequence?**
2. **Given a deck, what hands lead to good boards?**
3. **How resilient is a combo line to hand traps?**
4. **What's the expected board quality across all possible hands?**

### Short-term Goals (Current Phase)
- [x] Integrate ygopro-core for game simulation
- [x] Build state representation for board hashing
- [x] Implement exhaustive combo enumeration
- [x] Verify deduplication and transposition table
- [ ] Achieve reasonable performance for full hand enumeration

### Medium-term Goals
- [ ] Implement MCTS or beam search for larger state spaces
- [ ] Build board evaluation function (learned or heuristic)
- [ ] Enumerate all 5-card hands from a deck
- [ ] Analyze hand trap interaction points

### Long-term Goals
- [ ] Train RL agent for optimal play
- [ ] Build deck analysis tool
- [ ] Create interactive combo explorer
- [ ] Publish findings and tools

---

## 2. Architecture Overview

### System Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           COMBO PIPELINE                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────────────┐    │
│  │   Deck       │     │   Hand       │     │   Combo              │    │
│  │   Config     │────▶│   Generator  │────▶│   Enumerator         │    │
│  │   (JSON)     │     │   (C(n,5))   │     │   (DFS/MCTS)         │    │
│  └──────────────┘     └──────────────┘     └──────────┬───────────┘    │
│                                                       │                 │
│                                                       ▼                 │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────────────┐    │
│  │   ygopro     │◀───▶│   CFFI       │◀───▶│   State              │    │
│  │   core       │     │   Bindings   │     │   Representation     │    │
│  │   (C++)      │     │   (Python)   │     │   (Python)           │    │
│  └──────────────┘     └──────────────┘     └──────────┬───────────┘    │
│                                                       │                 │
│                                                       ▼                 │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────────────┐    │
│  │   Board      │◀────│   Transpo-   │◀────│   Terminal           │    │
│  │   Evaluator  │     │   sition     │     │   Collector          │    │
│  │              │     │   Table      │     │                      │    │
│  └──────────────┘     └──────────────┘     └──────────────────────┘    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Component Descriptions

| Component | File | Purpose |
|-----------|------|---------|
| **CFFI Bindings** | `ocg_bindings.py` | Low-level ygopro-core FFI interface |
| **Duel Manager** | `tests/integration/test_fiendsmith_duel.py` | Duel creation, card loading, script handling |
| **Combo Enumerator** | `combo_enumeration.py` | Exhaustive path exploration with branching |
| **State Representation** | `state_representation.py` | BoardSignature, IntermediateState, ActionSpec |
| **Transposition Table** | `transposition_table.py` | Memoization for explored states |
| **Card Library** | `config/locked_library.json` | Deck configuration (26 cards) |

### Data Flow

```
1. Load deck configuration (main + extra deck)
2. Create fresh duel instance
3. Set up starting hand
4. Process duel until MSG_IDLE
5. At MSG_IDLE:
   a. Compute IntermediateState hash
   b. Check transposition table
   c. If new: enumerate all legal actions
   d. For each action: replay from start, recurse
6. At PASS: record terminal state with BoardSignature
7. Group terminals by board hash
8. Evaluate board quality
```

---

## 3. Completed Work

### What's Been Built

| Component | Status | Verification |
|-----------|--------|--------------|
| OCG library loading | ✅ Complete | Duels run successfully |
| Card database integration | ✅ Complete | 26 cards loaded |
| Message parsing (15+ types) | ✅ Complete | All decision points handled |
| BoardSignature (zone-agnostic) | ✅ Complete | 19 unit tests pass |
| IntermediateState (with OPT) | ✅ Complete | Hash includes legal actions |
| ActionSpec (ygo-agent style) | ✅ Complete | Factory methods work |
| TranspositionTable | ✅ Complete | 39.3% hit rate verified |
| Board evaluation function | ✅ Complete | S/A/B/C/brick tiers |
| Exhaustive enumeration | ✅ Complete | 1000 paths in ~60s |

### What's Been Verified

**Verification Run (2026-01-24):**
```
Paths explored:              1,000
Terminal states found:         150
Unique board signatures:       150
Duplicate boards skipped:      228
Transposition hit rate:      39.3%
Intermediate states pruned:     77
Max depth seen:                 24
```

**Board Quality Distribution:**
- S-tier: 5 boards
- A-tier: 9 boards
- B-tier: 0 boards
- C-tier: 61 boards
- Brick: 75 boards

### Key Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| OPT Tracking | Trust engine (Option A) | Engine tracks internally; observable via legal actions |
| Card Identity | Passcode only (Option A) | Copies are fungible for evaluation |
| Zone Equality | Loose/zone-agnostic (Option B) | Exact zone rarely affects board quality |
| Hash Includes | Board + legal actions | Captures OPT state without explicit tracking |
| Equip Tracking | Include in signature | Important for Fiendsmith self-equip combos |

---

## 4. Current State

### Where We Are Now

- **Phase 1 (Foundation)**: Complete
- **Code Cleanup**: Complete (16 issues resolved, all tests passing)
- **Phase 2 (Search Strategy)**: In Progress - decision pending
- **Blocking issue:** Not finding strong boards (Caesar, A Bao A Qu) consistently

### What Works

| Component | Status | Notes |
|-----------|--------|-------|
| CFFI engine integration | ✅ Working | All rules enforced correctly |
| State representation | ✅ Working | 3-layer model (board/intermediate/replay) |
| Transposition table | ✅ Working | 39.3% hit rate, depth-prioritized eviction |
| Basic enumeration | ✅ Working | But depth-first, not optimal |
| Position/zone collapse | ✅ Working | Reduces branching significantly |
| Board grouping | ✅ Working | 64 boards with multiple paths |
| Cross-platform support | ✅ Working | .dylib/.so/.dll auto-detection |
| Graceful shutdown | ✅ Working | SIGINT/SIGTERM handling |
| Type hints | ✅ Working | All public functions annotated |

### Known Limitations

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| Depth-first exploration | Exhausts weaker branches first | Need round-robin or priority |
| Evaluation function is placeholder | "S-tier" doesn't reflect actual quality | Phase 3 will refine |
| Not finding full combos | S:P Little Knight is best, should find Caesar | Need deeper search |
| No intelligent search guidance | All branches treated equally | Heuristic ordering needed |
| Forward replay (no save/restore) | O(d) replay per path | Transposition table helps |
| Single hand only | Can't analyze full deck | Phase 6 will address |

### Immediate Next Step

**DECISION REQUIRED:** Choose search strategy before proceeding further.

Options:
1. Run state space analysis to measure true size
2. Implement breadth-first/round-robin exploration
3. Prototype MCTS for comparison
4. User provides board rankings to define evaluation function

---

## 5. Open Questions

### Search Strategy (Must Decide Before Proceeding)

1. **Exhaustive vs MCTS?**
   - Exhaustive guarantees finding all boards but may be too slow
   - MCTS finds good boards fast but may miss some
   - Need to measure actual state space size before deciding

2. **Exploration order?**
   - Current: Depth-first (exhausts Sanct branches before Tract)
   - Problem: Tract leads to stronger boards but explored last
   - Options: Breadth-first, round-robin, priority-based

3. **Depth limit?**
   - Depth 25: Finds S:P Little Knight
   - Depth 30: Found Caesar in earlier test
   - User's full combo: Estimated 35-40 actions
   - Need to verify actual depth required

### Evaluation Function (Phase 3, but informs Phase 2)

1. **How to define "good board"?**
   - Option A: User ranks sample boards, train model
   - Option B: User defines rules (Caesar = S, S:P alone = B)
   - Option C: Proxy metrics (more monsters = better)

2. **What specific cards indicate quality?**
   - Caesar: Top tier (Rank 6 Xyz with interaction)
   - A Bao A Qu: Top tier (Link-4 with recursion)
   - Rextremende: High tier (Fusion with recovery)
   - S:P Little Knight: Mid tier (Link-2 stepping stone)
   - Requiem alone: Low tier (Link-1, usually intermediate)

### Hand Trap Modeling (Phase 5, but worth considering now)

- Fork at each chain opportunity?
- Probabilistic modeling?
- Focus on most common interruption points?

### Circular Dependencies

- Phase 2 decision affects Phase 3 (how we sample boards to evaluate)
- Phase 3 informs Phase 2 (evaluation can guide search if we use MCTS)
- **Resolution:** Make explicit Phase 2 decision first, then iterate

### Research Needed

- [ ] Profile enumeration to find bottleneck
- [ ] Measure actual state space size at various depths
- [ ] Benchmark MCTS vs exhaustive on known combos
- [ ] Survey hand trap interaction patterns
- [ ] Identify which starter leads to best boards

### External Dependencies

- ygopro-core library (bundled in `bin/`)
- Card scripts (in `script/` directory)
- Card database (`cards.cdb`)
- Python 3.10+ with cffi

---

## 6. Phase Checklist

### Phase 1: Foundation ✅ COMPLETE

**Goal**: Build working game simulation and state representation

- [x] Load ygopro-core via CFFI
- [x] Parse all message types
- [x] Handle branching decisions (IDLE, SELECT_CARD, etc.)
- [x] Implement BoardSignature with zone-agnostic hashing
- [x] Implement IntermediateState with legal action capture
- [x] Implement TranspositionTable for memoization
- [x] Build exhaustive combo enumerator
- [x] Verify with 1000-path test run

**Verification Criteria**:
- All 19 state tests pass
- Transposition hit rate > 10%
- Can enumerate paths and collect terminals

**Verification Commands**:
```bash
cd src/cffi

# 1. Run state representation tests (expect: 19 passing)
python3 -m pytest tests/unit/test_state.py -v

# 2. Quick enumeration test (expect: ~50 terminals)
python3 combo_enumeration.py --max-depth 15 --max-paths 100

# 3. Full verification run (expect: 150+ terminals, >30% hit rate)
python3 combo_enumeration.py --max-depth 25 --max-paths 1000 --output verify.json

# 4. Check results
python3 -c "import json; d=json.load(open('verify.json')); print(f\"Terminals: {d['meta']['terminals_found']}, Hit rate: {d['meta']['transposition_hit_rate']:.1%}\")"
```

**Definition of Done**: Can enumerate all paths from a starting hand and collect unique terminal boards with quality scores.

---

### Phase 2: Search Strategy 🔄 IN PROGRESS

**Status:** Decision pending
**Goal:** Decide and implement optimal search approach for finding best boards

#### 2.1 Decision: Exhaustive vs MCTS

- [ ] Analyze state space size for Engraver + 4 dead cards
- [ ] Estimate time/memory for exhaustive search at depth 30, 35, 40
- [ ] Prototype MCTS if exhaustive is infeasible
- [ ] **DECISION REQUIRED:** Choose search strategy

**Current findings:**
- Depth 25, 1000 paths → 150 unique boards, best is S:P Little Knight (Link-2)
- Caesar found at depth 23 in earlier test
- Full combo (Caesar + A Bao A Qu + Rextremende) estimated at depth 35-40
- 39.3% transposition hit rate suggests significant state overlap

**Options:**

| Option | Pros | Cons |
|--------|------|------|
| Exhaustive + pruning | Guaranteed complete | Slow for deep combos |
| MCTS | Fast, finds good boards quickly | May miss some boards |
| Hybrid | Best of both | Complex implementation |

#### 2.2 Search Optimizations Implemented

- [x] Position collapse (ATK only)
- [x] Zone collapse (first available)
- [x] Card deduplication (Holactie copies equivalent)
- [x] Terminal board deduplication
- [x] Intermediate state pruning (transposition table)

#### 2.3 Search Optimizations Remaining

- [ ] Breadth-first or round-robin exploration (avoid exhausting one branch)
- [ ] Priority queue based on partial board evaluation
- [ ] Depth-limited iterative deepening
- [ ] Action ordering heuristics (try Tract before Sanct)

**Verification Criteria**:
- [ ] Can find Caesar board within reasonable time (<10 min)
- [ ] Can find boards matching user's example combos
- [ ] State space is either fully explored OR sampling is justified

**Verification Commands**:
```bash
cd src/cffi

# 1. State space measurement at different depths
for depth in 25 30 35; do
  echo "=== Depth $depth ==="
  time python3 combo_enumeration.py --max-depth $depth --max-paths 5000 --output depth_${depth}.json
done

# 2. Check for Caesar (passcode 79559912) in results
python3 -c "
import json
for d in [25, 30, 35]:
    try:
        data = json.load(open(f'depth_{d}.json'))
        caesar_found = any(
            79559912 in [c.get('code',0) for c in t.get('board_state',{}).get('player0',{}).get('monsters',[])]
            for t in data['terminals']
        )
        print(f'Depth {d}: Caesar found = {caesar_found}')
    except: pass
"

# 3. Memory usage check
/usr/bin/time -l python3 combo_enumeration.py --max-depth 30 --max-paths 10000 2>&1 | grep "maximum resident"
```

**Dependencies**: Phase 1 complete

**Definition of Done**: Search strategy decided, implemented, and verified to find target boards.

---

### Phase 3: Evaluation Function

**Goal**: Build accurate board quality assessment

- [ ] Define board quality metrics
- [ ] Implement heuristic evaluator (current: done)
- [ ] Collect training data from exhaustive runs
- [ ] Train learned evaluator (optional)
- [ ] Validate against human expert rankings
- [ ] Integrate into search for pruning

**Verification Criteria**:
- Evaluator correctly ranks known good vs bad boards
- Consistent with human intuition
- Fast enough for real-time use

**Dependencies**: Phase 1 complete

**Definition of Done**: Have a reliable board evaluator that can guide search and rank terminals.

---

### Phase 4: Optimization

**Goal**: Find best board efficiently for any starting hand

- [ ] Integrate evaluation into search
- [ ] Implement alpha-beta style pruning
- [ ] Add iterative deepening
- [ ] Optimize for "find best" vs "enumerate all"
- [ ] Benchmark on diverse hands

**Verification Criteria**:
- Can find S-tier board in <10s for any hand (if one exists)
- Correctly identifies brick hands quickly

**Dependencies**: Phase 2 and 3 complete

**Definition of Done**: Can quickly determine best achievable board for any 5-card hand.

---

### Phase 5: Hand Trap Analysis

**Goal**: Model opponent interaction and combo resilience

- [ ] Identify common hand traps (Ash, Veiler, Imperm, etc.)
- [ ] Model chain opportunities
- [ ] Implement branching for "with/without interrupt"
- [ ] Calculate resilience scores
- [ ] Find "play through" lines
- [ ] Identify critical choke points

**Verification Criteria**:
- Can answer "does this hand play through Ash?"
- Correctly identifies which action to Ash

**Dependencies**: Phase 4 complete

**Definition of Done**: Can analyze combo resilience to common hand traps.

---

### Phase 6: Any-Hand Generalization

**Goal**: Analyze all possible hands from a deck

- [ ] Implement hand generation (C(n,5))
- [ ] Parallelize hand analysis
- [ ] Aggregate statistics across hands
- [ ] Calculate deck consistency metrics
- [ ] Identify must-have starters
- [ ] Find brick patterns

**Verification Criteria**:
- Can analyze all C(40,5) = 658,008 hands
- Produces meaningful deck statistics

**Dependencies**: Phase 4 complete

**Definition of Done**: Can produce full deck analysis with expected board quality distribution.

---

### Phase 7: Deck Building Analysis

**Goal**: Optimize deck construction

- [ ] Model card slot variations
- [ ] Compare deck variants
- [ ] Identify optimal ratios
- [ ] Suggest improvements
- [ ] Build interactive explorer

**Verification Criteria**:
- Can recommend card changes
- Suggestions improve expected board quality

**Dependencies**: Phase 6 complete

**Definition of Done**: Can provide actionable deck building recommendations.

---

## 7. Technical Specifications

### State Representation Schema

#### BoardSignature
```python
@dataclass(frozen=True)
class BoardSignature:
    monsters: FrozenSet[int]      # Passcodes in monster zones
    spells: FrozenSet[int]        # Passcodes in spell/trap zones
    graveyard: FrozenSet[int]     # Passcodes in GY
    hand: FrozenSet[int]          # Passcodes in hand
    banished: FrozenSet[int]      # Passcodes banished
    extra_deck: FrozenSet[int]    # Passcodes in extra (optional)
    equips: FrozenSet[Tuple[int, int]]  # (equipped, target) pairs
```

#### IntermediateState
```python
@dataclass(frozen=True)
class IntermediateState:
    board: BoardSignature
    legal_actions: FrozenSet[str]  # ActionSpec.spec strings
```

#### ActionSpec
```python
@dataclass(frozen=True)
class ActionSpec:
    spec: str           # "act:CODE:EFFECT", "ss:CODE", "ns:CODE", "pass"
    passcode: int
    action_type: str    # "activate", "summon", "spsummon", "mset", "sset", "pass"
    effect_index: int
    location: int
```

### Hash Specifications

| Hash Type | Algorithm | Length | Includes |
|-----------|-----------|--------|----------|
| BoardSignature | MD5 | 16 hex chars | monsters, spells, GY, hand, banished, equips |
| IntermediateState | MD5 | 24 hex chars | BoardSignature.hash() + sorted(legal_actions) |
| ActionSpec | String | Variable | Just the spec string |

### File Formats

#### locked_library.json
```json
{
  "_meta": {
    "description": "LOCKED library configuration",
    "card_count": 26
  },
  "cards": {
    "PASSCODE": {
      "passcode": int,
      "name": "string",
      "type_flags": ["Monster", "Effect", ...],
      "deck_location": "main_deck_monsters|extra_deck|...",
      "effect_text": "string",
      ...
    }
  }
}
```

#### verification_run.json
```json
{
  "meta": {
    "timestamp": "ISO8601",
    "paths_explored": int,
    "terminals_found": int,
    "transposition_hit_rate": float,
    ...
  },
  "terminals": [
    {
      "action_sequence": [...],
      "board_state": {...},
      "depth": int,
      "board_hash": "string",
      "termination_reason": "PASS|MAX_DEPTH|NO_ACTIONS"
    }
  ],
  "board_groups": {"hash": count}
}
```

### API Contracts

#### Engine → Enumeration Engine

```python
# MSG_IDLE structure (parsed from ygopro-core)
idle_data = {
    "activatable": [
        {"code": int, "index": int, "loc": int, "desc": int},
        ...
    ],
    "spsummon": [{"code": int, "index": int}, ...],
    "summonable": [{"code": int, "index": int}, ...],
    "mset": [{"code": int, "index": int}, ...],
    "sset": [{"code": int, "index": int}, ...],
    "to_bp": bool,      # Can go to Battle Phase
    "to_ep": bool,      # Can go to End Phase
    "to_shuffle": bool, # Can shuffle
}
```

#### Enumeration Engine → State Representation

```python
# board_state dict (from capture_board_state)
board_state = {
    "player0": {
        "monsters": [{"code": int, "position": int, "zone_index": int}, ...],
        "spells": [{"code": int, "position": int, "equip_target": int}, ...],
        "graveyard": [{"code": int}, ...],
        "hand": [{"code": int}, ...],
        "banished": [{"code": int}, ...],
        "extra": [{"code": int}, ...],
    },
    "player1": {...}  # Opponent (empty in goldfish)
}

# BoardSignature.from_board_state(board_state) -> BoardSignature
# IntermediateState.from_idle_data(idle_data, board_state) -> IntermediateState
```

#### State Representation → Transposition Table

```python
# Key: state_hash (str, 24 hex chars from MD5)
# Value: TranspositionEntry

class TranspositionEntry:
    state_hash: str           # Redundant but useful for debugging
    best_terminal_hash: str   # Best board reachable from here
    best_terminal_value: float
    depth_to_terminal: int
    visit_count: int
```

#### EnumerationEngine Public API

```python
class EnumerationEngine:
    def __init__(self, lib, main_deck, extra_deck,
                 verbose=False, dedupe_boards=True, dedupe_intermediate=True)

    def enumerate_all(self) -> List[TerminalState]

    # After enumeration:
    # - self.terminals: List[TerminalState]
    # - self.terminal_boards: Dict[str, List[ActionSequence]]
    # - self.transposition_table: TranspositionTable
```

#### TranspositionTable Public API

```python
class TranspositionTable:
    def __init__(self, max_size: int = 1_000_000)
    def lookup(self, state_hash: str) -> Optional[TranspositionEntry]
    def store(self, state_hash: str, entry: TranspositionEntry)
    def stats(self) -> dict  # {"size", "hits", "misses", "hit_rate"}
```

---

## 8. Research Log

### ygo-agent Analysis (2026-01-24)

**Repository**: https://github.com/sbl1996/ygo-agent

**Key Findings**:

1. **State Representation** (41 features per card):
   - Card ID (16-bit), Location, Sequence, Controller
   - Position, Overlay status, Attribute, Race, Level
   - Counter, Negated flag, ATK/DEF (16-bit float transform)
   - 25 type flags (monster/spell/trap subtypes)

2. **Global Features** (23 dimensions):
   - LP (both players), Turn count, Phase ID
   - Is first player, Is my turn
   - Card counts per location (14 zones)

3. **Action Features** (12 dimensions per action):
   - Card index, Card ID, Message type
   - Action type, Finish flag, Effect index
   - Phase, Position, Number, Place, Attribute

4. **Spec String Format**:
   ```
   h1  = hand position 1
   m3  = monster zone 3
   s2  = spell zone 2
   g5  = graveyard position 5
   oh1 = opponent's hand position 1
   m3a1 = monster zone 3, overlay material 1
   ```

5. **Key Insight**: ygo-agent does NOT hash/cache intermediate states. Their `hash` field is unused. They rely on neural network generalization instead.

6. **Reward Shaping**:
   ```cpp
   if (turn_count <= 2) base_reward = 16.0;
   else if (turn_count <= 4) base_reward = 8.0;
   else if (turn_count <= 6) base_reward = 4.0;
   // Incentivizes fast wins
   ```

### Key Insights

1. **OPT is observable**: Engine tracks Once-Per-Turn internally; we see it via what actions are legal.

2. **Zone position rarely matters**: For Fiendsmith, exact zone only matters for Buio/Luce (leftmost/rightmost protection) and Cross-Sheep (link arrows).

3. **Equips are important**: Fiendsmith Links (Requiem, Sequence, Agnumday) equip themselves to non-Link monsters. Must track these relationships.

4. **Forward replay is acceptable**: ygo-agent also uses forward replay, not save/restore.

### Problem Structure Analysis

Our problem differs from typical game AI:

| Aspect | Typical Game AI | Our Problem |
|--------|-----------------|-------------|
| Players | Adversarial (2+) | Single-player optimization |
| Information | Hidden cards | Known information (goldfish) |
| Tree structure | Infinite/very deep | Finite (OPT bounds depth) |
| Objective | Win/loss | Board quality metric |
| Generalization | Many decks/cards | Fixed 26-card library |

This is closer to **puzzle solving** than game playing:
- Find shortest/best path to target state
- Dynamic programming / memoization applicable
- Could potentially solve exactly for small libraries
- State space is finite and enumerable

### ygo-agent Relevance

ygo-agent solves a different problem (playing full games vs opponents) but provides:
- State representation patterns (41 features per card)
- Action encoding (spec strings)
- Proof that ygopro-core can be wrapped effectively
- RL training infrastructure (if we go that route later)

Their approach won't directly solve our problem because:
- They optimize for winning, we optimize for board quality
- They need generalization across all cards, we have fixed library
- They use learned embeddings, we need exact state hashing
- They don't cache states (rely on NN generalization instead)

### Starter Card Analysis

From verification run observations:
- **Sanct** (Token generator): Explored first due to depth-first, leads to simple boards
- **Tract** (Search + discard): Explored later, likely leads to stronger combo lines
- **Engraver** (in hand): Discard effect or summon, multiple paths

**Hypothesis:** Tract-first lines reach Caesar more often than Sanct-first lines.
**Action needed:** Verify by comparing exploration orders.

---

## 9. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| State space too large for exhaustive | High | High | Implement MCTS/beam search (Phase 2) |
| Evaluation function inaccurate | Medium | High | Validate against expert; iterate on heuristics |
| ygopro-core API changes | Low | High | Pin to known working version |
| Memory exhaustion | Medium | Medium | Transposition table eviction; streaming results |
| Card script bugs | Medium | Low | Test with known combos; validate against manual play |
| Performance too slow | High | Medium | Profile and optimize; parallelize |
| Hash collisions | Low | Medium | Use longer hashes; verify on collision |

---

## 10. Troubleshooting Guide

### Engine Crashes (Segfault)

**Symptom:** Python crashes with no error message
**Cause:** Usually invalid response to engine message
**Fix:**
1. Check last MSG type in action_history
2. Verify response format matches expected
3. Run with `--verbose` to see last action

```bash
# Debug run
python3 combo_enumeration.py --max-depth 10 --max-paths 50 --verbose
```

### Out of Memory

**Symptom:** Process killed or MemoryError
**Cause:** Too many paths/states cached
**Fix:**
1. Reduce `--max-paths` (try 500)
2. Reduce `--max-depth` (try 20)
3. Check transposition table size in output
4. Increase eviction (currently removes 10% when full)

### No Terminals Found

**Symptom:** 0 terminals after enumeration
**Cause:** Starting hand has no legal actions
**Fix:**
1. Verify starting hand contains activatable card (Engraver)
2. Check that hand isn't all dead cards
3. Verify card passcodes match database

### All Terminals Are Bricks

**Symptom:** Only C-tier/Brick terminals found
**Cause:** Depth too shallow or wrong branch explored first
**Fix:**
1. Increase depth limit (`--max-depth 30`)
2. Check exploration order (Tract vs Sanct issue)
3. Verify combo line is possible from starting hand

### MSG_RETRY Errors

**Symptom:** Engine requests retry of response
**Cause:** Invalid response format sent
**Fix:**
1. Check `build_*_response()` functions
2. Verify byte order (little-endian)
3. Check response length matches expected

---

## 11. Decision Log

### D001: CFFI over Subprocess

| Field | Value |
|-------|-------|
| Date | 2026-01-XX |
| Decision | CFFI direct binding to ocgcore |
| Alternatives | Subprocess calls to ygopro executable; Python reimplementation |
| Rationale | CFFI gives 100% rule accuracy with good performance |
| Risks | CFFI complexity, platform dependency (dylib vs so) |
| Status | ✅ Implemented, working |

### D002: Holactie as Dead Card

| Field | Value |
|-------|-------|
| Date | 2026-01-24 |
| Decision | Use passcode 10000040 (internal EDOPro ID) |
| Alternatives | 99011877 (official passcode, not in database); Other unplayable cards |
| Rationale | Requires tributing 3 Egyptian Gods, impossible in our setup |
| Risks | None identified |
| Status | ✅ Verified working |

### D003: Position Collapse (ATK Only)

| Field | Value |
|-------|-------|
| Date | 2026-01-XX |
| Decision | Always choose ATK position, don't branch |
| Alternatives | Branch on ATK/DEF |
| Rationale | 35% path reduction; 12 path groups showed identical final boards; No effects in library care about position |
| Risks | May miss edge cases if library expands |
| Status | ✅ Implemented |

### D004: Zone Collapse (First Available)

| Field | Value |
|-------|-------|
| Date | 2026-01-XX |
| Decision | Always use first available zone |
| Alternatives | Branch on all zones |
| Rationale | Zone-sensitive cards (Cross-Sheep, Buio) appeared in 0 terminals; 170 zone selections × 5 zones would massively increase paths |
| Risks | Cross-Sheep/Buio combos would need revisiting |
| Status | ✅ Implemented |

### D005: Trust Engine for OPT

| Field | Value |
|-------|-------|
| Date | 2026-01-24 |
| Decision | Don't track OPT ourselves; observe via legal actions |
| Alternatives | Explicit OPT tracking per card |
| Rationale | Engine already tracks internally; observable via what actions are legal |
| Risks | None - engine is authoritative |
| Status | ✅ Implemented |

### D006: Zone-Agnostic Board Hashing

| Field | Value |
|-------|-------|
| Date | 2026-01-24 |
| Decision | Hash by card presence, not exact zone position |
| Alternatives | Include zone positions in hash |
| Rationale | Most terminals are equivalent regardless of zone; reduces duplicate boards |
| Risks | Miss zone-dependent effects (Buio leftmost/rightmost) |
| Status | ✅ Implemented |

### D007: Card Deduplication Strategy

| Field | Value |
|-------|-------|
| Date | 2026-01-24 |
| Decision | When selecting cards, deduplicate by passcode |
| Alternatives | Treat each card instance as unique |
| Rationale | Selecting Holactie #1 vs #2 produces identical outcomes |
| Risks | None for current library |
| Status | ✅ Implemented |

### D008: Legal Actions in State Hash

| Field | Value |
|-------|-------|
| Date | 2026-01-24 |
| Decision | Include activatable effects in intermediate state hash |
| Alternatives | Explicitly track OPT ourselves via MSG_HINT parsing |
| Rationale | Engine is authoritative; simpler than parsing hints |
| Risks | None |
| Status | ✅ Implemented |

### D009: Card Identity Tracking

| Field | Value |
|-------|-------|
| Date | 2026-01-24 |
| Decision | Use just passcode, not instance ID |
| Alternatives | Track individual card instances |
| Rationale | All copies of same card are functionally equivalent |
| Risks | None for current use case |
| Status | ✅ Implemented |

### D010: Terminal Board Equivalence

| Field | Value |
|-------|-------|
| Date | 2026-01-24 |
| Decision | Zone-agnostic - same passcodes = same board |
| Alternatives | Include zone positions in board signature |
| Rationale | Zone only matters for Link arrows; current combos don't depend on it |
| Risks | May need revisiting if Cross-Sheep line becomes important |
| Status | ✅ Implemented |

### D011: Three-Layer State Model

| Field | Value |
|-------|-------|
| Date | 2026-01-24 |
| Decision | Separate BoardSignature / IntermediateState / ActionSequence |
| Alternatives | Single unified state class |
| Rationale | Different use cases need different granularity |
| Risks | More complex API |
| Status | ✅ Implemented |

### D012: Transposition Table Eviction Policy

| Field | Value |
|-------|-------|
| Date | 2026-01-24 |
| Decision | FIFO with 10% batch eviction when full |
| Alternatives | LRU, depth-based priority, no eviction |
| Rationale | Simple, effective for our access patterns |
| Risks | May evict still-useful entries |
| Status | ✅ Implemented |

---

## 12. Quantified Success Criteria

### Phase 2 Success Metrics

| Criterion | Target | Current |
|-----------|--------|---------|
| Find Caesar board | < 10 min | ✅ Found at depth 23 |
| Transposition hit rate | > 30% | ✅ 39.3% |
| Memory usage at depth 30 | < 4 GB | ⏳ Not measured |
| Explore 10K paths | < 5 min | ⏳ ~60s for 1K paths |

### Phase 3 Success Metrics

| Criterion | Target | Current |
|-----------|--------|---------|
| Board rankings collected | ≥ 20 boards | ⏳ Not started |
| Ranking accuracy | ≥ 80% | ⏳ Not started |
| Evaluation time | < 1 ms/board | ✅ Current is instant |

### Phase 4 Success Metrics

| Criterion | Target | Current |
|-----------|--------|---------|
| Find target board | Caesar + A Bao A Qu + Rex | ❌ Not found yet |
| Search efficiency | ≥ 90% of known boards | ⏳ Unknown |
| Time to best board | < 5 min | ⏳ Not measured |

---

## 13. Glossary

### Yu-Gi-Oh Terms

| Term | Definition |
|------|------------|
| **Brick** | A hand that cannot execute the combo |
| **Chain Link** | Individual activation in a chain (CL1, CL2, etc.) |
| **Cost** | Requirement to activate effect (paid regardless of resolution) |
| **ED** | Extra Deck (Fusion, Synchro, Xyz, Link monsters) |
| **Effect** | The action a card performs (happens on resolution) |
| **End Board** | The final board state after combo completes |
| **Extender** | A card that continues the combo after the starter |
| **Fusion Material** | Cards used to Fusion Summon |
| **Goldfish** | Solo combo practice without opponent interaction |
| **GY** | Graveyard (discard pile) |
| **Hand Trap** | A monster that can be activated from hand to disrupt |
| **HOPT** | Hard Once Per Turn (card name restriction, not copy) |
| **Interruption** | Point where opponent can disrupt combo |
| **Link Arrow** | Direction a Link monster points for co-linking |
| **Link Material** | Monsters used to Link Summon |
| **Link Rating** | The "level" of a Link monster (1-4 typically) |
| **Main Phase** | The phase where most combo actions occur |
| **OPT** | Once Per Turn restriction on card effects |
| **SOPT** | Soft Once Per Turn (copy restriction) |
| **Starter** | A card that begins the combo (e.g., Fiendsmith Engraver) |
| **Xyz Material** | Cards attached to Xyz monster |

### Technical Terms

| Term | Definition |
|------|------------|
| **Backpropagation** | Updating node values from leaf to root in MCTS |
| **Branching Factor** | Average number of legal actions per state |
| **CFFI** | C Foreign Function Interface for Python |
| **Depth-First Search** | Explore deepest path first before backtracking |
| **Determinization** | Sampling from unknown information |
| **Evaluation Function** | Scores board quality numerically |
| **MCTS** | Monte Carlo Tree Search algorithm |
| **MSG_IDLE** | Engine message indicating player can take actions |
| **Passcode** | Unique 8-digit identifier for each card |
| **Rollout** | Random playout to estimate position value |
| **State Hash** | Unique identifier for a game state |
| **Terminal State** | A board state where no more actions are taken |
| **Transposition Table** | Hash table caching explored game states |
| **UCB1** | Upper Confidence Bound formula for exploration |

### Project-Specific Terms

| Term | Definition |
|------|------------|
| **ActionSpec** | Standardized representation of a game action |
| **BoardSignature** | Zone-agnostic hash of board state for deduplication |
| **Forward Replay** | Recreating game state by replaying actions from start |
| **IntermediateState** | Full state including board + legal actions |
| **Position Collapse** | Always choosing ATK position to reduce branching |
| **S-tier Board** | High-quality end board (score >= 100) |
| **Zone Collapse** | Always choosing first available zone |

---

## 14. Known Limitations & Edge Cases

### Not Supported (by design)

| Limitation | Reason |
|------------|--------|
| Battle Phase | Goldfish only, no attacks needed |
| Opponent cards | Solitaire enumeration |
| Random effects | No cards with random outcomes in library |
| Deck order | Assumes fixed deck, no shuffle variance |
| Side decking | Single deck focus |
| Best-of-3 strategy | Single game focus |

### Not Yet Supported (future phases)

| Feature | Phase | Notes |
|---------|-------|-------|
| Multiple starters | Phase 6 | Only Engraver tested |
| Mixed hands | Phase 6 | Only Engraver + dead cards |
| Hand traps | Phase 5 | Ash, Nibiru, etc. |
| Deck building | Phase 7 | Ratio optimization |

### Edge Cases to Watch

| Edge Case | Risk | Mitigation |
|-----------|------|------------|
| Equip loops | Requiem can re-equip multiple times | Loop detection in engine |
| GY recursion | Engraver GY effect + shuffle | OPT prevents true loops |
| Zone-sensitive plays | Cross-Sheep Link arrows | Currently collapsed; watch for issues |
| Position-sensitive plays | None in current library | Safe to ignore |

### Failure Modes

| Failure | Probability | Detection | Recovery |
|---------|-------------|-----------|----------|
| State hash collision | ~1e-29 (MD5 24 chars) | Duplicate boards with different actions | Increase hash length |
| Memory exhaustion | Medium at depth 35+ | Process killed | Reduce depth or enable streaming |
| Engine crash | Low | Segfault | Check last action, validate response |

---

## 15. Test Coverage Matrix

| Component | Unit Tests | Integration | Manual | Status |
|-----------|------------|-------------|--------|--------|
| `ocg_bindings.py` | ❌ | ✅ | ✅ | Working |
| `state_representation.py` | ✅ 19 tests | ✅ | ✅ | Complete |
| `transposition_table.py` | ✅ 5 tests | ✅ | ✅ | Complete |
| `combo_enumeration.py` | ❌ Partial | ✅ | ✅ | Working |
| Board evaluation | ❌ | ❌ | ⏳ Placeholder | Phase 3 |
| MCTS | ❌ | ❌ | ❌ | Not started |

### Test Commands

```bash
cd src/cffi

# Unit tests (19 tests)
python3 -m pytest tests/unit/test_state.py -v

# Integration test (quick)
python3 combo_enumeration.py --max-depth 15 --max-paths 100

# Full verification
python3 combo_enumeration.py --max-depth 25 --max-paths 1000 --output verify.json

# Check specific card appears
python3 -c "
import json
data = json.load(open('verify.json'))
codes = set()
for t in data['terminals']:
    for m in t.get('board_state',{}).get('player0',{}).get('monsters',[]):
        codes.add(m.get('code'))
print('Cards found:', codes)
"
```

---

## 16. Performance Baselines

### Enumeration Speed

| Depth | Paths | Time (sec) | Paths/sec | Notes |
|-------|-------|------------|-----------|-------|
| 15 | 100 | ~2s | ~50 | Quick test |
| 20 | 500 | ~15s | ~33 | Moderate |
| 25 | 1000 | ~60s | ~17 | Verification run |
| 30 | 5000 | TBD | TBD | Need measurement |

### Memory Usage

| Depth | Max Paths | Peak RAM | States Cached |
|-------|-----------|----------|---------------|
| 15 | 100 | ~50 MB | ~20 |
| 25 | 1000 | ~150 MB | ~119 |
| 30 | 5000 | TBD | TBD |

### Comparison Baselines

| System | Speed | Notes |
|--------|-------|-------|
| ygo-agent | 10K-30K games/sec | Full games, C++ with envpool |
| Hearthstone MCTS | 10K rollouts/sec | C++ implementation |
| Our system | ~17 paths/sec | Python, forward replay |

**Note:** Our low speed is expected due to Python + forward replay. Optimization opportunities exist but not critical for current use case.

---

## 17. Deferred Items

### Explicitly Deferred to Later Phases

| Item | Reason | Target Phase |
|------|--------|--------------|
| Learned evaluation function | Need sample boards first | Phase 3 |
| MCTS implementation | Pending decision | Phase 2 |
| Hand trap modeling | Architecture must support | Phase 5 |
| Multi-starter hands | Complexity | Phase 6 |
| Deck ratio optimization | Far future | Phase 7 |

### Explicitly Out of Scope

| Item | Reason |
|------|--------|
| Battle phase | Goldfish only |
| Side decking | Single deck focus |
| Best-of-3 strategy | Single game focus |
| Matchup analysis | Solitaire focus |
| Non-Fiendsmith decks | Library-specific tool |

### Considered But Rejected

| Item | Reason Rejected |
|------|-----------------|
| Instance ID tracking | All copies equivalent (D009) |
| Zone-specific hashing | No zone-sensitive cards (D010) |
| Position branching | Identical outcomes (D003) |
| Subprocess engine | CFFI more reliable (D001) |
| Explicit OPT tracking | Engine is authoritative (D005) |

---

## 18. Document Metadata

### Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-24 | Initial creation with 10 sections |
| 2.0 | 2026-01-24 | Added 10 appendices (A-J) |
| 3.0 | 2026-01-24 | Added troubleshooting, decision log, expanded glossary |
| 3.1 | 2026-01-24 | Added D007-D012, API contracts, limitations, test matrix |

### Consistency Checklist

Run this verification before major changes:

```bash
cd .

# Verify passcodes match
grep -r "79559912" docs/ src/cffi/  # Caesar
grep -r "4731783" docs/ src/cffi/   # A Bao A Qu
grep -r "60764609" docs/ src/cffi/  # Engraver

# Verify files exist
ls -la src/cffi/combo_enumeration.py
ls -la src/cffi/state_representation.py
ls -la src/cffi/transposition_table.py
ls -la config/locked_library.json

# Verify card count
python3 -c "import json; print(len(json.load(open('config/locked_library.json'))['cards']))"
# Expected: 26
```

### Review Checklist

- [x] All passcodes verified against locked_library.json
- [x] All metrics verified against latest test run
- [x] All file paths verified to exist
- [x] All phase dependencies accurately reflected
- [x] Glossary terms used consistently in document
- [x] Decision log complete (D001-D012)

---

## Appendix A: Complete Card Library

> All 26 cards verified against `cards.cdb`. Passcodes are canonical identifiers.

### Main Deck - Monsters (4 cards)

| Card Name | Passcode | Type | Role |
|-----------|----------|------|------|
| Fiendsmith Engraver | 60764609 | Effect Monster | Primary starter |
| Fabled Lurrie | 97651498 | Effect Monster | Discard extender |
| Lacrima the Crimson Tears | 28803166 | Effect Monster | Mill + recursion |
| Buio the Dawn's Light | 19000848 | Effect Monster | Protection + Mutiny search |

### Main Deck - Spells/Traps (5 cards)

| Card Name | Passcode | Type | Role |
|-----------|----------|------|------|
| Fiendsmith's Tract | 98567237 | Normal Spell | Search + discard outlet |
| Fiendsmith's Sanct | 35552985 | Quick-Play Spell | Token generator |
| Mutiny in the Sky | 71593652 | Normal Spell | GY Fusion Summon |
| Fiendsmith in Paradise | 99989863 | Normal Trap | Board wipe + mill |
| Fiendsmith Kyrie | 26434972 | Normal Trap | Protection + GY Fusion |

### Extra Deck (17 cards)

| Card Name | Passcode | Type | Role |
|-----------|----------|------|------|
| Fiendsmith's Requiem | 2463794 | Link-1 | Combo starter, equips self |
| Fiendsmith's Sequence | 49867899 | Link-2 | GY Fusion, equips self |
| Fiendsmith's Agnumday | 32991300 | Link-3 | Recursion, equips self |
| Fiendsmith's Lacrima | 46640168 | Fusion | ATK reduction, recursion |
| Fiendsmith's Desirae | 82135803 | Fusion | Effect negation |
| Fiendsmith's Rextremende | 11464648 | Fusion | Boss, unaffected when equipped |
| D/D/D Wave High King Caesar | 79559912 | Rank 6 Xyz | **TARGET** - Negate summons |
| S:P Little Knight | 29301450 | Link-2 | Banish on summon/response |
| A Bao A Qu, the Lightless Shadow | 4731783 | Link-4 | **TARGET** - Disruption + recursion |
| Luce the Dusk's Dark | 45409943 | Fusion | Protection + destruction |
| Aerial Eater | 28143384 | Fusion | Mill + recursion |
| Cross-Sheep | 50277355 | Link-2 | Fusion trigger |
| Muckraker From the Underworld | 71607202 | Link-2 | GY recursion |
| The Duke of Demise | 45445571 | Fusion | Extra Normal Summon |
| Necroquip Princess | 93860227 | Fusion | Equip synergy |
| Evilswarm Exciton Knight | 46772449 | Rank 4 Xyz | Emergency board wipe |
| Snake-Eyes Doomed Dragon | 58071334 | Fusion | Not used in combo |

### Dead Cards (for testing)

| Card Name | Passcode | Purpose |
|-----------|----------|---------|
| Holactie the Creator of Light | 10000040 | Dead card placeholder (4 copies in hand) |

---

## Appendix B: Target Combo Line

### User's Example Combo (Engraver + 4 Dead Cards)

```
Opening Hand: Fiendsmith Engraver + 4x Holactie (dead cards)

1. Activate Engraver in hand → discard self → search Tract
2. Activate Tract → add Lurrie to hand, discard Holactie
3. Lurrie triggers in GY → Special Summon self
4. Link Lurrie → Requiem (Link-1)
5. Requiem effect → tribute self → summon Lacrima from deck
6. Lacrima trigger → send Engraver from deck to GY
7. Link Lacrima → Sequence (Link-2)
8. Sequence effect → GY Fusion (shuffle materials) → Fiendsmith's Lacrima
9. Fiendsmith's Lacrima summon trigger → add/summon from GY
10. Continue building...
11. Make Agnumday (Link-3) → targets Rextremende
12. Fusion Summon Rextremende
13. Overlay 2 Level 6 Fiends → Caesar (Rank 6 Xyz)
14. Link into A Bao A Qu (Link-4)
15. Set Kyrie

Target End Board:
┌─────────────────────────────────────────────────┐
│ Monster Zones:                                  │
│   • D/D/D Wave High King Caesar (Xyz, 2 mats)   │
│   • A Bao A Qu, the Lightless Shadow (Link-4)   │
│   • Fiendsmith's Rextremende (equipped)         │
│                                                 │
│ Spell/Trap Zones:                               │
│   • Fiendsmith Kyrie (set)                      │
│                                                 │
│ Graveyard: (setup for Kyrie Fusion)             │
│   • Requiem, Sequence, Agnumday (equip targets) │
│   • Engraver, Lacrima (Fusion materials)        │
└─────────────────────────────────────────────────┘

Estimated Depth: 35-40 actions
```

### Why This Board Is Strong

| Card | Interaction |
|------|-------------|
| Caesar | Negates any summon effect (Quick Effect) |
| A Bao A Qu | Destroys or banishes, revives from GY |
| Rextremende | Unaffected by non-Fiendsmith effects when equipped |
| Kyrie | Can Fusion Summon during opponent's turn |

---

## Appendix C: Experimental Data

### Verification Run Results (2026-01-24)

| Metric | Value |
|--------|-------|
| Depth Limit | 25 |
| Paths Explored | 1,000 |
| Terminals Found | 150 |
| Unique Board Signatures | 150 |
| Duplicate Boards Skipped | 228 |
| Transposition Hit Rate | **39.3%** |
| Intermediate States Pruned | 77 |
| Max Depth Reached | 24 |

### Termination Reasons

| Reason | Count | Percentage |
|--------|-------|------------|
| PASS (voluntary end) | 85 | 56.7% |
| MAX_DEPTH (hit limit) | 65 | 43.3% |

### Depth Distribution

| Depth | Terminals | Notes |
|-------|-----------|-------|
| 25 | 69 | Hit depth limit |
| 22 | 17 | Natural PASS |
| 24 | 15 | Near limit |
| 20 | 11 | Mid-combo |
| 18 | 6 | Early end |

### Board Quality Distribution

| Tier | Count | Percentage | Best Card Found |
|------|-------|------------|-----------------|
| S-tier | 5 | 3.3% | S:P Little Knight |
| A-tier | 9 | 6.0% | S:P Little Knight |
| B-tier | 0 | 0% | - |
| C-tier | 61 | 40.7% | Various |
| Brick | 75 | 50.0% | Token only |

### Card Coverage

**Cards appearing in terminals:** 17/26 (65%)

**Never reached (Extra Deck):**
- A Bao A Qu (Link-4) - needs too many materials at depth 25
- Desirae - needs Engraver + 2 LIGHT Fiends
- Rextremende - two-step Fusion
- Luce - GY-based Fusion, needs setup

**Observation:** Depth 25 is insufficient for full combo.

### Intermediate State Growth

| Depth | Unique States | Growth vs Previous |
|-------|---------------|-------------------|
| 5 | 4 | - |
| 10 | 12 | 3x |
| 15 | 36 | 3x |
| 20 | 341 | 9.5x |

**Insight:** State explosion happens after depth 15 when multiple combo paths diverge.

### Convergence Pattern Analysis

From path group analysis:

| Pattern Type | Occurrences | Example |
|--------------|-------------|---------|
| Activation order | 39 | A→B same as B→A when no chain |
| Card selection | 208 | Different materials, same result |
| Summon choice | 671 | Mostly MAX_DEPTH artifacts |

**Insight:** Most "different paths, same board" are from arbitrary ordering of independent actions.

### Near-MAX_DEPTH Analysis

Diminishing returns at depth limit:

| Depth Range | % Duplicates | Unique Boards Lost if Pruned |
|-------------|--------------|------------------------------|
| 28+ | 96.5% | 7 (Aerial Eater/Duke variants) |
| 27+ | ~90% | ~15 |
| 26+ | ~80% | ~25 |

**Recommendation:** Could prune aggressively near MAX_DEPTH with minimal loss.

---

## Appendix D: Boss Monster Status

| Monster | Passcode | Status | First Found | Notes |
|---------|----------|--------|-------------|-------|
| D/D/D Caesar | 79559912 | ✅ Found | Depth 23 | Rank 6 Xyz, primary target |
| S:P Little Knight | 29301450 | ✅ Found | Depth 17+ | Link-2, stepping stone |
| Agnumday | 32991300 | ✅ Found | Depth 20+ | Link-3, equip enabler |
| A Bao A Qu | 4731783 | ❌ Not found | N/A | Link-4, needs 4+ materials |
| Rextremende | 11464648 | ❌ Not found | N/A | Two-step Fusion |
| Desirae | 82135803 | ❌ Not found | N/A | Needs 3 specific materials |
| Luce | 45409943 | ❌ Not found | N/A | GY Fusion, needs setup |

### Target Board Progress

```
Current Best: S:P Little Knight alone (depth 22)
Target: Caesar + A Bao A Qu + Rextremende + set Kyrie

Progress: [██░░░░░░░░] 20%
- ✅ Can reach Caesar
- ❌ Cannot reach A Bao A Qu
- ❌ Cannot reach Rextremende
- ❌ Cannot set Kyrie (need deeper search)
```

---

## Appendix E: Message Handling Verification

### Handled Response Messages (9 types)

| Message | Code | Purpose | Branching |
|---------|------|---------|-----------|
| MSG_IDLE | 11 | Main decision point | Yes - all actions |
| MSG_SELECT_CARD | 15 | Material/target selection | Yes - all choices |
| MSG_SELECT_CHAIN | 16 | Chain response | Auto-decline (goldfish) |
| MSG_SELECT_PLACE | 18 | Zone selection | Collapsed (first available) |
| MSG_SELECT_POSITION | 19 | ATK/DEF choice | Collapsed (ATK only) |
| MSG_SELECT_EFFECTYN | 24 | Effect activation Y/N | Yes - both options |
| MSG_SELECT_YESNO | 25 | General Y/N | Yes - both options |
| MSG_SELECT_OPTION | 26 | Effect option choice | Yes - all options |
| MSG_SELECT_UNSELECT_CARD | 27 | Multi-select | Yes - all combos |

### Not Encountered (library doesn't trigger)

| Message | Code | Reason |
|---------|------|--------|
| MSG_SELECT_TRIBUTE | 17 | No tribute summons in library |
| MSG_SELECT_BATTLECMD | 12 | Main Phase only |
| MSG_ANNOUNCE_ATTRIB | N/A | No attribute announcements |
| MSG_ANNOUNCE_NUMBER | N/A | No number announcements |

### Validation

```
MSG_RETRY errors: 0 (no invalid responses sent)
Unknown message types: 0
Engine crashes: 0
```

---

## Appendix F: Key Discovery - Tract vs Sanct Ordering

### Problem: Depth-First Search Order

Current enumeration explores actions in order returned by engine:

```
MSG_IDLE activatable actions:
  Index 0: Engraver (hand) - discard effect
  Index 1: Engraver (hand) - summon effect
  Index 2: Sanct - creates token
  Index 3: Tract - searches and discards
```

**Sanct is explored before Tract**, leading to:
- 1000+ paths through Token → Requiem line
- Tract line (stronger) never reached within path limits

### Evidence

At Depth 30 (from earlier test):

| Search Target | Terminals | % |
|---------------|-----------|---|
| Tract | 117 | 81.2% |
| Sanct | 24 | 16.7% |
| Kyrie | 1 | 0.7% |
| Paradise | 1 | 0.7% |

**Tract leads to 4.9x more terminals than Sanct** - it enables the Lurrie line which is the strongest combo path.

### Recommended Fix

Option 1: **Action ordering heuristic**
- Prioritize Tract over Sanct in action enumeration
- Requires knowledge of "good" actions

Option 2: **Round-robin exploration**
- Explore one level of each branch before going deeper
- Ensures all starters get explored

Option 3: **Breadth-first at low depths**
- BFS until depth 5, then DFS
- Covers all openers before committing

---

## Appendix G: File Inventory

### Core Implementation

| File | Purpose | Status |
|------|---------|--------|
| `src/cffi/combo_enumeration.py` | Main enumeration engine | ✅ Working |
| `src/cffi/state_representation.py` | BoardSignature, IntermediateState | ✅ Working |
| `src/cffi/transposition_table.py` | Memoization cache | ✅ Working |
| `src/cffi/ocg_bindings.py` | CFFI FFI interface | ✅ Working |
| `tests/integration/test_fiendsmith_duel.py` | Duel creation utilities | ✅ Working |

### Test Files

| File | Tests | Status |
|------|-------|--------|
| `tests/unit/test_state.py` | 19 unit tests | ✅ All passing |

### Configuration

| File | Purpose |
|------|---------|
| `config/locked_library.json` | Verified 26-card library |
| `cards.cdb` | SQLite card database |

### Output Files

| File | Contents |
|------|----------|
| `src/cffi/verification_run.json` | Latest enumeration results |
| `src/cffi/enumeration_results.json` | Historical results |

### External Dependencies

| File | Purpose |
|------|---------|
| `bin/libocgcore.dylib` | ygopro-core library (macOS) |
| `script/*.lua` | Card effect scripts |

---

## Appendix H: Phase Completion Criteria

### Phase 3: Evaluation Function

**Done When:**
- [ ] User has ranked 20+ sample boards manually
- [ ] Board scoring matches user rankings with >80% accuracy
- [ ] Can distinguish S-tier from A-tier from brick
- [ ] Scoring runs in <1ms per board

### Phase 4: Optimization

**Done When:**
- [ ] Can find Caesar board in <5 minutes from Engraver hand
- [ ] Can find user's target board (Caesar + A Bao A Qu + Rextremende)
- [ ] State space either fully explored OR sampling strategy justified
- [ ] Memory usage stays under 4GB

### Phase 5: Hand Trap Analysis

**Done When:**
- [ ] Can compute "best line through Ash Blossom"
- [ ] Can compute "best line through Nibiru"
- [ ] Can rank hands by resilience score
- [ ] Identifies optimal choke points for opponent

### Phase 6: Any-Hand Generalization

**Done When:**
- [ ] Can analyze all C(9,5) = 126 possible hands
- [ ] Produces deck consistency metrics
- [ ] Identifies auto-win vs brick hands
- [ ] Runtime <1 hour for full deck analysis

### Phase 7: Deck Building

**Done When:**
- [ ] Can compare deck variants quantitatively
- [ ] Recommendations improve expected board quality
- [ ] Interactive explorer allows "what if" analysis

---

## Appendix I: Phase Dependency Graph

```
┌─────────────────────────────────────────────────────────────────────┐
│                     PHASE DEPENDENCY GRAPH                          │
└─────────────────────────────────────────────────────────────────────┘

Phase 1: Foundation ✅ COMPLETE
    │
    ├── State representation (BoardSignature, IntermediateState)
    ├── Transposition table
    ├── Basic enumeration engine
    └── Message handling
         │
         ▼
Phase 2: Search Strategy ◀────────────────────────────────┐
    │                                                      │
    ├── 2.1 State space analysis                          │
    ├── 2.2 Decision: Exhaustive vs MCTS                  │
    └── 2.3 Implementation                                │
         │                                                 │
         ├─────────────────────┐                          │
         ▼                     ▼                          │
Phase 3: Evaluation     Phase 4: Optimization             │
    │                       │                             │
    │ DEPENDS ON:           │ DEPENDS ON:                 │
    │ - Sample boards       │ - Evaluation function       │
    │   from Phase 2        │ - Search strategy           │
    │                       │                             │
    ├── 3.1 Board ranking   ├── 4.1 Pruning               │
    ├── 3.2 Train model     ├── 4.2 Ordering              │
    └── 3.3 Validate        └── 4.3 Optimization          │
         │                       │                        │
         │                       │ FEEDBACK LOOP ─────────┘
         │                       │ (evaluation guides search)
         ▼                       ▼
         └───────────┬───────────┘
                     │
                     ▼
            Phase 5: Hand Trap Analysis
                     │
                     │ DEPENDS ON:
                     │ - Optimal play from Phase 4
                     │ - Board evaluation from Phase 3
                     │
                     ├── 5.1 Identify choke points
                     ├── 5.2 Fork on interrupts
                     └── 5.3 Resilience scoring
                          │
                          ▼
            Phase 6: Any-Hand Generalization
                     │
                     │ DEPENDS ON:
                     │ - Per-hand analysis from Phase 4/5
                     │
                     ├── 6.1 Hand enumeration
                     ├── 6.2 Aggregate statistics
                     └── 6.3 Consistency metrics
                          │
                          ▼
            Phase 7: Deck Building
                     │
                     │ DEPENDS ON:
                     │ - Deck-wide statistics from Phase 6
                     │
                     ├── 7.1 Variant comparison
                     └── 7.2 Optimization recommendations

LEGEND:
  ✅ = Complete
  ◀─ = Feedback loop (later phase informs earlier)
  ▼  = Forward dependency
```

### Critical Path

The minimum path to useful results:

```
Phase 1 → Phase 2.2 (decision) → Phase 4 (find target board)
                                      │
                                      ▼
                              "Can find Caesar + A Bao A Qu"
```

Everything else (Phase 3, 5, 6, 7) provides additional value but isn't blocking.

---

## Appendix J: Session Timeline

| Date | Milestone |
|------|-----------|
| 2026-01-24 | Phase 1 complete: state representation verified |
| 2026-01-24 | Verification run: 1000 paths, 39.3% hit rate |
| 2026-01-24 | Discovered Tract vs Sanct ordering issue |
| 2026-01-24 | Roadmap created with full documentation |
| 2026-01-25 | Project reorganization: archived deprecated code, consolidated directories |
| 2026-01-25 | Issues 1-5 fixed (critical: MSG_SELECT_OPTION, circular import, eviction, shutdown) |
| 2026-01-25 | Issues 9-16 fixed (CFFI layer: platform compat, constants, test locations) |
| 2026-01-25 | Issues 6-8 fixed (minor: test constants, docs, type hints) |
| 2026-01-25 | Test files relocated to tests/unit/ and tests/integration/ |

---

## Appendix K: Rollback Points

If current approach fails, fallback options:

| Trigger | Fallback |
|---------|----------|
| MCTS doesn't find target boards | Return to exhaustive with deeper limits |
| State space too large | Reduce library to core 15 cards |
| Evaluation function inaccurate | Use pure depth as proxy (shorter = better) |
| Memory exhaustion | Stream results to disk, process in batches |
| Performance too slow | Parallelize across hands, not paths |

---

*Document version: 3.1*
*Last updated: 2026-01-25*
*This document is a living roadmap. Update as work progresses.*
