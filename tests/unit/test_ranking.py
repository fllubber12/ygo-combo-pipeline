"""
Unit tests for the combo ranking module.
"""

import pytest
from src.ygo_combo.ranking import (
    ComboScore,
    ComboRanker,
    SortKey,
    TIER_ORDER,
    rank_terminals,
)
from src.ygo_combo.types import TerminalState, Action


# =============================================================================
# TEST FIXTURES
# =============================================================================

def make_action(action_type: str = "activate", card_code: int = None) -> Action:
    """Create a test action."""
    return Action(
        action_type=action_type,
        message_type=10,
        response_value=0,
        response_bytes=b"\x00",
        description="Test action",
        card_code=card_code,
        card_name="Test Card",
    )


def make_terminal(
    depth: int = 10,
    monsters: list = None,
    board_hash: str = "hash1"
) -> TerminalState:
    """Create a test terminal state."""
    if monsters is None:
        monsters = [{"code": 12345678, "name": "Test Monster"}]

    return TerminalState(
        action_sequence=[make_action(card_code=12345678) for _ in range(depth)],
        board_state={
            "player0": {
                "monsters": monsters,
                "spells": [],
                "graveyard": [],
                "hand": [{"code": 1}, {"code": 2}],
                "banished": [],
                "extra": [],
            }
        },
        depth=depth,
        state_hash="state_hash_123",
        termination_reason="PASS",
        board_hash=board_hash,
    )


def make_good_terminal(depth: int = 15) -> TerminalState:
    """Create a terminal with good monsters (boss + interaction)."""
    return TerminalState(
        action_sequence=[make_action(card_code=60764609) for _ in range(depth)],
        board_state={
            "player0": {
                "monsters": [
                    {"code": 79559912, "name": "D/D/D Wave High King Caesar"},  # Boss
                    {"code": 4731783, "name": "A Bao A Qu"},  # Boss
                    {"code": 27548199, "name": "Fiendsmith Requiem"},  # Interaction
                ],
                "spells": [],
                "graveyard": [
                    {"code": 25339070, "name": "Fiendsmith Sequence"},
                ],
                "hand": [],
                "banished": [],
                "extra": [],
            }
        },
        depth=depth,
        state_hash="good_state_hash",
        termination_reason="PASS",
        board_hash="good_board",
    )


def make_brick_terminal() -> TerminalState:
    """Create a terminal with no monsters (brick)."""
    return TerminalState(
        action_sequence=[make_action()],
        board_state={
            "player0": {
                "monsters": [],
                "spells": [],
                "graveyard": [],
                "hand": [{"code": 1}, {"code": 2}, {"code": 3}, {"code": 4}, {"code": 5}],
                "banished": [],
                "extra": [],
            }
        },
        depth=1,
        state_hash="brick_state",
        termination_reason="PASS",
        board_hash="brick_board",
    )


# =============================================================================
# COMBO SCORE TESTS
# =============================================================================

class TestComboScore:
    """Tests for ComboScore dataclass."""

    def test_depth_score_calculation(self):
        """Depth score should be inverted (lower depth = higher score)."""
        terminal = make_terminal(depth=10)
        score = ComboScore(
            terminal=terminal,
            board_power=50.0,
            efficiency=60.0,
            depth=10,
            resilience=30.0,
            tier="B",
            overall=50.0,
        )
        # 30 - 10 = 20
        assert score.depth_score == 20

    def test_depth_score_zero_at_max(self):
        """Depth score should be 0 at max depth."""
        terminal = make_terminal(depth=30)
        score = ComboScore(
            terminal=terminal,
            board_power=50.0,
            efficiency=60.0,
            depth=30,
            resilience=30.0,
            tier="C",
            overall=40.0,
        )
        assert score.depth_score == 0

    def test_depth_score_max_at_zero(self):
        """Depth score should be max at depth 0."""
        terminal = make_terminal(depth=0)
        score = ComboScore(
            terminal=terminal,
            board_power=50.0,
            efficiency=60.0,
            depth=0,
            resilience=30.0,
            tier="A",
            overall=60.0,
        )
        assert score.depth_score == 30

    def test_to_dict_serialization(self):
        """ComboScore should serialize to dict."""
        terminal = make_terminal(depth=5)
        score = ComboScore(
            terminal=terminal,
            board_power=80.0,
            efficiency=70.0,
            depth=5,
            resilience=40.0,
            tier="A",
            overall=65.0,
            details={"test": "value"},
        )
        d = score.to_dict()

        assert d["board_power"] == 80.0
        assert d["efficiency"] == 70.0
        assert d["depth"] == 5
        assert d["depth_score"] == 25
        assert d["tier"] == "A"
        assert d["overall"] == 65.0
        assert "terminal" in d


