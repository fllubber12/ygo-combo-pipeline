# Yu-Gi-Oh Rules Baseline for Simulation (TCG)

## Scope
This baseline targets TCG Advanced Format under the current Master Rule, aligned with the official TCG rulebook and the 2021 Rules Update. It is the source of truth for simulator legality and timing.

## Authoritative Sources
- Official Yu-Gi-Oh! TRADING CARD GAME Rulebook (current)
- Yu-Gi-Oh! TCG 2021 Rules Update
- Konami: Understanding Card Text (Part 3)
- Konami: Understanding Card Text (Part 5)
- Konami: Fast Effect Timing page

## Rules Coverage Checklist

### 1) Setup & Deckbuilding Constraints
- Deck size and side/extra deck limits per TCG Advanced Format.
- Starting hand size and mulligan rules (none in TCG).
- Card legality must follow the current banlist for the declared format.

Simulator Invariants:
- Main Deck size is within legal bounds at game start.
- Extra Deck size is within legal bounds at game start.
- Side Deck size is within legal bounds at game start.
- Starting hand size equals TCG standard; no mulligans.

### 2) Zones & Public/Private Information
- Public zones: field, GY, banished (face-up), face-up extra deck.
- Private zones: hand, deck, face-down banished, set cards.
- Ownership vs control must be tracked for all zones.

Simulator Invariants:
- Zone contents always match visibility rules (no hidden info leaks).
- Ownership and control are tracked for each card instance.
- Face-down cards reveal only when rules allow.

### 3) Turn Structure & Phases
- Draw Phase, Standby Phase, Main Phase 1, Battle Phase, Main Phase 2, End Phase.
- Turn player priority and timing windows follow Fast Effect Timing.

Simulator Invariants:
- Phase order is enforced; no action may occur in an invalid phase.
- Turn player priority is enforced at each timing window.

### 4) Summoning
- Normal Summon/Set, Tribute Summon/Set, Flip Summon, Special Summon.
- Fusion, Synchro, Xyz, Link, Pendulum Summons follow Master Rule placement.

Simulator Invariants:
- Normal Summon/Set count <= 1 per turn unless an effect grants extra.
- Tribute requirements are enforced by Level.
- Extra Deck monsters are placed in legal zones only.
- Pendulum Summons use legal scales and placement rules.
- Materials and requirements are validated for Fusion/Synchro/Xyz/Link.

### 5) Spell/Trap Rules + Spell Speed
- Activation legality by type, timing, and zone.
- Spell Speed hierarchy and restrictions on responses.

Simulator Invariants:
- Spell/Trap activations respect timing and speed rules.
- Continuous/Field/Equip/Quick-Play limitations are enforced.

### 6) Chains + Timing Windows + PSCT Execution Contract
- Chain building, response windows, and resolution order.
- PSCT colon/semicolon model determines activation vs effect resolution.

Simulator Invariants:
- Chain links resolve LIFO with no illegal interruptions.
- Fast Effect Timing windows are respected for all responses.
- PSCT parsing follows colon/semicolon execution semantics.

### 7) Battle Phase + Damage Step
- Attack declarations, replay rules, and targeting.
- Damage Step sub-steps and effect timing.

Simulator Invariants:
- Attacks occur only in Battle Phase and obey legality rules.
- Damage Step windows are enforced for activation eligibility.

### 8) State Tracking Requirements
- Counters: normal summon used, additional summon grants, OPT usage.
- Chain history and effect usage tracking.
- Zone contents + public/private visibility.
- Draw/discard/send/banish counters for auditability.

Simulator Invariants:
- OPT usage is tracked per card/effect and enforced across turns.
- Chain history and zone state updates are consistent and reproducible.
- Draw/discard/send/banish counters are incremented for each event.
