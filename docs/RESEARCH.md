# YuGiOh Combo Enumeration Pipeline: Research Report

## Executive Summary

After extensive research across game AI, card game-specific projects, YuGiOh community tools, and academic literature, I've identified several key approaches and existing projects that are highly relevant to our combo enumeration pipeline. This report synthesizes findings to help us evaluate our current approach and identify potential improvements.

---

## Part 1: Existing YuGiOh AI Projects

### 1.1 ygo-agent (sbl1996) - **Most Advanced**
**URL**: https://github.com/sbl1996/ygo-agent

**Architecture**:
- High-performance game environment (ygoenv) built on envpool + ygopro-core
- Deep reinforcement learning with JAX/Flax
- RNN-based actor-critic architecture with specialized encoders
- LSTM/RWKV for temporal context
- LLM embeddings for card text understanding

**Key Technical Details**:
- Observation space: 160 cards × 41 features each
- History buffer: 16 recent actions × 14 features
- Action space: Simple index selection from legal actions
- Card features: ID embedding, location, owner, position, ATK/DEF (binned), attribute, race, level, counter, negated
- Transformer layers for card relationship modeling

**Training**:
- Distributed training on 8×4090 GPUs for days
- Self-play reinforcement learning
- 100M+ game simulations for strong agents

**Relevance to Our Project**:
- **CRITICAL**: They've solved the ygopro-core integration problem
- Their feature engineering is sophisticated and battle-tested
- They use end-to-end RL rather than explicit combo enumeration
- Different goal: full game play vs. our combo discovery focus

### 1.2 WindBot (IceYGO)
**URL**: https://github.com/IceYGO/windbot

**Architecture**:
- C# bot for ygopro/ygosharp
- Rule-based AI with hand-coded deck executors
- Each deck has custom logic (e.g., `AI_Blue-Eyes.cs`)

**Relevance**:
- Contains expert human knowledge of combos encoded as rules
- Good source for validating discovered combos
- Shows the "manual" approach we're trying to automate

### 1.3 YugiohAi (crispy-chiken)
**URL**: https://github.com/crispy-chiken/YugiohAi

**Architecture**:
- Python deck building AI + C# game AI
- Uses EDOPro for simulation
- Training via self-play with win rate tracking

**Relevance**:
- Hybrid approach (deck building + gameplay)
- Less mature than ygo-agent but different design philosophy

### 1.4 Probability Calculators

**YGOProbCalc** (flipflipshift):
- Java-based
- Describes card functions, auto-discovers combos per hand
- Calculates consistency statistics

**ygo-advanced-probability-calculator** (SeyTi01):
- Combinatorial probability for category-based constraints
- Tags cards (Starter, Extender, etc.)
- Calculates exact opening hand probabilities

**YGO-Combo-Simulator** (SpearKitty):
- Monte Carlo simulation for consistency testing
- NOT exact calculation - statistical approximation

**Relevance**:
- These focus on "can I open this combo?" not "what combos exist?"
- Our pipeline discovers combos; these analyze known combos
- Complementary tools, not competitors

---

## Part 2: Academic Approaches to Card Game AI

### 2.1 Monte Carlo Tree Search (MCTS)

**Core Algorithm**:
1. Selection: UCB1 formula balances exploration/exploitation
2. Expansion: Add child nodes for unexplored actions
3. Simulation: Random playout to terminal state
4. Backpropagation: Update statistics along path

**Card Game Applications**:
- Magic: The Gathering (Ensemble Determinization)
- Hearthstone (MCTS + Neural Networks)
- Dou Di Zhu (Information Set MCTS)
- Hearts, Bridge, Poker

**Key Challenge**: Hidden information requires "determinization" - sampling possible opponent hands

**Relevance to Our Project**:
- MCTS is excellent for gameplay decisions
- Less suited for exhaustive combo enumeration
- Our current approach (exhaustive search with pruning) may be more appropriate for combo discovery
- MCTS could be useful for evaluating discovered combos against disruption

### 2.2 Information Set MCTS (ISMCTS)

**Innovation**: Instead of determinizing hidden info, operate directly on information sets (sets of possible game states consistent with observations)

**Advantages**:
- Handles "strategy fusion" problem in determinization
- More principled for imperfect information

**Relevance**:
- Important if we extend to consider opponent interaction
- Current "solitaire" combo enumeration doesn't need this

