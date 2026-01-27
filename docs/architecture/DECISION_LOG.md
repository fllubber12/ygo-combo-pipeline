# Architecture Decision: Combo Enumeration Search Strategy

## Executive Summary

After comprehensive research, **Option 3 (IDDFS + Proper State Tracking)** is the recommended approach. MCTS is fundamentally unsuited for our problem because we need complete enumeration, not optimization. The "state machine" approach (Option 1) is actually just a specific implementation of proper backtracking, which IDDFS already provides when implemented correctly.

---

## Problem Definition: What Are We Actually Solving?

### Our Goal
**Find ALL valid combo sequences** from a given starting hand that reach specific board states (e.g., A Bao A Qu + Caesar on field).

### Critical Requirements
| Requirement | Description |
|-------------|-------------|
| **Completeness** | Must find ALL valid combos, not just one or "best" |
| **Determinism** | Same input → same output (reproducible) |
| **Shortest-first** | Prefer shorter combos (more efficient plays) |
| **Scalability** | Must handle 5-card hands (~48^5 potential combinations) |
| **Correctness** | No infinite loops, no missed paths |

### Current Bug Analysis
The SELECT_SUM_CANCEL bug is a **failed choice tracking problem**:
```
1. Engine offers choices: [Duke, Aerial Eater, ...]
2. DFS picks Duke (index 0)
3. Fusion fails → SELECT_SUM_CANCEL
4. Engine re-prompts same choice
5. DFS picks Duke AGAIN (same index) ← INFINITE LOOP
```

This is NOT a search algorithm problem—it's a **state management problem**.

---

## Option 1: Proper State Machine with Exploration Tracking

### Concept
Build a general "exploration state" tracker that remembers which actions have been tried at each game state.

```python
class ExplorationState:
    def __init__(self):
        self.tried_at_state = {}  # state_hash -> set of (action_type, action_id)
    
    def mark_tried(self, state_hash, action):
        """Mark an action as tried at this state."""
        
    def get_untried(self, state_hash, available_actions):
        """Return only actions we haven't tried yet."""
        
    def mark_failed(self, state_hash, action):
        """Mark an action as tried AND failed (don't retry on backtrack)."""
```

### Research Assessment

| Aspect | Assessment |
|--------|------------|
| **Completeness** | ✅ Yes, if implemented correctly |
| **Complexity** | Medium - requires careful state hashing |
| **Novelty** | Low - this is standard backtracking |
| **Risk** | Medium - must handle all choice types |

### Key Insight
This is **not a different algorithm**—it's a proper implementation of backtracking. The standard backtracking framework already includes:
- `make_choice(state, choice)` - try a choice
- `undo_choice(state, choice)` - backtrack
- `is_valid(state, choice)` - check if choice should be tried

Our bug exists because we're not properly tracking "failed" choices separately from "untried" choices.

---

## Option 2: Monte Carlo Tree Search (MCTS)

### Concept
Use random simulation to estimate the value of different paths, focusing search on "promising" branches.

### Research Findings

#### MCTS Strengths
1. **No heuristic required** - works without evaluation function
2. **Anytime algorithm** - can stop at any point and get a result
3. **High branching factor tolerance** - handles games like Go well
4. **Asymmetric tree growth** - focuses on promising areas

#### MCTS Weaknesses (Critical for Our Problem)
1. **Designed for optimization, NOT enumeration**
   - MCTS finds the "best" move, not ALL valid paths
   - Quote from research: "The focus of MCTS is on the analysis of the most promising moves"

2. **Probabilistic, NOT deterministic**
   - Different runs may give different results
   - Cannot guarantee finding all combos