# =============================================================================
# COMBO RANKER TESTS
# =============================================================================

class TestComboRanker:
    """Tests for ComboRanker class."""

    def test_initialization_normalizes_weights(self):
        """Weights should be normalized to sum to 1."""
        ranker = ComboRanker(
            board_power_weight=2.0,
            efficiency_weight=2.0,
            depth_weight=2.0,
            resilience_weight=2.0,
        )
        total = (
            ranker.board_power_weight +
            ranker.efficiency_weight +
            ranker.depth_weight +
            ranker.resilience_weight
        )
        assert abs(total - 1.0) < 0.001

    def test_score_terminal_basic(self):
        """Scoring a terminal should return a ComboScore."""
        ranker = ComboRanker()
        terminal = make_terminal(depth=10)
        score = ranker.score_terminal(terminal)

        assert isinstance(score, ComboScore)
        assert score.depth == 10
        assert score.tier in ["S", "A", "B", "C", "brick"]
        assert score.overall >= 0

    def test_score_good_terminal_higher(self):
        """Good terminals should score higher than bricks."""
        ranker = ComboRanker()
        good = make_good_terminal(depth=15)
        brick = make_brick_terminal()

        good_score = ranker.score_terminal(good)
        brick_score = ranker.score_terminal(brick)

        assert good_score.overall > brick_score.overall
        assert good_score.board_power > brick_score.board_power

    def test_score_all(self):
        """score_all should score multiple terminals."""
        ranker = ComboRanker()
        terminals = [
            make_terminal(depth=5),
            make_terminal(depth=10),
            make_terminal(depth=15),
        ]
        scores = ranker.score_all(terminals)

        assert len(scores) == 3
        assert all(isinstance(s, ComboScore) for s in scores)

    def test_sort_by_overall(self):
        """sort_by OVERALL should order by overall score."""
        ranker = ComboRanker()
        terminals = [make_brick_terminal(), make_good_terminal(), make_terminal()]
        scores = ranker.score_all(terminals)
        sorted_scores = ranker.sort_by(scores, SortKey.OVERALL)

        # Should be in descending order
        for i in range(len(sorted_scores) - 1):
            assert sorted_scores[i].overall >= sorted_scores[i + 1].overall

    def test_sort_by_depth(self):
        """sort_by DEPTH should order by depth (lower = better)."""
        ranker = ComboRanker()
        terminals = [
            make_terminal(depth=20),
            make_terminal(depth=5),
            make_terminal(depth=10),
        ]
        scores = ranker.score_all(terminals)
        sorted_scores = ranker.sort_by(scores, SortKey.DEPTH)

        # Should be in ascending depth order (reversed in sort_by)
        depths = [s.depth for s in sorted_scores]
        assert depths == [5, 10, 20]

    def test_top_n(self):
        """top_n should return N best combos."""
        ranker = ComboRanker()
        terminals = [make_terminal(depth=i) for i in range(1, 11)]
        scores = ranker.score_all(terminals)
        top_5 = ranker.top_n(scores, n=5)

        assert len(top_5) == 5

    def test_filter_by_tier(self):
        """filter_by_tier should exclude lower tiers."""
        ranker = ComboRanker()
        terminals = [make_good_terminal(), make_brick_terminal()]
        scores = ranker.score_all(terminals)

        # Good terminal should be A or better
        good_scores = ranker.filter_by_tier(scores, min_tier="A")

        # At least the good one should remain
        assert len(good_scores) >= 1
        for s in good_scores:
            assert TIER_ORDER[s.tier] <= TIER_ORDER["A"]

    def test_filter_by_depth(self):
        """filter_by_depth should exclude deep combos."""
        ranker = ComboRanker()
        terminals = [
            make_terminal(depth=5),
            make_terminal(depth=15),
            make_terminal(depth=25),
        ]
        scores = ranker.score_all(terminals)
        filtered = ranker.filter_by_depth(scores, max_depth=20)

        assert len(filtered) == 2
        assert all(s.depth <= 20 for s in filtered)

    def test_filter_by_score(self):
        """filter_by_score should exclude low scores."""
        ranker = ComboRanker()
        terminals = [make_good_terminal(), make_brick_terminal()]
        scores = ranker.score_all(terminals)

        # Get the good score's overall value
        good_score = max(s.overall for s in scores)
        brick_score = min(s.overall for s in scores)

        # Filter at a threshold between them
        threshold = (good_score + brick_score) / 2
        filtered = ranker.filter_by_score(scores, min_score=threshold)

        # Should only include high-scoring combos
        assert all(s.overall >= threshold for s in filtered)

    def test_group_by_board(self):
        """group_by_board should group by board_hash."""
        ranker = ComboRanker()
        terminals = [
            make_terminal(depth=5, board_hash="board_A"),
            make_terminal(depth=10, board_hash="board_A"),
            make_terminal(depth=15, board_hash="board_B"),
        ]
        scores = ranker.score_all(terminals)
        groups = ranker.group_by_board(scores)

        assert "board_A" in groups
        assert "board_B" in groups
        assert len(groups["board_A"]) == 2
        assert len(groups["board_B"]) == 1

    def test_best_per_board(self):
        """best_per_board should return shortest for each board."""
        ranker = ComboRanker()
        terminals = [
            make_terminal(depth=5, board_hash="board_A"),
            make_terminal(depth=10, board_hash="board_A"),
            make_terminal(depth=15, board_hash="board_B"),
            make_terminal(depth=8, board_hash="board_B"),
        ]
        scores = ranker.score_all(terminals)
        best = ranker.best_per_board(scores, key=SortKey.DEPTH)

        # Should have 2 entries (one per board)
        assert len(best) == 2

        # Group by board to check we got the best
        by_board = {s.terminal.board_hash: s for s in best}
        assert by_board["board_A"].depth == 5  # Shortest
        assert by_board["board_B"].depth == 8  # Shortest

    def test_estimate_cards_used(self):
        """_estimate_cards_used should count unique cards played."""
        ranker = ComboRanker()
        actions = [
            make_action(action_type="activate", card_code=111),
            make_action(action_type="activate", card_code=111),  # Duplicate
            make_action(action_type="summon", card_code=222),
            make_action(action_type="select_card", card_code=333),  # Not counted
        ]
        terminal = TerminalState(
            action_sequence=actions,
            board_state={"player0": {"monsters": [], "spells": [], "graveyard": [], "hand": [], "banished": [], "extra": []}},
            depth=4,
            state_hash="test",
            termination_reason="PASS",
        )
        cards_used = ranker._estimate_cards_used(terminal)
        assert cards_used == 2  # 111 and 222


