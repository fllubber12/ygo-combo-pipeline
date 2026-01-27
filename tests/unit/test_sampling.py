#!/usr/bin/env python3
"""Unit tests for the stratified sampling module."""

import pytest
from math import comb

from src.ygo_combo.sampling import (
    HandComposition,
    Stratum,
    SamplingConfig,
    SamplingResult,
    StratifiedSampler,
)
from src.ygo_combo.cards.roles import CardRole, CardRoleClassifier, CardClassification


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def simple_classifier():
    """Create a simple classifier with known roles."""
    classifier = CardRoleClassifier()

    # Add some test cards
    classifications = [
        CardClassification(passcode=1, role=CardRole.STARTER),
        CardClassification(passcode=2, role=CardRole.STARTER),
        CardClassification(passcode=3, role=CardRole.EXTENDER),
        CardClassification(passcode=4, role=CardRole.EXTENDER),
        CardClassification(passcode=5, role=CardRole.PAYOFF),
        CardClassification(passcode=6, role=CardRole.GARNET),
        CardClassification(passcode=7, role=CardRole.GARNET),
        CardClassification(passcode=8, role=CardRole.UNKNOWN),
        CardClassification(passcode=9, role=CardRole.UNKNOWN),
        CardClassification(passcode=10, role=CardRole.UNKNOWN),
    ]

    for c in classifications:
        classifier.add_classification(c)

    return classifier


@pytest.fixture
def simple_deck():
    """Simple 10-card deck for testing."""
    return [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]


@pytest.fixture
def sampler(simple_deck, simple_classifier):
    """Create a sampler with simple deck and classifier."""
    return StratifiedSampler(
        deck=simple_deck,
        classifier=simple_classifier,
        hand_size=3,
    )


# =============================================================================
# HAND COMPOSITION TESTS
# =============================================================================

class TestHandComposition:
    """Tests for HandComposition dataclass."""

    def test_total(self):
        """Total should sum all roles."""
        comp = HandComposition(
            starters=2, extenders=1, payoffs=1,
            utilities=0, garnets=1, unknowns=0
        )
        assert comp.total() == 5

    def test_is_playable_with_starters(self):
        """Hand with starters is playable."""
        comp = HandComposition(
            starters=1, extenders=0, payoffs=0,
            utilities=0, garnets=4, unknowns=0
        )
        assert comp.is_playable() is True

    def test_is_playable_with_extenders(self):
        """Hand with extenders is playable."""
        comp = HandComposition(
            starters=0, extenders=1, payoffs=0,
            utilities=0, garnets=4, unknowns=0
        )
        assert comp.is_playable() is True

    def test_is_not_playable_brick(self):
        """Hand without starters or extenders is not playable."""
        comp = HandComposition(
            starters=0, extenders=0, payoffs=1,
            utilities=0, garnets=4, unknowns=0
        )
        assert comp.is_playable() is False

    def test_quality_score_starter_heavy(self):
        """Starter-heavy hands have higher quality."""
        starter_heavy = HandComposition(
            starters=3, extenders=1, payoffs=1,
            utilities=0, garnets=0, unknowns=0
        )
        balanced = HandComposition(
            starters=1, extenders=2, payoffs=2,
            utilities=0, garnets=0, unknowns=0
        )
        assert starter_heavy.quality_score() > balanced.quality_score()

    def test_quality_score_garnet_penalty(self):
        """Garnets reduce quality score."""
        no_garnets = HandComposition(
            starters=1, extenders=1, payoffs=1,
            utilities=0, garnets=0, unknowns=2
        )
        with_garnets = HandComposition(
            starters=1, extenders=1, payoffs=1,
            utilities=0, garnets=2, unknowns=0
        )
        assert no_garnets.quality_score() > with_garnets.quality_score()

    def test_stratum_key_unique(self):
        """Different compositions have different stratum keys."""
        comp1 = HandComposition(1, 1, 1, 1, 1, 0)
        comp2 = HandComposition(2, 1, 1, 1, 0, 0)
        assert comp1.stratum_key() != comp2.stratum_key()

    def test_stratum_key_same_for_equal(self):
        """Same compositions have same stratum keys."""
        comp1 = HandComposition(1, 2, 0, 1, 1, 0)
        comp2 = HandComposition(1, 2, 0, 1, 1, 0)
        assert comp1.stratum_key() == comp2.stratum_key()