### 2.3 Hearthstone AI Research

**Key Paper**: "Improving Hearthstone AI by Combining MCTS and Supervised Learning" (2018)

**Approach**:
- MCTS for action selection
- Neural network value/policy functions
- Iterative improvement: MCTS generates training data → train network → better MCTS

**Key Paper**: "Mastering Strategy Card Game (Hearthstone) with Improved Techniques" (2023)

**Approach**:
- End-to-end policy function
- Optimistic smooth fictitious play
- Defeated top-10 China players

**Relevance**:
- Shows RL can master complex card games
- Their combo handling is implicit in the policy network
- We're doing explicit combo discovery which is different

### 2.4 Alpha-Beta / Minimax Hybrids

**MCTS-αβ Hybrid** (Baier 2017):
- Combines MCTS strategic strength with minimax tactical strength
- Two types of rollouts: MCTS and alpha-beta
- Nodes accumulate both value estimates and bounds

**Relevance**:
- Our combo enumeration is more like exhaustive search than gameplay search
- But hybrid ideas could help when we evaluate combo quality

---

## Part 3: Search Algorithm Analysis for Combo Enumeration

### 3.1 Our Current Approach Assessment

**Current Design** (based on audit):
- Exhaustive DFS through game tree
- Transposition table for memoization
- State hashing for duplicate detection
- Pruning via "interesting action" filtering

**Strengths**:
- Guaranteed to find all combos (completeness)
- Deterministic and reproducible
- Can track exact combo paths

**Weaknesses**:
- Exponential worst-case complexity
- May waste time on suboptimal branches
- No built-in quality ranking during search

### 3.2 Alternative Approaches Considered

**A. Beam Search**
- Keep only top-k most promising partial combos
- Trade completeness for speed
- Risk missing rare but powerful combos

**B. Iterative Deepening**
- Search to depth 1, then 2, then 3...
- Find shortest combos first
- Good for "minimum resource" optimization

**C. Best-First Search / A***
- Priority queue by heuristic value
- Need good heuristic for "combo potential"
- Could prioritize paths leading to strong boards

**D. Monte Carlo Sampling**
- Random playouts to estimate combo quality
- Good for huge search spaces
- Gives approximate, not exact, results

### 3.3 Recommendation

**Stick with exhaustive search BUT add:**

1. **Better Pruning Heuristics**:
   - Prune branches that can't improve on best known combo
   - Use card role analysis (starter/extender/payoff)

2. **Iterative Deepening Wrapper**:
   - First find all depth-1 combos, then depth-2, etc.
   - Enables anytime behavior (stop when satisfied)

3. **Quality-Guided Ordering**:
   - Explore "likely good" branches first
   - Use board evaluation to prioritize

4. **Parallel Search**:
   - Different starting hands can be searched independently
   - Embarrassingly parallel structure

---

## Part 4: Feature Engineering Insights from ygo-agent

### 4.1 Card Representation (41 features per card)

| Feature | Encoding | Notes |
|---------|----------|-------|
| Card ID | 2 bytes → embedding | LLM-based embeddings available |
| Location | Categorical | Deck/Hand/Field/GY/Banished/Extra |
| Owner | Binary | Player 1 or 2 |
| Position | Categorical | ATK/DEF/Face-down |
| Attribute | Categorical | DARK/LIGHT/FIRE/etc |
| Race | Categorical | Dragon/Spellcaster/etc |
| Level/Rank | Integer | 1-12 |
| ATK/DEF | 16-bit float (2 bytes each) | Binned encoding |
| Counters | Integer | Spell counters, etc |
| Negated | Binary | Is effect negated? |

### 4.2 Global State Features (23 features)

- Turn count
- Phase
- Life points (both players)
- Cards in hand/deck/GY (both players)
- Normal summon available
- Battle phase availability

### 4.3 Action History (16 × 14 features)

Circular buffer of recent actions with:
- Action type
- Card involved
- Position/location changes
- Result

**Relevance**: Our state_representation.py could adopt similar encoding for better ML integration later.

---

## Part 5: Gaps and Opportunities

### 5.1 What Nobody Has Built (Our Niche)

1. **Exhaustive Combo Enumerator**: Projects focus on play, not discovery
2. **Hand→Board Mapping**: Given opening hand, what are ALL possible end boards?
3. **Combo Database Generator**: Automated creation of combo guides
4. **Consistency Analyzer**: Beyond probability, analyze combo tree structure

