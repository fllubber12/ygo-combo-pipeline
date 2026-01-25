import sys
import unittest
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "src"))

from sim.search import _select_diversified_beam, score_key, state_hash  # noqa: E402
from sim.state import CardInstance, FieldZones, GameState  # noqa: E402


def make_state(tag: str) -> GameState:
    return GameState(
        deck=[CardInstance(cid=tag, name=tag)],
        hand=[],
        gy=[],
        banished=[],
        extra=[],
        field=FieldZones(mz=[None] * 5, stz=[None] * 5, fz=[None], emz=[None] * 2),
        turn_number=1,
        phase="Main Phase 1",
        normal_summon_set_used=False,
        opt_used={},
        restrictions=[],
        events=[],
        last_moved_to_gy=[],
    )


class TestSearchBeamDiversification(unittest.TestCase):
    def test_diversified_beam_keeps_some_setup_states(self):
        # 6 A-states (rank_key: has_a=True), 2 setup states (has_a=False but with B count)
        candidates = []
        for i in range(6):
            st = make_state(f"A{i}")
            candidates.append((st, [], {"rank_key": (False, True, 0)}))
        for i in range(2):
            st = make_state(f"B{i}")
            candidates.append((st, [], {"rank_key": (False, False, 2)}))

        candidates.sort(
            key=lambda item: (score_key(item[2]), state_hash(item[0])),
            reverse=True,
        )

        beam = _select_diversified_beam(candidates, beam_width=4, setup_width=1)

        # Expect exactly one setup state preserved.
        setup_count = sum(1 for st, _acts in beam if st.deck and st.deck[0].cid.startswith("B"))
        self.assertEqual(setup_count, 1)

    def test_diversified_beam_falls_back_gracefully(self):
        candidates = []
        for i in range(3):
            st = make_state(f"A{i}")
            candidates.append((st, [], {"rank_key": (False, True, 0)}))

        candidates.sort(
            key=lambda item: (score_key(item[2]), state_hash(item[0])),
            reverse=True,
        )

        beam = _select_diversified_beam(candidates, beam_width=3, setup_width=1)
        self.assertEqual(len(beam), 3)


if __name__ == "__main__":
    unittest.main()
