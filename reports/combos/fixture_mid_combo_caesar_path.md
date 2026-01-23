# Combo Search Report: fixture_mid_combo_caesar_path

## Core Actions
1. extra_deck_summon: {'extra_index': 1, 'summon_type': 'link', 'materials': [('mz', 0), ('mz', 1)], 'min_materials': 2, 'link_rating': 2}

## Effect Actions
1. Fiendsmith Engraver [20196] gy_shuffle_light_fiend_then_ss_self: {'gy_index': 0, 'target_gy_index': 2, 'mz_index': 1}
2. Fiendsmith's Sequence [20238] sequence_shuffle_fuse_fiend: {'seq_zone': 'emz', 'seq_index': 0, 'extra_index': 0, 'mz_index': 1, 'gy_indices': [1, 0, 2]}
3. Fiendsmith's Sequence [20238] equip_sequence_to_fiend: {'source': 'emz', 'source_index': 0, 'target_mz_index': 1}
4. Fiendsmith's Desirae [20215] desirae_negate: {'mz_index': 1}
5. Fiendsmith's Tract [20240] search_light_fiend_then_discard: {'hand_index': 0, 'deck_index': 5, 'discard_hand_index': 1}
6. Fabled Lurrie [8092] lurrie_discard_ss_self: {'gy_index': 1, 'mz_index': 0}
7. Fiendsmith's Desirae [20215] desirae_negate: {'mz_index': 1}

## Final Snapshot
```json
{
  "zones": {
    "hand": [
      "Inert Card 1",
      "Inert Card 2",
      "Fiendsmith Engraver"
    ],
    "field": [
      "Fabled Lurrie",
      "Fiendsmith's Desirae"
    ],
    "gy": [
      "Fiendsmith's Tract"
    ],
    "banished": [],
    "deck": [
      "Fiendsmith's Sanct",
      "Fiendsmith in Paradise",
      "Fiendsmith Kyrie",
      "Lacrima the Crimson Tears",
      "Fiendsmith's Requiem",
      "Generic LIGHT Fiend Body",
      "Fiendsmith Engraver"
    ],
    "extra": [
      "Fiendsmith's Agnumday",
      "Necroquip Princess",
      "D/D/D Wave High King Caesar"
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
- rank_key: (1, 1, 0)
- summary: S=1 A=1 B=0
- achieved:
  - A card Fiendsmith's Desirae (zone=field)
  - S condition Desirae equipped link (zone=field)
