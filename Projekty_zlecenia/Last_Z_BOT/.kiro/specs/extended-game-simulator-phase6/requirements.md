# Phase 6: Advanced Analytics & ML — Requirements Document

**Data:** Luty 2027  
**Status:** Requirements Complete  
**Zakres:** Property-Based Testing (PBT), Advanced Anomaly Detection, Predictive Degradation, Statistical Comparisons

---

## 1. Wprowadzenie

Phase 6 rozszerza simulator o zaawansowaną analitykę bazującą na statystyce i machine learning. Framework Phase 1-5 zbiera bogate dane (accuracy, latency, CPU, memory); Phase 6 je **analizuje**, **detektuje anomalie** i **prognozuje degradację**.

**Decyzje z Clarify Phase:**
- **Metryki**: Accuracy & Latency (focus)
- **Anomaly Detection**: Multivariate LOF (Local Outlier Factor)
- **Forecasting**: ARIMA (AutoRegressive Integrated Moving Average)
- **Scope**: Core MVP (bez A/B testing, bez Bayesian learning)

---

## 2. Glossary

- **Metric**: Zmierzona wielkość z pojedynczej iteracji (accuracy, latency w ms)
- **Aggregation**: Zbiorowe statystyki z wielu iteracji (mean, std, min, max)
- **Anomaly**: Punkt danych znacznie odbiegający od normy (detekcja przez IQR, Z-score, LOF)
- **Outlier**: Synonim anomalii (używamy wymiennie)
- **Degradation**: Trend pogorszenia się metryk w czasie (forecast przez ARIMA)
- **LOF (Local Outlier Factor)**: Multivariate anomaly detection — bierze pod uwagę gęstość lokalnego sąsiedztwa
- **IQR (Interquartile Range)**: Univariate outlier detection — Q1, Q3, IQR = Q3 - Q1
- **Z-score**: Univariate outlier detection — (value - mean) / std, |z| > 3 = outlier
- **ARIMA**: AutoRegressive Integrated Moving Average — model do forecasting time-series
- **Property-Based Testing (PBT)**: Test generator'ów scenariuszy używając hypothesis framework
- **Threshold**: Wartość progowa dla alerty (e.g., accuracy < 70% = alert)

---

## 3. Wymagania

### Requirement 1: Property-Based Testing Framework

**User Story:** Jako developer, chcę generować randomowe scenariusze testowe (warianty, iteracje, perturbacje), żeby automatycznie znaleźć edge case'y gdzie simulator fails.

#### Acceptance Criteria

1. WHEN PBT suite runs THEN THE PBT Generator SHALL produce randomized variant combinations (chat_cleanliness, cpu_load, alert_timing, cps, eye_tracking) with Hypothesis strategy
   - Each property test runs minimum 100 iterations
   - Property test validates invariant across all generated combinations

2. WHERE PBT tests focus on metrics aggregation, THEN THE PBT Generator SHALL validate round-trip properties:
   - For any valid metric set, aggregating then re-aggregating should produce identical results
   - For any valid accuracy count and total, accuracy percentage should stay between 0-100%

3. WHEN iterating through variant space THEN THE PBT Generator SHALL ensure no edge variants crash simulator or produce invalid metrics (latency < 0, accuracy > 100%, NaN values)

4. WHERE custom perturbations are injected THEN THE PBT Framework SHALL validate simulator state remains consistent after perturbation (state machine doesn't deadlock, metrics don't overflow)

---

### Requirement 2: Univariate Anomaly Detection (IQR + Z-score)

**User Story:** Jako analyst, chcę identyfikować pojedyncze sesje z anomalną accuracy lub latency, żeby szybko znaleźć problemy (np. CPU spike, bot failure).

#### Acceptance Criteria

1. WHEN MetricsAnalyzer.detect_univariate_anomalies(metric_name) runs THEN THE MetricsAnalyzer SHALL:
   - Compute Q1, Q3, IQR for metric values
   - Flag points where value < Q1 - 1.5*IQR OR value > Q3 + 1.5*IQR as IQR anomalies
   - Flag points where |Z-score| > 3 as Z-score anomalies
   - Return list of (iteration_index, value, anomaly_type, severity)

