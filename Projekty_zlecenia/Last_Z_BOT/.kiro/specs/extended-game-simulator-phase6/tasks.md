# Phase 6: Advanced Analytics & ML — Implementation Plan

**Cel:** Implementacja Property-Based Testing, Advanced Anomaly Detection (IQR+Z+LOF), Predictive Degradation (ARIMA), Custom Thresholds, Integration z ReportingEngine.

**Tech Stack:** Python 3.11, hypothesis, scikit-learn, statsmodels, numpy, pandas

**Estimated Duration:** 2-3 tygodnie (8-12 godzin dev, 8-12 godzin testing)

---

## File Structure (New Files)

```
mvp/simulator/
├── pbt/
│   ├── __init__.py
│   ├── strategies.py          # Hypothesis strategies
│   ├── properties.py          # Property tests
│   └── generator.py           # PBT runner

├── analytics/
│   ├── __init__.py
│   ├── anomaly_detection.py   # MetricsAnalyzer
│   ├── degradation_forecast.py# DegradationForecaster
│   ├── thresholds.py          # ThresholdManager
│   └── utils.py               # ML helpers

tests/simulator/
├── test_pbt.py               # PBT suite
└── test_analytics.py         # Unit tests for analytics
```

---

## Tasks

### 1. Setup Phase 6 Module Structure

- [ ] 1.1 Create directory structure: mvp/simulator/pbt/, mvp/simulator/analytics/
  - Create __init__.py files for each subpackage
  - Verify imports work: `from mvp.simulator.pbt import ...`
  - _Requirements: 1.1_

- [ ] 1.2 Create tests/simulator/test_pbt.py and test_analytics.py stubs
  - Empty test files with placeholder imports
  - Verify pytest discovery works
  - _Requirements: 1.1_

---

### 2. Implement MetricsAnalyzer (IQR + Z-score)

- [ ] 2.1 Write unit tests for univariate anomaly detection (IQR + Z-score)
  - Test IQR boundary detection (upper, lower)
  - Test Z-score > 3 detection
  - Test severity classification (medium, high, critical)
  - Test small dataset handling (< 5 samples)
  - Test NaN/inf filtering
  - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [ ] 2.2 Implement MetricsAnalyzer.detect_univariate_anomalies()
  - Compute Q1, Q3, IQR
  - Flag IQR anomalies: value < Q1 - 1.5*IQR OR value > Q3 + 1.5*IQR
  - Flag Z-score anomalies: |z| > 3
  - Classify severity (medium/high/critical)
  - Return list of AnomalyRecord
  - _Requirements: 2.1, 2.2, 2.3_

- [ ]* 2.3 Write property test for univariate anomaly detection
  - **Property 1: Anomaly Detection Round-Trip**
  - **Property 2: Accuracy Bounds Preserved**
  - **Validates: Requirements 2.1, 2.2**

---

### 3. Implement MetricsAnalyzer (LOF)

- [ ] 3.1 Write unit tests for multivariate anomaly detection (LOF)
  - Test LOF score computation
  - Test threshold > 1.3 for anomaly
  - Test small dataset handling (< 5 samples)
  - Test 2D feature matrix handling (accuracy + latency)
  - Test thread safety
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [ ] 3.2 Implement MetricsAnalyzer.detect_multivariate_anomalies()
  - Prepare 2D feature matrix [accuracy, latency]
  - Apply LocalOutlierFactor with k-neighbors = min(5, N-1)
  - Threshold: LOF > 1.3 = anomaly
  - Annotate severity: 1.3-1.5 = "medium", 1.5+ = "high"
  - Return list of MultivariateAnomalyRecord
  - _Requirements: 3.1, 3.2_

- [ ]* 3.3 Write property test for multivariate anomaly detection
  - **Property 3: LOF Requires Minimum Samples**
  - **Validates: Requirements 3.3**

---

### 4. Implement DegradationForecaster (ARIMA)

- [ ] 4.1 Write unit tests for ARIMA forecasting
  - Test ARIMA model fitting with minimum 10 samples
  - Test forecast output shape (periods=10 → 10 forecasts)
  - Test confidence intervals (lower < forecast < upper)
  - Test degradation trend detection (downward trend)
  - Test degradation_rate_pct calculation
  - Test small dataset handling (< 10 samples → None)
  - Test ARIMA failure fallback to exponential smoothing
  - _Requirements: 4.1, 4.2, 4.3_

