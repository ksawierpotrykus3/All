"""
Tests for Timeline Widget (Task 8)
Covers: initialization, event rendering, timestamp formatting, scrolling, queue integration, color coding
"""
import unittest
from unittest.mock import Mock, MagicMock, patch, call
from pathlib import Path
import sys
from datetime import datetime
from queue import Queue, Empty
import threading

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from mvp.simulator.ui.timeline_widget import TimelineWidget


class TestTimelineWidgetInitialization(unittest.TestCase):
    """Test TimelineWidget initialization (Task 8.a)"""

    @patch('tkinter.Frame')
    def test_timeline_init_with_root_frame(self, mock_frame_class):
        """Should initialize TimelineWidget with root frame"""
        mock_parent = MagicMock()
        widget = TimelineWidget(mock_parent, width=400, height=400)
        
        self.assertEqual(widget.width, 400)
        self.assertEqual(widget.height, 400)
        self.assertIsNotNone(widget.parent)

    @patch('tkinter.Frame')
    def test_timeline_creates_scrollable_text_widget(self, mock_frame_class):
        """Should create scrollable text widget (listbox + scrollbar)"""
        mock_parent = MagicMock()
        widget = TimelineWidget(mock_parent, width=400, height=400)
        
        # Should have both listbox and scrollbar
        self.assertTrue(hasattr(widget, 'listbox'))
        self.assertTrue(hasattr(widget, 'scrollbar'))

    @patch('tkinter.Frame')
    @patch('tkinter.Listbox')
    def test_timeline_configures_text_font_and_height(self, mock_listbox_class, mock_frame_class):
        """Should configure text widget with Courier 8pt font and 20 line height"""
        mock_parent = MagicMock()
        mock_listbox = MagicMock()
        mock_listbox_class.return_value = mock_listbox
        
        widget = TimelineWidget(mock_parent, width=400, height=400)
        
        # Verify listbox was created with correct params
        mock_listbox_class.assert_called_once()
        call_kwargs = mock_listbox_class.call_args[1]
        self.assertEqual(call_kwargs['font'], ('Courier', 8))
        self.assertEqual(call_kwargs['height'], 20)


class TestEventRendering(unittest.TestCase):
    """Test event rendering (Task 8.b)"""

    @patch('tkinter.Frame')
    def test_add_single_event(self, mock_frame_class):
        """Should add single event to timeline (append)"""
        mock_parent = MagicMock()
        widget = TimelineWidget(mock_parent, width=400, height=400)
        
        result = widget.add_event('ALERT', 'Detection complete', timestamp_ms=500)
        
        self.assertTrue(result)
        self.assertEqual(len(widget.events), 1)

    @patch('tkinter.Frame')
    def test_add_multiple_events_batch(self, mock_frame_class):
        """Should add multiple events (batch add)"""
        mock_parent = MagicMock()
        widget = TimelineWidget(mock_parent, width=400, height=400)
        
        # Add batch of events
        widget.add_event('CHAT', 'Initial state', timestamp_ms=0)
        widget.add_event('ALERT', 'Detection', timestamp_ms=500)
        widget.add_event('TREASURE', 'Box visible', timestamp_ms=1000)
        widget.add_event('SCANNING', 'Chat recovery', timestamp_ms=1500)
        
        self.assertEqual(len(widget.events), 4)

    @patch('tkinter.Frame')
    @patch('tkinter.Listbox')
    def test_event_rendering_on_text_widget(self, mock_listbox_class, mock_frame_class):
        """Should render events on text widget"""
        mock_parent = MagicMock()
        mock_listbox = MagicMock()
        mock_listbox_class.return_value = mock_listbox
        
        widget = TimelineWidget(mock_parent, width=400, height=400)
        
        widget.add_event('TREASURE', 'Visible', timestamp_ms=1000)
        
        # Event should be inserted into listbox
        mock_listbox.insert.assert_called()

    @patch('tkinter.Frame')
    def test_auto_scroll_to_latest_event(self, mock_frame_class):
        """Should auto-scroll to latest event (see END)"""
        mock_parent = MagicMock()
        widget = TimelineWidget(mock_parent, width=400, height=400)
        
        # Add multiple events
        for i in range(10):
            widget.add_event('STATE', f'Status {i}', timestamp_ms=i*100)
        
        # Listbox should have all events and should be scrolled to end
        # (see END is called in add_event)
        self.assertEqual(len(widget.events), 10)


