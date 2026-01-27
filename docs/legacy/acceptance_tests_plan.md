# Acceptance Tests Plan (Simulation Kernel)

These scenarios define expected legality outcomes for the combo simulator. Each test is a given state with allowed and illegal actions. All tests are fail-closed: if legality cannot be proven, the action must be rejected.

1) Normal Summon/Set shared budget
- Given: normal_summon_set_used = true
- Expect: any additional Normal Summon or Normal Set is rejected unless an effect grants an extra

3) First turn draw restriction
- Given: turn_number = 1 for first player
- Expect: no Draw Phase draw is performed

4) Link summon material count
- Given: Link-2 monster requires 2 materials
- Expect: using 1 material is rejected

5) Link material counting flexibility
- Given: Link-2 + 1 monster and a Link-3 recipe that allows 2+ materials
- Expect: Link-2 counts as 2 for material count checks

6) Extra Deck placement (Fusion/Synchro/Xyz)
- Given: open Main Monster Zone and no Link arrows
- Expect: Fusion/Synchro/Xyz summon to a Main Monster Zone is legal

7) Link summon zone placement
- Given: no available EMZ or linked zones
- Expect: Link Summon is rejected

8) Fusion summon material legality
- Given: Fusion requires named materials
- Expect: incorrect material names are rejected

9) Synchro summon level sum
- Given: Tuner + non-tuner levels do not match target
- Expect: Synchro Summon is rejected

10) Xyz summon rank match
- Given: materials do not share Level required for Rank
- Expect: Xyz Summon is rejected

11) PSCT activation vs resolution
- Given: effect text has a cost before the semicolon
- Expect: cost is paid at activation, not at resolution

12) Chain building legality
- Given: Spell Speed 1 effect
- Expect: cannot be chained to a Spell Speed 2 effect

13) Priority passing
- Given: open game state with no action
- Expect: priority can be passed without effect

14) OPT enforcement
- Given: OPT already used this turn
- Expect: second activation is rejected

15) Zone capacity
- Given: Monster Zones full
- Expect: additional summon is rejected

16) Send-to-GY accounting
- Given: effect sends card to GY
- Expect: GY and counters update once per send

17) Damage Step note (out of v1 scope)
- Given: an effect only activatable in Damage Step
- Expect: action is rejected with out-of-scope error
