import json
import subprocess
import sys
import unittest
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "src"))

from combos.endboard_evaluator import evaluate_endboard  # noqa: E402
from sim.effects.registry import apply_effect_action, enumerate_effect_actions  # noqa: E402
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


def run_scenario(scenario_name: str) -> dict:
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
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    if not report.exists():
        raise AssertionError("Missing report")
    return load_snapshot(report)


class TestLibraryDecklistEffects(unittest.TestCase):
    def test_cross_sheep_revive(self):
        snapshot = run_scenario("fixture_cross_sheep_revive")
        self.assertIn("Buio the Dawn's Light", snapshot["zones"]["field"])
        self.assertNotIn("Buio the Dawn's Light", snapshot["zones"]["gy"])

    def test_muckraker_revive(self):
        snapshot = run_scenario("fixture_muckraker_revive")
        self.assertIn("Buio the Dawn's Light", snapshot["zones"]["field"])
        self.assertIn("Discard Fodder", snapshot["zones"]["gy"])

    def test_sp_little_knight_banish(self):
        snapshot = run_scenario("fixture_sp_little_knight_banish")
        self.assertIn("Opponent Card", snapshot["zones"]["banished"])

    def test_sequence_20226_equip(self):
        snapshot = run_scenario("fixture_sequence_20226_equip")
        self.assertIn("Fiendsmith Engraver", snapshot["zones"]["field"])
        self.assertNotIn("Fiendsmith's Sequence", snapshot["zones"]["field"])
        totals = snapshot.get("equipped_link_totals", [])
        total = None
        for entry in totals:
            if entry.get("name") == "Fiendsmith Engraver":
                total = entry.get("total")
                break
        self.assertIsNotNone(total)
        self.assertGreaterEqual(int(total), 2)

    def test_duke_demise_recover(self):
        snapshot = run_scenario("fixture_duke_demise_recover")
        self.assertIn("Fiendsmith Engraver", snapshot["zones"]["hand"])
        self.assertIn("The Duke of Demise", snapshot["zones"]["banished"])

    def test_necroquip_draw(self):
        snapshot = run_scenario("fixture_necroquip_draw")
        self.assertIn("Draw Fodder", snapshot["zones"]["hand"])

    def test_aerial_eater_send(self):
        snapshot = run_scenario("fixture_aerial_eater_send")
        self.assertIn("Buio the Dawn's Light", snapshot["zones"]["gy"])

    def test_abao_revive(self):
        snapshot = run_scenario("fixture_abao_revive")
        self.assertIn("Buio the Dawn's Light", snapshot["zones"]["field"])
        self.assertIn("A Bao A Qu, the Lightless Shadow", snapshot["zones"]["banished"])
        self.assertIn("Discard Fodder", snapshot["zones"]["gy"])

    def test_abao_revive_sequence_equip(self):
        snapshot = run_scenario("fixture_abao_revive_sequence_equip")
        self.assertIn("Fiendsmith Engraver", snapshot["zones"]["field"])
        self.assertIn("A Bao A Qu, the Lightless Shadow", snapshot["zones"]["banished"])
        self.assertNotIn("Fiendsmith's Sequence", snapshot["zones"]["field"])
        totals = snapshot.get("equipped_link_totals", [])
        total = None
        for entry in totals:
            if entry.get("name") == "Fiendsmith Engraver":
                total = entry.get("total")
                break
        self.assertIsNotNone(total)
        self.assertGreaterEqual(int(total), 2)

    def test_abao_revive_sequence_equip_auto_events(self):
        snapshot = run_scenario("fixture_abao_revive_sequence_equip_auto")
        self.assertIn("Fiendsmith Engraver", snapshot["zones"]["field"])
        self.assertIn("A Bao A Qu, the Lightless Shadow", snapshot["zones"]["banished"])
        self.assertNotIn("Fiendsmith's Sequence", snapshot["zones"]["field"])
        totals = snapshot.get("equipped_link_totals", [])
        total = None
        for entry in totals:
            if entry.get("name") == "Fiendsmith Engraver":
                total = entry.get("total")
                break
        self.assertIsNotNone(total)
        self.assertGreaterEqual(int(total), 2)

    def test_buio_hand_ss(self):
        snapshot = run_scenario("fixture_buio_hand_ss")
        self.assertIn("Buio the Dawn's Light", snapshot["zones"]["field"])
        self.assertNotIn("Buio the Dawn's Light", snapshot["zones"]["hand"])

    def test_buio_gy_search(self):
        snapshot = run_scenario("fixture_buio_gy_search")
        self.assertIn("Mutiny in the Sky", snapshot["zones"]["hand"])

    def test_luce_send_destroy(self):
        snapshot = run_scenario("fixture_luce_send_destroy")
        self.assertIn("Buio the Dawn's Light", snapshot["zones"]["gy"])
        self.assertIn("Opponent Card", snapshot["zones"]["gy"])

    def test_luce_destroy_trigger(self):
        snapshot = run_scenario("fixture_luce_destroy_trigger")
        self.assertIn("Opponent Card", snapshot["zones"]["gy"])

    def test_mutiny_fusion(self):
        snapshot = run_scenario("fixture_mutiny_fusion")
        self.assertIn("Luce the Dusk's Dark", snapshot["zones"]["field"])
        self.assertIn("Mutiny in the Sky", snapshot["zones"]["gy"])
        self.assertIn("Aerial Eater", snapshot["zones"]["extra"])
        self.assertIn("Buio the Dawn's Light", snapshot["zones"]["deck"])

    def test_buio_mutiny_luce_chain(self):
        snapshot = run_scenario("fixture_buio_gy_mutiny_luce_chain")
        self.assertIn("Luce the Dusk's Dark", snapshot["zones"]["field"])
        self.assertIn("Mutiny in the Sky", snapshot["zones"]["gy"])
        self.assertIn("Buio the Dawn's Light", snapshot["zones"]["deck"])

    def test_buio_mutiny_luce_chain_auto_events(self):
        snapshot = run_scenario("fixture_buio_gy_mutiny_luce_chain_auto")
        self.assertIn("Luce the Dusk's Dark", snapshot["zones"]["field"])
        self.assertIn("Mutiny in the Sky", snapshot["zones"]["gy"])
        self.assertIn("Buio the Dawn's Light", snapshot["zones"]["deck"])

    def test_desirae_equip_closure_s(self):
        snapshot = run_scenario("fixture_desirae_equip_closure_s")
        self.assertIn("Fiendsmith's Desirae", snapshot["zones"]["field"])
        self.assertNotIn("Fiendsmith's Requiem", snapshot["zones"]["field"])
        totals = snapshot.get("equipped_link_totals", [])
        total = None
        for entry in totals:
            if entry.get("name") == "Fiendsmith's Desirae":
                total = entry.get("total")
                break
        self.assertIsNotNone(total)
        self.assertGreaterEqual(int(total), 1)

    def test_desirae_equip_source_closure_s(self):
        snapshot = run_scenario("fixture_desirae_equip_source_closure_s")
        self.assertIn("Fiendsmith's Desirae", snapshot["zones"]["field"])
        self.assertNotIn("Fiendsmith's Sequence", snapshot["zones"]["field"])
        totals = snapshot.get("equipped_link_totals", [])
        total = None
        for entry in totals:
            if entry.get("name") == "Fiendsmith's Desirae":
                total = entry.get("total")
                break
        self.assertIsNotNone(total)
        self.assertGreaterEqual(int(total), 2)

    def test_desirae_requiem_link1_one_mat_closure_s(self):
        snapshot = run_scenario("fixture_desirae_requiem_link1_one_mat_closure_s")
        totals = snapshot.get("equipped_link_totals", [])
        total = None
        for entry in totals:
            if entry.get("name") == "Fiendsmith's Desirae":
                total = entry.get("total")
                break
        self.assertIsNotNone(total)
        self.assertGreaterEqual(int(total), 1)

    def test_batch_hand1_snapshot_s(self):
        snapshot = run_scenario("fixture_from_batch_fiendsmith_v1_seed7_hand1_final_snapshot")
        evaluation = evaluate_endboard(snapshot)
        self.assertTrue(any(item.get("bucket") == "S" for item in evaluation.get("achieved", [])))

    def test_doomed_dragon_move(self):
        scenario_path = repo_root / "tests" / "fixtures" / "combo_scenarios" / "fixture_doomed_dragon_move.json"
        scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
        state = GameState.from_snapshot(scenario.get("state", {}))
        actions = [
            action
            for action in enumerate_effect_actions(state)
            if action.effect_id == "doomed_dragon_move_to_stz"
        ]
        self.assertTrue(actions)
        new_state = apply_effect_action(state, actions[0])
        self.assertTrue(any(card and card.cid == "21624" for card in new_state.field.stz))


if __name__ == "__main__":
    unittest.main()