# =============================================================================
# TIER ORDER TESTS
# =============================================================================

class TestTierOrder:
    """Tests for tier ordering."""

    def test_tier_order_values(self):
        """Tier order should be S < A < B < C < brick."""
        assert TIER_ORDER["S"] < TIER_ORDER["A"]
        assert TIER_ORDER["A"] < TIER_ORDER["B"]
        assert TIER_ORDER["B"] < TIER_ORDER["C"]
        assert TIER_ORDER["C"] < TIER_ORDER["brick"]

    def test_all_tiers_present(self):
        """All tiers should be in TIER_ORDER."""
        for tier in ["S", "A", "B", "C", "brick"]:
            assert tier in TIER_ORDER


# =============================================================================
# CONVENIENCE FUNCTION TESTS
# =============================================================================

class TestRankTerminals:
    """Tests for rank_terminals convenience function."""

    def test_rank_terminals_returns_tuple(self):
        """rank_terminals should return (scores, ranker) tuple."""
        terminals = [make_terminal(depth=5), make_terminal(depth=10)]
        scores, ranker = rank_terminals(terminals)

        assert isinstance(scores, list)
        assert isinstance(ranker, ComboRanker)
        assert len(scores) == 2

    def test_rank_terminals_sorted_by_overall(self):
        """rank_terminals should return sorted scores."""
        terminals = [make_terminal(depth=20), make_terminal(depth=5)]
        scores, _ = rank_terminals(terminals)

        # Should be sorted descending by overall
        for i in range(len(scores) - 1):
            assert scores[i].overall >= scores[i + 1].overall

    def test_rank_terminals_custom_weights(self):
        """rank_terminals should accept custom weights."""
        terminals = [make_terminal()]
        scores, ranker = rank_terminals(
            terminals,
            depth_weight=1.0,
            board_power_weight=0.0,
            efficiency_weight=0.0,
            resilience_weight=0.0,
        )

        # Depth weight should be 1.0 (normalized)
        assert ranker.depth_weight == 1.0


