# Batch Combo Report: fiendsmith_v1_seed7_hand1

- seed: 7
- hand: 21624, 20490, 20251, 20389, 20389

## Core Actions
1. normal_summon: {'hand_index': 2, 'mz_index': 2}
2. special_summon: {'hand_index': 2, 'mz_index': 0}
3. extra_deck_summon: {'extra_index': 1, 'summon_type': 'fusion', 'materials': [('mz', 2), ('mz', 0)], 'min_materials': 2, 'link_rating': None}
4. special_summon: {'hand_index': 1, 'mz_index': 0}

## Effect Actions
1. Lacrima the Crimson Tears [20490] send_paradise_from_deck: {'zone': 'mz', 'field_index': 0, 'deck_index': 12}

## Equip Diagnostics
- equip_actions_available: 0
- equip_action_ids: (none)

## Final Snapshot
```json
{
  "zones": {
    "hand": [
      "Buio the Dawn's Light",
      "The Duke of Demise"
    ],
    "field": [
      "Lacrima the Crimson Tears",
      "Fiendsmith's Desirae"
    ],
    "gy": [
      "Fiendsmith in Paradise",
      "The Duke of Demise",
      "Fiendsmith in Paradise"
    ],
    "banished": [],
    "deck": [
      "Mutiny in the Sky",
      "Luce the Dusk's Dark",
      "Fiendsmith's Sanct",
      "Mutiny in the Sky",
      "Fiendsmith's Sanct",
      "Luce the Dusk's Dark",
      "Mutiny in the Sky",
      "Fiendsmith's Tract",
      "Fiendsmith in Paradise",
      "Fiendsmith Engraver",
      "The Duke of Demise",
      "Fiendsmith's Tract",
      "Buio the Dawn's Light",
      "Lacrima the Crimson Tears",
      "Fiendsmith's Tract",
      "Fiendsmith Engraver",
      "Fiendsmith Engraver",
      "Fiendsmith's Sanct",
      "Luce the Dusk's Dark",
      "Lacrima the Crimson Tears",
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
