# Phase 6: Advanced Analytics & ML — Design Document

**Data:** Luty 2027  
**Status:** Design Complete  
**Zakres:** PBT, Anomaly Detection (IQR + Z-score + LOF), Predictive Degradation (ARIMA), Custom Thresholds, Integration z ReportingEngine

---

## 1. Przegląd Architektury

Phase 6 składa się z 3 głównych subsystemów:

```
┌─────────────────────────────────────────────────────────────┐
│                     Phase 6: Analytics & ML                  │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────┐  │
│  │  PBT Generator   │  │ Metrics Analyzer │  │ Forecaster│  │
│  │  (hypothesis)    │  │ (IQR+Z+LOF)      │  │ (ARIMA)   │  │
│  └──────────────────┘  └──────────────────┘  └───────────┘  │
│           │                     │                     │       │
│           └─────────────────────┼─────────────────────┘       │
│                                 │                             │
│                    ┌────────────▼──────────┐                 │
│                    │  ThresholdManager     │                 │
│                    │  (Evaluation + Alerts)│                 │
│                    └────────────┬──────────┘                 │
│                                 │                             │
│                    ┌────────────▼──────────┐                 │
│                    │ ReportingEngine Ext.  │                 │
│                    │ (Anomaly viz + Plots) │                 │
│                    └───────────────────────┘                 │
│                                                               │
│  Integration: Metrics from Phase 1-5 → Analytics → Reports   │
│  Data flow: Real-time metric collection → anomaly detection  │
│            → threshold evaluation → reporting                 │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Module Structure

### 2.1 mvp/simulator/pbt/

**Property-Based Testing Framework** za pomocą Hypothesis.

```python
mvp/simulator/pbt/
├── __init__.py
├── strategies.py          # Hypothesis strategies (variants, metrics, perturbations)
├── properties.py          # Property tests (round-trip, invariants, edge cases)
└── generator.py           # PBT test runner / coordinator
```

**Strategies:**
- `variant_strategy()`: generates random variant combinations (clean/cluttered, visible/hidden, idle/medium/high, etc.)
- `metric_set_strategy()`: generates valid metric collections (accuracy 0-100%, latency > 0, etc.)
- `perturbation_strategy()`: generates random perturbations (CPU spike, delay, noise injection)

**Properties:**
- `prop_metrics_aggregation_roundtrip`: For any metric set, aggregate → re-aggregate = same result
- `prop_accuracy_bounds`: For any accuracy count/total, 0 <= percentage <= 100%
- `prop_variant_consistency`: After applying variant, GameStateManager state is valid
- `prop_no_crashes_under_perturbations`: Simulator doesn't crash with random perturbations

**Generator:**
- `run_pbt_suite(num_iterations=100)`: executes all properties with Hypothesis
- Returns: (total_tests, passed, failed, examples)

---

### 2.2 mvp/simulator/analytics/

**Advanced Analytics & Machine Learning** subsystem.

```python
mvp/simulator/analytics/
├── __init__.py
├── anomaly_detection.py    # MetricsAnalyzer (IQR, Z-score, LOF)
├── degradation_forecast.py # DegradationForecaster (ARIMA)
├── thresholds.py           # ThresholdManager (rules + evaluation)
└── utils.py                # ML helpers (fit_arima, lof_score, etc.)
```

#### 2.2.1 MetricsAnalyzer (anomaly_detection.py)

```python
class MetricsAnalyzer:
    """
    Detects anomalies in metrics using IQR, Z-score, and LOF.
    
    Properties:
    - detect_univariate_anomalies(metric_name, data) → list[AnomalyRecord]
    - detect_multivariate_anomalies(data_2d) → list[MultivariateAnomalyRecord]
    """
    
    def __init__(self, min_samples=5):
        self.min_samples = min_samples
        self.logger = get_logger(__name__)
    
    def detect_univariate_anomalies(self, metric_name, values):
        """
        IQR + Z-score detection.
        
        Args:
            metric_name: str ("accuracy", "latency", etc.)
            values: list[float]
        
        Returns:
            list[
                {
                    "iteration_idx": int,
                    "value": float,
                    "anomaly_type": str ("iqr", "zscore", "both"),
                    "severity": str ("medium", "high", "critical"),
                    "q1": float, "q3": float, "iqr": float,
                    "mean": float, "std": float
                }
            ]
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
            data_2d: list[list[float]] shape (n_samples, 2) = [[accuracy, latency], ...]
        
        Returns:
            list[
                {
                    "iteration_idx": int,
                    "features": [float, float],
                    "lof_score": float,
                    "is_anomaly": bool,
                    "severity": str ("medium", "high")
                }
            ]
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
            lof_scores = -lof_model.fit_predict(X)  # negate to get outlier scores (high = anomaly)
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
                    "features": features,
                    "lof_score": score,
                    "is_anomaly": True,
                    "severity": severity
                })
        
        return anomalies
```

#### 2.2.2 DegradationForecaster (degradation_forecast.py)

```python
class DegradationForecaster:
    """
    Forecasts metric degradation using ARIMA.
    
    Properties:
    - forecast(metric_name, values, periods=10) → ForecastResult
    """
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
    def forecast(self, metric_name, values, periods=10):
        """
        ARIMA forecasting with fallback to exponential smoothing.
        
        Args:
            metric_name: str
            values: list[float]
            periods: int (number of future periods to forecast)
        
        Returns:
            {
                "metric": str,
                "forecast_values": list[float],  # next `periods` values
                "lower_ci": list[float],  # 95% confidence interval lower
                "upper_ci": list[float],  # 95% confidence interval upper
                "current_value": float,
                "degradation_trend": bool,
                "degradation_rate_pct": float,  # (forecast_mean - current) / current * 100
                "forecast_method": str  ("arima" or "exponential_smoothing")
            }
        """
        if len(values) < 10:
            self.logger.warning(f"Forecast: only {len(values)} samples (min 10)")
            return None
        
        # Clean values
        clean_values = [v for v in values if np.isfinite(v)]
        if len(clean_values) < 10:
            self.logger.warning(f"Forecast: NaN removal left {len(clean_values)} samples")
            return None
        
        current_value = clean_values[-1]
        
        # Try ARIMA
        try:
            from statsmodels.tsa.arima.model import ARIMA
            
            # Auto-select (p,d,q) or use default (1,1,1)
            try:
                model = ARIMA(clean_values, order=(1, 1, 1))
                result = model.fit()
            except:
                # Fallback to simple ARIMA
                model = ARIMA(clean_values, order=(0, 1, 0))
                result = model.fit()
            
            forecast_obj = result.get_forecast(steps=periods)
            forecast_vals = forecast_obj.predicted_mean.tolist()
            ci = forecast_obj.conf_int(alpha=0.05)
            lower_ci = ci.iloc[:, 0].tolist()
            upper_ci = ci.iloc[:, 1].tolist()
            method = "arima"
        
        except Exception as e:
            self.logger.warning(f"ARIMA failed: {e}. Falling back to exponential smoothing.")
            
            # Exponential smoothing fallback
            alpha = 0.3
            forecast_vals = []
            last_val = clean_values[-1]
            for _ in range(periods):
                last_val = alpha * last_val + (1 - alpha) * np.mean(clean_values)
                forecast_vals.append(last_val)
            
            # Simple confidence bands
            residuals_std = np.std(np.diff(clean_values))
            lower_ci = [v - 1.96 * residuals_std for v in forecast_vals]
            upper_ci = [v + 1.96 * residuals_std for v in forecast_vals]
            method = "exponential_smoothing"
        
        # Detect degradation
        forecast_mean = np.mean(forecast_vals)
        degradation_trend = forecast_mean < current_value
        
        if degradation_trend:
            degradation_rate_pct = (forecast_mean - current_value) / current_value * 100
        else:
            degradation_rate_pct = 0.0
        
        return {
            "metric": metric_name,
            "forecast_values": forecast_vals,
            "lower_ci": lower_ci,
            "upper_ci": upper_ci,
            "current_value": current_value,
            "degradation_trend": degradation_trend,
            "degradation_rate_pct": degradation_rate_pct,
            "forecast_method": method
        }
```

#### 2.2.3 ThresholdManager (thresholds.py)

```python
class ThresholdManager:
    """
    Manages custom thresholds and evaluates them against incoming metrics.
    
    Properties:
    - set_threshold(metric, operator, value, severity) → None
    - evaluate(iteration_data) → list[AlertRecord]
    """
    
    def __init__(self):
        self.thresholds = []  # list[ThresholdRule]
        self.logger = get_logger(__name__)
    
    def set_threshold(self, metric, operator, value, severity):
        """
        Configure a threshold rule.
        
        Args:
            metric: str ("accuracy", "latency")
            operator: str ("<", ">", "<=", ">=", "==", "!=")
            value: float
            severity: str ("info", "warning", "critical")
        """
        valid_operators = {"<", ">", "<=", ">=", "==", "!="}
        valid_metrics = {"accuracy", "latency", "cpu_usage"}
        valid_severities = {"info", "warning", "critical"}
        
        if operator not in valid_operators:
            raise ValueError(f"Invalid operator: {operator}")
        if metric not in valid_metrics:
            raise ValueError(f"Invalid metric: {metric}")
        if severity not in valid_severities:
            raise ValueError(f"Invalid severity: {severity}")
        
        rule = {
            "metric": metric,
            "operator": operator,
            "value": value,
            "severity": severity,
            "created_at": datetime.now()
        }
        self.thresholds.append(rule)
        self.logger.info(f"Threshold set: {metric} {operator} {value} (severity: {severity})")
    
    def evaluate(self, iteration_data):
        """
        Evaluate all thresholds against iteration data.
        
        Args:
            iteration_data: dict with keys like "accuracy", "latency", "cpu_usage"
        
        Returns:
            list[
                {
                    "metric": str,
                    "triggered_value": float,
                    "threshold_value": float,
                    "operator": str,
                    "message": str,
                    "severity": str
                }
            ]
        """
        alerts = []
        
        for rule in self.thresholds:
            metric = rule["metric"]
            operator = rule["operator"]
            threshold_val = rule["value"]
            severity = rule["severity"]
            
            if metric not in iteration_data:
                continue
            
            actual_val = iteration_data[metric]
            triggered = self._eval_operator(actual_val, operator, threshold_val)
            
            if triggered:
                message = f"{metric} {operator} {threshold_val} (actual: {actual_val})"
                alerts.append({
                    "metric": metric,
                    "triggered_value": actual_val,
                    "threshold_value": threshold_val,
                    "operator": operator,
                    "message": message,
                    "severity": severity
                })
        
        # Sort by severity DESC
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        alerts.sort(key=lambda x: severity_order.get(x["severity"], 99))
        
        return alerts
    
    @staticmethod
    def _eval_operator(actual, operator, threshold):
        if operator == "<":
            return actual < threshold
        elif operator == ">":
            return actual > threshold
        elif operator == "<=":
            return actual <= threshold
        elif operator == ">=":
            return actual >= threshold
        elif operator == "==":
            return actual == threshold
        elif operator == "!=":
            return actual != threshold
        return False
```

#### 2.2.4 utils.py (ML helpers)

```python
def get_logger(name):
    """Consistent logging."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger

