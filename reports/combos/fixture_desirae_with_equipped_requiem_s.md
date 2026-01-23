# Combo Search Report: fixture_desirae_with_equipped_requiem_s

## Core Actions
(none)

## Effect Actions
1. Fiendsmith's Tract [20240] gy_banish_fuse_fiendsmith: {'gy_index': 0, 'extra_index': 0, 'mz_index': 0, 'materials': [{'source': 'hand', 'index': 0}, {'source': 'hand', 'index': 1}, {'source': 'hand', 'index': 2}]}
2. Fiendsmith's Requiem [20225] equip_requiem_to_fiend: {'source': 'gy', 'source_index': 3, 'target_mz_index': 0}
3. Fiendsmith Engraver [20196] gy_shuffle_light_fiend_then_ss_self: {'gy_index': 1, 'target_gy_index': 2, 'mz_index': 1}

## Final Snapshot
```json
{
  "zones": {
    "hand": [],
    "field": [
      "Fiendsmith's Desirae",
      "Fiendsmith Engraver"
    ],
    "gy": [
      "Fiendsmith's Requiem"
    ],
    "banished": [
      "Fiendsmith's Tract"
    ],
    "deck": [
      "Fiendsmith's Lacrima"
    ],
    "extra": []
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
- rank_key: (1, 1, 1)
- summary: S=1 A=1 B=1
- achieved:
  - A card Fiendsmith's Desirae (zone=field)
  - B condition Fiendsmith's Requiem in GY (zone=gy)
  - S condition Desirae equipped link (zone=field)
