# Batch Combo Report: fiendsmith_v1_seed7_hand7

- seed: 7
- hand: 20241, 21625, 20196, 21626, 21624

## Core Actions
1. normal_summon: {'hand_index': 2, 'mz_index': 2}
2. extra_deck_summon: {'extra_index': 1, 'summon_type': 'fusion', 'materials': [('mz', 2), ('mz', 1)], 'min_materials': 2, 'link_rating': None}
3. special_summon: {'hand_index': 0, 'mz_index': 1}

## Effect Actions
1. Fiendsmith's Sanct [20241] activate_sanct_token: {'hand_index': 0, 'mz_index': 1}
2. Fiendsmith Engraver [20196] discard_search_fiendsmith_st: {'hand_index': 1, 'deck_index': 0}
3. Fiendsmith's Tract [20240] search_light_fiend_then_discard: {'hand_index': 3, 'deck_index': 3, 'discard_hand_index': 0}
4. Fiendsmith Engraver [20196] gy_shuffle_light_fiend_then_ss_self: {'gy_index': 1, 'target_gy_index': 4, 'mz_index': 3}
5. Buio the Dawn's Light [21624] buio_hand_ss: {'hand_index': 0, 'target_mz_index': 0, 'mz_index': 2}

## Target Eligibility Diagnostics
- mz_count: 4
- Fiendsmith's Desirae (cid=20215) attr= race= summon_type=fusion properly=True is_light_fiend=True is_link=False
- Mutiny in the Sky (cid=21626) attr= race= summon_type= properly=False is_light_fiend=False is_link=False
- Buio the Dawn's Light (cid=21624) attr= race= summon_type= properly=False is_light_fiend=False is_link=False
- Fiendsmith Engraver (cid=20196) attr= race= summon_type= properly=False is_light_fiend=True is_link=False
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
      "Fiendsmith's Desirae",
      "Mutiny in the Sky",
      "Buio the Dawn's Light",
      "Fiendsmith Engraver"
    ],
    "gy": [
      "Fiendsmith's Sanct",
      "Fiendsmith's Tract",
      "Luce the Dusk's Dark",
      "Fiendsmith Token"
    ],
    "banished": [],
    "deck": [
      "Luce the Dusk's Dark",
      "Fiendsmith's Tract",
      "The Duke of Demise",
      "Fiendsmith's Tract",
      "Buio the Dawn's Light",
      "Lacrima the Crimson Tears",
      "Luce the Dusk's Dark",
      "Mutiny in the Sky",
      "Fiendsmith Engraver",
      "Fiendsmith's Sanct",
      "Fiendsmith in Paradise",
      "Fiendsmith in Paradise",
      "Lacrima the Crimson Tears",
      "The Duke of Demise",
      "Fiendsmith's Sanct",
      "Lacrima the Crimson Tears",
      "Mutiny in the Sky",
      "Fiendsmith in Paradise",
      "Buio the Dawn's Light",
      "The Duke of Demise",
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
- rank_key: (False, True, 0)
- summary: S=0 A=1 B=0

### Achieved Buckets
```json
[
  {
    "kind": "card",
    "name": "Fiendsmith's Desirae",
    "bucket": "A",
    "zone": "field",
    "notes": "needs equip spell / links equipped to be online"
  }
]
```