3. **Requires evaluation function**
   - How do we "score" a partial combo?
   - Is reaching Aerial Eater better than reaching Duke? (We don't know until the end)

4. **Can miss critical paths ("trap states")**
   - Quote from Wikipedia: "MCTS may not 'see' such lines due to its policy of selective node expansion"
   - Our A Bao A Qu combo is EXACTLY this—a deep, narrow path easily missed

5. **Research shows IDA* beats MCTS for puzzles with good heuristics**
   - Quote from Sokoban paper: "IDA* still provides the best performance"
   - SP-MCTS solved ~85% of levels; IDA* solved more

### Assessment for Our Problem

| Aspect | Assessment |
|--------|------------|
| **Completeness** | ❌ No - by design, skips "unpromising" paths |
| **Determinism** | ❌ No - random sampling |
| **Shortest-first** | ❌ No - no guarantee |
| **Requires evaluation** | ❌ Yes - we don't have one |
| **Implementation complexity** | High |

### Verdict: **NOT SUITABLE**
MCTS is designed for a fundamentally different problem (optimization/game-playing), not complete enumeration.

---

## Option 3: IDDFS + Transposition Table + Proper Backtracking

### Concept
Use Iterative Deepening DFS with a transposition table for duplicate detection, combined with proper failed-choice tracking.

### Research Findings

#### IDDFS Strengths
1. **Completeness guaranteed** - will find all solutions at each depth
2. **Optimal** - finds shortest solutions first
3. **Memory efficient** - O(bd) space like DFS
4. **Proven in chess engines** - decades of successful use

#### Transposition Table Benefits
1. **Avoids re-exploring duplicate states**
2. **Stores best move from previous iterations** - improves ordering
3. **Enables iterative deepening efficiency** - previous work not wasted

#### Key Research Quote
> "Iterative deepening, using a transposition table, embed the depth-first algorithms like alpha-beta into a framework with best-first characteristics."
> — Chess Programming Wiki

### What's Missing in Our Current Implementation

1. **Failed choice tracking**
   ```python
   # Current: Only tracks "visited states"
   transposition_table[state_hash] = result
   
   # Needed: Also track "failed actions at this state"
   failed_actions[state_hash] = {(SELECT_CARD, duke_id), ...}
   ```

2. **Proper backtracking on failure**
   ```python
   # When SELECT_SUM_CANCEL happens:
   def handle_select_sum_cancel(state_hash, last_choice):
       failed_actions[state_hash].add(last_choice)
       # Don't retry this choice when we return to this state
   ```

3. **Coarsened state hash**
   - Current: Includes legal actions in hash (high collision rate)
   - Needed: Board-only hash (better transposition detection)

### Assessment for Our Problem

| Aspect | Assessment |
|--------|------------|
| **Completeness** | ✅ Yes - exhaustive at each depth |
| **Determinism** | ✅ Yes - same order every time |
| **Shortest-first** | ✅ Yes - by design |
| **Memory efficient** | ✅ Yes - O(bd) |
| **Implementation** | ✅ Already partially implemented |

---

## Comparative Analysis

| Criterion | State Machine | MCTS | IDDFS + TT |
|-----------|---------------|------|------------|
| Find ALL combos | ✅ Yes | ❌ No | ✅ Yes |
| Deterministic | ✅ Yes | ❌ No | ✅ Yes |
| Shortest first | ⚠️ Depends | ❌ No | ✅ Yes |
| No evaluation needed | ✅ Yes | ❌ No | ✅ Yes |
| Memory efficient | ⚠️ Medium | ❌ No | ✅ Yes |
| Already implemented | ❌ No | ❌ No | ⚠️ Partial |
| Proven for similar problems | ✅ Yes | ❌ No | ✅ Yes |

---

## The Real Problem: What Needs Fixing

The core issue is NOT the search algorithm choice. It's the **lack of proper backtracking semantics**.

### Current Flow (Broken)
```
State S1 → SELECT_CARD [A, B, C]
         → Choose A
         → SELECT_SUM fails
         → SELECT_SUM_CANCEL
         → Back to SELECT_CARD [A, B, C]  ← SAME LIST!
         → Choose A again                  ← LOOP!
```

### Required Flow (Fixed)
```
State S1 → SELECT_CARD [A, B, C]
         → Choose A
         → SELECT_SUM fails
         → SELECT_SUM_CANCEL
         → Mark (S1, A) as FAILED
         → Back to SELECT_CARD [A, B, C]
         → Filter: [B, C]                  ← A excluded!
         → Choose B
         → (continues normally)
```

### Implementation Requirements

1. **Track failed actions per state**
   ```python
   class ComboEnumerator:
       def __init__(self):
           self.failed_at_state = {}  # state_hash -> set of action_ids
   ```

2. **Handle all "cancel" events**
   - SELECT_SUM_CANCEL
   - SELECT_CARD (when following choices fail)
   - YES/NO decisions that lead to dead ends

3. **Proper backtracking**
   ```python
   def backtrack(self):
       # Pop last choice from path
       last_state, last_action = self.path.pop()
       # Mark as failed so we don't retry
       self.mark_failed(last_state, last_action)
       # Return to last state
       self.restore_state(last_state)
   ```

---

## Recommendation

### Primary: Implement IDDFS + Proper Backtracking

1. **Keep IDDFS as the search strategy**
   - Already implemented in `iterative_deepening.py`
   - Guarantees shortest combos first
   - Memory efficient

2. **Add failed action tracking**
   ```python
   # In combo_enumeration.py
   self.failed_actions = {}  # state_hash -> set(action_ids)
   
   def get_valid_choices(self, state_hash, all_choices):
       failed = self.failed_actions.get(state_hash, set())
       return [c for c in all_choices if c['id'] not in failed]
   
   def mark_action_failed(self, state_hash, action_id):
       if state_hash not in self.failed_actions:
           self.failed_actions[state_hash] = set()
       self.failed_actions[state_hash].add(action_id)
   ```

3. **Handle SELECT_SUM_CANCEL properly**
   ```python
   def handle_select_sum_cancel(self, state_hash, last_card_id):
       self.mark_action_failed(state_hash, last_card_id)
       # Continue to retry with remaining options
   ```

4. **Coarsen state hash**
   - Remove legal actions from hash
   - Use only: cards in zones, life points, counters, etc.

### Why NOT MCTS

| Reason | Impact |
|--------|--------|
| Can't guarantee finding all combos | Fatal - violates core requirement |
| Random sampling = non-deterministic | Fatal - can't reproduce results |
| Requires evaluation function | We don't have one for partial combos |
| Overkill complexity | Simple backtracking fix solves the problem |

### Why NOT "New State Machine"

The "state machine" concept is just proper backtracking. We don't need a new architecture—we need to fix the existing one to properly track failed choices.

---

## Implementation Roadmap

### Phase 1: Fix the Bug (Immediate)
- [ ] Add `failed_actions` tracking to `ComboEnumerator`
- [ ] Handle `SELECT_SUM_CANCEL` by marking choice as failed
- [ ] Test: Verify Aerial Eater is selected after Duke fails
- [ ] Test: Verify A Bao A Qu combo is found

### Phase 2: Optimize State Hashing (This Week)
- [ ] Coarsen intermediate state hash (board-only)
- [ ] Measure transposition table hit rate improvement
- [ ] Verify no false positives (different states with same hash)

### Phase 3: Enable IDDFS as Default (This Week)
- [ ] Switch from DFS to IDDFS as primary search
- [ ] Measure: Time to find gold standard combo
- [ ] Measure: Total unique combos found

### Phase 4: 5-Card Hand Scaling (Next Week)
- [ ] Budget allocation per starter card
- [ ] Parallel enumeration with shared transposition table
- [ ] Benchmark on diverse hand samples

---

## Conclusion

**IDDFS + Proper Backtracking** is the clear winner:

1. **It's the right algorithm for enumeration problems** (not MCTS)
2. **We already have it partially implemented** (just needs fixes)
3. **The "bug" is a backtracking implementation issue**, not an algorithm choice issue
4. **Research confirms IDA*/IDDFS beats MCTS for puzzles** when you need complete solutions

The path forward is clear: fix the failed-choice tracking, enable IDDFS, and scale to 5-card hands.
