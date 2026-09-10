"""Click handler with timing and validation utilities"""

from dataclasses import dataclass
from typing import Tuple, List
import time


@dataclass
class ClickEvent:
    """Record of a click event with timing"""
    x: int
    y: int
    timestamp: float
    button: str = "left"


class ClickHandler:
    """Handles click input with timing validation"""
    
    MIN_CLICK_INTERVAL = 0.026  # 26ms = 38 CPS max
    
    def __init__(self):
        self.clicks: List[ClickEvent] = []
        self.last_click_time: float = 0.0
    
    def record_click(self, x: int, y: int, button: str = "left") -> Tuple[bool, str]:
        """
        Record a click with timing validation.
        Returns (success, message)
        """
        current_time = time.time()
        
        # Check if respecting minimum click interval
        if self.last_click_time > 0:
            interval = current_time - self.last_click_time
            if interval < self.MIN_CLICK_INTERVAL:
                return False, f"Click interval {interval:.3f}s below minimum {self.MIN_CLICK_INTERVAL}s"
        
        click = ClickEvent(x=x, y=y, timestamp=current_time, button=button)
        self.clicks.append(click)
        self.last_click_time = current_time
        
        return True, "Click recorded"
    
    def get_click_rate(self) -> float:
        """Calculate clicks per second from recorded clicks"""
        if len(self.clicks) < 2:
            return 0.0
        
        time_span = self.clicks[-1].timestamp - self.clicks[0].timestamp
        if time_span == 0:
            return 0.0
        
        return (len(self.clicks) - 1) / time_span
    
    def reset(self) -> None:
        """Reset click recording"""
        self.clicks.clear()
        self.last_click_time = 0.0
