# Fiendsmith Card Effect Audit

**Date:** 2026-01-26
**Sources:** [Yugipedia](https://yugipedia.com/wiki/Fiendsmith), [Official Konami DB](https://www.db.yugioh-card.com/), [YGOPRODeck](https://ygoprodeck.com/)

## CRITICAL FINDING

The combo enumeration logged:
```
Step 14: Activate Fiendsmith Engraver (GY eff2)
```
This was described as equipping Requiem. **THIS IS WRONG.**

Engraver's GY effect does NOT equip anything. The equip effect belongs to **Requiem**.

---

## Verified Card Effects

### Main Deck Fiendsmith Cards

#### Fiendsmith Engraver (60764609)
**Level 6 | LIGHT | Fiend/Effect | ATK 1800 / DEF 2400**

| Effect # | Type | Effect Text |
|----------|------|-------------|
| 1 | Hand | Discard this card; add 1 "Fiendsmith" Spell/Trap from Deck to hand |
| 2 | Field | Target 1 "Fiendsmith" Equip Card you control and 1 monster on field; send them to GY |
| 3 | GY | Shuffle 1 other LIGHT Fiend from your GY into Deck/Extra Deck; Special Summon this card |

**CRITICAL:** Effect 3 (GY) summons itself. It does NOT equip anything.

---

#### Fiendsmith's Sanct (35552985)
**Quick-Play Spell**

| Effect # | Type | Effect Text |
|----------|------|-------------|
| 1 | Hand/Field | If you control no face-up monsters, or only LIGHT Fiend monsters: SS 1 "Fiendsmith Token", cannot attack except with Fiends this turn |
| 2 | GY | If a "Fiendsmith" monster you control is destroyed by opponent's card effect: Set this card |

---

#### Fiendsmith's Tract (98567237)
**Normal Spell**

| Effect # | Type | Effect Text |
|----------|------|-------------|
| 1 | Hand | Add 1 "Fiendsmith" monster from Deck to hand, then discard 1 card |
| 2 | GY | Banish this card; Fusion Summon 1 Fiend Fusion using materials from hand/field |

---

### Extra Deck Fiendsmith Cards

#### Fiendsmith's Requiem (2463794)
**Link-1 | LIGHT | Fiend/Link/Effect | ATK 600 | Arrow: Down**

**Materials:** 1 LIGHT Fiend monster

| Effect # | Type | Effect Text |
|----------|------|-------------|
| 1 | Field (Quick) | Tribute this card; SS 1 "Fiendsmith" monster from hand or Deck |
| 2 | Field/GY | Target 1 LIGHT non-Link Fiend you control; **equip this card from field or GY** to it as Equip Spell (+600 ATK) |

**THIS is the equip effect, NOT Engraver's**

---

#### Fiendsmith's Sequence (49867899)
**Link-2 | LIGHT | Fiend/Link/Effect | ATK 1200 | Arrows: Bottom-Left, Bottom-Right**

**Materials:** 2 monsters, including a LIGHT Fiend monster

| Effect # | Type | Effect Text |
|----------|------|-------------|
| 1 | Field | Fusion Summon 1 Fiend Fusion by shuffling materials from GY into Deck |
| 2 | Field/GY | Target 1 LIGHT non-Link Fiend you control; **equip this card from field or GY** (opponent cannot target equipped monster) |

---

#### Fiendsmith's Lacrima (46640168)
**Level 6 | LIGHT | Fiend/Fusion/Effect | ATK 2400 / DEF 2400**

**Materials:** 2 LIGHT Fiend monsters

| Effect # | Type | Effect Text |
|----------|------|-------------|
| Continuous | - | Monsters opponent controls lose 600 ATK |
| 1 | If Fusion Summoned | Target 1 LIGHT Fiend banished or in GY; add to hand or SS it |
| 2 | If sent to GY | Shuffle 1 other LIGHT Fiend from GY into Deck/Extra Deck; inflict 1200 damage |

---

#### Fiendsmith's Desirae (82135803)
**Level 9 | LIGHT | Fiend/Fusion/Effect | ATK 2800 / DEF 2400**

**Materials:** "Fiendsmith Engraver" + 2 LIGHT Fiend monsters

| Effect # | Type | Effect Text |
|----------|------|-------------|
| 1 | Quick Effect | Negate effects of face-up cards on field, up to total Link Rating of equipped Link Monsters, until end of turn |
| 2 | If sent to GY | Shuffle 1 other LIGHT Fiend from GY into Deck/Extra Deck, then target 1 card; send it to GY |

---

#### Fiendsmith's Rextremende (11464648)
**Level 9 | LIGHT | Fiend/Fusion/Effect | ATK 3000 / DEF 3600**

**Materials:** 1 "Fiendsmith" Fusion Monster + 1 Fusion or Link Monster

| Effect # | Type | Effect Text |
|----------|------|-------------|
| Continuous | - | Unaffected by card effects except "Fiendsmith" cards while equipped with "Fiendsmith" Equip Spell |
| 1 | If Fusion Summoned | Discard 1; send 1 LIGHT Fiend from Deck or Extra Deck to GY |
| 2 | If sent to GY | Target 1 other "Fiendsmith" card in GY or banished; add it to hand |

---

#### Fiendsmith's Agnumday (32991300)
**Link-3 | LIGHT | Fiend/Link/Effect | ATK 1800**

**Materials:** 2+ monsters, including a LIGHT Fiend monster

| Effect # | Type | Effect Text |
|----------|------|-------------|
| 1 | Quick Effect | Target 1 LIGHT non-Link Fiend in GY; SS it, then **equip this card to it** (+600 ATK per Link Rating, piercing) |

---

## Cards with Equip Effects

Only these Fiendsmith cards can equip themselves:

1. **Fiendsmith's Requiem** - From field or GY to LIGHT non-Link Fiend you control
2. **Fiendsmith's Sequence** - From field or GY to LIGHT non-Link Fiend you control
3. **Fiendsmith's Agnumday** - Equips when summoning from GY

**Fiendsmith Engraver does NOT have an equip effect.**

---

## Issue with Combo Enumeration

The logged combo shows:
```
Step 14: Activate Fiendsmith Engraver (GY eff2)
Step 15: Select Fiendsmith's Requiem
```

If the engine is treating this as Engraver equipping Requiem, the ygopro-core card scripts may have incorrect effect implementations, OR the action labeling in `combo_enumeration.py` is wrong.

### Recommended Actions

1. **Verify cards.cdb** - Check if Engraver's effect data is correct
2. **Check ygopro-core scripts** - Verify `c60764609.lua` implements correct effects
3. **Fix action labeling** - The description generator may be mislabeling which card's effect is being used
