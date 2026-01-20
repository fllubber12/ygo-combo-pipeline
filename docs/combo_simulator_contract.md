# Combo Simulator Contract (Tier 1)

## Scope
Tier 1 targets solitaire combo evaluation only. There is no opponent interaction, no chain stack modeling, and no live response logic. The simulator focuses on deterministic, reproducible combo lines from a fixed starting hand and deck state.

## GameState Schema
GameState is a structured, serializable object with explicit zones and counters.

### Zones
- Deck: ordered list of card CIDs
- Hand: multiset of card CIDs
- GY: multiset of card CIDs
- Banished: multiset of card CIDs
- Field:
  - Monster Zones: 5 slots with face/position metadata
  - Spell/Trap Zones: 5 slots with face/position metadata
  - Field Zone: 1 slot with face/position metadata
  - Extra Monster Zones: 2 slots with face/position metadata
- Extra Deck: multiset of card CIDs

### Face/Position
- face: face-up / face-down
- position: attack / defense (monsters only)

### Counters / Turn State
- normal_summon_used: boolean
- draws_this_turn: integer
- discards_this_turn: integer
- search_count: integer
- special_summon_count: integer
- opt_used: map of {cid_or_effect_id: {turn_id, count}}
- restrictions: list of active restrictions (e.g., attribute/type locks)

## Event Log Schema
Each action emits an event record for auditability:
- event_id
- turn_id
- action_type: draw | discard | send_to_gy | banish | summon | activate | move | search | restriction | opt
- source: {zone, cid, metadata}
- target: {zone, cid, metadata}
- count
- notes

## Action Primitives
- move: move a card between zones (with face/position updates)
- summon: normal/special/ritual/fusion/synchro/xyz/link
- search: move from Deck to Hand (with reveal flag)
- apply_restriction: add a restriction to GameState
- mark_opt: record OPT usage for a card/effect

## Legality Rules Checklist
- Normal Summon/Set: at most 1 per turn
- Special Summons: allowed unless restricted by active locks
- Link Summon:
  - meet material count and requirement types
  - obey placement rules (Extra Monster Zones or linked zones)

## Search Strategy Overview
Tier 1 uses deterministic search with bounded exploration:
- DFS or beam search with configurable depth/width
- Pruning rules:
  - repeated states (hash-based)
  - illegal states (legality checklist)
  - dominated states (worse resources)
- Scoring:
  - reward board presence, resource gain, and combo objectives
  - penalty for dead ends and excessive resource loss

## Not in Tier 1
- Chain stack resolution
- Opponent responses or interaction
- Full PSCT parsing or semantic effect interpretation
