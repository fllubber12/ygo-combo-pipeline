# Combo Search Report: fixture_two_engravers_on_field

## Core Actions
1. extra_deck_summon: {'extra_index': 0, 'summon_type': 'link', 'materials': [('mz', 0), ('mz', 1)], 'min_materials': 2, 'link_rating': 2}
2. extra_deck_summon: {'extra_index': 0, 'summon_type': 'link', 'materials': [('mz', 0), ('emz', 0)], 'min_materials': 2, 'link_rating': 3}

## Effect Actions
1. Fiendsmith's Tract [20240] gy_banish_fuse_fiendsmith: {'gy_index': 1, 'extra_index': 0, 'mz_index': 3, 'materials': [{'source': 'mz', 'index': 0}, {'source': 'hand', 'index': 0}, {'source': 'mz', 'index': 2}]}
2. Fabled Lurrie [8092] lurrie_discard_ss_self: {'gy_index': 4, 'mz_index': 0}
3. Fiendsmith's Requiem [20225] equip_requiem_to_fiend: {'source': 'gy', 'source_index': 1, 'target_mz_index': 3}
4. Fabled Lurrie [8092] lurrie_discard_ss_self: {'gy_index': 3, 'mz_index': 0}
5. Fiendsmith's Requiem [20196] send_equip_and_monster_to_gy: {'equip_zone': 'mz', 'equip_host_index': 3, 'equip_index': 0, 'monster_zone': 'mz', 'monster_index': 3}
6. Fabled Lurrie [20215] gy_desirae_send_field: {'desirae_gy_index': 5, 'cost_gy_index': 0, 'target_zone': 'mz', 'target_index': 0}
7. Fabled Lurrie [8092] lurrie_discard_ss_self: {'gy_index': 5, 'mz_index': 0}
8. Fiendsmith's Agnumday [20521] agnumday_revive_equip: {'zone': 'emz', 'field_index': 1, 'gy_index': 4, 'mz_index': 0}
9. Fiendsmith's Desirae [20215] desirae_negate: {'mz_index': 0}
10. Fiendsmith's Desirae [20215] desirae_negate: {'mz_index': 0}
11. Fiendsmith's Desirae [20215] desirae_negate: {'mz_index': 0}

## Final Snapshot
```json
{
  "zones": {
    "hand": [
      "Inert Card 1"
    ],
    "field": [
      "Fiendsmith's Desirae"
    ],
    "gy": [
      "Fiendsmith Engraver",
      "Lacrima the Crimson Tears",
      "Fiendsmith Engraver",
      "Fiendsmith's Requiem",
      "Fabled Lurrie",
      "Fiendsmith's Sequence"
    ],
    "banished": [
      "Fiendsmith's Tract"
    ],
    "deck": [
      "Fiendsmith in Paradise",
      "Fiendsmith Kyrie",
      "Generic LIGHT Fiend Body"
    ],
    "extra": [
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
- rank_key: (1, 1, 2)
- summary: S=1 A=1 B=2
- achieved:
  - A card Fiendsmith's Desirae (zone=field)
  - B condition Fiendsmith's Requiem in GY (zone=gy)
  - B condition Fiendsmith's Sequence in GY (zone=gy)
  - S condition Desirae equipped link (zone=field)
