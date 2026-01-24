# Yu-Gi-Oh Game Rules Reference

This document defines core game mechanics that MUST be enforced by the simulation.
Each rule has a test case in `tests/test_game_rules.py` to verify correct implementation.

**Authoritative Sources:**
- Official Yu-Gi-Oh! TCG Rulebook (Version 10.0, 2020)
- Konami Official Card Database Rulings
- Yu-Gi-Oh! TCG 2021 Rules Update

---

## Token Rules

### Rule T1: Tokens cannot exist outside the field
**Definition:** When a Token would be sent to the GY, banished, returned to hand, or returned to Deck, it ceases to exist instead. Tokens can ONLY exist in Monster Zones.

**Source:** Official Rulebook v10.0, Page 47: "Tokens are not included in the Deck, and are not considered cards in the GY, hand, or Banished pile."

**Implementation:**
- When processing any card movement FROM a Monster Zone, check if card is a Token
- If Token, do NOT add to destination zone - it simply ceases to exist
- Token identification: `card.metadata.get("subtype") == "token"` or `card.cid.startswith("TOKEN_")`

**Test case:** `test_token_not_sent_to_gy_as_link_material`
- State: Fiendsmith Token on MZ[0]
- Action: Use Token as Link Material for Requiem
- Expected: Token ceases to exist, GY remains empty

### Rule T2: Tokens cannot be used as Xyz Material
**Definition:** Tokens cannot be used as Xyz Materials for an Xyz Summon.

**Source:** Official Rulebook v10.0, Page 47: "Tokens cannot be used as Xyz Materials."

**Implementation:**
- When enumerating Xyz Summon materials, filter out Tokens

**Test case:** `test_token_cannot_be_xyz_material`
- State: Token on MZ[0], Rank 4 Xyz in Extra
- Action: Enumerate Xyz Summon options
- Expected: No Xyz Summon actions available using the Token

### Rule T3: Tokens can be used as Link Material
**Definition:** Tokens CAN be used as Link Materials, but when used, they cease to exist instead of going to GY.

**Source:** Master Rule 4+ clarification: Link Materials go to GY, but Tokens cease to exist per Rule T1.

**Test case:** `test_token_can_be_link_material`
- State: Token on MZ[0], Link-1 in Extra
- Action: Enumerate Link Summon options
- Expected: Link Summon action IS available using the Token

### Rule T4: Tokens can be Tributed
**Definition:** Tokens can be Tributed for Tribute Summons or effects that require Tributing. When Tributed, they cease to exist.

**Source:** Official Rulebook v10.0, Page 47: "Tokens can be Tributed or used as Fusion Materials."

**Test case:** `test_token_can_be_tributed`
- State: Token on MZ[0], Level 5+ monster in hand
- Action: Tribute Summon
- Expected: Tribute Summon IS available, Token ceases to exist

---

## Link Summon Rules

### Rule L1: Link Materials go to GY (except Tokens)
**Definition:** When performing a Link Summon, the materials used are sent to the GY. Tokens cease to exist instead (Rule T1).

**Source:** Official Rulebook v10.0, Page 23: "Send the face-up Link Materials from your field to the Graveyard."

**Implementation:**
- After Link Summon, iterate materials
- For each material: if Token, skip; else add to GY

**Test case:** `test_link_material_sent_to_gy`
- State: Fiendsmith Engraver on MZ[0], Requiem in Extra
- Action: Link Summon Requiem using Engraver
- Expected: Engraver IS in GY after summon

### Rule L2: Link Rating determines minimum materials
**Definition:** A Link Monster requires a number of materials equal to its Link Rating. Link Monsters used as material can count as 1 OR their Link Rating.

**Source:** Official Rulebook v10.0, Page 22: "You can use a Link Monster as material by treating it as either 1 material, or as a number of materials equal to its Link Rating."

**Implementation:**
- `link_material_count_ok()` function handles this calculation
- Verified working in CDB single-source-of-truth system

**Test case:** `test_link_rating_material_count`
- State: 2 monsters on field, Link-3 Agnumday in Extra
- Action: Enumerate Link Summon options
- Expected: Agnumday NOT available (needs 3 materials)

