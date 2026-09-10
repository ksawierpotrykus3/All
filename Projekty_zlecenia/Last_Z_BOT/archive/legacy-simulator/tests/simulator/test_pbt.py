"""Tests for PBT framework."""
import pytest
from mvp.simulator.pbt import strategies, properties, generator


class TestPBTStrategies:
    """Test Hypothesis strategies."""
    
    def test_strategies_import(self):
        """Verify strategies module imports."""
        assert hasattr(strategies, "variant_strategy")
        assert hasattr(strategies, "metric_set_strategy")
        assert hasattr(strategies, "perturbation_strategy")


class TestPBTProperties:
    """Test PBT properties."""
    
    def test_properties_import(self):
        """Verify properties module imports."""
        assert hasattr(properties, "prop_metrics_aggregation_roundtrip")
        assert hasattr(properties, "prop_accuracy_bounds")


class TestPBTGenerator:
    """Test PBT generator."""
    
    def test_generator_import(self):
        """Verify generator module imports."""
        assert hasattr(generator, "run_pbt_suite")
