# Batch Combo Report: fiendsmith_v1_seed7_hand10

- seed: 7
- hand: 21626, 20490, 21626, 20251, 20240

## Core Actions
1. normal_summon: {'hand_index': 1, 'mz_index': 2}
2. extra_deck_summon: {'extra_index': 1, 'summon_type': 'fusion', 'materials': [('mz', 0), ('mz', 2)], 'min_materials': 2, 'link_rating': 0}

## Effect Actions
1. Fiendsmith's Tract [20240] search_light_fiend_then_discard: {'hand_index': 3, 'deck_index': 0, 'discard_hand_index': 2}
2. Fiendsmith Engraver [20196] discard_search_fiendsmith_st: {'hand_index': 2, 'deck_index': 1}
3. Fiendsmith's Sanct [20241] activate_sanct_token: {'hand_index': 2, 'mz_index': 0}

## Target Eligibility Diagnostics
- mz_count: 1
- Fiendsmith's Desirae (cid=20215) attr=LIGHT race=FIEND summon_type=fusion properly=True is_light_fiend=True is_link=False
- open_mz: 4
- open_emz: 2
- hand_size: 2 fiend_in_hand: 0
- gy_size: 6
- extra_has_sequence: True
- extra_has_requiem: True

## Equip Diagnostics
- equip_actions_available: 0
- equip_action_ids: (none)

## Final Snapshot
```json
{
  "zones": {
    "hand": [
      "Mutiny in the Sky",
      "Mutiny in the Sky"
    ],
    "field": [
      "Fiendsmith's Desirae"
    ],
    "gy": [
      "Fiendsmith's Tract",
      "Fiendsmith in Paradise",
      "Fiendsmith Engraver",
      "Fiendsmith's Sanct",
      "Fiendsmith Token",
      "Lacrima the Crimson Tears"
    ],
    "banished": [],
    "deck": [
      "The Duke of Demise",
      "Luce the Dusk's Dark",
      "Fiendsmith Engraver",
      "Buio the Dawn's Light",
      "Lacrima the Crimson Tears",
      "Fiendsmith's Sanct",
      "Lacrima the Crimson Tears",
      "Fiendsmith's Sanct",
      "Fiendsmith's Tract",
      "Fiendsmith in Paradise",
      "The Duke of Demise",
      "Fiendsmith in Paradise",
      "Fiendsmith Engraver",
      "Luce the Dusk's Dark",
      "The Duke of Demise",
      "Luce the Dusk's Dark",
      "Buio the Dawn's Light",
      "Mutiny in the Sky",
      "Fiendsmith's Tract",
      "Buio the Dawn's Light"
    ],
    "extra": [
      "Fiendsmith's Lacrima",
      "Necroquip Princess",
      "Aerial Eater",
      "Snake-Eyes Doomed Dragon",
      "Fiendsmith's Rextremende",
      "A Bao A Qu, the Lightless Shadow",
      "Fiendsmith Kyrie",
      "Fiendsmith's Requiem",
      "Fiendsmith's Sequence",
      "Fiendsmith's Sequence",
      "Fiendsmith's Agnumday",
      "Muckraker From the Underworld",
      "Cross-Sheep",
      "S:P Little Knight"
    ]
  },
  "equipped_link_totals": []
}
```

## Endboard Evaluation
- rank_key: (False, True, 1)
- summary: S=0 A=1 B=1

### Achieved Buckets
```json
[
  {
    "kind": "card",
    "name": "Fiendsmith's Desirae",
    "bucket": "A",
    "zone": "field",
    "notes": "needs equip spell / links equipped to be online"
  },
  {
    "kind": "condition",
    "name": "Fiendsmith in Paradise in GY",
    "bucket": "B",
    "zone": "gy",
    "notes": "endboard trap live in GY; ideally Desirae remains in Extra Deck (best target)"
  }
]
```
