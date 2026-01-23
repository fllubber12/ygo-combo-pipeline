# Batch Combo Report: fiendsmith_v1_seed7_hand4

- seed: 7
- hand: 20241, 21624, 21624, 20196, 20490

## Core Actions
1. normal_summon: {'hand_index': 4, 'mz_index': 2}
2. extra_deck_summon: {'extra_index': 1, 'summon_type': 'fusion', 'materials': [('mz', 1), ('mz', 2)], 'min_materials': 2, 'link_rating': 0}
3. extra_deck_summon: {'extra_index': 7, 'summon_type': 'link', 'materials': [('mz', 1)], 'min_materials': 1, 'link_rating': 1}

## Effect Actions
1. Lacrima the Crimson Tears [20490] send_paradise_from_deck: {'zone': 'mz', 'field_index': 2, 'deck_index': 3}
2. Fiendsmith Engraver [20196] discard_search_fiendsmith_st: {'hand_index': 3, 'deck_index': 2}
3. Fiendsmith's Sanct [20241] activate_sanct_token: {'hand_index': 0, 'mz_index': 1}
4. Fiendsmith's Sanct [20241] activate_sanct_token: {'hand_index': 2, 'mz_index': 1}
5. Fiendsmith's Requiem [20225] equip_requiem_to_fiend: {'source': 'emz', 'source_index': 0, 'target_mz_index': 0}

## Target Eligibility Diagnostics
- mz_count: 1
- Fiendsmith's Desirae (cid=20215) attr=LIGHT race=FIEND summon_type=fusion properly=True is_light_fiend=True is_link=False
- open_mz: 4
- open_emz: 2
- hand_size: 2 fiend_in_hand: 2
- gy_size: 7
- extra_has_sequence: True
- extra_has_requiem: False

## Equip Diagnostics
- equip_actions_available: 0
- equip_action_ids: (none)

## Final Snapshot
```json
{
  "zones": {
    "hand": [
      "Buio the Dawn's Light",
      "Buio the Dawn's Light"
    ],
    "field": [
      "Fiendsmith's Desirae"
    ],
    "gy": [
      "Fiendsmith in Paradise",
      "Fiendsmith Engraver",
      "Fiendsmith's Sanct",
      "Fiendsmith Token",
      "Lacrima the Crimson Tears",
      "Fiendsmith's Sanct",
      "Fiendsmith Token"
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
      "Fiendsmith's Sequence",
      "Fiendsmith's Sequence",
      "Fiendsmith's Agnumday",
      "Muckraker From the Underworld",
      "Cross-Sheep",
      "S:P Little Knight"
    ]
  },
  "equipped_link_totals": [
    {
      "name": "Fiendsmith's Desirae",
      "total": 1
    }
  ]
}
```

## Endboard Evaluation
- rank_key: (True, True, 1)
- summary: S=1 A=1 B=1

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
  },
  {
    "kind": "condition",
    "name": "Desirae equipped link",
    "bucket": "S",
    "zone": "field",
    "notes": "Desirae with equipped Link rating"
  }
]
```