def normalize_features(data, feature_names=None):
    """Normalize 2D feature matrix to [0,1] range (for LOF)."""
    X = np.array(data)
    if X.ndim != 2:
        raise ValueError("Expected 2D array")
    
    X_min = X.min(axis=0)
    X_max = X.max(axis=0)
    X_normalized = (X - X_min) / (X_max - X_min + 1e-10)
    return X_normalized
```

---

## 3. Data Structures

### AnomalyRecord (univariate)

```python
@dataclass
class AnomalyRecord:
    iteration_idx: int
    value: float
    anomaly_type: str  # "iqr", "zscore", "both"
    severity: str      # "medium", "high", "critical"
    q1: float
    q3: float
    iqr: float
    mean: float
    std: float
    z_score: float
```

### MultivariateAnomalyRecord

```python
@dataclass
class MultivariateAnomalyRecord:
    iteration_idx: int
    features: list  # [accuracy, latency]
    lof_score: float
    is_anomaly: bool
    severity: str
```

### ForecastResult

```python
@dataclass
class ForecastResult:
    metric: str
    forecast_values: list
    lower_ci: list
    upper_ci: list
    current_value: float
    degradation_trend: bool
    degradation_rate_pct: float
    forecast_method: str
```

### AlertRecord

```python
@dataclass
class AlertRecord:
    metric: str
    triggered_value: float
    threshold_value: float
    operator: str
    message: str
    severity: str
