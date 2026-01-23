import json
import subprocess
import sys
import unittest
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "src"))

from combos.endboard_evaluator import evaluate_endboard  # noqa: E402
from sim.effects.fiendsmith_effects import is_fiendsmith_st, total_equipped_link_rating  # noqa: E402
from sim.effects.registry import apply_effect_action, enumerate_effect_actions  # noqa: E402
from sim.effects.types import EffectAction  # noqa: E402
from sim.errors import IllegalActionError  # noqa: E402
from sim.search import search_best_line  # noqa: E402
from sim.state import GameState  # noqa: E402


def load_snapshot(report_path: Path) -> dict:
    content = report_path.read_text(encoding="utf-8")
    start = content.find("```json")
    if start == -1:
        raise AssertionError("Missing JSON block in report.")
    start = content.find("\n", start) + 1
    end = content.find("```", start)
    if end == -1:
        raise AssertionError("Unterminated JSON block in report.")
    return json.loads(content[start:end])


def run_scenario_inline(scenario_name: str):
    scenario_path = repo_root / "tests" / "fixtures" / "combo_scenarios" / f"{scenario_name}.json"
    scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
    state = GameState.from_snapshot(scenario.get("state", {}))
    search_cfg = scenario.get("search", {})
    return search_best_line(
        state,
        max_depth=int(search_cfg.get("max_depth", 2)),
        beam_width=int(search_cfg.get("beam_width", 10)),
        allowed_actions=search_cfg.get("allowed_actions"),
        prefer_longest=bool(search_cfg.get("prefer_longest", False)),
    )