### 5.2 Integration Opportunities

1. **Use ygo-agent's Environment**: Their ygoenv is mature and fast
2. **Leverage LLM Embeddings**: Their card text embeddings could improve our analysis
3. **Validate Against WindBot**: Their hand-coded combos are ground truth
4. **Feed Back to RL**: Discovered combos could bootstrap RL training

### 5.3 Technical Improvements to Consider

| Area | Current | Potential Improvement |
|------|---------|----------------------|
| Engine | ygopro-core direct | Consider ygoenv wrapper |
| State Encoding | Custom | Adopt ygo-agent's 41-feature encoding |
| Parallelism | Single-threaded | Multi-process by starting hand |
| Evaluation | Board heuristics | ML-based quality scoring |
| Pruning | Basic | Card role + resource analysis |

---

## Part 6: Strategic Recommendations

### 6.1 Keep Our Core Approach
- Exhaustive search is correct for our goal (combo discovery)
- RL approaches solve a different problem (gameplay)
- Our transposition table + pruning is sound

### 6.2 Near-Term Improvements (Low Effort, High Value)

1. **Adopt ygo-agent's state encoding** for future ML compatibility
2. **Add iterative deepening** for anytime behavior
3. **Implement parallel search** across different opening hands
4. **Create validation suite** using WindBot's known combos

### 6.3 Medium-Term Enhancements

1. **Integrate board quality ML model** for pruning guidance
2. **Build combo clustering** to group similar lines
3. **Add disruption analysis** via MCTS simulation
4. **Create visualization tools** for combo trees

### 6.4 Long-Term Vision

1. **Hybrid System**:
   - Our exhaustive search finds combo space
   - RL agent learns to navigate it optimally

2. **Generalization**:
   - Train models on discovered combos
   - Enable zero-shot combo discovery for new cards

---

---

## Part 7: Technical Implementation Deep Dive

### 7.1 Transposition Tables - Best Practices

**From Chess Programming Research:**

Our current transposition table implementation can be improved using techniques from chess engines:

**Zobrist Hashing for YuGiOh:**
```
Components to hash (XOR together):
- Card ID × Location (Hand/Field/GY/Banished/Deck/Extra)
- Card position (ATK/DEF/Face-down)
- Card owner (Player 1/2)
- Zone index (which monster zone, which S/T zone)
- Normal summon used this turn
- Battle phase availability
- Turn count
- Player to act
```

**Key Insight**: Zobrist hashing allows O(1) incremental updates:
- When card moves: `hash ^= old_position_key ^ new_position_key`
- No need to recompute full board hash

**Replacement Strategy Options:**
1. **Always Replace**: Simple, but loses valuable deep evaluations
2. **Depth-Preferred**: Keep entries with greater search depth
3. **Two-Tier**: Separate tables for depth-preferred and always-replace
4. **Aging**: Track "freshness" and prefer recent entries

**Recommended for Combo Enumeration:**
- Use depth-preferred replacement (deeper = more valuable combo info)
- Store: hash, depth reached, best continuation, combo quality score

### 7.2 State Hashing for YuGiOh Specifics

**Challenges unique to YuGiOh:**

1. **OPT (Once Per Turn) Tracking**:
   - Many cards have "you can only use this effect once per turn"
   - Must be part of state hash
   - Solution: Bitmap of activated OPT effects

2. **Chain State**:
   - Effects can be chained in response
   - Chain resolution order matters
   - Solution: Include chain stack in hash OR only hash at "stable" states

3. **Resource Tracking**:
   - Normal summon used
   - Extra deck summon constraints (link arrows)
   - Pendulum scales set
   - Solution: Dedicated hash bits for each resource

4. **Hidden Information**:
   - For solitaire combo enumeration: full information available
   - For gameplay: opponent hand unknown
   - Solution: Different hash schemes for different use cases

### 7.3 Pruning Strategies for Combo Enumeration

**From Game AI Research:**

1. **Move Ordering**:
   - Search "likely good" moves first
   - For combos: prioritize starters > extenders > payoffs
   - Use card role analysis to classify

2. **Null Move Pruning** (adapted):
   - Original: "If passing is good, current position is good"
   - For combos: "If we can't improve board with N more actions, stop"
   - Skip branches that can't beat current best combo