### Rule L3: Link Summons go to Extra Monster Zone or Linked Zone
**Definition:** Link Monsters must be Summoned to an Extra Monster Zone, OR to a Main Monster Zone that a Link Monster points to.

**Source:** Official Rulebook v10.0, Page 22

**Test case:** `test_link_summon_placement`
- State: No Link Monsters on field, EMZ empty
- Action: Link Summon
- Expected: Link Monster placed in EMZ[0]

---

## Xyz Summon Rules

### Rule X1: Xyz Materials are attached, not on field
**Definition:** Cards used as Xyz Materials are placed underneath the Xyz Monster. They are not considered to be on the field.

**Source:** Official Rulebook v10.0, Page 20: "Xyz Materials are not treated as cards on the field."

**Implementation:**
- Xyz Materials stored in `card.attached_materials` list
- Materials NOT in any zone (not MZ, not GY, not anywhere)

**Test case:** `test_xyz_materials_not_on_field`
- State: Xyz Monster with attached materials
- Action: Check field monster count
- Expected: Only the Xyz Monster counts, not its materials

### Rule X2: Detached Xyz Materials go to GY
**Definition:** When an Xyz Material is detached, it is sent to the GY.

**Source:** Official Rulebook v10.0, Page 21: "To use [Xyz Monster effects], you remove the Xyz Material from underneath it and place it in the Graveyard."

**Test case:** `test_xyz_material_detach_to_gy`
- State: Xyz Monster with 2 materials
- Action: Detach 1 material
- Expected: 1 material now in GY

### Rule X3: Xyz Monsters have Rank, not Level
**Definition:** Xyz Monsters have Rank instead of Level. Cards that reference "Level" do not affect Xyz Monsters (unless specifically stated).

**Source:** Official Rulebook v10.0, Page 20

**Test case:** `test_xyz_has_rank_not_level`
- State: Rank 4 Xyz Monster on field
- Action: Check monster's Level
- Expected: Level is None/0, Rank is 4

---

## Fusion Summon Rules

### Rule F1: Fusion Materials go to GY (standard Fusion)
**Definition:** When Fusion Summoning with a Fusion Spell Card, the materials are sent to the GY.

**Source:** Official Rulebook v10.0, Page 18: "Send the Fusion Material Monsters listed on the Fusion Monster Card from your hand or your side of the field to the Graveyard."

**Test case:** `test_fusion_materials_to_gy`
- State: 2 monsters, Fusion Spell, Fusion Monster in Extra
- Action: Activate Fusion
- Expected: Materials in GY, Fusion Monster on field

### Rule F2: Contact Fusion materials location varies
**Definition:** Some Fusion Monsters can be Special Summoned without a Fusion Spell (Contact Fusion). Where the materials go depends on the card text.

**Source:** Card-specific text (e.g., "shuffle into Deck", "banish", "send to GY")

**Test case:** Card-specific tests

---

## Equip Card Rules

### Rule E1: Equipped cards destroyed when equipped monster leaves
**Definition:** If the equipped monster leaves the field, any Equip Cards equipped to it are destroyed and sent to the GY.

**Source:** Official Rulebook v10.0, Page 29: "If the equipped monster is destroyed, or leaves the field, any Equip Cards equipped to it are destroyed."

**Implementation:**
- When monster leaves field, iterate `card.equipped` list
- Send each equipped card to GY (destroyed)

**Test case:** `test_equipped_card_destroyed_when_monster_leaves`
- State: Monster with Equip Card equipped
- Action: Send monster to GY
- Expected: Equip Card also in GY

### Rule E2: Equip Cards equipped from GY
**Definition:** Some effects equip cards directly from the GY. These cards become Equip Spells and follow Equip Card rules.