- [ ] 4.2 Implement DegradationForecaster.forecast()
  - Accept metric values (list), periods (int)
  - Fit ARIMA(1,1,1) model (or auto-select p,d,q)
  - Generate forecast + 95% confidence intervals
  - Detect degradation: forecast_mean < current_value
  - Compute degradation_rate_pct
  - Fallback to exponential smoothing (alpha=0.3) if ARIMA fails
  - Return ForecastResult dict
  - _Requirements: 4.1, 4.2, 4.3_

- [ ]* 4.3 Write property test for degradation forecasting
  - **Property 4: Forecast Always Returns Bounded Trend**
  - **Validates: Requirements 4.1, 4.2**

---

### 5. Implement ThresholdManager

- [ ] 5.1 Write unit tests for ThresholdManager
  - Test set_threshold() validation (metric, operator, severity)
  - Test threshold evaluation with various operators (<, >, <=, >=, ==, !=)
  - Test alert aggregation by severity (critical > warning > info)
  - Test handling missing metrics in iteration_data
  - _Requirements: 5.1, 5.2, 5.3_

- [ ] 5.2 Implement ThresholdManager class
  - Implement set_threshold() with validation
  - Implement evaluate(iteration_data) with operator evaluation
  - Sort alerts by severity (critical DESC)
  - Implement _eval_operator() helper
  - Return list of AlertRecord
  - _Requirements: 5.1, 5.2, 5.3_

- [ ]* 5.3 Write property test for threshold evaluation
  - **Property 5: Threshold Evaluation is Deterministic**
  - **Property 6: Alert Severity Ordering**
  - **Validates: Requirements 5.1, 5.2, 5.3**

---

### 6. Implement PBT Framework (Hypothesis Strategies)

- [ ] 6.1 Write unit tests for Hypothesis strategies
  - Test variant_strategy() generates valid variant dicts
  - Test metric_set_strategy() generates metrics with 0 <= accuracy <= 100
  - Test perturbation_strategy() generates perturbation configs
  - _Requirements: 1.1, 1.2, 1.3_

- [ ] 6.2 Implement Hypothesis strategies (pbt/strategies.py)
  - variant_strategy(): generates {chat_state, cpu_load, alert_timing, cps, eye_tracking}
  - metric_set_strategy(): generates {accuracy: 0-100, latency > 0}
  - perturbation_strategy(): generates {type, intensity}
  - _Requirements: 1.1_

- [ ]* 6.3 Write property tests for PBT generator correctness
  - **Property 1: Metrics Aggregation Round-Trip**
  - **Validates: Requirements 1.2**

---

### 7. Implement PBT Property Tests

- [ ] 7.1 Write property tests (pbt/properties.py)
  - prop_metrics_aggregation_roundtrip: aggregate → re-aggregate = same
  - prop_accuracy_bounds: 0 <= accuracy <= 100 after any operation
  - prop_variant_consistency: variant application keeps state valid
  - prop_no_crashes_under_perturbations: random perturbations don't crash
  - _Requirements: 1.2, 1.3, 1.4_

- [ ] 7.2 Implement PBT runner (pbt/generator.py)
  - run_pbt_suite(num_iterations=100) orchestrates all property tests
  - Execute with Hypothesis @given decorator
  - Aggregate: total_tests, passed, failed, examples
  - Log results to INFO level
  - _Requirements: 1.1_

---

### 8. Checkpoint — Verify Core Analytics & PBT

- [ ] 8.1 Run all unit tests
  - `uv run pytest tests/simulator/test_analytics.py -v`
  - `uv run pytest tests/simulator/test_pbt.py -v`
  - Ensure 100% pass rate
  - _Requirements: 2.1-5.3, 1.1-1.4_

- [ ] 8.2 Run PBT suite manually
  - `python -c "from mvp.simulator.pbt import generator; generator.run_pbt_suite(100)"`
  - Verify all properties pass
  - _Requirements: 1.1-1.4_

