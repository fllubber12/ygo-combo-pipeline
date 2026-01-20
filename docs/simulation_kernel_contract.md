# Simulation Kernel Contract (Combo Sims)

## Scope
This contract defines the rules-accurate simulation kernel for combo-only evaluation in TCG Advanced Format. It follows the official TCG rulebook, the Fast Effect Timing guide, and PSCT colon/semicolon semantics. The scope is solitaire combo lines and legality enforcement for the active player. Opponent interaction is out of scope for v1.

Out of scope for v1:
- Opponent responses and hand traps
- Full duel completeness (turn player alternation across a full duel)
- Damage calculation resolution and battle step-by-step resolution

## Game State Model
GameState must be fully serializable and deterministic.

### Zones
- Deck: ordered list of card instances
- Hand: multiset of card instances
- Extra Deck: multiset of card instances
- Graveyard: multiset of card instances
- Banished: multiset of card instances
- Field:
  - Monster Zones: 5 slots
  - Spell/Trap Zones: 5 slots
  - Field Zone: 1 slot
  - Extra Monster Zones: 2 slots

### Card Instance Fields
- cid
- name
- owner
- controller
- face: face-up / face-down
- position: attack / defense (monsters only)
- location: zone + index (for field zones)
- attachments: list of attached card instance ids (materials/equips)

### Counters / Turn State
- turn_number
- phase
- turn_player
- normal_summon_set_used (boolean; shared budget for Normal Summon/Set unless an effect grants an extra)
- draws_this_turn
- discards_this_turn
- sends_to_gy_this_turn
- banishes_this_turn
- special_summon_count
- search_count
- opt_used: map of effect_id or cid -> {turn_number, count}
- restrictions: list of active restrictions (type/attribute/zone/summon locks)
- chain: list of pending chain links

## Action Interface
An Action is a pure transition with explicit validation.

### Action Structure
- action_id
- actor (player id)
- action_type
- inputs (targets, costs, chosen options)
- preconditions (list of required checks)
- costs (list of cost operations)
- resolution (list of state changes)
- event_log (list of emitted events)

### Action Lifecycle
1) Validate preconditions
2) Pay costs (if any)
3) Apply resolution
4) Emit event log entries

Actions must fail-closed: any missing rule support or illegal state causes the action to be rejected with a clear error.

## Turn and Phase Model
Minimum viable turn model for combo sims:
- Draw Phase
- Standby Phase
- Main Phase 1
- End Phase

Out of scope in v1:
- Battle Phase and Damage Step resolution
- Main Phase 2

## Chain Model
Chains follow Fast Effect Timing and PSCT rules.
- Spell Speed hierarchy is enforced.
- Chain links are built in LIFO order.
- Priority passes explicitly between actions.
- Open game state windows are tracked.

## PSCT Execution Contract
Official structure: CONDITION : ACTIVATION ; RESOLUTION (per Konami \"New Terminology and card text\" PDF).
- Activation text (before ;) includes costs and target declarations applied at activation.
- Resolution text (after ;) happens only when resolving the chain link.
- Costs are paid at activation; effects resolve at chain resolution.

## Extra Deck Placement Rules
- Fusion/Synchro/Xyz from the Extra Deck can be placed in any Main Monster Zone.
- Link and Pendulum-from-Extra-Deck summons are restricted to the Extra Monster Zone or linked zones (2021 Rules Update).

## Link Material Counting
- A Link monster used as material can count as 1 OR its Link Rating for material count checks.

## Fail-Closed Rules
- If an action or effect type is not modeled, the simulator must reject the action.
- If legality cannot be proven, the simulator must reject the action.
- Any unresolved or ambiguous rule must produce a structured error explaining what is missing.