**Source:** Card-specific effects (e.g., Requiem's equip effect)

**Test case:** `test_equip_from_gy`
- State: Requiem in GY, valid target on field
- Action: Activate Requiem's equip effect
- Expected: Requiem equipped to target

---

## Graveyard Rules

### Rule G1: GY is public information
**Definition:** Both players can look at each other's GY at any time.

**Source:** Official Rulebook v10.0, Page 4

**Implementation:** GY contents always visible in game state

### Rule G2: GY order matters for some effects
**Definition:** Cards in the GY are placed in order. Some effects reference position.

**Source:** Official Rulebook v10.0

**Implementation:** GY is a list, not a set. Order preserved.

**Test case:** `test_gy_order_preserved`
- State: Send Card A, then Card B to GY
- Action: Check GY order
- Expected: GY = [A, B] in order

---

## Banish Rules

### Rule B1: Banished cards face-up by default
**Definition:** When a card is banished, it is banished face-up unless an effect specifies face-down.

**Source:** Official Rulebook v10.0, Page 5

**Test case:** `test_banish_face_up_default`
- State: Card on field
- Action: Banish the card
- Expected: Card in banished zone, face-up

### Rule B2: Face-down banished cards are not public
**Definition:** Face-down banished cards cannot be viewed by either player (unless an effect allows).

**Source:** Official Rulebook v10.0, Page 5

---

## Special Summon Rules

### Rule S1: "Properly Summoned" requirement for revival
**Definition:** Monsters that must first be Special Summoned by specific means cannot be Special Summoned from GY/Banished unless they were first properly Summoned.

**Source:** Official Rulebook v10.0, Page 24: "Some monsters have specific requirements for how they can be Special Summoned."

**Implementation:**
- Track `properly_summoned` flag on CardInstance
- Revival effects check this flag before allowing summon

**Test case:** `test_revival_requires_properly_summoned`
- State: Fusion Monster in GY, never properly Summoned
- Action: Try to revive with Monster Reborn
- Expected: NOT allowed

### Rule S2: Nomi vs Semi-Nomi monsters
**Definition:**
- Nomi: Can ONLY be Special Summoned by specific method (cannot be revived)
- Semi-Nomi: Must FIRST be Summoned by specific method, then can be revived

**Source:** Official Rulebook v10.0

**Test case:** `test_semi_nomi_can_be_revived_after_proper_summon`
- State: Properly summoned Fusion Monster in GY
- Action: Revive with effect
- Expected: Allowed

---

## Zone Rules

### Rule Z1: Main Monster Zone capacity
**Definition:** Each player has 5 Main Monster Zones.

**Source:** Official Rulebook v10.0, Page 3

**Test case:** `test_main_monster_zone_capacity`
- State: 5 monsters in MZ
- Action: Try to Special Summon 6th
- Expected: NOT allowed (no space)

### Rule Z2: Extra Monster Zone rules
**Definition:** Link Monsters and Pendulum Monsters Summoned from Extra Deck go to EMZ or Linked zones.

**Source:** Official Rulebook v10.0, Page 3

---

## Summary Test Matrix

| Rule ID | Rule Name | Test Function | Status |
|---------|-----------|---------------|--------|
| T1 | Tokens cannot exist outside field | `test_token_not_sent_to_gy_as_link_material` | TODO |
| T2 | Tokens cannot be Xyz Material | `test_token_cannot_be_xyz_material` | TODO |
| T3 | Tokens can be Link Material | `test_token_can_be_link_material` | TODO |
| T4 | Tokens can be Tributed | `test_token_can_be_tributed` | TODO |
| L1 | Link Materials to GY | `test_link_material_sent_to_gy` | TODO |
| L2 | Link Rating material count | `test_link_rating_material_count` | PASS |
| L3 | Link Summon placement | `test_link_summon_placement` | TODO |
| X1 | Xyz Materials not on field | `test_xyz_materials_not_on_field` | TODO |
| X2 | Detached materials to GY | `test_xyz_material_detach_to_gy` | TODO |
| X3 | Xyz has Rank not Level | `test_xyz_has_rank_not_level` | TODO |
| F1 | Fusion Materials to GY | `test_fusion_materials_to_gy` | TODO |
| E1 | Equipped cards destroyed | `test_equipped_card_destroyed_when_monster_leaves` | TODO |
| E2 | Equip from GY | `test_equip_from_gy` | TODO |
| G1 | GY is public | N/A (design) | PASS |
| G2 | GY order preserved | `test_gy_order_preserved` | TODO |
| B1 | Banish face-up default | `test_banish_face_up_default` | TODO |
| S1 | Revival requires proper summon | `test_revival_requires_properly_summoned` | PASS |
| S2 | Semi-Nomi can be revived | `test_semi_nomi_can_be_revived_after_proper_summon` | PASS |
| Z1 | MZ capacity | `test_main_monster_zone_capacity` | TODO |