2. WHEN anomalies are detected THEN THE MetricsAnalyzer SHALL assign severity:
   - IQR-only: severity = "medium"
   - Z-score-only: severity = "high"
   - Both IQR AND Z-score: severity = "critical"

3. WHEN fewer than 5 data points exist THEN THE MetricsAnalyzer SHALL skip anomaly detection for that metric and return empty list (avoid false positives on small datasets)

4. WHERE metric contains NaN or infinite values THEN THE MetricsAnalyzer SHALL filter them out before detection, log warning

---

### Requirement 3: Multivariate Anomaly Detection (LOF)

**User Story:** Jako performance analyst, chcę znaleźć sesje gdzie kombinacja metryk (accuracy + latency) jest anomalna, nawet jeśli każda z osobna wygląda ok.

#### Acceptance Criteria

1. WHEN MetricsAnalyzer.detect_multivariate_anomalies() runs THEN THE MetricsAnalyzer SHALL:
   - Prepare 2D feature matrix: [accuracy, latency] per iteration
   - Apply LOF (Local Outlier Factor) with k-neighbors = min(5, N-1) where N = number of samples
   - LOF scores > 1.3 = anomaly (threshold based on common practice)
   - Return list of (iteration_index, features, lof_score, is_anomaly)

2. WHEN LOF detects anomaly THEN THE MetricsAnalyzer SHALL annotate context:
   - Variant config active in that iteration
   - Neighboring iterations' LOF scores (context)
   - Severity based on LOF score: 1.3-1.5 = "medium", 1.5+ = "high"

3. WHEN fewer than 5 samples exist THEN THE MetricsAnalyzer SHALL skip LOF (requires neighbor density estimation) and log warning

4. WHERE LOF model is trained THEN THE MetricsAnalyzer SHALL be thread-safe for concurrent metric collection + anomaly detection

---

### Requirement 4: Predictive Degradation (ARIMA Forecasting)

**User Story:** Jako DevOps, chcę prognozować czy accuracy/latency będzie się pogorszać w ciągu kolejnych 10 iteracji, żeby proaktywnie reagować.

#### Acceptance Criteria

1. WHEN DegradationForecaster.forecast(metric_name, periods=10) runs THEN THE DegradationForecaster SHALL:
   - Fit ARIMA(p,d,q) model to historical metric values (auto-select p, d, q or use defaults)
   - Generate point forecast for next `periods` iterations
   - Return (forecast_values, confidence_interval_lower, confidence_interval_upper)
   - Confidence interval = 95%

2. WHEN forecast detects downward trend (forecast_mean < current_value) THEN THE DegradationForecaster SHALL:
   - Flag "degradation_trend" = True
   - Compute slope (forecast_mean - current_value) / periods
   - Return degradation_rate as percentage per iteration

3. WHEN fewer than 10 historical points exist THEN THE DegradationForecaster SHALL return None (ARIMA needs enough history) and log warning

4. WHERE ARIMA fails to converge THEN THE DegradationForecaster SHALL fall back to exponential smoothing (simple alpha=0.3) and log fallback warning

---

### Requirement 5: Custom Threshold Engine

**User Story:** Jako DevOps, chcę ustawić thresholds (e.g., accuracy < 70% = alert) i automatycznie otrzymywać alarmy w real-time.

#### Acceptance Criteria

1. WHEN ThresholdManager.set_threshold(metric, operator, value, severity) is called THEN THE ThresholdManager SHALL:
   - Store threshold config: {"metric": "accuracy", "operator": "<", "value": 70, "severity": "critical"}
   - Validate operator ∈ {"<", ">", "<=", ">=", "==", "!="}
   - Validate metric ∈ {"accuracy", "latency", "cpu_usage"}
   - Validate severity ∈ {"info", "warning", "critical"}

2. WHEN metric value arrives (per iteration) THEN THE ThresholdManager SHALL evaluate all thresholds:
   - If accuracy < 70%, raise alert with severity "critical" and message "Accuracy below threshold"
   - Callbacks/hooks should allow UI or logging to react

