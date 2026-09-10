"""Univariate and multivariate anomaly detection."""
import logging
import numpy as np
from sklearn.neighbors import LocalOutlierFactor


def get_logger(name):
    """Get consistent logger."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


class MetricsAnalyzer:
    """Detect anomalies using IQR, Z-score, LOF."""
    
    def __init__(self, min_samples=5):
        self.min_samples = min_samples
        self.logger = get_logger(__name__)
    
    def detect_univariate_anomalies(self, metric_name, values):
        """
        IQR + Z-score detection.
        
        Args:
            metric_name: str
            values: list[float]
        
        Returns:
            list[dict] with keys: iteration_idx, value, anomaly_type, severity, q1, q3, iqr, mean, std, z_score
        """
        if len(values) < self.min_samples:
            self.logger.warning(f"Skipping {metric_name}: only {len(values)} samples (min {self.min_samples})")
            return []
        
        # Clean NaN/inf
        clean_values = [v for v in values if np.isfinite(v)]
        if len(clean_values) < self.min_samples:
            self.logger.warning(f"{metric_name}: NaN removal left {len(clean_values)} samples")
            return []
        
        # IQR detection
        q1 = np.percentile(clean_values, 25)
        q3 = np.percentile(clean_values, 75)
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        
        iqr_flags = [lower_bound <= v <= upper_bound for v in clean_values]
        
        # Z-score detection
        mean = np.mean(clean_values)
        std = np.std(clean_values)
        if std == 0:
            z_scores = [0 if v == mean else float('inf') for v in clean_values]
        else:
            z_scores = [(v - mean) / std for v in clean_values]
        zscore_flags = [abs(z) > 3 for z in z_scores]
        
        # Classify
        anomalies = []
        for idx, value in enumerate(clean_values):
            is_iqr_outlier = not iqr_flags[idx]
            is_zscore_outlier = zscore_flags[idx]
            
            if is_iqr_outlier or is_zscore_outlier:
                if is_iqr_outlier and is_zscore_outlier:
                    anomaly_type = "both"
                    severity = "critical"
                elif is_zscore_outlier:
                    anomaly_type = "zscore"
                    severity = "high"
                else:
                    anomaly_type = "iqr"
                    severity = "medium"
                
                anomalies.append({
                    "iteration_idx": idx,
                    "value": value,
                    "anomaly_type": anomaly_type,
                    "severity": severity,
                    "q1": q1, "q3": q3, "iqr": iqr,
                    "mean": mean, "std": std,
                    "z_score": z_scores[idx]
                })
        
        return anomalies
    
    def detect_multivariate_anomalies(self, data_2d):
        """
        LOF (Local Outlier Factor) detection.
        
        Args:
            data_2d: list[list[float]] shape (n_samples, 2)
        
        Returns:
            list[dict] with keys: iteration_idx, features, lof_score, is_anomaly, severity
        """
        if len(data_2d) < self.min_samples:
            self.logger.warning(f"LOF: only {len(data_2d)} samples (min {self.min_samples})")
            return []
        
        # Clean NaN
        clean_data = [row for row in data_2d if all(np.isfinite(v) for v in row)]
        if len(clean_data) < self.min_samples:
            self.logger.warning(f"LOF: NaN removal left {len(clean_data)} samples")
            return []
        
        # Apply LOF
        X = np.array(clean_data)
        k_neighbors = min(5, len(clean_data) - 1)
        
        try:
            lof_model = LocalOutlierFactor(n_neighbors=k_neighbors)
            lof_scores = -lof_model.fit_predict(X)  # negate to get outlier scores
        except Exception as e:
            self.logger.error(f"LOF fitting failed: {e}")
            return []
        
        threshold = 1.3
        anomalies = []
        for idx, (features, score) in enumerate(zip(clean_data, lof_scores)):
            is_anomaly = score > threshold
            if is_anomaly:
                severity = "high" if score > 1.5 else "medium"
                anomalies.append({
                    "iteration_idx": idx,
                    "features": list(features),
                    "lof_score": float(score),
                    "is_anomaly": True,
                    "severity": severity
                })
        
        return anomalies
