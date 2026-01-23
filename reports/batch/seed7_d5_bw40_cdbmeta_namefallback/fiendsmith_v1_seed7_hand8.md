# Batch Combo Report: fiendsmith_v1_seed7_hand8

- seed: 7
- hand: 20240, 21626, 20196, 21625, 21626

## Core Actions
1. normal_summon: {'hand_index': 3, 'mz_index': 2}
2. special_summon: {'hand_index': 1, 'mz_index': 1}
3. extra_deck_summon: {'extra_index': 1, 'summon_type': 'fusion', 'materials': [('mz', 2), ('mz', 1)], 'min_materials': 2, 'link_rating': 0}
4. extra_deck_summon: {'extra_index': 7, 'summon_type': 'link', 'materials': [('mz', 1)], 'min_materials': 1, 'link_rating': 1}

## Effect Actions
1. Fiendsmith Engraver [20196] discard_search_fiendsmith_st: {'hand_index': 2, 'deck_index': 14}
2. Fiendsmith's Tract [20240] search_light_fiend_then_discard: {'hand_index': 0, 'deck_index': 5, 'discard_hand_index': 4}
3. Fiendsmith Engraver [20196] gy_shuffle_light_fiend_then_ss_self: {'gy_index': 0, 'target_gy_index': 3, 'mz_index': 1}
4. Fiendsmith's Requiem [20225] equip_requiem_to_fiend: {'source': 'emz', 'source_index': 0, 'target_mz_index': 0}

## Target Eligibility Diagnostics
- mz_count: 1
- Fiendsmith's Desirae (cid=20215) attr=LIGHT race=FIEND summon_type=fusion properly=True is_light_fiend=True is_link=False
- open_mz: 4
- open_emz: 2
- hand_size: 2 fiend_in_hand: 0
- gy_size: 4
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
      "Mutiny in the Sky",
      "Mutiny in the Sky"
    ],
    "field": [
      "Fiendsmith's Desirae"
    ],
    "gy": [
      "Fiendsmith's Tract",
      "Fiendsmith in Paradise",
      "Luce the Dusk's Dark",
      "Fiendsmith Engraver"
    ],
    "banished": [],
    "deck": [
      "Buio the Dawn's Light",
      "Fiendsmith's Tract",
      "Lacrima the Crimson Tears",
      "Mutiny in the Sky",
      "Lacrima the Crimson Tears",
      "Luce the Dusk's Dark",
      "The Duke of Demise",
      "Buio the Dawn's Light",
      "Fiendsmith in Paradise",
      "Fiendsmith's Sanct",
      "Luce the Dusk's Dark",
      "Fiendsmith Engraver",
      "Buio the Dawn's Light",
      "The Duke of Demise",
      "The Duke of Demise",
      "Fiendsmith's Tract",
      "Fiendsmith's Sanct",
      "Fiendsmith in Paradise",
      "Fiendsmith's Sanct",
      "Lacrima the Crimson Tears",
      "Fiendsmith Engraver"
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
