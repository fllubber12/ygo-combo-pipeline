#!/usr/bin/env python3
"""
Stratified sampling for combo enumeration.

With C(40,5) = 658,008 possible starting hands (or 1.7M for larger decks),
exhaustive enumeration is impractical. This module implements stratified
sampling to efficiently estimate deck performance.

Key concepts:
- Hands are classified by composition (# starters, # extenders, etc.)
- Hands are grouped into strata based on composition
- Samples are drawn proportionally from each stratum
- Results can be aggregated with confidence intervals

Usage:
    from sampling import StratifiedSampler, SamplingConfig

    sampler = StratifiedSampler(deck, classifier)
    sample = sampler.sample(n=1000)

    # Integrate with parallel enumeration
    config = ParallelConfig(deck=sample.hands, ...)
    result = parallel_enumerate(config)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple, Optional, FrozenSet
from itertools import combinations
from collections import Counter
import random
import math

from .cards.roles import CardRole, CardRoleClassifier


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass(frozen=True)
class HandComposition:
    """
    Composition of a hand by card roles.

    Frozen for use as dict key (hashable).
    """
    starters: int
    extenders: int
    payoffs: int
    utilities: int
    garnets: int
    unknowns: int

    def total(self) -> int:
        """Total cards in hand."""
        return (self.starters + self.extenders + self.payoffs +
                self.utilities + self.garnets + self.unknowns)

    def is_playable(self) -> bool:
        """Heuristic: hand has at least one starter or extender."""
        return self.starters > 0 or self.extenders > 0

    def quality_score(self) -> float:
        """
        Heuristic quality score for the hand composition.

        Higher = more likely to produce good boards.
        Used for prioritizing strata in sampling.
        """
        score = 0.0

        # Starters are very valuable
        score += self.starters * 3.0

        # Extenders add value, but with diminishing returns
        score += min(self.extenders, 2) * 1.5

        # Payoffs in hand are mildly useful (can be summoned sometimes)
        score += self.payoffs * 0.5

        # Utilities are context-dependent, neutral
        score += self.utilities * 0.3

        # Garnets are actively bad
        score -= self.garnets * 2.0

        # Unknowns are neutral
        score += self.unknowns * 0.0

        return score

    def stratum_key(self) -> str:
        """String key for stratum grouping."""
        return f"S{self.starters}E{self.extenders}P{self.payoffs}U{self.utilities}G{self.garnets}X{self.unknowns}"


@dataclass
class Stratum:
    """
    A group of hands with the same composition.
    """
    composition: HandComposition
    hands: List[Tuple[int, ...]]

    def __len__(self) -> int:
        return len(self.hands)

    @property
    def quality_score(self) -> float:
        """Composition quality score for prioritization."""
        return self.composition.quality_score()

    def sample(self, n: int, rng: random.Random = None) -> List[Tuple[int, ...]]:
        """Sample n hands from this stratum."""
        if rng is None:
            rng = random.Random()

        if n >= len(self.hands):
            return list(self.hands)

        return rng.sample(self.hands, n)


@dataclass
class SamplingConfig:
    """
    Configuration for stratified sampling.

    Attributes:
        total_samples: Total number of hands to sample.
        min_per_stratum: Minimum samples per non-empty stratum.
        prioritize_playable: Weight playable hands higher in sampling.
        seed: Random seed for reproducibility.
    """
    total_samples: int = 1000
    min_per_stratum: int = 1
    prioritize_playable: bool = True
    seed: Optional[int] = None


@dataclass
class SamplingResult:
    """
    Result of stratified sampling.

    Attributes:
        hands: Sampled hands as tuples of passcodes.
        strata_stats: Statistics per stratum.
        total_population: Total hands in deck.
        sample_fraction: Fraction of population sampled.
    """
    hands: List[Tuple[int, ...]]
    strata_stats: Dict[str, Dict]
    total_population: int
    sample_fraction: float

    def __len__(self) -> int:
        return len(self.hands)


# =============================================================================
# STRATIFIED SAMPLER
# =============================================================================

class StratifiedSampler:
    """
    Stratified sampler for starting hands.

    Groups hands by composition and samples proportionally or with
    custom weighting to ensure coverage of different hand types.
    """

    def __init__(
        self,
        deck: List[int],
        classifier: CardRoleClassifier,
        hand_size: int = 5,
    ):
        """
        Initialize sampler with deck and classifier.

        Args:
            deck: List of card passcodes in main deck.
            classifier: CardRoleClassifier for role lookups.
            hand_size: Cards per starting hand (default 5).
        """
        self.deck = sorted(deck)  # Sorted for deterministic ordering
        self.classifier = classifier
        self.hand_size = hand_size

        # Lazily computed strata
        self._strata: Optional[Dict[str, Stratum]] = None
        self._total_hands: Optional[int] = None

    @property
    def total_hands(self) -> int:
        """Total number of unique starting hands."""
        if self._total_hands is None:
            self._total_hands = math.comb(len(self.deck), self.hand_size)
        return self._total_hands

    def _classify_hand(self, hand: Tuple[int, ...]) -> HandComposition:
        """Classify a hand by card roles."""
        counts = Counter()

        for card in hand:
            role = self.classifier.get_role(card)
            counts[role] += 1

        return HandComposition(
            starters=counts.get(CardRole.STARTER, 0),
            extenders=counts.get(CardRole.EXTENDER, 0),
            payoffs=counts.get(CardRole.PAYOFF, 0),
            utilities=counts.get(CardRole.UTILITY, 0),
            garnets=counts.get(CardRole.GARNET, 0),
            unknowns=counts.get(CardRole.UNKNOWN, 0),
        )

    def _build_strata(self) -> Dict[str, Stratum]:
        """Build strata by enumerating all hands and grouping by composition."""
        strata: Dict[str, Stratum] = {}

        for hand in combinations(self.deck, self.hand_size):
            composition = self._classify_hand(hand)
            key = composition.stratum_key()

            if key not in strata:
                strata[key] = Stratum(composition=composition, hands=[])
            strata[key].hands.append(hand)

        return strata

    @property
    def strata(self) -> Dict[str, Stratum]:
        """Get or compute strata."""
        if self._strata is None:
            self._strata = self._build_strata()
        return self._strata

    def get_strata_summary(self) -> Dict[str, Dict]:
        """Get summary statistics for each stratum."""
        summary = {}

        for key, stratum in self.strata.items():
            summary[key] = {
                "composition": {
                    "starters": stratum.composition.starters,
                    "extenders": stratum.composition.extenders,
                    "payoffs": stratum.composition.payoffs,
                    "utilities": stratum.composition.utilities,
                    "garnets": stratum.composition.garnets,
                    "unknowns": stratum.composition.unknowns,
                },
                "count": len(stratum),
                "fraction": len(stratum) / self.total_hands,
                "quality_score": stratum.quality_score,
                "is_playable": stratum.composition.is_playable(),
            }

        return summary

    def sample(self, config: SamplingConfig = None) -> SamplingResult:
        """
        Draw stratified sample from hand space.

        Args:
            config: Sampling configuration (uses defaults if None).

        Returns:
            SamplingResult with sampled hands and statistics.
        """
        if config is None:
            config = SamplingConfig()

        rng = random.Random(config.seed)

        # Calculate samples per stratum
        allocations = self._allocate_samples(config, rng)

        # Sample from each stratum
        sampled_hands = []
        strata_stats = {}

        for key, n_samples in allocations.items():
            stratum = self.strata[key]
            hands = stratum.sample(n_samples, rng)
            sampled_hands.extend(hands)

            strata_stats[key] = {
                "population": len(stratum),
                "sampled": len(hands),
                "sample_rate": len(hands) / len(stratum) if len(stratum) > 0 else 0,
                "composition": stratum.composition.stratum_key(),
                "quality_score": stratum.quality_score,
            }

        # Shuffle to remove stratum ordering
        rng.shuffle(sampled_hands)

        return SamplingResult(
            hands=sampled_hands,
            strata_stats=strata_stats,
            total_population=self.total_hands,
            sample_fraction=len(sampled_hands) / self.total_hands,
        )

    def _allocate_samples(
        self,
        config: SamplingConfig,
        rng: random.Random,
    ) -> Dict[str, int]:
        """
        Allocate sample budget across strata.

        Uses proportional allocation with optional weighting for playable hands.
        """
        allocations: Dict[str, int] = {}

        # Calculate weights for each stratum
        weights = {}
        total_weight = 0.0

        for key, stratum in self.strata.items():
            if len(stratum) == 0:
                continue

            # Base weight is stratum size (proportional allocation)
            weight = len(stratum)

            # Optionally boost playable hands
            if config.prioritize_playable:
                if stratum.composition.is_playable():
                    weight *= 2.0  # 2x weight for playable hands
                else:
                    weight *= 0.5  # 0.5x weight for brick hands

            weights[key] = weight
            total_weight += weight

        if total_weight == 0:
            return allocations

        # Allocate samples proportionally to weights
        remaining_samples = config.total_samples

        # First pass: minimum allocation per stratum
        for key in weights:
            allocations[key] = min(config.min_per_stratum, len(self.strata[key]))
            remaining_samples -= allocations[key]

        # Second pass: proportional allocation of remaining budget
        if remaining_samples > 0:
            for key, weight in weights.items():
                extra = int((weight / total_weight) * remaining_samples)
                # Don't exceed stratum size
                max_additional = len(self.strata[key]) - allocations[key]
                allocations[key] += min(extra, max_additional)

        return allocations

    def sample_by_quality(
        self,
        n: int,
        min_quality: float = 0.0,
        seed: int = None,
    ) -> SamplingResult:
        """
        Sample hands with quality score above threshold.

        Convenience method for sampling only "good" hands.

        Args:
            n: Number of hands to sample.
            min_quality: Minimum quality score for inclusion.
            seed: Random seed.

        Returns:
            SamplingResult with high-quality hands.
        """
        rng = random.Random(seed)

        # Filter strata by quality
        eligible_strata = {
            key: stratum for key, stratum in self.strata.items()
            if stratum.quality_score >= min_quality
        }

        # Count eligible hands
        eligible_count = sum(len(s) for s in eligible_strata.values())

        if eligible_count == 0:
            return SamplingResult(
                hands=[],
                strata_stats={},
                total_population=self.total_hands,
                sample_fraction=0.0,
            )

        # Proportional sampling from eligible strata
        sampled_hands = []
        strata_stats = {}

        for key, stratum in eligible_strata.items():
            # Proportional allocation
            stratum_samples = int((len(stratum) / eligible_count) * n)
            stratum_samples = max(1, stratum_samples)  # At least 1
            stratum_samples = min(stratum_samples, len(stratum))  # Cap at stratum size

            hands = stratum.sample(stratum_samples, rng)
            sampled_hands.extend(hands)

            strata_stats[key] = {
                "population": len(stratum),
                "sampled": len(hands),
                "quality_score": stratum.quality_score,
            }

        rng.shuffle(sampled_hands)

        return SamplingResult(
            hands=sampled_hands[:n],  # Trim to exact count
            strata_stats=strata_stats,
            total_population=self.total_hands,
            sample_fraction=min(n, len(sampled_hands)) / self.total_hands,
        )

    def estimate_brick_rate(self) -> float:
        """
        Estimate the brick rate (hands with no playable composition).

        Returns:
            Fraction of hands that are bricks (0.0 to 1.0).
        """
        brick_count = sum(
            len(stratum) for stratum in self.strata.values()
            if not stratum.composition.is_playable()
        )
        return brick_count / self.total_hands if self.total_hands > 0 else 0.0

    def print_summary(self):
        """Print human-readable summary of strata."""
        summary = self.get_strata_summary()

        print(f"\n{'='*70}")
        print(f"STRATIFIED SAMPLING SUMMARY")
        print(f"{'='*70}")
        print(f"Deck size: {len(self.deck)}")
        print(f"Hand size: {self.hand_size}")
        print(f"Total hands: {self.total_hands:,}")
        print(f"Number of strata: {len(self.strata)}")
        print(f"Estimated brick rate: {self.estimate_brick_rate():.1%}")

        print(f"\n{'Stratum':<20} {'Count':>10} {'Fraction':>10} {'Quality':>10} {'Playable':>10}")
        print("-" * 70)

        # Sort by quality score
        sorted_strata = sorted(
            summary.items(),
            key=lambda x: x[1]["quality_score"],
            reverse=True,
        )

        for key, stats in sorted_strata[:15]:  # Top 15
            print(f"{key:<20} {stats['count']:>10,} {stats['fraction']:>10.2%} "
                  f"{stats['quality_score']:>10.1f} {'Yes' if stats['is_playable'] else 'No':>10}")

        if len(sorted_strata) > 15:
            print(f"... and {len(sorted_strata) - 15} more strata")

        print(f"{'='*70}\n")


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_sampler_from_library(library_path: str = None) -> StratifiedSampler:
    """
    Create a sampler from the locked library.

    Args:
        library_path: Path to library JSON (uses default if None).

    Returns:
        StratifiedSampler configured for the library deck.
    """
    from pathlib import Path
    import json

    from .engine.paths import LOCKED_LIBRARY_PATH
    from .cards.roles import create_fiendsmith_classifier

    path = Path(library_path) if library_path else LOCKED_LIBRARY_PATH

    with open(path) as f:
        library = json.load(f)

    # Extract main deck cards
    main_deck = []
    for passcode_str, card in library.get("cards", {}).items():
        if not card.get("is_extra_deck", False):
            main_deck.append(int(passcode_str))

    # Use Fiendsmith classifier
    classifier = create_fiendsmith_classifier()

    return StratifiedSampler(
        deck=main_deck,
        classifier=classifier,
        hand_size=5,
    )


def sample_hands(
    n: int,
    library_path: str = None,
    seed: int = None,
    prioritize_playable: bool = True,
) -> List[Tuple[int, ...]]:
    """
    Convenience function to sample hands from library.

    Args:
        n: Number of hands to sample.
        library_path: Path to library JSON (uses default if None).
        seed: Random seed for reproducibility.
        prioritize_playable: Weight playable hands higher.

    Returns:
        List of sampled hands as tuples of passcodes.
    """
    sampler = create_sampler_from_library(library_path)

    config = SamplingConfig(
        total_samples=n,
        seed=seed,
        prioritize_playable=prioritize_playable,
    )

    result = sampler.sample(config)
    return result.hands


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Stratified hand sampling")
    parser.add_argument("-n", "--samples", type=int, default=100, help="Number of samples")
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    parser.add_argument("--summary", action="store_true", help="Print stratum summary")

    args = parser.parse_args()

    print("Creating sampler from locked library...")
    sampler = create_sampler_from_library()

    if args.summary:
        sampler.print_summary()

    print(f"\nSampling {args.samples} hands...")
    config = SamplingConfig(
        total_samples=args.samples,
        seed=args.seed,
        prioritize_playable=True,
    )
    result = sampler.sample(config)

    print(f"Sampled {len(result)} hands ({result.sample_fraction:.2%} of population)")
    print(f"Strata represented: {len(result.strata_stats)}")

    # Show sample statistics
    playable_count = sum(
        1 for hand in result.hands
        if sampler._classify_hand(hand).is_playable()
    )
    print(f"Playable hands in sample: {playable_count}/{len(result)} ({playable_count/len(result):.1%})")
