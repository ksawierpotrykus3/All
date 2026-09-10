"""
Real-time Metrics Dashboard for Simulator.
Displays accuracy gauge, latency meter, CPU monitor, state indicator.
"""
import tkinter as tk
from tkinter import ttk
from typing import Dict, Any, Optional
from queue import Queue, Empty
import logging

logger = logging.getLogger(__name__)


class MetricsDashboard:
    """
    Real-time metrics dashboard widget.
    Displays gauges and meters for current simulation metrics.
    """

    def __init__(self, parent: tk.Widget, width: int = 400, height: int = 200):
        """
        Initialize MetricsDashboard.

        Args:
            parent: Parent Tkinter widget
            width: Dashboard width
            height: Dashboard height
        """
        self.parent = parent
        self.width = width
        self.height = height
        
        # Current metric values
        self.current_metrics: Dict[str, Any] = {
            'accuracy': 0,
            'latency_ms': 0,
            'cpu_percent': 0,
            'state': 'CHAT',
            'variant': 'default',
            'cps': 0,
            'system_load': 0,
        }
        
        # Create dashboard frame
        self.frame = ttk.Frame(parent)
        self.frame.pack(fill=tk.BOTH, expand=True)
        
        # Create metric widgets
        self._create_accuracy_gauge()
        self._create_latency_meter()
        self._create_cpu_monitor()
        self._create_state_indicator()
        self._create_variant_display()
        self._create_cps_display()
        self._create_load_display()

    def _create_accuracy_gauge(self) -> None:
        """Create accuracy gauge display."""
        gauge_frame = ttk.LabelFrame(self.frame, text='Accuracy', padding=5)
        gauge_frame.pack(fill=tk.X, pady=3)
        
        self.accuracy_gauge = tk.Label(
            gauge_frame, text='0.0%', fg='#4caf50',
            font=('Courier', 16, 'bold'), anchor=tk.W
        )
        self.accuracy_gauge.pack(side=tk.LEFT, padx=10)
        
        # Accuracy bar
        self.accuracy_bar = ttk.Progressbar(
            gauge_frame, length=200, maximum=100, mode='determinate'
        )
        self.accuracy_bar.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

    def _create_latency_meter(self) -> None:
        """Create latency meter display."""
        latency_frame = ttk.LabelFrame(self.frame, text='Latency (ms)', padding=5)
        latency_frame.pack(fill=tk.X, pady=3)
        
        self.latency_meter = tk.Label(
            latency_frame, text='0.0 ms', fg='#4caf50',
            font=('Courier', 14, 'bold'), anchor=tk.W
        )
        self.latency_meter.pack(side=tk.LEFT, padx=10)
        
        # Latency bar (max 200ms)
        self.latency_bar = ttk.Progressbar(
            latency_frame, length=200, maximum=200, mode='determinate'
        )
        self.latency_bar.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

    def _create_cpu_monitor(self) -> None:
        """Create CPU monitor display."""
        cpu_frame = ttk.LabelFrame(self.frame, text='CPU (%)', padding=5)
        cpu_frame.pack(fill=tk.X, pady=3)
        
        self.cpu_monitor = tk.Label(
            cpu_frame, text='0 %', fg='#4caf50',
            font=('Courier', 14, 'bold'), anchor=tk.W
        )
        self.cpu_monitor.pack(side=tk.LEFT, padx=10)
        
        # CPU bar (max 100%)
        self.cpu_bar = ttk.Progressbar(
            cpu_frame, length=200, maximum=100, mode='determinate'
        )
        self.cpu_bar.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

    def _create_state_indicator(self) -> None:
        """Create state indicator display."""
        state_frame = ttk.LabelFrame(self.frame, text='State', padding=5)
        state_frame.pack(fill=tk.X, pady=3)
        
        self.state_indicator = tk.Label(
            state_frame, text='CHAT', fg='#2e7d32',
            font=('Courier', 12, 'bold'), anchor=tk.W, width=20
        )
        self.state_indicator.pack(side=tk.LEFT, padx=10)

    def _create_variant_display(self) -> None:
        """Create variant display."""
        variant_frame = ttk.LabelFrame(self.frame, text='Variant', padding=5)
        variant_frame.pack(fill=tk.X, pady=3)
        
        self.variant_display = tk.Label(
            variant_frame, text='default', fg='#666',
            font=('Courier', 10), anchor=tk.W, width=20
        )
        self.variant_display.pack(side=tk.LEFT, padx=10)

    def _create_cps_display(self) -> None:
        """Create CPS display."""
        cps_frame = ttk.LabelFrame(self.frame, text='CPS', padding=5)
        cps_frame.pack(fill=tk.X, pady=3)
        
        self.cps_display = tk.Label(
            cps_frame, text='0 CPS', fg='#1976d2',
            font=('Courier', 12, 'bold'), anchor=tk.W, width=20
        )
        self.cps_display.pack(side=tk.LEFT, padx=10)

    def _create_load_display(self) -> None:
        """Create system load display."""
        load_frame = ttk.LabelFrame(self.frame, text='System Load', padding=5)
        load_frame.pack(fill=tk.X, pady=3)
        
        self.load_display = tk.Label(
            load_frame, text='0.0 %', fg='#ff9800',
            font=('Courier', 12, 'bold'), anchor=tk.W, width=20
        )
        self.load_display.pack(side=tk.LEFT, padx=10)

    def render_accuracy_gauge(self, value: float) -> bool:
        """
        Render accuracy gauge.

        Args:
            value: Accuracy percentage (0-100)

        Returns:
            True if successful
        """
        try:
            clamped = max(0, min(100, value))
            self.accuracy_gauge.config(text=f'{clamped:.1f}%')
            
            # Try to set progress bar if it exists and has set method
            try:
                if hasattr(self, 'accuracy_bar') and hasattr(self.accuracy_bar, 'set'):
                    self.accuracy_bar.set(clamped)
            except Exception:
                pass  # Skip progress bar update if not available
            
            # Color based on accuracy
            if clamped >= 80:
                color = '#4caf50'  # Green
            elif clamped >= 60:
                color = '#fdd835'  # Yellow
            else:
                color = '#f44336'  # Red
            self.accuracy_gauge.config(fg=color)
            
            return True
        except Exception as e:
            logger.error(f"Error rendering accuracy gauge: {e}")
            return False

    def render_latency_meter(self, value_ms: float) -> bool:
        """
        Render latency meter.

        Args:
            value_ms: Latency in milliseconds

        Returns:
            True if successful
        """
        try:
            clamped = max(0, min(200, value_ms))
            self.latency_meter.config(text=f'{clamped:.1f} ms')
            
            # Try to set progress bar if it exists and has set method
            try:
                if hasattr(self, 'latency_bar') and hasattr(self.latency_bar, 'set'):
                    self.latency_bar.set(clamped)
            except Exception:
                pass  # Skip progress bar update if not available
            
            # Color based on latency thresholds
            # green <100ms, yellow 100-500ms, red >500ms
            if clamped < 100:
                color = '#4caf50'  # Green
            elif clamped <= 500:
                color = '#fdd835'  # Yellow
            else:
                color = '#f44336'  # Red
            self.latency_meter.config(fg=color)
            
            return True
        except Exception as e:
            logger.error(f"Error rendering latency meter: {e}")
            return False

    def render_cpu_monitor(self, value_percent: float) -> bool:
        """
        Render CPU monitor.

        Args:
            value_percent: CPU usage percentage (0-100)

        Returns:
            True if successful
        """
        try:
            clamped = max(0, min(100, value_percent))
            self.cpu_monitor.config(text=f'{clamped:.0f} %')
            
            # Try to set progress bar if it exists and has set method
            try:
                if hasattr(self, 'cpu_bar') and hasattr(self.cpu_bar, 'set'):
                    self.cpu_bar.set(clamped)
            except Exception:
                pass  # Skip progress bar update if not available
            
            # Color based on CPU thresholds
            # green <50%, yellow 50-75%, red >75%
            if clamped < 50:
                color = '#4caf50'  # Green
            elif clamped <= 75:
                color = '#fdd835'  # Yellow
            else:
                color = '#f44336'  # Red
            self.cpu_monitor.config(fg=color)
            
            return True
        except Exception as e:
            logger.error(f"Error rendering CPU monitor: {e}")
            return False

    def update_metrics(self, metrics: Dict[str, Any]) -> bool:
        """
        Update all metrics from dictionary.

        Args:
            metrics: Dictionary with metric values

        Returns:
            True if successful
        """
        try:
            if 'accuracy' in metrics:
                self.current_metrics['accuracy'] = metrics['accuracy']
                self.render_accuracy_gauge(metrics['accuracy'])
            
            if 'latency_ms' in metrics:
                self.current_metrics['latency_ms'] = metrics['latency_ms']
                self.render_latency_meter(metrics['latency_ms'])
            
            if 'cpu_percent' in metrics:
                self.current_metrics['cpu_percent'] = metrics['cpu_percent']
                self.render_cpu_monitor(metrics['cpu_percent'])
            
            if 'state' in metrics:
                self.current_metrics['state'] = metrics['state']
                self.state_indicator.config(text=str(metrics['state']))
            
            return True
        except Exception as e:
            logger.error(f"Error updating metrics: {e}")
            return False

    def get_current_metric(self, metric_name: str) -> Optional[Any]:
        """
        Get current value of a metric.

        Args:
            metric_name: Name of metric

        Returns:
            Metric value or None if not found
        """
        return self.current_metrics.get(metric_name)

    def set_variant(self, variant_name: str) -> bool:
        """
        Set variant display.

        Args:
            variant_name: Variant name

        Returns:
            True if successful
        """
        try:
            self.current_metrics['variant'] = variant_name
            self.variant_display.config(text=variant_name)
            return True
        except Exception as e:
            logger.error(f"Error setting variant: {e}")
            return False

    def set_cps(self, cps_value: float) -> bool:
        """
        Set CPS display.

        Args:
            cps_value: Clicks per second

        Returns:
            True if successful
        """
        try:
            self.current_metrics['cps'] = cps_value
            self.cps_display.config(text=f'{cps_value:.1f} CPS')
            return True
        except Exception as e:
            logger.error(f"Error setting CPS: {e}")
            return False

    def set_load(self, load_value: float) -> bool:
        """
        Set system load display.

        Args:
            load_value: System load percentage (0-100%)

        Returns:
            True if successful
        """
        try:
            clamped = max(0, min(100, load_value))
            self.current_metrics['system_load'] = clamped
            self.load_display.config(text=f'{clamped:.1f} %')
            
            # Color based on load thresholds
            # green <50%, yellow 50-75%, red >75%
            if clamped < 50:
                color = '#4caf50'  # Green
            elif clamped <= 75:
                color = '#fdd835'  # Yellow
            else:
                color = '#f44336'  # Red
            self.load_display.config(fg=color)
            
            return True
        except Exception as e:
            logger.error(f"Error setting load: {e}")
            return False

    def process_queue(self, metrics_queue: Queue) -> bool:
        """
        Process all pending metrics from queue in non-blocking mode.

        Drains all pending metrics from queue and updates dashboard.
        Uses Queue.get_nowait() for non-blocking reads with graceful
        handling of Queue.Empty exceptions.

        Args:
            metrics_queue: Thread-safe queue containing metrics dictionaries

        Returns:
            True if at least one metric was processed, False otherwise
        """
        try:
            processed = False
            while True:
                try:
                    # Non-blocking read: raises Queue.Empty if queue is empty
                    metrics = metrics_queue.get_nowait()
                    
                    # Update dashboard with metrics
                    if isinstance(metrics, dict):
                        self.update_metrics(metrics)
                        
                        # Handle system_load separately if present
                        if 'system_load' in metrics:
                            self.set_load(metrics['system_load'])
                        
                        processed = True
                except Empty:
                    # Queue is empty, stop processing
                    break
            
            return processed
        except Exception as e:
            logger.warning(f'Error processing metrics queue: {e}')
            return False


__all__ = ['MetricsDashboard']
