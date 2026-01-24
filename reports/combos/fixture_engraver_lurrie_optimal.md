# Combo Search Report: fixture_engraver_lurrie_optimal

## Core Actions
1. normal_summon: {'hand_index': 2, 'mz_index': 0, 'tribute_indices': []}
2. extra_deck_summon: {'extra_index': 1, 'summon_type': 'link', 'materials': [('mz', 0)], 'min_materials': 1, 'link_rating': 1}

## Effect Actions
1. Fiendsmith Engraver [20196] discard_search_fiendsmith_st: {'hand_index': 0, 'deck_index': 0}
2. Fiendsmith Engraver [20196] gy_shuffle_light_fiend_then_ss_self: {'gy_index': 1, 'target_gy_index': 0, 'mz_index': 0}
3. Fiendsmith's Tract [20240] search_light_fiend_then_discard: {'hand_index': 3, 'deck_index': 4, 'discard_hand_index': 1}
4. Fiendsmith's Tract [20240] gy_banish_fuse_fiendsmith: {'gy_index': 0, 'extra_index': 0, 'mz_index': 1, 'materials': [{'source': 'emz', 'index': 0}, {'source': 'hand', 'index': 0}, {'source': 'hand', 'index': 2}]}
5. Fiendsmith's Requiem [20225] equip_requiem_to_fiend: {'source': 'gy', 'source_index': 1, 'target_mz_index': 1}
6. Fiendsmith's Desirae [20215] desirae_negate: {'mz_index': 1}
7. Fiendsmith's Requiem [20196] send_equip_and_monster_to_gy: {'equip_zone': 'mz', 'equip_host_index': 1, 'equip_index': 0, 'monster_zone': 'mz', 'monster_index': 0}
8. Fiendsmith's Requiem [20225] equip_requiem_to_fiend: {'source': 'gy', 'source_index': 3, 'target_mz_index': 1}

## Final Snapshot
```json
{
  "zones": {
    "hand": [
      "Inert Card 2"
    ],
    "field": [
      "Fiendsmith's Desirae"
    ],
    "gy": [
      "Inert Card 1",
      "Fabled Lurrie",
      "Fiendsmith Engraver",
      "Fiendsmith Engraver"
    ],
    "banished": [
      "Fiendsmith's Tract"
    ],
    "deck": [
      "Fiendsmith's Sanct",
      "Fiendsmith in Paradise",
      "Fiendsmith Kyrie",
      "Lacrima the Crimson Tears",
      "Generic LIGHT Fiend Body"
    ],
    "extra": [
      "Fiendsmith's Sequence",
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
- rank_key: (1, 1, 0)
- summary: S=1 A=1 B=0
- achieved:
  - A card Fiendsmith's Desirae (zone=field)
  - S condition Desirae equipped link (zone=field)
