# Batch Combo Report: fiendsmith_v1_seed7_hand5

- seed: 7
- hand: 21625, 21624, 21624, 21624, 21625

## Core Actions
1. normal_summon: {'hand_index': 1, 'mz_index': 0}
2. extra_deck_summon: {'extra_index': 1, 'summon_type': 'fusion', 'materials': [('mz', 0), ('mz', 1)], 'min_materials': 2, 'link_rating': 0}
3. special_summon: {'hand_index': 1, 'mz_index': 1}
4. special_summon: {'hand_index': 0, 'mz_index': 0}
5. extra_deck_summon: {'extra_index': 9, 'summon_type': 'link', 'materials': [('mz', 0), ('mz', 1)], 'min_materials': 2, 'link_rating': 2}

## Effect Actions
1. Buio the Dawn's Light [21624] buio_hand_ss: {'hand_index': 1, 'target_mz_index': 0, 'mz_index': 1}
2. Fiendsmith's Sequence [20226] sequence_20226_equip: {'source': 'emz', 'source_index': 0, 'target_mz_index': 2}

## Target Eligibility Diagnostics
- mz_count: 1
- Fiendsmith's Desirae (cid=20215) attr=LIGHT race=FIEND summon_type=fusion properly=True is_light_fiend=True is_link=False
- open_mz: 4
- open_emz: 2
- hand_size: 1 fiend_in_hand: 1
- gy_size: 4
- extra_has_sequence: False
- extra_has_requiem: True

## Equip Diagnostics
- equip_actions_available: 0
- equip_action_ids: (none)

## Final Snapshot
```json
{
  "zones": {
    "hand": [
      "Luce the Dusk's Dark"
    ],
    "field": [
      "Fiendsmith's Desirae"
    ],
    "gy": [
      "Buio the Dawn's Light",
      "Buio the Dawn's Light",
      "Luce the Dusk's Dark",
      "Buio the Dawn's Light"
    ],
    "banished": [],
    "deck": [
      "Mutiny in the Sky",
      "Lacrima the Crimson Tears",
      "Fiendsmith's Sanct",
      "Fiendsmith Engraver",
      "The Duke of Demise",
      "Fiendsmith in Paradise",
      "Fiendsmith Engraver",
      "Lacrima the Crimson Tears",
      "The Duke of Demise",
      "Fiendsmith Engraver",
      "Fiendsmith's Sanct",
      "Fiendsmith's Tract",
      "Fiendsmith in Paradise",
      "Lacrima the Crimson Tears",
      "The Duke of Demise",
      "Fiendsmith's Sanct",
      "Fiendsmith's Tract",
      "Fiendsmith in Paradise",
      "Mutiny in the Sky",
      "Mutiny in the Sky",
      "Fiendsmith's Tract",
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
      "Fiendsmith's Agnumday",
      "Muckraker From the Underworld",
      "Cross-Sheep",
      "S:P Little Knight"
    ]
  },
  "equipped_link_totals": [
    {
      "name": "Fiendsmith's Desirae",
      "total": 2
    }
  ]
}
```

## Endboard Evaluation
- rank_key: (True, True, 0)
- summary: S=1 A=1 B=0

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
    "name": "Desirae equipped link",
    "bucket": "S",
    "zone": "field",
    "notes": "Desirae with equipped Link rating"
  }
]
```