3. **Late Move Reductions**:
   - Search later moves to reduced depth
   - For combos: If first 5 actions don't setup combo, reduce search
   - Trust that good combos use efficient action sequences

4. **Futility Pruning**:
   - If position + max possible gain < alpha, prune
   - For combos: If current board + best possible additions < target, prune

### 7.4 Parallel Search Architecture

**Embarrassingly Parallel Structure:**

Our combo enumeration has natural parallelism:
```
For each possible opening hand (C(40,5) = 658,008 hands):
    Enumerate all combos from this hand
    Merge results into global combo database
```

**Implementation Options:**

1. **Process Pool**:
   - Each worker gets subset of hands
   - Workers share read-only card database
   - Workers write to separate result files
   - Main process merges results

2. **Work Stealing**:
   - Central queue of hands to process
   - Workers pull hands as they complete
   - Better load balancing for variable combo complexity

3. **GPU Acceleration** (speculative):
   - Batch evaluation of board states
   - Parallel action generation
   - Limited by ygopro-core being CPU-only

**Recommended**: Start with process pool (simplest), upgrade to work stealing if load imbalance is observed.

### 7.5 Memory Optimization

**State Compression:**

Current YuGiOh state is large. Compression options:

1. **Card ID Compression**:
   - Full card IDs are 32-bit (4 bytes each)
   - Use deck-local indices (8-bit if deck < 256 cards)
   - Save 3 bytes per card reference

2. **Zone Packing**:
   - Monster zones: 5 + 2 EMZ = 7 slots × 2 players = 14 slots
   - S/T zones: 5 + 1 field = 6 slots × 2 players = 12 slots
   - Use bitfield for empty/occupied

3. **Delta Encoding**:
   - Store combo paths as deltas from previous state
   - "Card X from Hand → Field" vs full state dump
   - Massive memory savings for deep combos

**Memory Budget Estimation:**
- 658,008 starting hands
- Average 100 unique board states per hand (conservative)
- 65.8M states to potentially store
- At 100 bytes/state = 6.58 GB (manageable)
- At 1KB/state = 65.8 GB (problematic)

→ Compression is important!

---

## Appendix A: Key GitHub Repositories

| Repository | URL | Focus |
|------------|-----|-------|
| ygo-agent | github.com/sbl1996/ygo-agent | RL gameplay |
| M-YGO-Agent | github.com/KohakuBlueleaf/M-YGO-Agent | Fork with improvements |
| ygo-env | github.com/izzak98/ygo-env | Minimal gym environment |
| windbot | github.com/IceYGO/windbot | Rule-based AI |
| YugiohAi | github.com/crispy-chiken/YugiohAi | Learning bot |
| YGOProbCalc | github.com/flipflipshift/YGOProbCalc | Probability calculator |
| ygo-advanced-probability-calculator | github.com/SeyTi01/ygo-advanced-probability-calculator-web | Combinatorial probability |
| YGO-Combo-Simulator | github.com/SpearKitty/YGO-Combo-Simulator | Monte Carlo consistency |

## Appendix B: Key Academic References

1. Browne et al. (2012) - "A Survey of Monte Carlo Tree Search Methods"
2. Cowling et al. (2012) - "Ensemble Determinization in MCTS for Magic: The Gathering"
3. Świechowski et al. (2018) - "Improving Hearthstone AI by Combining MCTS and Supervised Learning"
4. Silver et al. (2016) - "Mastering the Game of Go with Deep Neural Networks and Tree Search"
5. Baier & Winands (2015) - "Monte-Carlo Tree Search and Minimax Hybrids"

## Appendix C: YuGiOh-Specific Resources

1. NEURON Combo Feature - Official Konami combo sharing tool
2. YGOPRODeck - Community deck/combo database
3. Commander Spellbook (MTG) - Model for combo database structure

---

## Conclusion

Our current approach (exhaustive search with transposition tables and pruning) is **fundamentally sound** for the combo enumeration problem. The main alternatives (MCTS, RL) solve different problems (gameplay optimization).

**Key insight**: ygo-agent proves that ygopro-core integration at scale is feasible, and their feature engineering is mature. We should consider adopting their environment wrapper and state encoding while keeping our exhaustive search core.

**Unique value proposition**: No existing project does what we're building - systematic, exhaustive combo discovery with full path tracking. This fills a gap in the YuGiOh AI ecosystem.
