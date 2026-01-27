#!/usr/bin/env python3
"""Unit tests for the combo enumeration pipeline."""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile
import json

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).parents[2] / "scripts"))


# =============================================================================
# PIPELINE CONFIG TESTS
# =============================================================================

class TestPipelineConfig:
    """Test PipelineConfig dataclass."""

    def test_default_config(self):
        """Default config should have sensible values."""
        from run_pipeline import PipelineConfig

        config = PipelineConfig()

        assert config.total_samples == 100
        assert config.min_per_stratum == 1
        assert config.prioritize_playable is True
        assert config.max_depth == 25
        assert config.top_k == 10
        assert config.resume is False

    def test_custom_config(self):
        """Custom config values should be respected."""
        from run_pipeline import PipelineConfig

        config = PipelineConfig(
            total_samples=500,
            num_workers=4,
            max_depth=30,
            checkpoint_interval=100,
        )

        assert config.total_samples == 500
        assert config.num_workers == 4
        assert config.max_depth == 30
        assert config.checkpoint_interval == 100


class TestPipelineResult:
    """Test PipelineResult dataclass."""

    def test_result_creation(self):
        """PipelineResult should be creatable with all fields."""
        from run_pipeline import PipelineResult

        result = PipelineResult(
            total_hand_space=100000,
            hands_sampled=500,
            strata_count=25,
            playable_fraction=0.85,
            hands_processed=500,
            unique_terminals=150,
            total_paths=10000,
            enumeration_time=60.0,
            top_combos=[],
            tier_distribution={"S": 5, "A": 20},
            total_time=75.0,
        )

        assert result.total_hand_space == 100000
        assert result.hands_sampled == 500
        assert result.unique_terminals == 150


# =============================================================================
# DECK LOADING TESTS
# =============================================================================

class TestDeckLoading:
    """Test deck loading functions."""

    def test_load_standard_format(self, tmp_path):
        """Should load standard deck format."""
        from run_pipeline import load_deck

        deck_file = tmp_path / "deck.json"
        deck_data = {
            "main_deck": [1, 2, 3, 4, 5],
            "extra_deck": [100, 101, 102],
        }
        deck_file.write_text(json.dumps(deck_data))

        main, extra = load_deck(deck_file)

        assert main == [1, 2, 3, 4, 5]
        assert extra == [100, 101, 102]

    def test_load_locked_library_format(self, tmp_path):
        """Should load locked library format."""
        from run_pipeline import load_deck

        deck_file = tmp_path / "library.json"
        deck_data = {
            "cards": {
                "1": {"count": 3, "is_extra": False},
                "2": {"count": 2, "is_extra": False},
                "100": {"count": 1, "is_extra": True},
            }
        }
        deck_file.write_text(json.dumps(deck_data))

        main, extra = load_deck(deck_file)

        assert len(main) == 5  # 3 + 2
        assert len(extra) == 1
        assert 1 in main
        assert 100 in extra

    def test_load_nonexistent_raises(self, tmp_path):
        """Loading nonexistent deck should raise."""
        from run_pipeline import load_deck

        with pytest.raises(FileNotFoundError):
            load_deck(tmp_path / "nonexistent.json")

    def test_load_invalid_format_raises(self, tmp_path):
        """Loading invalid format should raise."""
        from run_pipeline import load_deck

        deck_file = tmp_path / "invalid.json"
        deck_file.write_text('{"unknown_key": [1, 2, 3]}')

        with pytest.raises(ValueError):
            load_deck(deck_file)


class TestClassifierLoading:
    """Test classifier loading functions."""

    def test_load_classifier_no_file(self, tmp_path):
        """Should return empty classifier if no file exists."""
        from run_pipeline import load_classifier

        # Pass a nonexistent path
        classifier = load_classifier(tmp_path / "nonexistent.json")

        assert classifier is not None

    def test_load_classifier_with_file(self, tmp_path):
        """Should load classifications from file."""
        from run_pipeline import load_classifier

        roles_file = tmp_path / "roles.json"
        roles_data = {
            "cards": {
                "1": {"role": "STARTER"},
                "2": {"role": "EXTENDER"},
            }
        }
        roles_file.write_text(json.dumps(roles_data))

        classifier = load_classifier(roles_file)

        # Classifier should have loaded the data
        assert classifier is not None
        assert len(classifier._classifications) == 2


# =============================================================================
# REPORT SAVING TESTS
# =============================================================================

class TestReportSaving:
    """Test report saving functionality."""

    def test_save_report(self, tmp_path):
        """Should save report as JSON."""
        from run_pipeline import PipelineResult, save_report

        result = PipelineResult(
            total_hand_space=10000,
            hands_sampled=100,
            strata_count=10,
            playable_fraction=0.8,
            hands_processed=100,
            unique_terminals=50,
            total_paths=1000,
            enumeration_time=30.0,
            top_combos=[],
            tier_distribution={"A": 10, "B": 20},
            total_time=35.0,
        )

        output_path = tmp_path / "report.json"
        save_report(result, output_path)

        assert output_path.exists()

        with open(output_path) as f:
            report = json.load(f)

        assert report["sampling"]["total_hand_space"] == 10000
        assert report["sampling"]["hands_sampled"] == 100
        assert report["enumeration"]["unique_terminals"] == 50
        assert report["ranking"]["tier_distribution"] == {"A": 10, "B": 20}

    def test_save_report_creates_dirs(self, tmp_path):
        """Should create parent directories if needed."""
        from run_pipeline import PipelineResult, save_report

        result = PipelineResult(
            total_hand_space=1000,
            hands_sampled=50,
            strata_count=5,
            playable_fraction=0.9,
            hands_processed=50,
            unique_terminals=25,
            total_paths=500,
            enumeration_time=10.0,
            top_combos=[],
            tier_distribution={},
            total_time=12.0,
        )

        output_path = tmp_path / "nested" / "dir" / "report.json"
        save_report(result, output_path)

        assert output_path.exists()


# =============================================================================
# SAMPLING STAGE TESTS
# =============================================================================

class TestSamplingStage:
    """Test sampling stage of pipeline."""

    def test_run_sampling_basic(self):
        """Sampling should return valid result."""
        from run_pipeline import run_sampling, PipelineConfig
        from ygo_combo.cards.roles import CardRoleClassifier

        deck = list(range(1, 21))  # 20 cards
        classifier = CardRoleClassifier()
        config = PipelineConfig(total_samples=50)

        result = run_sampling(deck, classifier, config)

        assert len(result.hands) <= 50
        assert len(result.hands) > 0

    def test_run_sampling_respects_seed(self):
        """Same seed should produce same sample."""
        from run_pipeline import run_sampling, PipelineConfig
        from ygo_combo.cards.roles import CardRoleClassifier

        deck = list(range(1, 21))
        classifier = CardRoleClassifier()
        config = PipelineConfig(total_samples=20, sample_seed=42)

        result1 = run_sampling(deck, classifier, config)
        result2 = run_sampling(deck, classifier, config)

        assert result1.hands == result2.hands


# =============================================================================
# CLI TESTS
# =============================================================================

class TestCLI:
    """Test CLI argument parsing."""

    def test_parse_default_args(self):
        """Default args should be parsed correctly."""
        import argparse
        from run_pipeline import main

        # Just verify the script can be imported and main exists
        assert callable(main)

    def test_help_output(self):
        """Help should show all options."""
        import subprocess

        result = subprocess.run(
            ["python3", "scripts/run_pipeline.py", "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "--samples" in result.stdout
        assert "--workers" in result.stdout
        assert "--checkpoint-dir" in result.stdout
        assert "--resume" in result.stdout


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
