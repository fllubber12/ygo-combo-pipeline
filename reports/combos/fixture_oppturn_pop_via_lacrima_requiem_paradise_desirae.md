# Combo Search Report: fixture_oppturn_pop_via_lacrima_requiem_paradise_desirae

## Core Actions
(none)

## Effect Actions
1. Lacrima the Crimson Tears [20490] gy_shuffle_ss_fiendsmith_link: {'gy_index': 0, 'target_gy_index': 1, 'emz_index': 0}
2. Fiendsmith's Requiem [20225] tribute_self_ss_fiendsmith: {'zone': 'emz', 'field_index': 0, 'source': 'deck', 'source_index': 1, 'mz_index': 0}
3. Lacrima the Crimson Tears [20490] send_fiendsmith_from_deck: {'zone': 'mz', 'field_index': 0, 'deck_index': 0}
4. Fiendsmith in Paradise [20251] paradise_gy_banish_send_fiendsmith: {'gy_index': 2, 'send_source': 'extra', 'send_index': 0}
5. OPP_CARD_1 [20215] gy_desirae_send_field: {'desirae_gy_index': 2, 'cost_gy_index': 0, 'target_zone': 'stz', 'target_index': 0}

## Final Snapshot
```json
{
  "zones": {
    "hand": [],
    "field": [
      "Lacrima the Crimson Tears"
    ],
    "gy": [
      "Fiendsmith's Requiem",
      "Fiendsmith's Desirae",
      "OPP_CARD_1"
    ],
    "banished": [
      "Fiendsmith in Paradise"
    ],
    "deck": [
      "Lacrima the Crimson Tears",
      "G_LIGHT_FIEND_A"
    ],
    "extra": []
  },
  "equipped_link_totals": []
}
```

## Endboard Evaluation
- rank_key: (0, 0, 1)
- summary: S=0 A=0 B=1
- achieved:
  - B condition Fiendsmith's Requiem in GY (zone=gy)