class TestFiendsmithMoreEffects(unittest.TestCase):
    def run_scenario(self, scenario_name: str) -> Path:
        scenario = repo_root / "tests" / "fixtures" / "combo_scenarios" / f"{scenario_name}.json"
        report = repo_root / "reports" / "combos" / f"{scenario_name}.md"
        if report.exists():
            report.unlink()
        result = subprocess.run(
            [
                sys.executable,
                str(repo_root / "scripts" / "combos" / "search_combo.py"),
                "--scenario",
                str(scenario),
            ],
            cwd=str(repo_root),
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(report.exists())
        return report

    def test_engraver_revive(self):
        report = self.run_scenario("fixture_engraver_revive")
        snapshot = load_snapshot(report)
        self.assertIn("Fiendsmith Engraver", snapshot["zones"]["field"])
        self.assertIn("Fiendsmith's Lacrima", snapshot["zones"]["deck"])

    def test_requiem_tribute_ss(self):
        report = self.run_scenario("fixture_requiem_tribute_ss")
        snapshot = load_snapshot(report)
        self.assertIn("Fiendsmith's Lacrima", snapshot["zones"]["field"])
        self.assertIn("Fiendsmith's Requiem", snapshot["zones"]["gy"])

    def test_requiem_fail_closed_on_no_open_mz(self):
        snapshot = {
            "zones": {
                "hand": [],
                "deck": [{"cid": "20490", "name": "Fiendsmith's Lacrima"}],
                "gy": [],
                "banished": [],
                "extra": [],
                "field_zones": {
                    "mz": [
                        {"cid": "20196", "name": "Fiendsmith Engraver"},
                        {"cid": "20196", "name": "Fiendsmith Engraver"},
                        {"cid": "20196", "name": "Fiendsmith Engraver"},
                        {"cid": "20196", "name": "Fiendsmith Engraver"},
                        {"cid": "20196", "name": "Fiendsmith Engraver"},
                    ],
                    "emz": [
                        {"cid": "20225", "name": "Fiendsmith's Requiem"},
                        None,
                    ],
                },
            }
        }
        state = GameState.from_snapshot(snapshot)
        action = EffectAction(
            cid="20225",
            name="Fiendsmith's Requiem",
            effect_id="tribute_self_ss_fiendsmith",
            params={
                "zone": "emz",
                "field_index": 0,
                "source": "deck",
                "source_index": 0,
                "mz_index": 0,
            },
            sort_key=("20225",),
        )
        with self.assertRaises(IllegalActionError):
            apply_effect_action(state, action)

    def test_lacrima_send_fiendsmith_from_deck(self):
        """Lacrima CT can send any Fiendsmith card from deck to GY."""
        snapshot = {
            "zones": {
                "hand": [],
                "deck": [{"cid": "20251", "name": "Fiendsmith in Paradise"}],
                "gy": [],
                "field_zones": {
                    "mz": [{"cid": "20490", "name": "Lacrima the Crimson Tears"}, None, None, None, None],
                    "emz": [None, None],
                },
            }
        }
        state = GameState.from_snapshot(snapshot)
        actions = [
            action
            for action in enumerate_effect_actions(state)
            if action.effect_id == "send_fiendsmith_from_deck"
        ]
        self.assertTrue(actions)
        new_state = apply_effect_action(state, actions[0])
        self.assertTrue(any(card.cid == "20251" for card in new_state.gy))
        self.assertTrue(new_state.opt_used.get("20490:e1"))

    def test_lacrima_can_send_kyrie_from_deck(self):
        """Lacrima CT can send Kyrie (Trap) from deck to GY."""
        snapshot = {
            "zones": {
                "hand": [],
                "deck": [{"cid": "20816", "name": "Fiendsmith Kyrie"}],
                "gy": [],
                "field_zones": {
                    "mz": [{"cid": "20490", "name": "Lacrima the Crimson Tears"}, None, None, None, None],
                    "emz": [None, None],
                },
            }
        }
        state = GameState.from_snapshot(snapshot)
        actions = [
            action
            for action in enumerate_effect_actions(state)
            if action.effect_id == "send_fiendsmith_from_deck"
        ]
        self.assertTrue(actions, "Lacrima CT should be able to send Kyrie from deck")
        new_state = apply_effect_action(state, actions[0])
        self.assertTrue(any(card.cid == "20816" for card in new_state.gy))

    def test_lacrima_send_fails_without_fiendsmith_target(self):
        """Lacrima CT cannot send non-Fiendsmith cards from deck."""
        snapshot = {
            "zones": {
                "hand": [],
                "deck": [{"cid": "RANDOM_CARD", "name": "Random Card"}],
                "gy": [],
                "field_zones": {
                    "mz": [{"cid": "20490", "name": "Lacrima the Crimson Tears"}, None, None, None, None],
                    "emz": [None, None],
                },
            }
        }
        state = GameState.from_snapshot(snapshot)
        actions = [
            action
            for action in enumerate_effect_actions(state)
            if action.effect_id == "send_fiendsmith_from_deck"
        ]
        self.assertFalse(actions)

    def test_lacrima_gy_ss_requiem(self):
        snapshot = {
            "zones": {
                "gy": [
                    {"cid": "20490", "name": "Fiendsmith's Lacrima"},
                    {"cid": "20225", "name": "Fiendsmith's Requiem", "properly_summoned": True},
                ],
                "field_zones": {
                    "mz": [None, None, None, None, None],
                    "emz": [None, None],
                },
            },
            "events": ["OPP_TURN"],
        }
        state = GameState.from_snapshot(snapshot)
        actions = [
            action
            for action in enumerate_effect_actions(state)
            if action.effect_id == "gy_shuffle_ss_fiendsmith_link"
        ]
        self.assertTrue(actions)
        new_state = apply_effect_action(state, actions[0])
        self.assertIsNotNone(new_state.field.emz[0])
        self.assertEqual(new_state.field.emz[0].name, "Fiendsmith's Requiem")
        self.assertTrue(any(card.cid == "20490" for card in new_state.deck))
        self.assertTrue(new_state.opt_used.get("20490:e2"))

    def test_requiem_tribute_ss_lacrima(self):
        snapshot = {
            "zones": {
                "hand": [],
                "deck": [{"cid": "20490", "name": "Fiendsmith's Lacrima"}],
                "gy": [],
                "field_zones": {
                    "mz": [None, None, None, None, None],
                    "emz": [{"cid": "20225", "name": "Fiendsmith's Requiem"}, None],
                },
            },
            "phase": "Main Phase 1",
        }
        state = GameState.from_snapshot(snapshot)
        actions = [
            action
            for action in enumerate_effect_actions(state)
            if action.cid == "20225"
        ]
        self.assertTrue(actions)
        new_state = apply_effect_action(state, actions[0])
        field_names = [card.name for card in new_state.field.mz if card]
        self.assertIn("Fiendsmith's Lacrima", field_names)
        self.assertIn("Fiendsmith's Requiem", [card.name for card in new_state.gy])
        self.assertTrue(new_state.opt_used.get("20225:e1"))

    def test_paradise_gy_trigger_requires_event(self):
        snapshot = {
            "zones": {
                "gy": [{"cid": "20251", "name": "Fiendsmith in Paradise"}],
                "extra": [{"cid": "20215", "name": "Fiendsmith's Desirae"}],
            }
        }
        state = GameState.from_snapshot(snapshot)
        actions = [
            action
            for action in enumerate_effect_actions(state)
            if action.effect_id == "gy_banish_send_desirae"
        ]
        self.assertFalse(actions)

        snapshot["events"] = ["OPP_SPECIAL_SUMMON"]
        state = GameState.from_snapshot(snapshot)
        actions = [
            action
            for action in enumerate_effect_actions(state)
            if action.effect_id == "gy_banish_send_desirae"
        ]
        self.assertTrue(actions)
        new_state = apply_effect_action(state, actions[0])
        self.assertTrue(any(card.cid == "20251" for card in new_state.banished))
        self.assertTrue(any(card.cid == "20215" for card in new_state.gy))
        self.assertTrue(new_state.opt_used.get("20251:e1"))
        self.assertIn("20215", new_state.last_moved_to_gy)

    def test_desirae_gy_trigger_requires_cost(self):
        snapshot = {
            "zones": {
                "gy": [{"cid": "20215", "name": "Fiendsmith's Desirae"}],
                "field_zones": {
                    "mz": [None, None, None, None, None],
                    "emz": [None, None],
                    "stz": [{"cid": "OPP_CARD_1", "name": "Opponent Card"}, None, None, None, None],
                    "fz": [None],
                },
            },
            "last_moved_to_gy": ["20215"],
        }
        state = GameState.from_snapshot(snapshot)
        actions = [
            action
            for action in enumerate_effect_actions(state)
            if action.effect_id == "gy_desirae_send_field"
        ]
        self.assertFalse(actions)

    def test_desirae_gy_trigger_sends_opponent_card(self):
        snapshot = {
            "zones": {
                "gy": [
                    {"cid": "20215", "name": "Fiendsmith's Desirae"},
                    {"cid": "20196", "name": "Fiendsmith Engraver"},
                ],
                "field_zones": {
                    "mz": [None, None, None, None, None],
                    "emz": [None, None],
                    "stz": [{"cid": "OPP_CARD_1", "name": "Opponent Card"}, None, None, None, None],
                    "fz": [None],
                },
            },
            "last_moved_to_gy": ["20215"],
        }
        state = GameState.from_snapshot(snapshot)
        actions = [
            action
            for action in enumerate_effect_actions(state)
            if action.effect_id == "gy_desirae_send_field"
        ]
        self.assertTrue(actions)
        new_state = apply_effect_action(state, actions[0])
        self.assertTrue(any(card.name == "Opponent Card" for card in new_state.gy))
        self.assertTrue(any(card.cid == "20196" for card in new_state.deck))
        self.assertTrue(new_state.opt_used.get("20215:e1"))

    def test_requiem_equip_from_gy_success(self):
        snapshot = {
            "zones": {
                "gy": [{"cid": "20225", "name": "Fiendsmith's Requiem"}],
                "field_zones": {
                    "mz": [{"cid": "20215", "name": "Fiendsmith's Desirae"}, None, None, None, None],
                    "emz": [None, None],
                },
            }
        }
        state = GameState.from_snapshot(snapshot)
        actions = [
            action
            for action in enumerate_effect_actions(state)
            if action.effect_id == "equip_requiem_to_fiend"
        ]
        self.assertTrue(actions)
        new_state = apply_effect_action(state, actions[0])
        desirae = new_state.field.mz[0]
        self.assertIsNotNone(desirae)
        self.assertTrue(any(card.cid == "20225" for card in desirae.equipped))

    def test_requiem_equip_requires_light_nonlink_fiend_target(self):
        snapshot = {
            "zones": {
                "gy": [{"cid": "20225", "name": "Fiendsmith's Requiem"}],
                "field_zones": {
                    "mz": [
                        {
                            "cid": "DARK_FIEND",
                            "name": "Dark Fiend",
                            "metadata": {"attribute": "DARK", "race": "FIEND"},
                        },
                        None,
                        None,
                        None,
                        None,
                    ],
                    "emz": [None, None],
                },
            }
        }
        state = GameState.from_snapshot(snapshot)
        actions = [
            action
            for action in enumerate_effect_actions(state)
            if action.effect_id == "equip_requiem_to_fiend"
        ]
        self.assertFalse(actions)

        snapshot["zones"]["field_zones"]["mz"][0] = {
            "cid": "LINK_FIEND",
            "name": "Link Fiend",
            "metadata": {"attribute": "LIGHT", "race": "FIEND", "link_rating": 1},
        }
        state = GameState.from_snapshot(snapshot)
        actions = [
            action
            for action in enumerate_effect_actions(state)
            if action.effect_id == "equip_requiem_to_fiend"
        ]
        self.assertFalse(actions)

    def test_total_equipped_link_rating_counts_requiem_as_1(self):
        snapshot = {
            "zones": {
                "field_zones": {
                    "mz": [
                        {
                            "cid": "20215",
                            "name": "Fiendsmith's Desirae",
                            "equipped": [
                                {
                                    "cid": "20225",
                                    "name": "Fiendsmith's Requiem",
                                    "metadata": {"link_rating": 1},
                                }
                            ],
                        },
                        None,
                        None,
                        None,
                        None,
                    ],
                    "emz": [None, None],
                }
            }
        }
        state = GameState.from_snapshot(snapshot)
        self.assertEqual(total_equipped_link_rating(state.field.mz[0]), 1)

    def test_desirae_negate_credit_scales_with_equipped_link_rating(self):
        snapshot = {
            "zones": {
                "field_zones": {
                    "mz": [
                        {
                            "cid": "20215",
                            "name": "Fiendsmith's Desirae",
                            "equipped": [
                                {
                                    "cid": "20225",
                                    "name": "Fiendsmith's Requiem",
                                    "metadata": {"link_rating": 1},
                                }
                            ],
                        },
                        None,
                        None,
                        None,
                        None,
                    ],
                    "emz": [None, None],
                }
            }
        }
        state = GameState.from_snapshot(snapshot)
        actions = [
            action
            for action in enumerate_effect_actions(state)
            if action.effect_id == "desirae_negate"
        ]
        self.assertTrue(actions)
        new_state = apply_effect_action(state, actions[0])
        actions_after = [
            action
            for action in enumerate_effect_actions(new_state)
            if action.effect_id == "desirae_negate"
        ]
        self.assertFalse(actions_after)

    def test_agnumday_revive_equips_desirae(self):
        snapshot = {
            "zones": {
                "gy": [
                    {
                        "cid": "20215",
                        "name": "Fiendsmith's Desirae",
                        "metadata": {"from_extra": True},
                        "properly_summoned": True,
                    },
                ],
                "field_zones": {
                    "mz": [None, None, None, None, None],
                    "emz": [
                        {"cid": "20521", "name": "Fiendsmith's Agnumday", "metadata": {"link_rating": 3}},
                        None,
                    ],
                },
            }
        }
        state = GameState.from_snapshot(snapshot)
        actions = [
            action
            for action in enumerate_effect_actions(state)
            if action.effect_id == "agnumday_revive_equip"
        ]
        self.assertTrue(actions)
        new_state = apply_effect_action(state, actions[0])
        desirae = new_state.field.mz[0]
        self.assertIsNotNone(desirae)
        self.assertTrue(any(card.cid == "20521" for card in desirae.equipped))

    def test_agnumday_requires_light_nonlink(self):
        snapshot = {
            "zones": {
                "gy": [
                    {"cid": "DARK_TARGET", "name": "Dark Target", "metadata": {"attribute": "DARK", "race": "FIEND"}},
                    {
                        "cid": "LINK_TARGET",
                        "name": "Link Target",
                        "metadata": {"attribute": "LIGHT", "race": "FIEND", "link_rating": 1},
                    },
                ],
                "field_zones": {
                    "mz": [None, None, None, None, None],
                    "emz": [
                        {"cid": "20521", "name": "Fiendsmith's Agnumday", "metadata": {"link_rating": 3}},
                        None,
                    ],
                },
            }
        }
        state = GameState.from_snapshot(snapshot)
        actions = [
            action
            for action in enumerate_effect_actions(state)
            if action.effect_id == "agnumday_revive_equip"
        ]
        self.assertFalse(actions)

    def test_agnumday_requires_properly_summoned_extra(self):
        snapshot = {
            "zones": {
                "gy": [
                    {
                        "cid": "20215",
                        "name": "Fiendsmith's Desirae",
                        "metadata": {"from_extra": True},
                        "properly_summoned": False,
                    },
                ],
                "field_zones": {
                    "mz": [None, None, None, None, None],
                    "emz": [
                        {"cid": "20521", "name": "Fiendsmith's Agnumday", "metadata": {"link_rating": 3}},
                        None,
                    ],
                },
            }
        }
        state = GameState.from_snapshot(snapshot)
        actions = [
            action
            for action in enumerate_effect_actions(state)
            if action.effect_id == "agnumday_revive_equip"
        ]
        self.assertFalse(actions)
    def test_sanct_activation_from_empty_field(self):
        snapshot = {
            "zones": {
                "hand": [
                    {"cid": "20241", "name": "Fiendsmith's Sanct"},
                ],
                "field": [],
                "gy": [],
                "banished": [],
                "deck": [],
                "extra": [],
            }
        }
        state = GameState.from_snapshot(snapshot)
        actions = [action for action in enumerate_effect_actions(state) if action.cid == "20241"]
        self.assertTrue(actions)

        new_state = apply_effect_action(state, actions[0])
        self.assertTrue(any(card.cid == "20241" for card in new_state.gy))
        self.assertTrue(any(card and card.name == "Fiendsmith Token" for card in new_state.field.mz))

    def test_sanct_activation_fails_with_non_light_fiend(self):
        snapshot = {
            "zones": {
                "hand": [
                    {"cid": "20241", "name": "Fiendsmith's Sanct"},
                ],
                "field": [
                    {"cid": "NON_LIGHT_FIEND", "name": "Dark Monster", "metadata": {"attribute": "DARK"}},
                ],
                "gy": [],
                "banished": [],
                "deck": [],
                "extra": [],
            }
        }
        state = GameState.from_snapshot(snapshot)
        actions = [action for action in enumerate_effect_actions(state) if action.cid == "20241"]
        self.assertFalse(actions)

    def test_engraver_search_excludes_link_cids(self):
        self.assertFalse(is_fiendsmith_st("20226"))
        self.assertFalse(is_fiendsmith_st("20521"))

    def test_caesar_via_sanct_fixture(self):
        report = self.run_scenario("fixture_caesar_via_sanct")
        snapshot = load_snapshot(report)
        evaluation = evaluate_endboard(snapshot)
        self.assertTrue(any(item["bucket"] == "S" and item["name"] == "D/D/D Wave High King Caesar"
                            for item in evaluation["achieved"]))

    def test_requiem_link_summon_fixture(self):
        result = run_scenario_inline("fixture_requiem_link_summon")
        final_state = result.final_state
        self.assertIsNotNone(final_state.field.emz[0])
        self.assertEqual(final_state.field.emz[0].name, "Fiendsmith's Requiem")
        gy_names = [card.name for card in final_state.gy]
        self.assertIn("Material A", gy_names)
        self.assertNotIn("Material B", gy_names)

    def test_tract_gy_fusion_desirae_success(self):
        snapshot = {
            "zones": {
                "gy": [
                    {"cid": "20240", "name": "Fiendsmith's Tract"},
                ],
                "hand": [
                    {"cid": "20225", "name": "Fiendsmith's Requiem"},
                ],
                "field_zones": {
                    "mz": [
                        {"cid": "20196", "name": "Fiendsmith Engraver"},
                        {"cid": "20214", "name": "Fiendsmith's Lacrima"},
                        None,
                        None,
                        None,
                    ],
                    "emz": [None, None],
                },
                "extra": [
                    {
                        "cid": "20215",
                        "name": "Fiendsmith's Desirae",
                        "metadata": {"summon_type": "fusion", "min_materials": 3},
                    }
                ],
            }
        }
        state = GameState.from_snapshot(snapshot)
        actions = [
            action
            for action in enumerate_effect_actions(state)
            if action.effect_id == "gy_banish_fuse_fiendsmith"
        ]
        self.assertTrue(actions)

        new_state = apply_effect_action(state, actions[0])
        field_names = [card.name for card in new_state.field.mz if card]
        self.assertIn("Fiendsmith's Desirae", field_names)
        self.assertTrue(any(card.cid == "20240" for card in new_state.banished))
        gy_names = [card.name for card in new_state.gy]
        self.assertIn("Fiendsmith Engraver", gy_names)
        self.assertIn("Fiendsmith's Lacrima", gy_names)
        self.assertIn("Fiendsmith's Requiem", gy_names)
        self.assertTrue(new_state.opt_used.get("20240:e2"))

    def test_tract_gy_fusion_missing_engraver_no_action(self):
        snapshot = {
            "zones": {
                "gy": [
                    {"cid": "20240", "name": "Fiendsmith's Tract"},
                ],
                "hand": [
                    {"cid": "20225", "name": "Fiendsmith's Requiem"},
                ],
                "field_zones": {
                    "mz": [
                        {"cid": "20214", "name": "Fiendsmith's Lacrima"},
                        None,
                        None,
                        None,
                        None,
                    ],
                    "emz": [None, None],
                },
                "extra": [
                    {
                        "cid": "20215",
                        "name": "Fiendsmith's Desirae",
                        "metadata": {"summon_type": "fusion", "min_materials": 3},
                    }
                ],
            }
        }
        state = GameState.from_snapshot(snapshot)
        actions = [
            action
            for action in enumerate_effect_actions(state)
            if action.effect_id == "gy_banish_fuse_fiendsmith"
        ]
        self.assertFalse(actions)

    def test_tract_gy_fusion_opt_blocks_action(self):
        snapshot = {
            "zones": {
                "gy": [
                    {"cid": "20240", "name": "Fiendsmith's Tract"},
                ],
                "hand": [
                    {"cid": "20225", "name": "Fiendsmith's Requiem"},
                ],
                "field_zones": {
                    "mz": [
                        {"cid": "20196", "name": "Fiendsmith Engraver"},
                        {"cid": "20214", "name": "Fiendsmith's Lacrima"},
                        None,
                        None,
                        None,
                    ],
                    "emz": [None, None],
                },
                "extra": [
                    {
                        "cid": "20215",
                        "name": "Fiendsmith's Desirae",
                        "metadata": {"summon_type": "fusion", "min_materials": 3},
                    }
                ],
            },
            "opt_used": {"20240:e2": True},
        }
        state = GameState.from_snapshot(snapshot)
        actions = [
            action
            for action in enumerate_effect_actions(state)
            if action.effect_id == "gy_banish_fuse_fiendsmith"
        ]
        self.assertFalse(actions)

    def test_desirae_via_tract_fixture(self):
        report = self.run_scenario("fixture_desirae_via_tract_gy_fusion")
        snapshot = load_snapshot(report)
        evaluation = evaluate_endboard(snapshot)
        self.assertTrue(
            any(item["bucket"] == "A" and item["name"] == "Fiendsmith's Desirae"
                for item in evaluation["achieved"])
        )

    def test_desirae_with_equipped_requiem_fixture(self):
        report = self.run_scenario("fixture_desirae_with_equipped_requiem_s")
        snapshot = load_snapshot(report)
        evaluation = evaluate_endboard(snapshot)
        self.assertTrue(any(item["bucket"] == "S" for item in evaluation["achieved"]))

    def test_oppturn_pop_fixture(self):
        report = self.run_scenario("fixture_oppturn_pop_via_lacrima_requiem_paradise_desirae")
        snapshot = load_snapshot(report)
        self.assertIn("Opponent Card", snapshot["zones"]["gy"])

    def test_oppturn_agnumday_revive_fixture(self):
        report = self.run_scenario("fixture_oppturn_agnumday_revive_desirae")
        snapshot = load_snapshot(report)
        evaluation = evaluate_endboard(snapshot)
        self.assertTrue(any(item["bucket"] == "S" for item in evaluation["achieved"]))


if __name__ == "__main__":
    unittest.main()