```

---

## 4. Integration Points

### 4.1 With MetricsCollector (Phase 1-5)

```python
# In Phase 1-5 code:
collector = MetricsCollector()

# ... collect metrics ...

# Phase 6 integration:
analyzer = MetricsAnalyzer()
accuracy_values = collector.get_metric_history("accuracy")
anomalies = analyzer.detect_univariate_anomalies("accuracy", accuracy_values)
```

### 4.2 With ReportingEngine

```python
# After session complete:
reporter = ReportingEngine(session_data)

# Add analytics sections:
anomalies = analyzer.detect_univariate_anomalies("accuracy", accuracy_history)
reporter.add_section("Anomaly Detection", format_anomaly_table(anomalies))

forecaster = DegradationForecaster()
forecast = forecaster.forecast("accuracy", accuracy_history, periods=10)
reporter.add_plot("Degradation Forecast", plot_forecast(forecast))

# Report with thresholds:
threshold_breaches = threshold_manager.get_session_breaches()
reporter.add_section("Threshold Breaches", format_breaches(threshold_breaches))
```

### 4.3 Real-time Threshold Evaluation (Optional Enhancement)

```python
# In metric collection loop:
for iteration_idx in range(num_iterations):
    iteration_data = {"accuracy": acc, "latency": lat}
    
    # Real-time threshold check
    alerts = threshold_manager.evaluate(iteration_data)
    if alerts:
        for alert in alerts:
            if alert["severity"] == "critical":
                logger.error(alert["message"])
                # Could trigger UI notification, pause, etc.
