# Combo Search Report: fixture_double_engraver

## Core Actions
1. normal_summon: {'hand_index': 3, 'mz_index': 2, 'tribute_indices': []}
2. extra_deck_summon: {'extra_index': 1, 'summon_type': 'link', 'materials': [('mz', 2)], 'min_materials': 1, 'link_rating': 1}
3. extra_deck_summon: {'extra_index': 1, 'summon_type': 'link', 'materials': [('mz', 0), ('emz', 0)], 'min_materials': 2, 'link_rating': 2}
4. extra_deck_summon: {'extra_index': 5, 'summon_type': 'link', 'materials': [('mz', 0)], 'min_materials': 1, 'link_rating': 1}
5. extra_deck_summon: {'extra_index': 1, 'summon_type': 'link', 'materials': [('mz', 0), ('emz', 1)], 'min_materials': 2, 'link_rating': 3}

## Effect Actions
1. Fiendsmith Engraver [20196] discard_search_fiendsmith_st: {'hand_index': 0, 'deck_index': 0}
2. Fiendsmith's Tract [20240] search_light_fiend_then_discard: {'hand_index': 4, 'deck_index': 4, 'discard_hand_index': 0}
3. Lacrima the Crimson Tears [20490] send_fiendsmith_from_deck: {'zone': 'mz', 'field_index': 2, 'deck_index': 1}
4. Fiendsmith Engraver [20196] gy_shuffle_light_fiend_then_ss_self: {'gy_index': 0, 'target_gy_index': 4, 'mz_index': 0}
5. Fiendsmith's Sequence [20238] sequence_shuffle_fuse_fiend: {'seq_zone': 'emz', 'seq_index': 1, 'extra_index': 0, 'mz_index': 0, 'gy_indices': [1, 3, 4]}
6. Fiendsmith's Requiem [20225] tribute_self_ss_fiendsmith: {'zone': 'emz', 'field_index': 0, 'source': 'deck', 'source_index': 4, 'mz_index': 0}
7. Fiendsmith's Agnumday [20521] agnumday_revive_equip: {'zone': 'emz', 'field_index': 0, 'gy_index': 2, 'mz_index': 0}
8. Fiendsmith's Desirae [20215] desirae_negate: {'mz_index': 0}
9. Fiendsmith's Desirae [20215] desirae_negate: {'mz_index': 0}
10. Fiendsmith's Desirae [20215] desirae_negate: {'mz_index': 0}

## Final Snapshot
```json
{
  "zones": {
    "hand": [
      "Generic LIGHT Fiend Body",
      "Inert Card 1",
      "Inert Card 2"
    ],
    "field": [
      "Fiendsmith's Desirae"
    ],
    "gy": [
      "Fiendsmith's Tract",
      "Fiendsmith in Paradise",
      "Fiendsmith's Requiem",
      "Fiendsmith Engraver",
      "Fiendsmith's Sequence"
    ],
    "banished": [],
    "deck": [
      "Fiendsmith's Sanct",
      "Fiendsmith Kyrie",
      "Fabled Lurrie",
      "Lacrima the Crimson Tears",
      "Fiendsmith Engraver"
    ],
    "extra": [
      "Fiendsmith's Lacrima",
      "Fiendsmith's Rextremende",
      "Necroquip Princess",
      "D/D/D Wave High King Caesar"
    ]
  },
  "equipped_link_totals": [
    {
      "name": "Fiendsmith's Desirae",
      "total": 3
    }
  ]
}
```

## Endboard Evaluation
- rank_key: (1, 1, 3)
- summary: S=1 A=1 B=3
- achieved:
  - A card Fiendsmith's Desirae (zone=field)
  - B condition Fiendsmith in Paradise in GY (zone=gy)
  - B condition Fiendsmith's Requiem in GY (zone=gy)
  - B condition Fiendsmith's Sequence in GY (zone=gy)
  - S condition Desirae equipped link (zone=field)