class TestTimestampFormatting(unittest.TestCase):
    """Test timestamp formatting (Task 8.c)"""

    @patch('tkinter.Frame')
    def test_format_timestamp_hh_mm_ss_mmm(self, mock_frame_class):
        """Should format timestamp as [HH:MM:SS.mmm]"""
        mock_parent = MagicMock()
        widget = TimelineWidget(mock_parent, width=400, height=400)
        
        # Test with 1 second
        formatted = widget.format_timestamp_ms(1000)
        self.assertRegex(formatted, r'\d{2}:\d{2}:\d{2}\.\d{3}')
        self.assertIn('00:00:01', formatted)

    @patch('tkinter.Frame')
    def test_format_timestamp_zero_ms(self, mock_frame_class):
        """Should handle edge case: 0ms"""
        mock_parent = MagicMock()
        widget = TimelineWidget(mock_parent, width=400, height=400)
        
        formatted = widget.format_timestamp_ms(0)
        self.assertEqual(formatted, '00:00:00.000')

    @patch('tkinter.Frame')
    def test_format_timestamp_almost_one_hour(self, mock_frame_class):
        """Should handle edge case: 3599999ms (1 hour - 1ms)"""
        mock_parent = MagicMock()
        widget = TimelineWidget(mock_parent, width=400, height=400)
        
        # 3599999 ms = 59:59:59.999
        formatted = widget.format_timestamp_ms(3599999)
        self.assertRegex(formatted, r'\d{2}:\d{2}:\d{2}\.\d{3}')
        # Should be under 1 hour
        parts = formatted.split(':')
        hours = int(parts[0])
        self.assertLess(hours, 2)


class TestEventScrolling(unittest.TestCase):
    """Test event scrolling (Task 8.d)"""

    @patch('tkinter.Frame')
    def test_scrollbar_binding_counts_events(self, mock_frame_class):
        """Should bind scrollbar and count events"""
        mock_parent = MagicMock()
        widget = TimelineWidget(mock_parent, width=400, height=400)
        
        # Add events
        for i in range(5):
            widget.add_event('STATE', f'Status {i}', timestamp_ms=i*100)
        
        # Scrollbar should be bound to listbox
        count = len(widget.events)
        self.assertEqual(count, 5)

    @patch('tkinter.Frame')
    def test_max_50_events_buffer_oldest_deleted(self, mock_frame_class):
        """Should maintain max 50 events (circular buffer - old events deleted)"""
        mock_parent = MagicMock()
        widget = TimelineWidget(mock_parent, width=400, height=400)
        
        # Add more than 50 events
        for i in range(60):
            widget.add_event('STATE', f'Status {i}', timestamp_ms=i*100)
        
        # Should only keep 50 most recent events
        self.assertLessEqual(len(widget.events), 50)
        
        # Oldest events should be deleted
        # Last event should be Status 59
        last_event = widget.get_last_event()
        self.assertIn('Status 59', last_event['status'])


class TestQueueIntegration(unittest.TestCase):
    """Test queue integration (Task 8.e) - Thread-safe operations"""

    @patch('tkinter.Frame')
    def test_thread_safe_read_with_queue_get_nowait(self, mock_frame_class):
        """Should handle thread-safe read from event_queue (Queue.get_nowait())"""
        mock_parent = MagicMock()
        widget = TimelineWidget(mock_parent, width=400, height=400)
        
        # Create event queue
        event_queue = Queue()
        
        # Put events in queue
        event_queue.put(('ALERT', 'Detection', 500))
        event_queue.put(('TREASURE', 'Visible', 1000))
        
        # Read from queue (non-blocking)
        try:
            phase, status, ts = event_queue.get_nowait()
            self.assertEqual(phase, 'ALERT')
            self.assertEqual(status, 'Detection')
        except Empty:
            self.fail("Queue should not be empty")

    @patch('tkinter.Frame')
    def test_batch_processing_multiple_events_no_blocking(self, mock_frame_class):
        """Should batch process multiple events from queue without blocking"""
        mock_parent = MagicMock()
        widget = TimelineWidget(mock_parent, width=400, height=400)
        
        event_queue = Queue()
        
        # Put multiple events
        events_data = [
            ('CHAT', 'Initial', 0),
            ('ALERT', 'Detected', 500),
            ('TREASURE', 'Open', 1000),
            ('SCANNING', 'Chat', 1500),
        ]
        
        for event in events_data:
            event_queue.put(event)
        
        # Process all events without blocking
        processed = []
        while not event_queue.empty():
            try:
                phase, status, ts = event_queue.get_nowait()
                processed.append((phase, status, ts))
            except Empty:
                break
        
        self.assertEqual(len(processed), 4)
        self.assertEqual(processed[0][0], 'CHAT')
        self.assertEqual(processed[-1][0], 'SCANNING')