```

---

## 5. Correctness Properties

*Properties validate universal correctness guarantees across all inputs.*

### Property 1: Anomaly Detection Round-Trip
**For any** valid metric values with at least 5 samples, detecting anomalies twice in sequence should return identical results (deterministic).

**Validates: Requirements 2.1, 2.2, 3.1**

### Property 2: Accuracy Bounds Preserved
**For any** accuracy value (0-100%) and any anomaly detection method (IQR, Z-score, LOF), the detected anomalies should never suggest accuracy outside [0, 100%].

**Validates: Requirements 2.1, 2.2**

### Property 3: LOF Requires Minimum Samples
**For any** dataset with N < 5 samples, LOF detection SHALL return empty list (no false positives).

**Validates: Requirements 3.3**

### Property 4: Forecast Always Returns Bounded Trend
**For any** valid metric history (≥ 10 samples), ARIMA forecast SHALL return degradation_rate_pct as real number (not NaN or inf).

**Validates: Requirements 4.1, 4.2**

### Property 5: Threshold Evaluation is Deterministic
**For any** threshold rule set and iteration data, evaluating thresholds twice SHALL return identical alert lists (same order, same values).

**Validates: Requirements 5.1, 5.2**

### Property 6: Alert Severity Ordering
**For any** alert list returned by ThresholdManager.evaluate(), alerts SHALL be sorted by severity in descending order (critical > warning > info).

**Validates: Requirements 5.3**

---

## 6. Testing Strategy

### Unit Tests (tests/simulator/test_analytics.py)

- **MetricsAnalyzer**: IQR detection, Z-score detection, LOF, handling edge cases (small N, NaN, inf)
- **DegradationForecaster**: ARIMA fitting, fallback to exponential smoothing, result structure
- **ThresholdManager**: threshold configuration, evaluation, alert aggregation

### Property-Based Tests (tests/simulator/test_pbt.py)

- **Hypothesis strategies**: variant generation, metric generation, perturbation generation
- **Properties**: round-trip, bounds, determinism, no-crashes

### Integration Tests

- **End-to-end**: MetricsCollector → MetricsAnalyzer → alerts → ReportingEngine
- **Real-time evaluation**: threshold evaluation during session

---

## 7. Dependencies

- `scikit-learn`: LocalOutlierFactor (LOF)
- `statsmodels`: ARIMA
- `hypothesis`: Property-based testing
- `numpy`, `pandas`: Existing (Phase 1-5)

---

## 8. Backward Compatibility

- **No changes** to Phase 1-5 APIs (GameStateManager, MetricsCollector, VariantExecutor, BotIntegrationLayer)
- **New modules only** in `mvp/simulator/pbt/` and `mvp/simulator/analytics/`
- **Existing ReportingEngine** extended with new sections (no breaking changes)
- **Existing tests** continue to pass without modification