---

### 9. Integration with MetricsCollector (Phase 1-5)

- [ ] 9.1 Write integration tests for analytics ↔ metrics flow
  - Create MetricsCollector session with 20-30 iterations
  - Feed accuracy/latency data to MetricsAnalyzer
  - Verify anomaly detection works on real data
  - _Requirements: 6.1, 6.2_

- [ ] 9.2 Add analytics methods to MetricsCollector
  - Add get_metric_history(metric_name) → list[float]
  - Expose methods for Phase 6 consumers (analyzer, forecaster)
  - Keep backward compatibility (no changes to existing methods)
  - _Requirements: 6.1_

---

### 10. Integrate with ReportingEngine

- [ ] 10.1 Write integration tests for ReportingEngine ↔ analytics
  - Create post-session report with anomaly detection section
  - Create forecast plot
  - Create threshold breach section
  - Verify plot generation (matplotlib)
  - _Requirements: 6.1, 6.2, 6.3_

- [ ] 10.2 Extend ReportingEngine with analytics sections
  - Add report_anomalies(anomalies_list) section
  - Add plot_degradation_forecast(forecast_result) plot
  - Add report_threshold_breaches(breach_list) section
  - Integrate into generate_html_report()
  - _Requirements: 6.1, 6.2, 6.3_

---

### 11. Add ML Dependencies & Utilities

- [ ] 11.1 Update pyproject.toml with new dependencies
  - Add scikit-learn (LOF)
  - Add statsmodels (ARIMA)
  - Add hypothesis (PBT, already dev-only but ensure version)
  - Update uv.lock
  - _Requirements: All_

- [ ] 11.2 Implement utils.py helpers
  - get_logger() for consistent logging
  - normalize_features() for LOF feature scaling
  - Any other shared utilities
  - _Requirements: All_

---

### 12. Final Verification & Documentation

- [ ] 12.1 Run full test suite
  - `uv run pytest tests/simulator/ -v --cov=mvp.simulator`
  - Ensure Phase 6 tests + Phase 1-5 tests still pass
  - Target: > 90% coverage for new modules
  - _Requirements: All_

- [ ] 12.2 Documentation & cleanup
  - Add docstrings to all public methods (MetricsAnalyzer, DegradationForecaster, ThresholdManager, PBT)
  - Add inline comments for complex logic (LOF, ARIMA)
  - Verify README.md mentions Phase 6 (optional, link to spec)
  - _Requirements: All_

- [ ] 12.3 Commit Phase 6 complete
  - `git add mvp/simulator/pbt/ mvp/simulator/analytics/ tests/simulator/test_pbt.py tests/simulator/test_analytics.py`
  - `git commit -m "feat: add Phase 6 — Advanced Analytics (PBT, Anomaly Detection, ARIMA, Thresholds)"`
  - _Requirements: All_

---

## Notes

- **Backward Compatibility**: All Phase 6 code is **additive only** — no changes to Phase 1-5 APIs
- **New Modules**: `mvp/simulator/pbt/` and `mvp/simulator/analytics/` are self-contained
- **Testing**: Property tests use Hypothesis with `@given` decorator (100+ iterations each)
- **Logging**: All anomaly detection, forecasting, threshold events logged at INFO level
- **Integration**: Phase 6 consumers (UI, reporting) can optionally use new analytics modules
- **Scope**: MVP = core analytics only (no A/B testing, no Bayesian learning for Phase 6)

---

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["2.1", "3.1", "4.1", "5.1", "6.1"] },
    { "id": 2, "tasks": ["2.2", "3.2", "4.2", "5.2", "6.2"] },
    { "id": 3, "tasks": ["2.3", "3.3", "4.3", "5.3", "6.3"] },
    { "id": 4, "tasks": ["7.1", "7.2"] },
    { "id": 5, "tasks": ["8.1", "8.2"] },
    { "id": 6, "tasks": ["9.1", "9.2"] },
    { "id": 7, "tasks": ["10.1", "10.2"] },
    { "id": 8, "tasks": ["11.1", "11.2"] },
    { "id": 9, "tasks": ["12.1", "12.2", "12.3"] }
  ]
}
```

