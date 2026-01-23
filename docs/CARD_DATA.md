# Card Data Reference (Verified from ProjectIgnis CDB)

**Generated:** 2026-01-23
**Source:** https://github.com/ProjectIgnis/BabelCDB/raw/master/cards.cdb

This document contains verified card properties for all cards in the decklist.
**ALL effect implementations and hardcoded metadata MUST match this document.**

---

## Main Deck Monsters

### Fiendsmith Engraver
| Property | Value |
|----------|-------|
| Passcode | 60764609 |
| Our CID | 20196 |
| Type | Effect Monster |
| Attribute | LIGHT |
| Race | Fiend |
| Level | **6** |
| ATK/DEF | 1800/2400 |

**Effects:**
1. Discard this card → Add 1 "Fiendsmith" Spell/Trap from Deck to hand (OPT)
2. Target 1 "Fiendsmith" Equip Card you control and 1 monster on field → Send both to GY (OPT)
3. (GY) Shuffle 1 other LIGHT Fiend monster from GY into Deck/Extra Deck → SS this card (OPT)

**Notes:**
- Level 6 requires 1 Tribute for Normal Summon
- Cannot be Normal Summoned without a monster on field to tribute

---

### Lacrima the Crimson Tears
| Property | Value |
|----------|-------|
| Passcode | 28803166 |
| Our CID | 20490 (INCORRECT - was named "Fiendsmith's Lacrima - Crimson Tears") |
| Type | Effect Monster |
| Attribute | LIGHT |
| Race | Fiend |
| Level | **4** |
| ATK/DEF | (check CDB) |