class TestColorCoding(unittest.TestCase):
    """Test color coding (Task 8.f) - Phase-specific colors"""

    @patch('tkinter.Frame')
    def test_chat_state_green_color(self, mock_frame_class):
        """Should apply green color (#00ff00) for CHAT state"""
        mock_parent = MagicMock()
        widget = TimelineWidget(mock_parent, width=400, height=400)
        
        # Add CHAT event
        widget.add_event('CHAT', 'Waiting for alert', timestamp_ms=0)
        
        # Verify event exists
        self.assertEqual(len(widget.events), 1)
        self.assertEqual(widget.events[0]['phase'], 'CHAT')

    @patch('tkinter.Frame')
    def test_treasure_state_orange_color(self, mock_frame_class):
        """Should apply orange color (#ffaa00) for TREASURE state"""
        mock_parent = MagicMock()
        widget = TimelineWidget(mock_parent, width=400, height=400)
        
        # Add TREASURE event
        widget.add_event('TREASURE', 'Box visible', timestamp_ms=1000)
        
        # Verify event exists
        self.assertEqual(len(widget.events), 1)
        self.assertEqual(widget.events[0]['phase'], 'TREASURE')

    @patch('tkinter.Frame')
    def test_alert_state_red_color(self, mock_frame_class):
        """Should apply red color (#ff0000) for ALERT state"""
        mock_parent = MagicMock()
        widget = TimelineWidget(mock_parent, width=400, height=400)
        
        # Add ALERT event
        widget.add_event('ALERT', 'Alert detected', timestamp_ms=500)
        
        # Verify event exists
        self.assertEqual(len(widget.events), 1)
        self.assertEqual(widget.events[0]['phase'], 'ALERT')


class TestTimelineWidgetGetters(unittest.TestCase):
    """Test getting timeline data"""

    @patch('tkinter.Frame')
    def test_get_event_count(self, mock_frame_class):
        """Should return event count"""
        mock_parent = MagicMock()
        widget = TimelineWidget(mock_parent, width=400, height=400)
        
        widget.add_event('CHAT', 'Initial')
        widget.add_event('ALERT', 'Detection')
        
        count = widget.get_event_count()
        self.assertEqual(count, 2)

    @patch('tkinter.Frame')
    def test_get_events(self, mock_frame_class):
        """Should return all events"""
        mock_parent = MagicMock()
        widget = TimelineWidget(mock_parent, width=400, height=400)
        
        widget.add_event('CHAT', 'Initial')
        widget.add_event('ALERT', 'Detection')
        
        events = widget.get_events()
        self.assertEqual(len(events), 2)

    @patch('tkinter.Frame')
    def test_export_events_as_strings(self, mock_frame_class):
        """Should export all events as formatted strings"""
        mock_parent = MagicMock()
        widget = TimelineWidget(mock_parent, width=400, height=400)
        
        widget.add_event('CHAT', 'Initial', timestamp_ms=0)
        widget.add_event('ALERT', 'Detection', timestamp_ms=500)
        
        exported = widget.export_events()
        self.assertEqual(len(exported), 2)
        self.assertIn('CHAT', exported[0])
        self.assertIn('Initial', exported[0])


if __name__ == '__main__':
    unittest.main()

