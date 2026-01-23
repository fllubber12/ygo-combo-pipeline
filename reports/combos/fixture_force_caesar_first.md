# Combo Search Report: fixture_force_caesar_first

## Core Actions
1. extra_deck_summon: {'extra_index': 1, 'summon_type': 'link', 'materials': [('mz', 2)], 'min_materials': 1, 'link_rating': 1}
2. extra_deck_summon: {'extra_index': 0, 'summon_type': 'xyz', 'materials': [('mz', 0), ('mz', 1)], 'min_materials': 2, 'link_rating': 0}

## Effect Actions
1. Fabled Lurrie [8092] lurrie_discard_ss_self: {'gy_index': 0, 'mz_index': 2}
2. Fiendsmith Engraver [20196] gy_shuffle_light_fiend_then_ss_self: {'gy_index': 0, 'target_gy_index': 1, 'mz_index': 1}
3. Fiendsmith's Requiem [20225] tribute_self_ss_fiendsmith: {'zone': 'emz', 'field_index': 0, 'source': 'deck', 'source_index': 0, 'mz_index': 0}

## Final Snapshot
```json
{
  "zones": {
    "hand": [],
    "field": [
      "Fiendsmith Engraver",
      "Fiendsmith Engraver",
      "Fabled Lurrie",
      "D/D/D Wave High King Caesar"
    ],
    "gy": [
      "Fiendsmith's Requiem"
    ],
    "banished": [],
    "deck": [],
    "extra": []
  },
  "equipped_link_totals": []
}
```

## Endboard Evaluation
- rank_key: (1, 0, 1)
- summary: S=1 A=0 B=1
- achieved:
  - B condition Fiendsmith's Requiem in GY (zone=gy)
  - S card D/D/D Wave High King Caesar (zone=field)
