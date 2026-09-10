"""Degradation forecasting with ARIMA."""
import logging
import numpy as np


def get_logger(name):
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


class DegradationForecaster:
    """Forecast metric degradation using ARIMA."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
    def forecast(self, metric_name, values, periods=10):
        """ARIMA forecasting with fallback to exponential smoothing."""
        if len(values) < 10:
            self.logger.warning(f"Forecast: only {len(values)} samples (min 10)")
            return None
        
        clean_values = [v for v in values if np.isfinite(v)]
        if len(clean_values) < 10:
            return None
        
        current_value = clean_values[-1]
        
        try:
            from statsmodels.tsa.arima.model import ARIMA
            try:
                model = ARIMA(clean_values, order=(1, 1, 1))
                result = model.fit()
            except:
                model = ARIMA(clean_values, order=(0, 1, 0))
                result = model.fit()
            
            forecast_obj = result.get_forecast(steps=periods)
            forecast_vals = forecast_obj.predicted_mean.tolist()
            ci = forecast_obj.conf_int(alpha=0.05)
            lower_ci = ci.iloc[:, 0].tolist()
            upper_ci = ci.iloc[:, 1].tolist()
            method = "arima"
        except Exception as e:
            self.logger.warning(f"ARIMA failed: {e}. Using exponential smoothing.")
            alpha = 0.3
            forecast_vals = []
            last_val = clean_values[-1]
            for _ in range(periods):
                last_val = alpha * last_val + (1 - alpha) * np.mean(clean_values)
                forecast_vals.append(last_val)
            residuals_std = np.std(np.diff(clean_values))
            lower_ci = [v - 1.96 * residuals_std for v in forecast_vals]
            upper_ci = [v + 1.96 * residuals_std for v in forecast_vals]
            method = "exponential_smoothing"
        
        forecast_mean = np.mean(forecast_vals)
        degradation_trend = forecast_mean < current_value
        degradation_rate_pct = (forecast_mean - current_value) / current_value * 100 if degradation_trend else 0.0
        
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
