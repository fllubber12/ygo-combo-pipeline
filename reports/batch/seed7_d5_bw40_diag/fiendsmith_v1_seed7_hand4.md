# Batch Combo Report: fiendsmith_v1_seed7_hand4

- seed: 7
- hand: 20241, 21624, 21624, 20196, 20490

## Core Actions
1. normal_summon: {'hand_index': 4, 'mz_index': 1}
2. special_summon: {'hand_index': 0, 'mz_index': 2}
3. extra_deck_summon: {'extra_index': 1, 'summon_type': 'fusion', 'materials': [('mz', 2), ('mz', 1)], 'min_materials': 2, 'link_rating': None}

## Effect Actions
1. Lacrima the Crimson Tears [20490] send_paradise_from_deck: {'zone': 'mz', 'field_index': 1, 'deck_index': 3}
2. Fiendsmith Engraver [20196] discard_search_fiendsmith_st: {'hand_index': 3, 'deck_index': 2}

## Target Eligibility Diagnostics
- mz_count: 1
- Fiendsmith's Desirae (cid=20215) attr= race= summon_type=fusion properly=True is_light_fiend=True is_link=False
- open_mz: 4
- open_emz: 2
- hand_size: 3 fiend_in_hand: 0
- gy_size: 4
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
      "Buio the Dawn's Light",
      "Buio the Dawn's Light",
      "Fiendsmith's Sanct"
    ],
    "field": [
      "Fiendsmith's Desirae"
    ],
    "gy": [
      "Fiendsmith in Paradise",
      "Fiendsmith Engraver",
      "Fiendsmith's Sanct",
      "Lacrima the Crimson Tears"
    ],
    "banished": [],
    "deck": [
      "Buio the Dawn's Light",
      "Mutiny in the Sky",
      "Luce the Dusk's Dark",
      "Lacrima the Crimson Tears",
      "Fiendsmith in Paradise",
      "Fiendsmith's Tract",
      "The Duke of Demise",
      "Fiendsmith's Tract",
      "Mutiny in the Sky",
      "Lacrima the Crimson Tears",
      "The Duke of Demise",
      "Fiendsmith in Paradise",
      "Luce the Dusk's Dark",
      "The Duke of Demise",
      "Fiendsmith Engraver",
      "Mutiny in the Sky",
      "Fiendsmith's Tract",
      "Luce the Dusk's Dark",
      "Fiendsmith Engraver",
      "Fiendsmith's Sanct"
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
