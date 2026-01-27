# Rules Coverage Matrix

| Rule Concept | Enforcement (placeholder) | Planned Tests | Notes / Edge Cases |
| --- | --- | --- | --- |
| Turn structure + first turn restrictions | `validate_turn_phase()` | `test_turn_phase_order`, `test_first_turn_no_draw` | First turn draw rules must follow TCG. |
| Normal Summon/Set shared budget | `validate_normal_summon_set_limit()` | `test_normal_summon_set_shared_budget` | Enforced in v1; extra Normal Summon/Set effects modeled later. |
| Special Summon procedures (Fusion) | `validate_fusion_summon()` | `test_fusion_materials`, `test_fusion_zone_legality` | Uses correct materials and zones. |
| Special Summon procedures (Synchro) | `validate_synchro_summon()` | `test_synchro_level_sum`, `test_synchro_zone_legality` | Tuner + non-tuner rules. |
| Special Summon procedures (Xyz) | `validate_xyz_summon()` | `test_xyz_rank_match`, `test_xyz_material_count` | Materials become attachments. |
| Special Summon procedures (Link) | `validate_link_summon()` | `test_link_material_count`, `test_link_zone_placement` | Enforced in v1; Link marker placement rules. |
| Link material counting | `validate_link_material_count()` | `test_link_material_counting` | Enforced in v1; Link monsters count as 1 or Link Rating. |
| Extra Deck placement (2021 rules) | `validate_extra_deck_placement()` | `test_extra_deck_mz_placement`, `test_link_zone_placement` | Enforced in v1; Fusion/Synchro/Xyz to MMZ allowed. |
| Zone legality + placement | `validate_zone_placement()` | `test_zone_capacity`, `test_emz_placement` | Enforced in v1. |
| Chain legality + timing windows | `validate_chain_timing()` | `test_chain_building`, `test_priority_passing` | Enforced in v1; Fast Effect Timing. |
| PSCT activation vs resolution | `parse_psct_semantics()` | `test_psct_costs_at_activation` | Enforced in v1; CONDITION : ACTIVATION ; RESOLUTION. |
| Mandatory vs optional triggers | `validate_trigger_type()` | `test_mandatory_triggers` | Documented as out of v1 scope if not implemented. |
