# Batch Combo Report: fiendsmith_v1_seed7_hand3

- seed: 7
- hand: 20251, 21625, 20490, 21625, 20251

## Core Actions
1. normal_summon: {'hand_index': 2, 'mz_index': 0}
2. special_summon: {'hand_index': 0, 'mz_index': 2}
3. extra_deck_summon: {'extra_index': 1, 'summon_type': 'fusion', 'materials': [('mz', 2), ('mz', 0)], 'min_materials': 2, 'link_rating': None}
4. special_summon: {'hand_index': 2, 'mz_index': 0}
5. special_summon: {'hand_index': 0, 'mz_index': 2}
6. special_summon: {'hand_index': 0, 'mz_index': 3}

## Effect Actions
1. Lacrima the Crimson Tears [20490] send_paradise_from_deck: {'zone': 'mz', 'field_index': 0, 'deck_index': 9}

## Target Eligibility Diagnostics
- mz_count: 4
- Fiendsmith in Paradise (cid=20251) attr= race= summon_type= properly=False is_light_fiend=False is_link=False
- Fiendsmith's Desirae (cid=20215) attr= race= summon_type=fusion properly=True is_light_fiend=True is_link=False
- Luce the Dusk's Dark (cid=21625) attr= race= summon_type= properly=False is_light_fiend=False is_link=False
- Luce the Dusk's Dark (cid=21625) attr= race= summon_type= properly=False is_light_fiend=False is_link=False
- open_mz: 1
- open_emz: 2
- hand_size: 0 fiend_in_hand: 0
- gy_size: 3
- extra_has_sequence: True
- extra_has_requiem: True

## Equip Diagnostics
- equip_actions_available: 0
- equip_action_ids: (none)

## Final Snapshot
```json
{
  "zones": {
    "hand": [],
    "field": [
      "Fiendsmith in Paradise",
      "Fiendsmith's Desirae",
      "Luce the Dusk's Dark",
      "Luce the Dusk's Dark"
    ],
    "gy": [
      "Fiendsmith in Paradise",
      "Fiendsmith in Paradise",
      "Lacrima the Crimson Tears"
    ],
    "banished": [],
    "deck": [
      "Fiendsmith's Tract",
      "Fiendsmith Engraver",
      "Fiendsmith's Tract",
      "The Duke of Demise",
      "Fiendsmith's Sanct",
      "The Duke of Demise",
      "Fiendsmith's Sanct",
      "Mutiny in the Sky",
      "Buio the Dawn's Light",
      "Mutiny in the Sky",
      "Fiendsmith Engraver",
      "Mutiny in the Sky",
      "Fiendsmith's Tract",
      "Buio the Dawn's Light",
      "Fiendsmith Engraver",
      "Lacrima the Crimson Tears",
      "Lacrima the Crimson Tears",
      "The Duke of Demise",
      "Buio the Dawn's Light",
      "Fiendsmith's Sanct",
      "Luce the Dusk's Dark"
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
