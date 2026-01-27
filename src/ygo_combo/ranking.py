"""
Combo ranking and scoring system.

Provides multi-dimensional scoring for discovered combos, enabling
comparison, filtering, and selection of optimal combo lines.

Scoring Dimensions:
    - board_power: Raw strength of the final board (monsters, negates, etc.)
    - efficiency: Cards used vs board value (fewer cards = more efficient)
    - depth: Number of actions to reach the board (shorter = better)
    - resilience: Estimated ability to play through interruptions

Usage:
    from src.ygo_combo.ranking import ComboRanker, ComboScore

    ranker = ComboRanker()
    scored_combos = ranker.score_all(terminals)

    # Get top 10 by overall score
    top_combos = ranker.top_n(scored_combos, n=10)

    # Filter to only S/A tier boards
    good_combos = ranker.filter_by_tier(scored_combos, min_tier="A")

    # Sort by efficiency
    efficient = ranker.sort_by(scored_combos, "efficiency", reverse=True)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable, Tuple
from enum import Enum

from .types import TerminalState, Action
from .engine.state import BoardSignature, evaluate_board_quality


class SortKey(str, Enum):
    """Available sorting keys for combo ranking."""
    OVERALL = "overall"
    BOARD_POWER = "board_power"
    EFFICIENCY = "efficiency"
    DEPTH = "depth"
    RESILIENCE = "resilience"
    TIER = "tier"


@dataclass
class ComboScore:
    """
    Multi-dimensional score for a combo.

    Attributes:
        terminal: The terminal state being scored
        board_power: Raw board strength (0-200 typical range)
        efficiency: Cards used efficiency score (higher = more efficient)
        depth: Action count to reach board (lower = better, inverted for scoring)
        resilience: Estimated interruption tolerance (0-100)
        tier: Board tier (S/A/B/C/brick)
        overall: Weighted combined score
        details: Explanation of scoring breakdown
    """
    terminal: TerminalState
    board_power: float
    efficiency: float
    depth: int
    resilience: float
    tier: str
    overall: float
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def depth_score(self) -> float:
        """Inverted depth score (higher = shorter combo = better)."""
        # Max depth 30, so 30 - depth gives higher scores for shorter combos
        return max(0, 30 - self.depth)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "board_power": self.board_power,
            "efficiency": self.efficiency,
            "depth": self.depth,
            "depth_score": self.depth_score,
            "resilience": self.resilience,
            "tier": self.tier,
            "overall": self.overall,
            "details": self.details,
            "terminal": self.terminal.to_dict(),
        }


# Tier ordering for comparisons (lower = better)
TIER_ORDER = {"S": 0, "A": 1, "B": 2, "C": 3, "brick": 4}


class ComboRanker:
    """
    Scores and ranks combo terminals by multiple dimensions.

    Weights can be customized to prioritize different aspects:
        - board_power_weight: Importance of raw board strength
        - efficiency_weight: Importance of card efficiency
        - depth_weight: Importance of combo shortness
        - resilience_weight: Importance of interruption tolerance
    """

    def __init__(
        self,
        board_power_weight: float = 0.4,
        efficiency_weight: float = 0.2,
        depth_weight: float = 0.25,
        resilience_weight: float = 0.15,
    ):
        """
        Initialize ranker with scoring weights.

        Args:
            board_power_weight: Weight for board strength (default 0.4)
            efficiency_weight: Weight for card efficiency (default 0.2)
            depth_weight: Weight for combo shortness (default 0.25)
            resilience_weight: Weight for resilience (default 0.15)
        """
        # Normalize weights
        total = board_power_weight + efficiency_weight + depth_weight + resilience_weight
        self.board_power_weight = board_power_weight / total
        self.efficiency_weight = efficiency_weight / total
        self.depth_weight = depth_weight / total
        self.resilience_weight = resilience_weight / total

        # Boss monsters that indicate resilience
        self.resilience_indicators = self._get_resilience_indicators()

    def _get_resilience_indicators(self) -> Dict[int, int]:
        """Get cards that indicate combo resilience with their values."""
        # Cards that provide protection/negation
        return {
            79559912: 30,   # D/D/D Wave High King Caesar (negate)
            4731783: 20,    # A Bao A Qu (protection)
            27548199: 25,   # Fiendsmith Requiem (negate)
            25339070: 15,   # Fiendsmith Sequence (GY recursion)
            16195942: 20,   # Baronne de Fleur (negate + destruction)
            63977008: 25,   # Herald of Ultimateness (multiple negates)
            86066372: 15,   # Apollousa (multiple negates based on materials)
        }

    def score_terminal(self, terminal: TerminalState) -> ComboScore:
        """
        Score a single terminal state.

        Args:
            terminal: The terminal state to score

        Returns:
            ComboScore with all dimension scores
        """
        board_state = terminal.board_state

        # Extract board info
        player_data = board_state.get("player0", {})
        monsters = player_data.get("monsters", [])
        hand = player_data.get("hand", [])
        graveyard = player_data.get("graveyard", [])

        # Calculate board power using existing evaluation
        sig = self._board_state_to_signature(board_state)
        eval_result = evaluate_board_quality(sig)
        board_power = eval_result["score"]
        tier = eval_result["tier"]

        # Calculate efficiency
        # Starting hand is typically 5 cards, actions consume resources
        cards_used = self._estimate_cards_used(terminal)
        efficiency = self._calculate_efficiency(board_power, cards_used)

        # Calculate resilience
        resilience = self._calculate_resilience(monsters, graveyard)

        # Calculate overall score
        # Normalize each dimension to 0-100 range for fair weighting
        normalized_power = min(board_power, 200) / 2  # 0-100
        normalized_depth = max(0, 30 - terminal.depth) * (100 / 30)  # 0-100
        normalized_efficiency = min(efficiency, 100)  # 0-100
        normalized_resilience = min(resilience, 100)  # 0-100

        overall = (
            normalized_power * self.board_power_weight +
            normalized_efficiency * self.efficiency_weight +
            normalized_depth * self.depth_weight +
            normalized_resilience * self.resilience_weight
        )

        details = {
            "eval_details": eval_result.get("details", []),
            "monsters_on_field": len(monsters),
            "cards_in_hand": len(hand),
            "cards_in_gy": len(graveyard),
            "cards_used": cards_used,
            "normalized_scores": {
                "power": normalized_power,
                "efficiency": normalized_efficiency,
                "depth": normalized_depth,
                "resilience": normalized_resilience,
            },
        }

        return ComboScore(
            terminal=terminal,
            board_power=board_power,
            efficiency=efficiency,
            depth=terminal.depth,
            resilience=resilience,
            tier=tier,
            overall=overall,
            details=details,
        )

    def _board_state_to_signature(self, board_state: dict) -> BoardSignature:
        """Convert board_state dict to BoardSignature for evaluation."""
        player_data = board_state.get("player0", {})

        monsters = frozenset(m.get("code", 0) for m in player_data.get("monsters", []))
        spells = frozenset(s.get("code", 0) for s in player_data.get("spells", []))
        graveyard = frozenset(g.get("code", 0) for g in player_data.get("graveyard", []))
        hand = frozenset(h.get("code", 0) for h in player_data.get("hand", []))
        banished = frozenset(b.get("code", 0) for b in player_data.get("banished", []))
        extra_deck = frozenset(e.get("code", 0) for e in player_data.get("extra", []))

        # Extract equips if available - format is (equipped_code, target_code)
        equips: set = set()
        for m in player_data.get("monsters", []):
            monster_code = m.get("code", 0)
            if m.get("equips"):
                for equip_code in m["equips"]:
                    equips.add((equip_code, monster_code))

        return BoardSignature(
            monsters=monsters,
            spells=spells,
            graveyard=graveyard,
            hand=hand,
            banished=banished,
            extra_deck=extra_deck,
            equips=frozenset(equips),
        )

    def _estimate_cards_used(self, terminal: TerminalState) -> int:
        """Estimate how many cards were consumed by this combo."""
        # Count unique cards played (activations, summons)
        cards_played = set()
        for action in terminal.action_sequence:
            if action.card_code and action.action_type in ("activate", "summon", "spsummon"):
                cards_played.add(action.card_code)

        # Minimum 1 card used (the starter)
        return max(1, len(cards_played))

    def _calculate_efficiency(self, board_power: float, cards_used: int) -> float:
        """
        Calculate efficiency score.

        Higher board power with fewer cards = more efficient.
        Score = board_power / cards_used, scaled to 0-100 range.
        """
        if cards_used <= 0:
            return 0.0

        # Base efficiency: power per card
        raw_efficiency = board_power / cards_used

        # Scale to reasonable range (assuming ~20 power per card is average)
        # 40+ power per card = excellent (100), 10 = average (50), 0 = poor (0)
        scaled = min(100, raw_efficiency * 2.5)

        return scaled

    def _calculate_resilience(
        self,
        monsters: List[Dict],
        graveyard: List[Dict]
    ) -> float:
        """
        Estimate combo resilience based on board composition.

        Factors:
        - Negation capabilities on board
        - Protection effects
        - GY recursion available
        """
        resilience = 0.0

        # Check monsters on field
        for monster in monsters:
            code = monster.get("code", 0)
            if code in self.resilience_indicators:
                resilience += self.resilience_indicators[code]

        # Bonus for multiple monsters (harder to break)
        monster_count = len(monsters)
        if monster_count >= 3:
            resilience += 10
        if monster_count >= 5:
            resilience += 10

        # Bonus for GY setup (recursion potential)
        fiendsmith_gy = sum(
            1 for g in graveyard
            if g.get("code", 0) in {25339070, 27548199, 4731783}  # Sequence, Requiem, A Bao A Qu
        )
        resilience += fiendsmith_gy * 5

        return min(100, resilience)

    def score_all(self, terminals: List[TerminalState]) -> List[ComboScore]:
        """
        Score all terminal states.

        Args:
            terminals: List of terminal states to score

        Returns:
            List of ComboScore objects
        """
        return [self.score_terminal(t) for t in terminals]

    def sort_by(
        self,
        scores: List[ComboScore],
        key: SortKey = SortKey.OVERALL,
        reverse: bool = True
    ) -> List[ComboScore]:
        """
        Sort scored combos by a specific dimension.

        Args:
            scores: List of ComboScore objects
            key: Dimension to sort by
            reverse: True for descending (default), False for ascending

        Returns:
            Sorted list of ComboScore objects
        """
        key_funcs = {
            SortKey.OVERALL: lambda s: s.overall,
            SortKey.BOARD_POWER: lambda s: s.board_power,
            SortKey.EFFICIENCY: lambda s: s.efficiency,
            SortKey.DEPTH: lambda s: -s.depth,  # Lower depth is better
            SortKey.RESILIENCE: lambda s: s.resilience,
            SortKey.TIER: lambda s: -TIER_ORDER.get(s.tier, 99),  # Lower tier order is better
        }

        return sorted(scores, key=key_funcs[key], reverse=reverse)

    def top_n(
        self,
        scores: List[ComboScore],
        n: int = 10,
        key: SortKey = SortKey.OVERALL
    ) -> List[ComboScore]:
        """
        Get top N combos by a specific dimension.

        Args:
            scores: List of ComboScore objects
            n: Number of top combos to return
            key: Dimension to rank by

        Returns:
            Top N ComboScore objects
        """
        sorted_scores = self.sort_by(scores, key=key, reverse=True)
        return sorted_scores[:n]

    def filter_by_tier(
        self,
        scores: List[ComboScore],
        min_tier: str = "A"
    ) -> List[ComboScore]:
        """
        Filter combos by minimum tier.

        Args:
            scores: List of ComboScore objects
            min_tier: Minimum acceptable tier ("S", "A", "B", "C")

        Returns:
            Filtered list of ComboScore objects
        """
        min_order = TIER_ORDER.get(min_tier, 99)
        return [s for s in scores if TIER_ORDER.get(s.tier, 99) <= min_order]

    def filter_by_depth(
        self,
        scores: List[ComboScore],
        max_depth: int = 20
    ) -> List[ComboScore]:
        """
        Filter combos by maximum depth.

        Args:
            scores: List of ComboScore objects
            max_depth: Maximum acceptable action count

        Returns:
            Filtered list of ComboScore objects
        """
        return [s for s in scores if s.depth <= max_depth]

    def filter_by_score(
        self,
        scores: List[ComboScore],
        min_score: float = 50.0,
        key: SortKey = SortKey.OVERALL
    ) -> List[ComboScore]:
        """
        Filter combos by minimum score.

        Args:
            scores: List of ComboScore objects
            min_score: Minimum acceptable score
            key: Which score dimension to filter on

        Returns:
            Filtered list of ComboScore objects
        """
        key_funcs = {
            SortKey.OVERALL: lambda s: s.overall,
            SortKey.BOARD_POWER: lambda s: s.board_power,
            SortKey.EFFICIENCY: lambda s: s.efficiency,
            SortKey.RESILIENCE: lambda s: s.resilience,
        }

        get_score = key_funcs.get(key, lambda s: s.overall)
        return [s for s in scores if get_score(s) >= min_score]

    def group_by_board(
        self,
        scores: List[ComboScore]
    ) -> Dict[str, List[ComboScore]]:
        """
        Group combos by final board hash.

        Args:
            scores: List of ComboScore objects

        Returns:
            Dict mapping board_hash to list of ComboScores reaching that board
        """
        groups: Dict[str, List[ComboScore]] = {}
        for score in scores:
            board_hash = score.terminal.board_hash or "unknown"
            if board_hash not in groups:
                groups[board_hash] = []
            groups[board_hash].append(score)
        return groups

    def best_per_board(
        self,
        scores: List[ComboScore],
        key: SortKey = SortKey.DEPTH
    ) -> List[ComboScore]:
        """
        Get the best combo for each unique board.

        Useful for finding the shortest/most efficient path to each endpoint.

        Args:
            scores: List of ComboScore objects
            key: Dimension to rank by (default: DEPTH for shortest)

        Returns:
            List of best ComboScore per unique board
        """
        groups = self.group_by_board(scores)
        best = []
        for board_hash, group_scores in groups.items():
            sorted_group = self.sort_by(group_scores, key=key, reverse=True)
            if sorted_group:
                best.append(sorted_group[0])
        return best

    def print_summary(
        self,
        scores: List[ComboScore],
        top_n: int = 10,
        title: str = "Combo Ranking Summary"
    ):
        """
        Print a formatted summary of scored combos.

        Args:
            scores: List of ComboScore objects
            top_n: Number of top combos to show
            title: Title for the summary
        """
        print(f"\n{'=' * 70}")
        print(f"{title:^70}")
        print(f"{'=' * 70}")

        # Overall stats
        print(f"\n{'OVERALL STATISTICS':^70}")
        print(f"{'-' * 70}")
        print(f"  Total combos scored:     {len(scores):>10,}")

        if scores:
            # Tier distribution
            tier_counts = {}
            for s in scores:
                tier_counts[s.tier] = tier_counts.get(s.tier, 0) + 1

            print(f"\n  Tier distribution:")
            for tier in ["S", "A", "B", "C", "brick"]:
                count = tier_counts.get(tier, 0)
                pct = count / len(scores) * 100
                bar = "#" * int(pct / 5)
                print(f"    {tier:>5}: {count:>6} ({pct:>5.1f}%) {bar}")

            # Score stats
            overall_scores = [s.overall for s in scores]
            print(f"\n  Overall score range:     {min(overall_scores):.1f} - {max(overall_scores):.1f}")
            print(f"  Average overall score:   {sum(overall_scores) / len(overall_scores):.1f}")

            # Depth stats
            depths = [s.depth for s in scores]
            print(f"\n  Depth range:             {min(depths)} - {max(depths)} actions")
            print(f"  Average depth:           {sum(depths) / len(depths):.1f} actions")

        # Top combos
        print(f"\n{'TOP ' + str(top_n) + ' COMBOS':^70}")
        print(f"{'-' * 70}")

        top = self.top_n(scores, n=top_n)
        for i, score in enumerate(top, 1):
            print(f"\n  #{i}: Overall={score.overall:.1f} | Tier={score.tier} | "
                  f"Depth={score.depth} | Power={score.board_power:.0f}")
            print(f"       Efficiency={score.efficiency:.1f} | Resilience={score.resilience:.1f}")

            # Show key cards on board
            monsters = score.terminal.board_state.get("player0", {}).get("monsters", [])
            if monsters:
                names = [m.get("name", f"ID:{m.get('code')}") for m in monsters[:3]]
                if len(monsters) > 3:
                    names.append(f"+{len(monsters)-3} more")
                print(f"       Board: {', '.join(names)}")

        print(f"\n{'=' * 70}\n")


def rank_terminals(
    terminals: List[TerminalState],
    **ranker_kwargs
) -> Tuple[List[ComboScore], ComboRanker]:
    """
    Convenience function to score and rank terminals.

    Args:
        terminals: List of terminal states to rank
        **ranker_kwargs: Arguments passed to ComboRanker constructor

    Returns:
        Tuple of (sorted scores, ranker instance)
    """
    ranker = ComboRanker(**ranker_kwargs)
    scores = ranker.score_all(terminals)
    sorted_scores = ranker.sort_by(scores, SortKey.OVERALL)
    return sorted_scores, ranker


__all__ = [
    'ComboScore',
    'ComboRanker',
    'SortKey',
    'TIER_ORDER',
    'rank_terminals',
]
