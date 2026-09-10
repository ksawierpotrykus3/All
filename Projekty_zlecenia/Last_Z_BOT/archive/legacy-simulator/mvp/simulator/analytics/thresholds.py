"""Threshold management and alert evaluation."""
import logging
from datetime import datetime


def get_logger(name):
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


class ThresholdManager:
    """Manage thresholds and evaluate metrics."""
    
    def __init__(self):
        self.thresholds = []
        self.logger = get_logger(__name__)
    
    def set_threshold(self, metric, operator, value, severity):
        """Configure threshold rule."""
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
        """Evaluate all thresholds against iteration data."""
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