# =============================================================================
# RESILIENCE SCORING TESTS
# =============================================================================

class TestResilienceScoring:
    """Tests for resilience calculation."""

    def test_resilience_with_negates(self):
        """Monsters with negates should increase resilience."""
        ranker = ComboRanker()
        terminal_with_negate = TerminalState(
            action_sequence=[],
            board_state={
                "player0": {
                    "monsters": [
                        {"code": 79559912, "name": "Caesar"},  # Has negate
                    ],
                    "spells": [],
                    "graveyard": [],
                    "hand": [],
                    "banished": [],
                    "extra": [],
                }
            },
            depth=10,
            state_hash="test",
            termination_reason="PASS",
        )
        terminal_without_negate = TerminalState(
            action_sequence=[],
            board_state={
                "player0": {
                    "monsters": [
                        {"code": 12345678, "name": "Random Monster"},
                    ],
                    "spells": [],
                    "graveyard": [],
                    "hand": [],
                    "banished": [],
                    "extra": [],
                }
            },
            depth=10,
            state_hash="test2",
            termination_reason="PASS",
        )

        score_with = ranker.score_terminal(terminal_with_negate)
        score_without = ranker.score_terminal(terminal_without_negate)

        assert score_with.resilience > score_without.resilience

    def test_resilience_with_multiple_monsters(self):
        """Multiple monsters should increase resilience."""
        ranker = ComboRanker()
        terminal_many = TerminalState(
            action_sequence=[],
            board_state={
                "player0": {
                    "monsters": [
                        {"code": 1}, {"code": 2}, {"code": 3}, {"code": 4}, {"code": 5}
                    ],
                    "spells": [],
                    "graveyard": [],
                    "hand": [],
                    "banished": [],
                    "extra": [],
                }
            },
            depth=10,
            state_hash="test",
            termination_reason="PASS",
        )
        terminal_one = TerminalState(
            action_sequence=[],
            board_state={
                "player0": {
                    "monsters": [{"code": 1}],
                    "spells": [],
                    "graveyard": [],
                    "hand": [],
                    "banished": [],
                    "extra": [],
                }
            },
            depth=10,
            state_hash="test2",
            termination_reason="PASS",
        )

        score_many = ranker.score_terminal(terminal_many)
        score_one = ranker.score_terminal(terminal_one)

        assert score_many.resilience > score_one.resilience
