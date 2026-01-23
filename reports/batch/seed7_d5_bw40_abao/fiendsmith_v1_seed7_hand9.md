# Batch Combo Report: fiendsmith_v1_seed7_hand9

- seed: 7
- hand: 20490, 20241, 21625, 20389, 21624

## Core Actions
1. normal_summon: {'hand_index': 0, 'mz_index': 2}
2. extra_deck_summon: {'extra_index': 1, 'summon_type': 'fusion', 'materials': [('mz', 0), ('mz', 2)], 'min_materials': 2, 'link_rating': None}
3. special_summon: {'hand_index': 1, 'mz_index': 0}

## Effect Actions
1. Fiendsmith's Sanct [20241] activate_sanct_token: {'hand_index': 1, 'mz_index': 0}
2. Lacrima the Crimson Tears [20490] send_paradise_from_deck: {'zone': 'mz', 'field_index': 2, 'deck_index': 13}

## Equip Diagnostics
- equip_actions_available: 0
- equip_action_ids: (none)

## Final Snapshot
```json
{
  "zones": {
    "hand": [
      "Luce the Dusk's Dark",
      "Buio the Dawn's Light"
    ],
    "field": [
      "The Duke of Demise",
      "Fiendsmith's Desirae"
    ],
    "gy": [
      "Fiendsmith's Sanct",
      "Fiendsmith in Paradise",
      "Fiendsmith Token",
      "Lacrima the Crimson Tears"
    ],
    "banished": [],
    "deck": [
      "Luce the Dusk's Dark",
      "Fiendsmith Engraver",
      "Buio the Dawn's Light",
      "Mutiny in the Sky",
      "Fiendsmith's Tract",
      "Luce the Dusk's Dark",
      "Mutiny in the Sky",
      "Fiendsmith's Tract",
      "Fiendsmith in Paradise",
      "Fiendsmith's Sanct",
      "Fiendsmith's Sanct",
      "Buio the Dawn's Light",
      "Lacrima the Crimson Tears",
      "Mutiny in the Sky",
      "The Duke of Demise",
      "Lacrima the Crimson Tears",
      "Fiendsmith Engraver",
      "Fiendsmith in Paradise",
      "Fiendsmith's Tract",
      "Fiendsmith Engraver",
      "The Duke of Demise"
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
