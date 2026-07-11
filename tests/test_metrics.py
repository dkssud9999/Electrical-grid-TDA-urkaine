"""Tests for metrics.py — Electrical distance metric classes."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pytest

from electrical_distance.metrics import (
    PTDFVectorDistance,
    EffectiveResistanceDistance,
    BusLODFDistance,
    PTDFInverseDistance,
    HybridDistance,
    GeodesicElectricalHybrid,
    KCLCurrentDistance,
)

# Shared test data: 3-bus system
BUS_PAIRS = [(0, 1), (1, 2), (0, 2)]
SUSCEPTANCES = [10.0, 6.667, 5.0]
N_BUS = 3


class TestPTDFVectorDistance:
    """Test PTDFVectorDistance metric."""

    def test_l2_default(self):
        metric = PTDFVectorDistance()
        D = metric.compute(N_BUS, BUS_PAIRS, SUSCEPTANCES)
        assert D.shape == (3, 3)
        np.testing.assert_array_almost_equal(D, D.T)
        np.testing.assert_array_almost_equal(np.diag(D), np.zeros(3))

    def test_l1_norm(self):
        metric = PTDFVectorDistance(p_norm=1.0)
        D = metric.compute(N_BUS, BUS_PAIRS, SUSCEPTANCES)
        assert D.shape == (3, 3)

    def test_name(self):
        metric = PTDFVectorDistance(p_norm=2.0)
        assert "L2" in metric.name
        metric2 = PTDFVectorDistance(p_norm=1.0)
        assert "L1" in metric2.name

    def test_description(self):
        metric = PTDFVectorDistance()
        assert isinstance(metric.description, str)
        assert len(metric.description) > 0


class TestEffectiveResistanceDistance:
    """Test EffectiveResistanceDistance metric."""

    def test_compute(self):
        metric = EffectiveResistanceDistance()
        D = metric.compute(N_BUS, BUS_PAIRS, SUSCEPTANCES)
        assert D.shape == (3, 3)
        np.testing.assert_array_almost_equal(D, D.T)
        np.testing.assert_array_almost_equal(np.diag(D), np.zeros(3))

    def test_name(self):
        metric = EffectiveResistanceDistance()
        assert "Effective" in metric.name


class TestBusLODFDistance:
    """Test BusLODFDistance metric."""

    def test_compute(self):
        metric = BusLODFDistance()
        D = metric.compute(N_BUS, BUS_PAIRS, SUSCEPTANCES)
        assert D.shape == (3, 3)
        np.testing.assert_array_almost_equal(D, D.T)

    def test_name(self):
        metric = BusLODFDistance()
        assert "LODF" in metric.name


class TestPTDFInverseDistance:
    """Test PTDFInverseDistance metric."""

    def test_inverse_mode(self):
        metric = PTDFInverseDistance(mode="inverse")
        D = metric.compute(N_BUS, BUS_PAIRS, SUSCEPTANCES)
        assert D.shape == (3, 3)
        assert np.all(D >= 0.0) and np.all(D <= 1.0)

    def test_gaussian_mode(self):
        metric = PTDFInverseDistance(mode="gaussian", sigma=2.0)
        D = metric.compute(N_BUS, BUS_PAIRS, SUSCEPTANCES)
        assert D.shape == (3, 3)
        assert np.all(D >= 0.0) and np.all(D <= 1.0)

    def test_logistic_mode(self):
        metric = PTDFInverseDistance(mode="logistic", sigma=1.0)
        D = metric.compute(N_BUS, BUS_PAIRS, SUSCEPTANCES)
        assert D.shape == (3, 3)
        assert np.all(D >= 0.0) and np.all(D <= 1.0)

    def test_invalid_mode(self):
        metric = PTDFInverseDistance(mode="unknown")
        with pytest.raises(ValueError, match="Unknown mode"):
            metric.compute(N_BUS, BUS_PAIRS, SUSCEPTANCES)


class TestHybridDistance:
    """Test HybridDistance metric."""

    def test_two_metrics_equal_weight(self):
        ptdf = PTDFVectorDistance()
        eff = EffectiveResistanceDistance()
        hybrid = HybridDistance([(ptdf, 0.5), (eff, 0.5)])
        D = hybrid.compute(N_BUS, BUS_PAIRS, SUSCEPTANCES)
        assert D.shape == (3, 3)
        assert np.all(D >= 0.0)

    def test_single_metric(self):
        ptdf = PTDFVectorDistance()
        hybrid = HybridDistance([(ptdf, 1.0)])
        D = hybrid.compute(N_BUS, BUS_PAIRS, SUSCEPTANCES)
        assert D.shape == (3, 3)

    def test_name(self):
        ptdf = PTDFVectorDistance()
        hybrid = HybridDistance([(ptdf, 1.0)])
        assert "Hybrid" in hybrid.name


class TestKCLCurrentDistance:
    """Test KCLCurrentDistance metric."""

    def test_l2_default(self):
        metric = KCLCurrentDistance(p_norm=2.0)
        D = metric.compute(N_BUS, BUS_PAIRS, SUSCEPTANCES)
        assert D.shape == (3, 3)
        np.testing.assert_array_almost_equal(D, D.T)
        np.testing.assert_array_almost_equal(np.diag(D), np.zeros(3))

    def test_l1_norm(self):
        metric = KCLCurrentDistance(p_norm=1.0)
        D = metric.compute(N_BUS, BUS_PAIRS, SUSCEPTANCES)
        assert D.shape == (3, 3)

    def test_name(self):
        metric = KCLCurrentDistance()
        assert "KCL" in metric.name

    def test_description(self):
        metric = KCLCurrentDistance()
        assert isinstance(metric.description, str)
        assert len(metric.description) > 0

    def test_all_positive_values(self):
        """Current-based distances should be non-negative."""
        metric = KCLCurrentDistance()
        D = metric.compute(N_BUS, BUS_PAIRS, SUSCEPTANCES)
        assert np.all(D >= 0.0)
    """Test GeodesicElectricalHybrid metric."""

    def test_compute(self):
        positions = [(0, 0), (1, 0), (0, 1)]
        elec = EffectiveResistanceDistance()
        hybrid = GeodesicElectricalHybrid(positions, elec, w_geo=0.3, w_elec=0.7)
        D = hybrid.compute(N_BUS, BUS_PAIRS, SUSCEPTANCES)
        assert D.shape == (3, 3)
        assert np.all(D >= 0.0)

    def test_all_geo(self):
        """w_geo=1, w_elec=0 -> only geographic."""
        positions = [(0, 0), (1, 0), (0, 1)]
        elec = EffectiveResistanceDistance()
        hybrid = GeodesicElectricalHybrid(positions, elec, w_geo=1.0, w_elec=0.0)
        D = hybrid.compute(N_BUS, BUS_PAIRS, SUSCEPTANCES)
        assert D.shape == (3, 3)
        # Geographic distance (0,0)-(1,0) = 1, normalized by max dist sqrt(2) ≈ 1.414
        # So D[0,1] = 1.0 / sqrt(2) ≈ 0.707
        assert D[0, 1] == pytest.approx(1.0 / np.sqrt(2), rel=1e-2)

    def test_name(self):
        positions = [(0, 0), (1, 0), (0, 1)]
        elec = EffectiveResistanceDistance()
        hybrid = GeodesicElectricalHybrid(positions, elec)
        assert "Geo" in hybrid.name

