# YGO-Agent Architecture Analysis

## Overview

[ygo-agent](https://github.com/sbl1996/ygo-agent) is a deep reinforcement learning project for Yu-Gi-Oh! that provides:
- High-performance game environment (ygoenv) built on envpool
- RL agents using PPO with JAX/Flax
- Support for both ygopro-core and edopro-core

## 1. State Representation

### 1.1 Card Features (41 dimensions per card)

Each card is encoded as a 41-byte vector:

| Index | Feature | Encoding |
|-------|---------|----------|
| 0-1 | Card ID | 16-bit (high/low byte) |
| 2 | Location | 1=deck, 2=hand, 3=mzone, 4=szone, 5=grave, 6=removed, 7=extra |
| 3 | Sequence | Position in zone (0 for non-field) |
| 4 | Controller | 0=me, 1=opponent |
| 5 | Position | 0-8 (faceup/down, attack/defense) |
| 6 | Overlay | 0/1 (is XYZ material) |
| 7 | Attribute | 0-7 (earth, water, fire, wind, light, dark, divine) |
| 8 | Race | 0-26 (warrior, spellcaster, etc.) |
| 9 | Level | 0-13 (capped) |
| 10 | Counter | 0-15 (spell counters, etc.) |
| 11 | Negated | 0/1 (effect negated) |
| 12-13 | ATK | 16-bit float transform |
| 14-15 | DEF | 16-bit float transform |
| 16-40 | Type flags | 25 bits for monster/spell/trap subtypes |

**Key insight**: They use a learned embedding for card IDs (up to 999 unique cards + 1 unknown), not raw passcodes.

### 1.2 Global Features (23 dimensions)

| Index | Feature |
|-------|---------|
| 0-1 | My LP (16-bit) |
| 2-3 | Opponent LP (16-bit) |
| 4 | Turn count (0-16) |
| 5 | Phase ID (0-9) |
| 6 | Is first player (0/1) |
| 7 | Is my turn (0/1) |
| 8-21 | Card counts per location (14 zones) |
| 22 | Reserved |

### 1.3 Action Features (12 dimensions per action)

| Index | Feature |
|-------|---------|
| 0 | Card index (reference to cards array) |
| 1-2 | Card ID (16-bit) |
| 3 | Message type (1-15) |
| 4 | Action type (0-9: none, set, repo, spsummon, summon, etc.) |
| 5 | Finish flag (for multi-select) |
| 6 | Effect index (0-255) |
| 7 | Phase (0-3: none, battle, main2, end) |
| 8 | Position (0-8) |
| 9 | Number (for announce_number) |
| 10 | Place (0-30: zone selection) |
| 11 | Attribute (for announce_attrib) |

### 1.4 History Actions (32 x 14)

Tracks last 32 actions with turn/phase information for temporal context.

## 2. ygopro-core Integration

### 2.1 API Wrapper

They wrap the OCG API with convenience functions:

```cpp
// Create duel with options
OCG_DuelOptions YGO_CreateDuel(seed, init_lp, startcount, drawcount);
int create_status = OCG_CreateDuel(&pduel_, opts);

// Load utility scripts
g_ScriptReader(nullptr, pduel_, "constant.lua");
g_ScriptReader(nullptr, pduel_, "utility.lua");

// Add cards
OCG_NewCardInfo info = {team, duelist, code, con, loc, seq, pos};
OCG_DuelNewCard(pduel, info);

// Process and respond
int status = OCG_DuelProcess(pduel);
uint8_t* buf = OCG_DuelGetMessage(pduel, &len);
OCG_DuelSetResponse(pduel, response, len);
```

### 2.2 Message Handling

They handle ALL message types systematically:

```cpp
// Decision messages that branch
MSG_SELECT_IDLECMD, MSG_SELECT_CHAIN, MSG_SELECT_CARD,
MSG_SELECT_TRIBUTE, MSG_SELECT_POSITION, MSG_SELECT_EFFECTYN,
MSG_SELECT_YESNO, MSG_SELECT_BATTLECMD, MSG_SELECT_UNSELECT_CARD,
MSG_SELECT_OPTION, MSG_SELECT_PLACE, MSG_SELECT_SUM,
MSG_SELECT_DISFIELD, MSG_ANNOUNCE_ATTRIB, MSG_ANNOUNCE_NUMBER
```

### 2.3 Response Formats

Same as our implementation:
```cpp
// IDLE: (index << 16) | action_type
// action_type: 0=summon, 1=spsummon, 2=repos, 3=mset, 4=set, 5=activate, 6=battle, 7=end

// SELECT_CARD: 4-byte header + indices
// SELECT_PLACE: 3 bytes (player, location, sequence)
// SELECT_CHAIN: -1 to decline, index to activate
```

## 3. Neural Network Architecture

### 3.1 Encoder Stack

1. **Card Encoder**: Embeds each card feature separately, concatenates, passes through MLP
2. **Global Encoder**: Embeds global features, applies LayerNorm
3. **Action Encoder**: Embeds action features for policy head
4. **Transformer Layers**: 2+ encoder layers for card sequence processing

### 3.2 Policy/Value Heads

- Uses attention between cards and action embeddings
- Outputs action probabilities and state value
- Optional LSTM for history tracking

```python
class Encoder(nn.Module):
    channels: int = 128
    num_layers: int = 2  # Transformer layers
    embedding_shape: (999, 1024)  # Card ID embeddings
```

## 4. Reward Structure

```cpp
// Greedy reward based on turn count (incentivizes fast wins)
if (greedy_reward_) {
    if (turn_count_ <= 2) base_reward = 16.0;
    else if (turn_count_ <= 4) base_reward = 8.0;
    else if (turn_count_ <= 6) base_reward = 4.0;
    else if (turn_count_ <= 8) base_reward = 2.0;
    else base_reward = 0.5 + 1.0 / (turn_count_ - 7);
}
// Simple reward
else base_reward = 1.0;

reward = (winner == ai_player_) ? base_reward : -base_reward;
```

## 5. Key Architectural Decisions

### 5.1 Card ID Embedding
- Map passcodes to sequential IDs (0-999)
- Use learned embeddings (1024 dims)
- Unknown cards map to ID 0

### 5.2 Spec System
- Cards referenced by "spec" strings: `m1`, `s2`, `oh3` (opponent hand 3)
- Links cards between state and actions

### 5.3 Max Limits
- `MAX_CARDS = 80` (both players)
- `MAX_ACTIONS = 24` (truncated if more)
- `N_HISTORY_ACTIONS = 32`

### 5.4 Opponent Information
- `oppo_info` flag controls whether opponent's hidden cards are visible
- For self-play training vs human play

## 6. What We Can Learn/Reuse

### 6.1 State Encoding
Their 41-feature card encoding is well-designed:
- Compact but information-rich
- Handles hidden information properly
- Uses float transform for ATK/DEF to normalize

**Recommendation**: Adopt similar encoding for our combo evaluator.

### 6.2 Action Handling
Their legal_actions system with specs is cleaner than raw indices:
- `LegalAction` class with all action metadata
- `spec` strings for card references
- Response encoding handled per message type

**Recommendation**: Refactor our action handling to use similar abstraction.

### 6.3 History Tracking
They track 32 previous actions with turn/phase context for temporal reasoning.

**Recommendation**: Could be useful for combo sequencing - understanding what actions lead to good outcomes.

### 6.4 Reward Shaping
Their greedy reward incentivizes fast wins (turn 1-2 = 16x reward).

**Recommendation**: For combo evaluation, we could use similar rewards for reaching target boards quickly.

## 7. Differences from Our Approach

| Aspect | ygo-agent | Our Implementation |
|--------|-----------|-------------------|
| Language | C++ (envpool) | Python (CFFI) |
| Purpose | RL training | Combo enumeration |
| State | Fixed-size arrays | Dynamic parsing |
| Actions | Truncated to 24 | All enumerated |
| Cards | 999 ID embedding | Raw passcodes |

## 8. Potential Integration Points

1. **Card Encoding**: Use their 41-feature format for board state hashing
2. **Action Abstraction**: Adopt LegalAction class pattern
3. **Reward Design**: Apply greedy reward concept to combo evaluation
4. **History**: Track action sequences like their h_actions for pattern learning

## 9. Repository Structure

```
ygo-agent/
├── ygoenv/           # Game environment
│   └── ygoenv/
│       ├── core/     # envpool infrastructure
│       ├── ygopro/   # ygopro-core wrapper
│       └── edopro/   # edopro-core wrapper
├── ygoai/            # AI agents
│   └── rl/
│       ├── jax/      # JAX implementations
│       └── ppo.py    # PPO algorithm
├── ygoinf/           # Inference server
│   └── ygoinf/
│       ├── features.py  # Feature encoding
│       └── server.py    # API server
├── mcts/             # Monte Carlo Tree Search
│   └── alphazero/
└── scripts/          # Training/eval scripts
```