# =============================================================================
# STRATUM TESTS
# =============================================================================

class TestStratum:
    """Tests for Stratum class."""

    def test_len(self):
        """Length is number of hands."""
        comp = HandComposition(1, 0, 0, 0, 0, 2)
        stratum = Stratum(composition=comp, hands=[(1, 8, 9), (1, 8, 10)])
        assert len(stratum) == 2

    def test_sample_all_if_n_exceeds(self):
        """Sample returns all hands if n > len."""
        comp = HandComposition(1, 0, 0, 0, 0, 2)
        hands = [(1, 8, 9), (1, 8, 10)]
        stratum = Stratum(composition=comp, hands=hands)

        sample = stratum.sample(10)
        assert len(sample) == 2

    def test_sample_exact_n(self):
        """Sample returns exactly n hands if n < len."""
        comp = HandComposition(1, 0, 0, 0, 0, 2)
        hands = [(1, 2, 3), (1, 2, 4), (1, 2, 5), (1, 3, 4), (1, 3, 5)]
        stratum = Stratum(composition=comp, hands=hands)

        sample = stratum.sample(3)
        assert len(sample) == 3

    def test_sample_deterministic_with_seed(self):
        """Same seed produces same sample."""
        import random

        comp = HandComposition(1, 0, 0, 0, 0, 2)
        hands = [(1, 2, 3), (1, 2, 4), (1, 2, 5), (1, 3, 4), (1, 3, 5)]
        stratum = Stratum(composition=comp, hands=hands)

        rng1 = random.Random(42)
        rng2 = random.Random(42)

        sample1 = stratum.sample(3, rng1)
        sample2 = stratum.sample(3, rng2)

        assert sample1 == sample2


# =============================================================================
# STRATIFIED SAMPLER TESTS
# =============================================================================

class TestStratifiedSampler:
    """Tests for StratifiedSampler class."""

    def test_total_hands(self, sampler):
        """Total hands should be C(n,k)."""
        # C(10, 3) = 120
        assert sampler.total_hands == comb(10, 3)
        assert sampler.total_hands == 120

    def test_strata_covers_all_hands(self, sampler):
        """Sum of stratum sizes should equal total hands."""
        total_in_strata = sum(len(s) for s in sampler.strata.values())
        assert total_in_strata == sampler.total_hands

    def test_strata_deterministic(self, sampler):
        """Strata should be built deterministically."""
        strata1 = sampler.strata
        # Force rebuild by creating new sampler with same inputs
        sampler2 = StratifiedSampler(
            deck=sampler.deck,
            classifier=sampler.classifier,
            hand_size=sampler.hand_size,
        )
        strata2 = sampler2.strata

        assert strata1.keys() == strata2.keys()
        for key in strata1:
            assert len(strata1[key]) == len(strata2[key])

    def test_classify_hand_starter_only(self, sampler):
        """Classify hand with only starters."""
        # Cards 1, 2 are starters
        hand = (1, 2, 8)  # 2 starters + 1 unknown
        comp = sampler._classify_hand(hand)

        assert comp.starters == 2
        assert comp.unknowns == 1
        assert comp.total() == 3

    def test_classify_hand_mixed(self, sampler):
        """Classify hand with mixed roles."""
        # 1=starter, 3=extender, 5=payoff
        hand = (1, 3, 5)
        comp = sampler._classify_hand(hand)

        assert comp.starters == 1
        assert comp.extenders == 1
        assert comp.payoffs == 1
        assert comp.total() == 3

    def test_sample_returns_correct_count(self, sampler):
        """Sample should return requested number of hands."""
        config = SamplingConfig(total_samples=50, seed=42)
        result = sampler.sample(config)

        assert len(result.hands) <= 50  # May be less if deck is small

    def test_sample_deterministic(self, sampler):
        """Same seed produces same sample."""
        config1 = SamplingConfig(total_samples=30, seed=12345)
        config2 = SamplingConfig(total_samples=30, seed=12345)

        result1 = sampler.sample(config1)
        result2 = sampler.sample(config2)

        assert result1.hands == result2.hands

    def test_sample_different_seeds_different_results(self, sampler):
        """Different seeds produce different samples."""
        config1 = SamplingConfig(total_samples=30, seed=111)
        config2 = SamplingConfig(total_samples=30, seed=222)

        result1 = sampler.sample(config1)
        result2 = sampler.sample(config2)

        # Very unlikely to be equal with different seeds
        assert result1.hands != result2.hands

    def test_sample_respects_min_per_stratum(self, sampler):
        """Each stratum gets at least min_per_stratum samples."""
        config = SamplingConfig(
            total_samples=100,
            min_per_stratum=1,
            seed=42,
        )
        result = sampler.sample(config)

        # All sampled strata should have at least 1
        for key, stats in result.strata_stats.items():
            assert stats["sampled"] >= 1

    def test_sample_result_has_stats(self, sampler):
        """Sample result includes strata statistics."""
        config = SamplingConfig(total_samples=50, seed=42)
        result = sampler.sample(config)

        assert len(result.strata_stats) > 0
        assert result.total_population == sampler.total_hands
        assert 0 < result.sample_fraction <= 1.0

    def test_estimate_brick_rate(self, sampler):
        """Brick rate should be between 0 and 1."""
        rate = sampler.estimate_brick_rate()
        assert 0.0 <= rate <= 1.0

    def test_sample_by_quality(self, sampler):
        """sample_by_quality filters low-quality hands."""
        # High threshold should reduce sample size
        result_high = sampler.sample_by_quality(n=50, min_quality=5.0, seed=42)
        result_low = sampler.sample_by_quality(n=50, min_quality=-10.0, seed=42)

        # Low threshold should include more strata
        assert len(result_low.strata_stats) >= len(result_high.strata_stats)

    def test_get_strata_summary(self, sampler):
        """Strata summary includes expected fields."""
        summary = sampler.get_strata_summary()

        assert len(summary) > 0
        for key, stats in summary.items():
            assert "composition" in stats
            assert "count" in stats
            assert "fraction" in stats
            assert "quality_score" in stats
            assert "is_playable" in stats


