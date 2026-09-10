"""
Timeline Widget for displaying phase events.
Shows scrollable list of events with timestamps and phase indicators.
"""
import tkinter as tk
from tkinter import ttk
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class TimelineWidget:
    """
    Timeline widget for displaying simulation events.
    Each event shows: [HH:MM:SS.mmm] Phase -> Status
    """

    def __init__(self, parent: tk.Widget, width: int = 400, height: int = 400):
        """
        Initialize TimelineWidget.

        Args:
            parent: Parent Tkinter widget
            width: Widget width
            height: Widget height
        """
        self.parent = parent
        self.width = width
        self.height = height
        
        # Event storage with max 50 events (circular buffer)
        self.events: List[Dict[str, Any]] = []
        self.max_events = 50
        
        # Color mapping for phases
        self.phase_colors = {
            'CHAT': '#00ff00',      # Green
            'TREASURE': '#ffaa00',  # Orange
            'ALERT': '#ff0000',     # Red
        }
        
        # Create frame
        self.frame = ttk.Frame(parent)
        self.frame.pack(fill=tk.BOTH, expand=True)
        
        # Create scrollbar
        self.scrollbar = ttk.Scrollbar(self.frame)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Create listbox
        self.listbox = tk.Listbox(
            self.frame,
            bg='#2e2e2e', fg='#aaa',
            font=('Courier', 8),
            yscrollcommand=self.scrollbar.set,
            height=20
        )
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.config(command=self.listbox.yview)
        
        # Configure color tags in listbox
        self._configure_tags()

    def _configure_tags(self) -> None:
        """Configure color tags for different phases."""
        # Note: Listbox doesn't support tags like Text widget does
        # This is a placeholder for future enhancement with Text widget
        pass


    def format_timestamp_ms(self, timestamp_ms: int) -> str:
        """
        Format milliseconds to HH:MM:SS.mmm.

        Args:
            timestamp_ms: Milliseconds

        Returns:
            Formatted timestamp string
        """
        total_seconds = timestamp_ms // 1000
        milliseconds = timestamp_ms % 1000
        
        hours = total_seconds // 3600
        remaining = total_seconds % 3600
        minutes = remaining // 60
        seconds = remaining % 60
        
        return f'{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}'

    def format_event(self, phase: str, status: str, timestamp_ms: int = 0) -> str:
        """
        Format event as [timestamp] phase -> status.

        Args:
            phase: Phase name
            status: Status description
            timestamp_ms: Event timestamp

        Returns:
            Formatted event string
        """
        timestamp_str = self.format_timestamp_ms(timestamp_ms)
        return f'[{timestamp_str}] {phase} -> {status}'

    def add_event(self, phase: str, status: str, timestamp_ms: Optional[int] = None) -> bool:
        """
        Add event to timeline.
        Maintains max 50 events (circular buffer - oldest deleted when exceeded).

        Args:
            phase: Phase name (e.g., 'CHAT', 'ALERT', 'TREASURE')
            status: Status description
            timestamp_ms: Optional timestamp (default: 0)

        Returns:
            True if successful
        """
        try:
            if timestamp_ms is None:
                timestamp_ms = 0
            
            # Format event string
            event_str = self.format_event(phase, status, timestamp_ms)
            
            # If we've reached max events, remove oldest
            if len(self.events) >= self.max_events:
                self.events.pop(0)
                self.listbox.delete(0)
            
            # Add to listbox
            self.listbox.insert(tk.END, event_str)
            
            # Store event
            event_data = {
                'phase': phase,
                'status': status,
                'timestamp_ms': timestamp_ms,
                'formatted': event_str,
            }
            self.events.append(event_data)
            
            # Auto-scroll to end
            self.listbox.see(tk.END)
            
            logger.debug(f'Timeline event added: {event_str}')
            return True
        except Exception as e:
            logger.error(f"Error adding timeline event: {e}")
            return False

    def clear(self) -> bool:
        """
        Clear all timeline events.

        Returns:
            True if successful
        """
        try:
            self.listbox.delete(0, tk.END)
            self.events.clear()
            logger.debug('Timeline cleared')
            return True
        except Exception as e:
            logger.error(f"Error clearing timeline: {e}")
            return False

    def get_event_count(self) -> int:
        """Get number of events in timeline."""
        return len(self.events)

    def get_events(self) -> List[Dict[str, Any]]:
        """Get all events."""
        return self.events.copy()

    def get_last_event(self) -> Optional[Dict[str, Any]]:
        """Get last event added."""
        if self.events:
            return self.events[-1]
        return None

    def remove_last_event(self) -> bool:
        """Remove last event from timeline."""
        try:
            if self.events:
                self.events.pop()
                self.listbox.delete(tk.END - 1)
                return True
            return False
        except Exception as e:
            logger.error(f"Error removing event: {e}")
            return False

    def export_events(self) -> List[str]:
        """
        Export all events as formatted strings.

        Returns:
            List of event strings
        """
        return [event['formatted'] for event in self.events]


__all__ = ['TimelineWidget']
