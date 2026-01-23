# Batch Combo Report: fiendsmith_v1_seed7_hand2

- seed: 7
- hand: 20251, 20241, 20241, 20490, 21625

## Core Actions
1. normal_summon: {'hand_index': 3, 'mz_index': 0}
2. special_summon: {'hand_index': 1, 'mz_index': 3}
3. extra_deck_summon: {'extra_index': 1, 'summon_type': 'fusion', 'materials': [('mz', 3), ('mz', 0)], 'min_materials': 2, 'link_rating': None}
4. special_summon: {'hand_index': 1, 'mz_index': 2}
5. special_summon: {'hand_index': 0, 'mz_index': 3}

## Effect Actions
1. Lacrima the Crimson Tears [20490] send_paradise_from_deck: {'zone': 'mz', 'field_index': 0, 'deck_index': 14}
2. Fiendsmith's Sanct [20241] activate_sanct_token: {'hand_index': 1, 'mz_index': 0}

## Target Eligibility Diagnostics
- mz_count: 4
- Fiendsmith Token (cid=FIENDSMITH_TOKEN) attr=LIGHT race=FIEND summon_type= properly=False is_light_fiend=True is_link=False
- Fiendsmith's Desirae (cid=20215) attr= race= summon_type=fusion properly=True is_light_fiend=True is_link=False
- Luce the Dusk's Dark (cid=21625) attr= race= summon_type= properly=False is_light_fiend=False is_link=False
- Fiendsmith in Paradise (cid=20251) attr= race= summon_type= properly=False is_light_fiend=False is_link=False
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
      "Fiendsmith Token",
      "Fiendsmith's Desirae",
      "Luce the Dusk's Dark",
      "Fiendsmith in Paradise"
    ],
    "gy": [
      "Fiendsmith in Paradise",
      "Fiendsmith's Sanct",
      "Lacrima the Crimson Tears",
      "Fiendsmith's Sanct"
    ],
    "banished": [],
    "deck": [
      "The Duke of Demise",
      "Buio the Dawn's Light",
      "Lacrima the Crimson Tears",
      "Luce the Dusk's Dark",
      "Fiendsmith's Tract",
      "Mutiny in the Sky",
      "Fiendsmith's Tract",
      "Fiendsmith's Sanct",
      "Fiendsmith Engraver",
      "Buio the Dawn's Light",
      "Mutiny in the Sky",
      "Fiendsmith in Paradise",
      "Fiendsmith's Tract",
      "Mutiny in the Sky",
      "Fiendsmith Engraver",
      "Fiendsmith Engraver",
      "The Duke of Demise",
      "Lacrima the Crimson Tears",
      "Luce the Dusk's Dark",
      "Buio the Dawn's Light",
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
