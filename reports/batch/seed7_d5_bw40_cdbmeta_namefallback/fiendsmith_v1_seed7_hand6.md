# Batch Combo Report: fiendsmith_v1_seed7_hand6

- seed: 7
- hand: 20196, 21625, 20389, 21625, 20196

## Core Actions
1. normal_summon: {'hand_index': 0, 'mz_index': 2}
2. special_summon: {'hand_index': 1, 'mz_index': 1}
3. extra_deck_summon: {'extra_index': 1, 'summon_type': 'fusion', 'materials': [('mz', 2), ('mz', 1)], 'min_materials': 2, 'link_rating': 0}
4. extra_deck_summon: {'extra_index': 7, 'summon_type': 'link', 'materials': [('mz', 1)], 'min_materials': 1, 'link_rating': 1}

## Effect Actions
1. Fiendsmith Engraver [20196] discard_search_fiendsmith_st: {'hand_index': 3, 'deck_index': 0}
2. Fiendsmith Engraver [20196] gy_shuffle_light_fiend_then_ss_self: {'gy_index': 0, 'target_gy_index': 1, 'mz_index': 1}
3. Fiendsmith's Requiem [20225] equip_requiem_to_fiend: {'source': 'emz', 'source_index': 0, 'target_mz_index': 0}

## Target Eligibility Diagnostics
- mz_count: 1
- Fiendsmith's Desirae (cid=20215) attr=LIGHT race=FIEND summon_type=fusion properly=True is_light_fiend=True is_link=False
- open_mz: 4
- open_emz: 2
- hand_size: 3 fiend_in_hand: 2
- gy_size: 2
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
      "Luce the Dusk's Dark",
      "Luce the Dusk's Dark",
      "Fiendsmith's Sanct"
    ],
    "field": [
      "Fiendsmith's Desirae"
    ],
    "gy": [
      "The Duke of Demise",
      "Fiendsmith Engraver"
    ],
    "banished": [],
    "deck": [
      "Lacrima the Crimson Tears",
      "Fiendsmith's Sanct",
      "Fiendsmith in Paradise",
      "Lacrima the Crimson Tears",
      "Buio the Dawn's Light",
      "Fiendsmith's Tract",
      "The Duke of Demise",
      "Fiendsmith's Sanct",
      "Buio the Dawn's Light",
      "Mutiny in the Sky",
      "Mutiny in the Sky",
      "Fiendsmith in Paradise",
      "Fiendsmith Engraver",
      "Luce the Dusk's Dark",
      "Lacrima the Crimson Tears",
      "Buio the Dawn's Light",
      "Mutiny in the Sky",
      "Fiendsmith's Tract",
      "Fiendsmith in Paradise",
      "The Duke of Demise",
      "Fiendsmith's Tract",
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
