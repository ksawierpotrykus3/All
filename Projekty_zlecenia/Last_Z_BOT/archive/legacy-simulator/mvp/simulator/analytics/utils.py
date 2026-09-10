"""ML utilities and helpers."""
import logging
import numpy as np


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


def normalize_features(data, feature_names=None):
    """Normalize 2D feature matrix to [0,1] range."""
    X = np.array(data)
    if X.ndim != 2:
        raise ValueError("Expected 2D array")
    
    X_min = X.min(axis=0)
    X_max = X.max(axis=0)
    X_normalized = (X - X_min) / (X_max - X_min + 1e-10)
    return X_normalized