**Effects:**
1. (This card is always treated as a "Fiendsmith" card)
2. If Normal/Special Summoned → Send 1 "Fiendsmith" card from Deck to GY (OPT)
3. (GY, Quick Effect, opponent's turn) Target 1 "Fiendsmith" Link Monster in GY → Shuffle this card into Deck, SS that monster (OPT)

**Notes:**
- IS a valid Requiem target (treated as Fiendsmith)
- Main Deck monster, Level 4 (no tribute needed)

---

### Buio the Dawn's Light
| Property | Value |
|----------|-------|
| Passcode | 19000848 |
| Our CID | 21624 |
| Type | Effect Monster |
| Attribute | DARK |
| Race | Fiend |
| Level | **3** |

**Effects:**
1. Monsters in leftmost/rightmost Main Monster Zones cannot be destroyed by card effects
2. (Hand) Target 1 Fiend Effect Monster you control → Negate its effects, SS this card (OPT)
3. (GY) If sent to GY → Add 1 "Mutiny in the Sky" from Deck to hand (OPT)

**Notes:**
- NOT a Fiendsmith monster (cannot be summoned by Requiem)
- Can Special Summon itself from hand by negating a Fiend on field

---

---

## Extra Deck - Link Monsters

### Fiendsmith's Requiem
| Property | Value |
|----------|-------|
| Passcode | 2463794 |
| Our CID | 20225 |
| Type | Link Effect Monster |
| Attribute | LIGHT |
| Race | Fiend |
| Link Rating | **1** |
| ATK | 600 |
| Materials | 1 LIGHT Fiend monster |

**Effects:**
1. Can only Special Summon "Fiendsmith's Requiem(s)" once per turn
2. (Quick Effect) Tribute this card → SS 1 "Fiendsmith" monster from hand or Deck (OPT)
3. Target 1 LIGHT non-Link Fiend monster you control → Equip this card from field/GY as Equip Spell (+600 ATK) (OPT)

**Valid SS targets from hand/deck:**
- Fiendsmith Engraver
- Lacrima the Crimson Tears
- (Any other Fiendsmith monster in Main Deck)

---

### Fiendsmith's Sequence
| Property | Value |
|----------|-------|
| Passcode | 49867899 |
| Our CID | 20238 |
| Type | Link Effect Monster |
| Attribute | LIGHT |
| Race | Fiend |
| Link Rating | **2** |
| ATK | 1200 |
| Materials | 2 LIGHT Fiend monsters |

---

### Fiendsmith's Agnumday
| Property | Value |
|----------|-------|
| Passcode | 32991300 |
| Our CID | 20521 |
| Type | Link Effect Monster |
| Attribute | LIGHT |
| Race | Fiend |
| Link Rating | **3** |
| Materials | 2+ monsters, including a LIGHT Fiend monster |

**Effects:**
1. (Quick Effect, OPT) Target 1 LIGHT non-Link Fiend in GY → SS it, equip this card to it as Equip Spell
   - Equipped monster gains ATK = total Link Rating of equipped Link Monsters x 600
   - Piercing battle damage

---

### Cross-Sheep
| Property | Value |
|----------|-------|
| Passcode | 50277355 |
| Our CID | 14856 |
| Type | Link Effect Monster |
| Attribute | EARTH |
| Race | Beast |
| Link Rating | **2** |
| ATK | 700 |

---

### Muckraker From the Underworld
| Property | Value |
|----------|-------|
| Passcode | 71607202 |
| Our CID | 17806 |
| Type | Link Effect Monster |
| Attribute | DARK |
| Race | Fiend |
| Link Rating | **2** |
| ATK | 1000 |

---

### S:P Little Knight
| Property | Value |
|----------|-------|
| Passcode | 29301450 |
| Our CID | 19188 |
| Type | Link Effect Monster |
| Attribute | DARK |
| Race | Warrior |
| Link Rating | **2** |
| ATK | 1600 |

---

### A Bao A Qu, the Lightless Shadow
| Property | Value |
|----------|-------|
| Passcode | 4731783 |
| Our CID | 20786 |
| Type | Link Effect Monster |
| Attribute | DARK |
| Race | Fiend |
| Link Rating | **4** |
| ATK | 2800 |

---

## Extra Deck - Fusion Monsters

### Fiendsmith's Desirae
| Property | Value |
|----------|-------|
| Passcode | 82135803 |
| Our CID | 20215 |
| Type | Fusion Effect Monster |
| Attribute | LIGHT |
| Race | Fiend |
| Level | **9** |
| ATK/DEF | 2800/2400 |
| Materials | (check CDB for fusion materials) |

---

### Fiendsmith's Lacrima
| Property | Value |
|----------|-------|
| Passcode | 46640168 |
| Our CID | 20214 |
| Type | Fusion Effect Monster |
| Attribute | LIGHT |
| Race | Fiend |
| Level | **6** |
| ATK/DEF | 2400/2400 |

**Notes:**
- This is an Extra Deck FUSION monster
- NOT the same as "Lacrima the Crimson Tears" (Main Deck monster)

---

### Fiendsmith's Rextremende
| Property | Value |
|----------|-------|
| Passcode | 11464648 |
| Our CID | 20774 |
| Type | Fusion Effect Monster |
| Attribute | LIGHT |
| Race | Fiend |
| Level | **9** |
| ATK/DEF | 3000/3600 |

---

### Luce the Dusk's Dark
| Property | Value |
|----------|-------|
| Passcode | 45409943 |
| Our CID | 21625 |
| Type | Fusion Effect Monster |
| Attribute | DARK |
| Race | Fiend |
| Level | **8** |

---

### The Duke of Demise
| Property | Value |
|----------|-------|
| Passcode | 45445571 |
| Our CID | 20389 |
| Type | Fusion Effect Monster |
| Attribute | DARK |
| Race | Fiend |
| Level | **6** |

---

### Aerial Eater
| Property | Value |
|----------|-------|
| Passcode | 28143384 |
| Our CID | 20427 |
| Type | Fusion Effect Monster |
| Attribute | WIND |
| Race | Fiend |
| Level | **6** |
| ATK/DEF | 2100/2600 |

---

### Necroquip Princess
| Property | Value |
|----------|-------|
| Passcode | 93860227 |
| Our CID | 20423 |
| Type | Fusion Effect Monster |
| Attribute | DARK |
| Race | Fiend |
| Level | **6** |
| ATK/DEF | 2000/2000 |

**Contact Fusion Summoning Condition:**
"1 monster equipped with a Monster Card + 1 Fiend Monster Card.
Must be Special Summoned (from your Extra Deck) by sending the above cards from your hand and/or field to the GY."

**On-field Effect:**
"If a monster(s) is sent from the hand to the GY to activate a card or effect: Draw 1 card. (OPT)"

**Control Restriction:** "You can only control 1 Necroquip Princess."

**Implementation Notes:**
- Contact Fusion: No spell card required
- Materials: Host monster (with Monster Card equipped) + Fiend monster (hand or field)
- Equipped cards on the host are also sent to GY
- Fiendsmith combo: Desirae (with Requiem equipped) + Engraver → Necroquip

---

### Snake-Eyes Doomed Dragon
| Property | Value |
|----------|-------|
| Passcode | (check CDB) |
| Our CID | 20772 |
| Type | Fusion Effect Monster |
| Attribute | FIRE |
| Race | Dragon |
| Level | **9** |

**Notes:**
- This is an Extra Deck FUSION monster
- NOT "Snake-Eyes Diabellstar" (that is a different Main Deck card)

---

## Extra Deck - Xyz Monsters

### Evilswarm Exciton Knight
| Property | Value |
|----------|-------|
| Passcode | 46772449 |
| Our CID | 10942 |
| Type | Xyz Effect Monster |
| Attribute | LIGHT |
| Race | Fiend |
| Rank | **4** |
| ATK/DEF | 1900/0 |

**Notes:**
- CID 10942 is Evilswarm Exciton Knight, NOT D/D/D Wave High King Caesar

---

### D/D/D Wave High King Caesar
| Property | Value |
|----------|-------|
| Passcode | 79559912 |
| Our CID | 13081 |
| Type | Xyz Effect Monster |
| Attribute | WATER |
| Race | Fiend |
| Rank | **6** |
| ATK/DEF | 2800/1800 |

---

## Spell Cards

### Fiendsmith's Tract
| Property | Value |
|----------|-------|
| Passcode | 98567237 |
| Our CID | 20240 |
| Type | Spell |

---

### Fiendsmith's Sanct
| Property | Value |
|----------|-------|
| Passcode | 35552985 |
| Our CID | 20241 |
| Type | Spell |

---

### Mutiny in the Sky
| Property | Value |
|----------|-------|
| Passcode | 71593652 |
| Our CID | 21626 |
| Type | Spell |

---

## Trap Cards

### Fiendsmith Kyrie
| Property | Value |
|----------|-------|
| Passcode | 26434972 |
| Our CID | 20816 |
| Type | **TRAP** |

**Official Effect Text:**
- Primary: "This turn, your LIGHT Fiend monsters cannot be destroyed by battle, also any battle damage you take becomes halved."
- GY Effect: "You can banish this card from your GY; Fusion Summon 1 'Fiendsmith' Fusion Monster from your Extra Deck, using monsters you control, and/or monsters in your Spell & Trap Zones that are equipped to a 'Fiendsmith' monster as an Equip Spell, as material."
- OPT: "You can only use this effect of 'Fiendsmith Kyrie' once per turn."

**Implementation Notes:**
- This is a TRAP CARD, not a monster
- CANNOT be summoned by Requiem's effect
- GY effect targets ANY Fiendsmith Fusion (Lacrima 20214, Desirae 20215, Rextremende 20774)
- Materials: monsters on field + equipped cards on Fiendsmith monsters
- Cannot use the target Fusion as material

---

### Fiendsmith in Paradise
| Property | Value |
|----------|-------|
| Passcode | 99989863 |
| Our CID | 20251 |
| Type | **TRAP** |

---

## Code Corrections Status

### FIENDSMITH_ST_CIDS ✓ CORRECT
`{"20240", "20241", "20251", "20816"}` - Contains Kyrie (20816) which is correct (it's a Trap)

### REQUIEM_QUICK_TARGET_CIDS ✓ FIXED
- Removed Fiendsmith's Lacrima (20214) - it's a Fusion, cannot be summoned from deck
- Added Lacrima the Crimson Tears (20490) - Main Deck, "treated as Fiendsmith"

### LIGHT_FIEND_MONSTER_CIDS ✓ FIXED
Now includes: `{"20196", "20214", "20215", "20225", "20238", "20521", "20774", "20490"}`
- 20196: Engraver ✓ (LIGHT Fiend, Main Deck)
- 20214: Fiendsmith's Lacrima ✓ (LIGHT Fiend, Fusion)
- 20215: Desirae ✓ (LIGHT Fiend, Fusion)
- 20225: Requiem ✓ (LIGHT Fiend, Link-1)
- 20238: Sequence ✓ (LIGHT Fiend, Link-2)
- 20521: Agnumday ✓ (LIGHT Fiend, Link-3)
- 20774: Rextremende ✓ (LIGHT Fiend, Fusion)
- 20490: Lacrima the Crimson Tears ✓ (LIGHT Fiend, Main Deck)

### SUMMON_TYPE_BY_CID ✓ FIXED
- Removed CID 20816 (Fiendsmith Kyrie) - it's a TRAP, not a Fusion monster

### Fixture Metadata ✓ VERIFIED
- Engraver level is **6** (correct)
- Kyrie is a Trap (not included in monster metadata)

### Xyz Level Matching ✓ IMPLEMENTED
- All Xyz materials must have the SAME Level
- Material Level must equal the Xyz monster's Rank
- Link monsters (no Level) cannot be used as Xyz material
- Example: D/D/D Wave High King Caesar (Rank 6) requires 2 Level 6 monsters

**Fixture Updates:**
- fixture_caesar_via_sanct: Uses 2 Engravers (Level 6) for Caesar (Rank 6)
- fixture_search_combo: Uses 2 Level 6 materials for Caesar (Rank 6)
- All Caesar fixtures now have correct rank: 6

---

## Engraver Solo Combo Analysis

With Engraver (Level 6) + 4 inert cards:

**CANNOT do:**
- Normal Summon Engraver (no tribute available)
- Use generic "special_summon" (not a real YGO mechanic)

**CAN do:**
1. Engraver discards self → Search Fiendsmith S/T (e.g., Sanct)
2. Sanct → Create Fiendsmith Token (LIGHT Fiend)
3. Token → Link into Requiem
4. Requiem tributes → SS Lacrima the Crimson Tears from deck (if in deck)
5. Continue combo...

**Fixture needs:**
- Lacrima the Crimson Tears in deck for Requiem to summon