3. WHEN multiple thresholds trigger simultaneously THEN THE ThresholdManager SHALL:
   - Aggregate alerts by severity (critical > warning > info)
   - Return list of (metric, triggered_value, threshold, message, severity) ordered by severity DESC

4. WHERE thresholds are configured THEN THE ReportingEngine SHALL include threshold breaches in post-session reports (e.g., "Accuracy breached 70% threshold 3 times in session")

---

### Requirement 6: Integration with Existing ReportingEngine

**User Story:** Jako data analyst, chcę widzieć anomalies, forecasts i thresholds w standardowych raportach (HTML, PNG), razem z istniejącymi heatmapami i timelinami.

#### Acceptance Criteria

1. WHEN ReportingEngine generates post-session report THEN THE ReportingEngine SHALL include new sections:
   - "Anomaly Detection Results": table of detected anomalies (iteration, metric, type, severity)
   - "Degradation Forecast": plot of historical + forecast trend (ARIMA prediction band)
   - "Threshold Breaches": timeline of threshold violations with context

2. WHEN anomalies are found THEN THE ReportingEngine SHALL:
   - Highlight anomalous iterations in existing heatmaps (red border or marker)
   - Add marker on timeline graph at anomaly iteration
   - Include iteration context (variant config, CPU state, previous/next metrics)

3. WHERE ReportingEngine creates plots THEN THE ReportingEngine SHALL use matplotlib with existing style (fonts, colors, size)

4. WHEN threshold configuration exists THEN THE ReportingEngine SHALL add threshold lines to latency/accuracy trend plots (horizontal lines at threshold values)

---

## 4. Non-Functional Requirements

### Performance
- PBT suite must complete 100 iterations in < 30 seconds (per property test)
- LOF computation for 1000 samples in < 5 seconds
- ARIMA fit + forecast (20 periods) in < 2 seconds

### Compatibility
- **Backward Compatibility**: No changes to Phase 1-5 APIs (GameStateManager, MetricsCollector, VariantExecutor, ReportingEngine)
- **New Modules Only**: All Phase 6 code in new `mvp/simulator/pbt/`, `mvp/simulator/analytics/` directories
- **Test Location**: New tests in `tests/simulator/test_pbt.py`, `test_analytics.py`

### Maintainability
- All anomaly detection and forecasting functions must include docstrings with examples
- Threshold system must be configurable via JSON or Python dict
- Logging at INFO level for major operations (anomaly found, forecast generated, threshold triggered)

---

## 5. Requirements Traceability Matrix (RTM)

| ID | Title | PBT | Anomaly (Uni) | Anomaly (Multi) | Forecast | Threshold | Reporting |
|----|-------|-----|---------------|-----------------|----------|-----------|-----------|
| 1.1 | Generate randomized scenarios | ✓ | | | | | |
| 1.2 | Round-trip property validation | ✓ | | | | | |
| 1.3 | Edge case invariants | ✓ | | | | | |
| 1.4 | Perturbation consistency | ✓ | | | | | |
| 2.1 | IQR anomaly detection | | ✓ | | | | |
| 2.2 | Z-score anomaly detection | | ✓ | | | | |
| 2.3 | Severity classification | | ✓ | | | | |
| 2.4 | Small dataset handling | | ✓ | | | | |
| 3.1 | LOF multivariate detection | | | ✓ | | | |
| 3.2 | LOF context annotation | | | ✓ | | | |
| 3.3 | LOF sample size validation | | | ✓ | | | |
| 3.4 | LOF thread safety | | | ✓ | | | |
| 4.1 | ARIMA model fitting | | | | ✓ | | |
| 4.2 | Degradation trend detection | | | | ✓ | | |
| 4.3 | ARIMA fallback | | | | ✓ | | |
| 5.1 | Threshold configuration | | | | | ✓ | |
| 5.2 | Threshold evaluation | | | | | ✓ | |
| 5.3 | Alert aggregation | | | | | ✓ | |
| 5.4 | Threshold breach logging | | | | | ✓ | |
| 6.1 | Report sections | | | | | | ✓ |
| 6.2 | Anomaly highlighting | | | | | | ✓ |
| 6.3 | Threshold visualization | | | | | | ✓ |