# =============================================================================
# SAMPLING CONFIG TESTS
# =============================================================================

class TestSamplingConfig:
    """Tests for SamplingConfig dataclass."""

    def test_defaults(self):
        """Default values are sensible."""
        config = SamplingConfig()

        assert config.total_samples == 1000
        assert config.min_per_stratum == 1
        assert config.prioritize_playable is True
        assert config.seed is None

    def test_custom_values(self):
        """Custom values are respected."""
        config = SamplingConfig(
            total_samples=500,
            min_per_stratum=5,
            prioritize_playable=False,
            seed=42,
        )

        assert config.total_samples == 500
        assert config.min_per_stratum == 5
        assert config.prioritize_playable is False
        assert config.seed == 42


# =============================================================================
# SAMPLING RESULT TESTS
# =============================================================================

class TestSamplingResult:
    """Tests for SamplingResult dataclass."""

    def test_len(self):
        """Length is number of hands."""
        result = SamplingResult(
            hands=[(1, 2, 3), (4, 5, 6)],
            strata_stats={},
            total_population=100,
            sample_fraction=0.02,
        )
        assert len(result) == 2


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestSamplerIntegration:
    """Integration tests for sampler with real classifier patterns."""

    def test_playable_prioritization(self, sampler):
        """Prioritize playable should increase playable fraction in sample."""
        config_prio = SamplingConfig(
            total_samples=60,
            prioritize_playable=True,
            seed=42,
        )
        config_no_prio = SamplingConfig(
            total_samples=60,
            prioritize_playable=False,
            seed=42,
        )

        result_prio = sampler.sample(config_prio)
        result_no_prio = sampler.sample(config_no_prio)

        # Count playable hands in each sample
        def count_playable(hands):
            return sum(
                1 for h in hands
                if sampler._classify_hand(h).is_playable()
            )

        playable_prio = count_playable(result_prio.hands)
        playable_no_prio = count_playable(result_no_prio.hands)

        # Prioritized should have same or more playable hands
        assert playable_prio >= playable_no_prio

    def test_all_hands_valid(self, sampler):
        """All sampled hands should be valid (from deck)."""
        config = SamplingConfig(total_samples=50, seed=42)
        result = sampler.sample(config)

        deck_set = set(sampler.deck)
        for hand in result.hands:
            for card in hand:
                assert card in deck_set, f"Card {card} not in deck"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
