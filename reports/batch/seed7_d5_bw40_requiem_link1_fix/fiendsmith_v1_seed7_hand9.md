# Batch Combo Report: fiendsmith_v1_seed7_hand9

- seed: 7
- hand: 20490, 20241, 21625, 20389, 21624

## Core Actions
1. normal_summon: {'hand_index': 0, 'mz_index': 0}
2. extra_deck_summon: {'extra_index': 1, 'summon_type': 'fusion', 'materials': [('mz', 2), ('mz', 0)], 'min_materials': 2, 'link_rating': None}
3. special_summon: {'hand_index': 1, 'mz_index': 0}
4. special_summon: {'hand_index': 0, 'mz_index': 2}

## Effect Actions
1. Fiendsmith's Sanct [20241] activate_sanct_token: {'hand_index': 1, 'mz_index': 2}
2. Lacrima the Crimson Tears [20490] send_paradise_from_deck: {'zone': 'mz', 'field_index': 0, 'deck_index': 13}
3. Buio the Dawn's Light [21624] buio_hand_ss: {'hand_index': 0, 'target_mz_index': 1, 'mz_index': 3}

## Target Eligibility Diagnostics
- mz_count: 4
- The Duke of Demise (cid=20389) attr= race= summon_type= properly=False is_light_fiend=False is_link=False
- Fiendsmith's Desirae (cid=20215) attr= race= summon_type=fusion properly=True is_light_fiend=True is_link=False
- Luce the Dusk's Dark (cid=21625) attr= race= summon_type= properly=False is_light_fiend=False is_link=False
- Buio the Dawn's Light (cid=21624) attr= race= summon_type= properly=False is_light_fiend=False is_link=False
- open_mz: 1
- open_emz: 2
- hand_size: 0 fiend_in_hand: 0
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
    "hand": [],
    "field": [
      "The Duke of Demise",
      "Fiendsmith's Desirae",
      "Luce the Dusk's Dark",
      "Buio the Dawn's Light"
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
