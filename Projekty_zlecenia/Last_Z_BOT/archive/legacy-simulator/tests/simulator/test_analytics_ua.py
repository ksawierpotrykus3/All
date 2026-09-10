import pytest
import numpy as np
from mvp.simulator.analytics.anomaly_detection import MetricsAnalyzer


class TestMetricsAnalyzerUnivariate:
    """Tests for univariate anomaly detection."""
    
    def test_init(self):
        analyzer = MetricsAnalyzer(min_samples=5)
        assert analyzer.min_samples == 5
    
    def test_iqr_detection_upper_outlier(self):
        """Test IQR detection for upper outlier."""
        analyzer = MetricsAnalyzer()
        values = [10, 20, 30, 40, 50, 100]  # 100 is outlier
        anomalies = analyzer.detect_univariate_anomalies('test_metric', values)
        assert len(anomalies) > 0
        assert any(a['value'] == 100 for a in anomalies)
    
    def test_iqr_detection_lower_outlier(self):
        """Test IQR detection for lower outlier."""
        analyzer = MetricsAnalyzer()
        values = [-50, 10, 20, 30, 40, 50]  # -50 is outlier
        anomalies = analyzer.detect_univariate_anomalies('test_metric', values)
        assert len(anomalies) > 0
        assert any(a['value'] == -50 for a in anomalies)
    
    def test_zscore_detection(self):
        """Test Z-score detection."""
        analyzer = MetricsAnalyzer()
        values = [1, 2, 3, 4, 5, 6, 100]  # 100 is z-score outlier
        anomalies = analyzer.detect_univariate_anomalies('test_metric', values)
        assert len(anomalies) > 0
    
    def test_small_dataset_handling(self):
        """Test handling of datasets smaller than min_samples."""
        analyzer = MetricsAnalyzer(min_samples=5)
        values = [1, 2, 3]  # Only 3 samples
        anomalies = analyzer.detect_univariate_anomalies('test_metric', values)
        assert anomalies == []
    
    def test_nan_filtering(self):
        """Test NaN and inf filtering."""
        analyzer = MetricsAnalyzer()
        values = [1.0, 2.0, float('nan'), 3.0, 4.0, 5.0, float('inf')]
        anomalies = analyzer.detect_univariate_anomalies('test_metric', values)
        # Should not crash
        assert isinstance(anomalies, list)
