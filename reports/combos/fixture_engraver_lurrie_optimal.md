# Combo Search Report: fixture_engraver_lurrie_optimal

## Core Actions
1. normal_summon: {'hand_index': 2, 'mz_index': 4, 'tribute_indices': []}
2. extra_deck_summon: {'extra_index': 1, 'summon_type': 'link', 'materials': [('mz', 4)], 'min_materials': 1, 'link_rating': 1}
3. extra_deck_summon: {'extra_index': 1, 'summon_type': 'link', 'materials': [('mz', 0), ('mz', 1)], 'min_materials': 2, 'link_rating': 2}

## Effect Actions
1. Fiendsmith's Requiem [20225] tribute_self_ss_fiendsmith: {'zone': 'emz', 'field_index': 0, 'source': 'deck', 'source_index': 4, 'mz_index': 1}
2. Lacrima the Crimson Tears [20490] send_fiendsmith_from_deck: {'zone': 'mz', 'field_index': 1, 'deck_index': 2}
3. Fiendsmith Engraver [20196] discard_search_fiendsmith_st: {'hand_index': 0, 'deck_index': 0}
4. Fiendsmith's Tract [20240] search_light_fiend_then_discard: {'hand_index': 3, 'deck_index': 2, 'discard_hand_index': 0}
5. Fabled Lurrie [8092] lurrie_discard_ss_self: {'gy_index': 5, 'mz_index': 0}
6. Fabled Lurrie [8092] lurrie_discard_ss_self: {'gy_index': 5, 'mz_index': 1}
7. Fiendsmith Engraver [20196] gy_shuffle_light_fiend_then_ss_self: {'gy_index': 3, 'target_gy_index': 5, 'mz_index': 2}
8. Fiendsmith's Tract [20240] gy_banish_fuse_fiendsmith: {'gy_index': 3, 'extra_index': 0, 'mz_index': 0, 'materials': [{'source': 'hand', 'index': 2}, {'source': 'mz', 'index': 1}, {'source': 'emz', 'index': 0}]}
9. Fiendsmith's Sequence [20238] equip_sequence_to_fiend: {'source': 'gy', 'source_index': 5, 'target_mz_index': 0}
10. Fiendsmith's Desirae [20215] desirae_negate: {'mz_index': 0}
11. Fiendsmith's Desirae [20215] desirae_negate: {'mz_index': 0}
12. Fiendsmith's Requiem [20225] equip_requiem_to_fiend: {'source': 'gy', 'source_index': 1, 'target_mz_index': 0}
13. Fiendsmith's Desirae [20215] desirae_negate: {'mz_index': 0}
14. Fiendsmith's Sequence [20196] send_equip_and_monster_to_gy: {'equip_zone': 'mz', 'equip_host_index': 0, 'equip_index': 0, 'monster_zone': 'mz', 'monster_index': 2}

## Final Snapshot
```json
{
  "zones": {
    "hand": [
      "Inert Card 1",
      "Inert Card 2"
    ],
    "field": [
      "Fiendsmith's Desirae"
    ],
    "gy": [
      "Generic LIGHT Fiend Body",
      "Fiendsmith in Paradise",
      "Fiendsmith Engraver",
      "Fabled Lurrie",
      "Fiendsmith's Sequence",
      "Fiendsmith Engraver"
    ],
    "banished": [
      "Fiendsmith's Tract"
    ],
    "deck": [
      "Fiendsmith's Sanct",
      "Fiendsmith Kyrie",
      "Lacrima the Crimson Tears"
    ],
    "extra": [
      "Fiendsmith's Lacrima",
      "Fiendsmith's Agnumday",
      "Fiendsmith's Rextremende",
      "Necroquip Princess",
      "D/D/D Wave High King Caesar"
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
- rank_key: (1, 1, 2)
- summary: S=1 A=1 B=2
- achieved:
  - A card Fiendsmith's Desirae (zone=field)
  - B condition Fiendsmith in Paradise in GY (zone=gy)
  - B condition Fiendsmith's Sequence in GY (zone=gy)
  - S condition Desirae equipped link (zone=field)
