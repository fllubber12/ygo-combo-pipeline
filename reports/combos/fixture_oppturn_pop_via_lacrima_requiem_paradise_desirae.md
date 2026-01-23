# Combo Search Report: fixture_oppturn_pop_via_lacrima_requiem_paradise_desirae

## Core Actions
(none)

## Effect Actions
1. Fiendsmith's Lacrima [20490] gy_shuffle_ss_fiendsmith_link: {'gy_index': 0, 'target_gy_index': 1, 'emz_index': 0}
2. Fiendsmith's Requiem [20225] tribute_self_ss_fiendsmith: {'zone': 'emz', 'field_index': 0, 'source': 'deck', 'source_index': 1, 'mz_index': 0}
3. Fiendsmith's Requiem [20225] equip_requiem_to_fiend: {'source': 'gy', 'source_index': 1, 'target_mz_index': 0}
4. Fiendsmith's Lacrima [20490] send_fiendsmith_from_deck: {'zone': 'mz', 'field_index': 0, 'deck_index': 0}
5. Fiendsmith in Paradise [20251] paradise_gy_banish_send_fiendsmith: {'gy_index': 1, 'send_source': 'extra', 'send_index': 0}
6. Opponent Card [20215] gy_desirae_send_field: {'desirae_gy_index': 1, 'cost_gy_index': 0, 'target_zone': 'stz', 'target_index': 0}

## Final Snapshot
```json
{
  "zones": {
    "hand": [],
    "field": [
      "Fiendsmith's Lacrima"
    ],
    "gy": [
      "Fiendsmith's Desirae",
      "Opponent Card"
    ],
    "banished": [
      "Fiendsmith in Paradise"
    ],
    "deck": [
      "Fiendsmith's Lacrima",
      "Generic LIGHT Fiend"
    ],
    "extra": []
  },
  "equipped_link_totals": [
    {
      "name": "Fiendsmith's Lacrima",
      "total": 1
    }
  ]
}
```

## Endboard Evaluation
- rank_key: (0, 0, 0)
- summary: S=0 A=0 B=0
- achieved:
  - (none)
