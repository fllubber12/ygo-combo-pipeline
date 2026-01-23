# Combo Search Report: fixture_engraver_solo_minimal

## Core Actions
1. normal_summon: {'hand_index': 3, 'mz_index': 0, 'tribute_indices': []}
2. extra_deck_summon: {'extra_index': 1, 'summon_type': 'link', 'materials': [('mz', 0)], 'min_materials': 1, 'link_rating': 1}
3. extra_deck_summon: {'extra_index': 1, 'summon_type': 'link', 'materials': [('mz', 1), ('mz', 2)], 'min_materials': 2, 'link_rating': 2}
4. extra_deck_summon: {'extra_index': 3, 'summon_type': 'link', 'materials': [('emz', 0)], 'min_materials': 1, 'link_rating': 1}

## Effect Actions
1. Fiendsmith Engraver [20196] discard_search_fiendsmith_st: {'hand_index': 0, 'deck_index': 0}
2. Fiendsmith's Tract [20240] search_light_fiend_then_discard: {'hand_index': 4, 'deck_index': 3, 'discard_hand_index': 0}
3. Lacrima the Crimson Tears [20490] send_paradise_from_deck: {'zone': 'mz', 'field_index': 0, 'deck_index': 1}
4. Fiendsmith Engraver [20196] gy_shuffle_light_fiend_then_ss_self: {'gy_index': 0, 'target_gy_index': 4, 'mz_index': 1}
5. Fiendsmith's Requiem [20225] tribute_self_ss_fiendsmith: {'zone': 'emz', 'field_index': 0, 'source': 'deck', 'source_index': 2, 'mz_index': 2}
6. Fiendsmith's Sequence [20238] sequence_shuffle_fuse_fiend: {'seq_zone': 'emz', 'seq_index': 0, 'extra_index': 0, 'mz_index': 0, 'gy_indices': [4, 3, 5]}

## Final Snapshot
```json
{
  "zones": {
    "hand": [
      "Placeholder 2",
      "Placeholder 3",
      "Placeholder 4"
    ],
    "field": [
      "Fiendsmith's Desirae",
      "Fiendsmith's Requiem"
    ],
    "gy": [
      "Fiendsmith's Tract",
      "Placeholder 1",
      "Fiendsmith in Paradise",
      "Fiendsmith's Sequence"
    ],
    "banished": [],
    "deck": [
      "Fiendsmith's Sanct",
      "Fiendsmith Kyrie",
      "Fiendsmith Engraver",
      "Lacrima the Crimson Tears"
    ],
    "extra": [
      "Fiendsmith's Lacrima",
      "Fiendsmith's Agnumday",
      "Fiendsmith's Rextremende"
    ]
  },
  "equipped_link_totals": []
}
```

## Endboard Evaluation
- rank_key: (False, True, 3)
- summary: S=0 A=1 B=3
- achieved:
  - A card Fiendsmith's Desirae (zone=field)
  - B condition Fiendsmith in Paradise in GY (zone=gy)
  - B card Fiendsmith's Requiem (zone=field)
  - B condition Fiendsmith's Sequence in GY (zone=gy)
