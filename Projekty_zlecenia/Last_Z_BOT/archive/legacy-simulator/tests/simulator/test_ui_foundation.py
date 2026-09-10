"""
Tests for Tkinter UI Foundation (Task 6)
Test-driven: tests first, then implementation
"""
import unittest
from unittest.mock import Mock, MagicMock, patch, call
from pathlib import Path
import sys

# Ensure mvp/ is in path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from mvp.simulator.ui.interactive_ui import InteractiveUI
from mvp.simulator.ui.canvas_renderer import CanvasRenderer
from mvp.simulator.core import GameState


class TestCanvasRendererInit(unittest.TestCase):
    """Test CanvasRenderer initialization"""

    def test_canvas_renderer_init(self):
        """Should initialize CanvasRenderer with width, height, master canvas"""
        with patch('tkinter.Canvas'):
            master_canvas = MagicMock()
            renderer = CanvasRenderer(master_canvas, width=600, height=700)
            
            self.assertEqual(renderer.width, 600)
            self.assertEqual(renderer.height, 700)
            self.assertEqual(renderer.canvas, master_canvas)

    def test_canvas_renderer_create_id(self):
        """Should have a unique canvas ID"""
        with patch('tkinter.Canvas'):
            master_canvas1 = MagicMock()
            master_canvas2 = MagicMock()
            renderer1 = CanvasRenderer(master_canvas1, width=600, height=700)
            renderer2 = CanvasRenderer(master_canvas2, width=600, height=700)
            
            self.assertNotEqual(renderer1.canvas_id, renderer2.canvas_id)


class TestCanvasRendererStateVisualization(unittest.TestCase):
    """Test CanvasRenderer state visualization"""

    def setUp(self):
        with patch('tkinter.Canvas'):
            self.master_canvas = MagicMock()
            self.renderer = CanvasRenderer(self.master_canvas, width=600, height=700)

    def test_render_state_chat(self):
        """Should render CHAT state with text indicator"""
        with patch.object(self.renderer.canvas, 'create_text') as mock_text:
            self.renderer.render_state(GameState.CHAT)
            mock_text.assert_called()
            # Verify state was rendered (multiple calls for different text)
            self.assertGreater(mock_text.call_count, 1)

    def test_render_state_alert_animation(self):
        """Should render ALERT_ANIMATION state"""
        with patch.object(self.renderer.canvas, 'create_text') as mock_text:
            self.renderer.render_state(GameState.ALERT_ANIMATION)
            mock_text.assert_called()
            self.assertGreater(mock_text.call_count, 1)

    def test_render_state_treasure(self):
        """Should render TREASURE state"""
        with patch.object(self.renderer.canvas, 'create_text') as mock_text:
            self.renderer.render_state(GameState.TREASURE)
            mock_text.assert_called()
            self.assertGreater(mock_text.call_count, 1)

    def test_render_state_scanning(self):
        """Should render SCANNING state"""
        with patch.object(self.renderer.canvas, 'create_text') as mock_text:
            self.renderer.render_state(GameState.SCANNING)
            mock_text.assert_called()

    def test_render_state_clears_previous(self):
        """Should clear previous renders before new state"""
        with patch.object(self.renderer.canvas, 'delete') as mock_delete:
            self.renderer.render_state(GameState.CHAT)
            mock_delete.assert_called()

    def test_render_state_returns_bool(self):
        """Should return True on successful render"""
        result = self.renderer.render_state(GameState.CHAT)
        self.assertTrue(result)


class TestInteractiveUIInit(unittest.TestCase):
    """Test InteractiveUI initialization"""

    @patch('tkinter.Tk')
    def test_interactive_ui_init(self, mock_tk_class):
        """Should initialize InteractiveUI with Tkinter root window"""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        
        ui = InteractiveUI()
        
        self.assertIsNotNone(ui)
        self.assertEqual(ui.width, 1400)
        self.assertEqual(ui.height, 900)

    @patch('tkinter.Tk')
    def test_interactive_ui_window_title(self, mock_tk_class):
        """Should set window title"""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        
        ui = InteractiveUI()
        
        mock_root.title.assert_called()
        args = mock_root.title.call_args
        self.assertIn("Simulator", str(args))

    @patch('tkinter.Tk')
    def test_interactive_ui_geometry(self, mock_tk_class):
        """Should set window geometry to 1400x900"""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        
        ui = InteractiveUI()
        
        mock_root.geometry.assert_called_with("1400x900")


class TestInteractiveUIPanels(unittest.TestCase):
    """Test InteractiveUI panel layout"""

    @patch('tkinter.Tk')
    @patch('tkinter.Canvas')
    @patch('tkinter.Frame')
    def test_interactive_ui_has_left_panel(self, mock_frame_class, mock_canvas_class, mock_tk_class):
        """Should have left panel for game canvas"""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        
        ui = InteractiveUI()
        
        self.assertIsNotNone(ui.left_panel)

    @patch('tkinter.Tk')
    @patch('tkinter.Canvas')
    @patch('tkinter.Frame')
    def test_interactive_ui_has_right_panel(self, mock_frame_class, mock_canvas_class, mock_tk_class):
        """Should have right panel for metrics"""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        
        ui = InteractiveUI()
        
        self.assertIsNotNone(ui.right_panel)

    @patch('tkinter.Tk')
    @patch('tkinter.Canvas')
    @patch('tkinter.Frame')
    def test_interactive_ui_has_game_canvas(self, mock_frame_class, mock_canvas_class, mock_tk_class):
        """Should have game canvas in left panel (600x700)"""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        
        ui = InteractiveUI()
        
        self.assertIsNotNone(ui.game_canvas)

    @patch('tkinter.Tk')
    @patch('tkinter.Canvas')
    @patch('tkinter.Frame')
    def test_interactive_ui_has_canvas_renderer(self, mock_frame_class, mock_canvas_class, mock_tk_class):
        """Should have CanvasRenderer for game state"""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        
        ui = InteractiveUI()
        
        self.assertIsNotNone(ui.canvas_renderer)
        self.assertIsInstance(ui.canvas_renderer, CanvasRenderer)


class TestInteractiveUIRendering(unittest.TestCase):
    """Test InteractiveUI rendering methods"""

    @patch('tkinter.Tk')
    @patch('tkinter.Canvas')
    @patch('tkinter.Frame')
    def test_render_game_state(self, mock_frame_class, mock_canvas_class, mock_tk_class):
        """Should have method to render game state"""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        
        ui = InteractiveUI()
        
        self.assertTrue(hasattr(ui, 'render_game_state'))
        self.assertTrue(callable(ui.render_game_state))

    @patch('tkinter.Tk')
    @patch('tkinter.Canvas')
    @patch('tkinter.Frame')
    def test_update_metrics_display(self, mock_frame_class, mock_canvas_class, mock_tk_class):
        """Should have method to update metrics display"""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        
        ui = InteractiveUI()
        
        self.assertTrue(hasattr(ui, 'update_metrics_display'))
        self.assertTrue(callable(ui.update_metrics_display))

    @patch('tkinter.Tk')
    @patch('tkinter.Canvas')
    @patch('tkinter.Frame')
    def test_add_timeline_event(self, mock_frame_class, mock_canvas_class, mock_tk_class):
        """Should have method to add timeline event"""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        
        ui = InteractiveUI()
        
        self.assertTrue(hasattr(ui, 'add_timeline_event'))
        self.assertTrue(callable(ui.add_timeline_event))


class TestCanvasRendererUtilities(unittest.TestCase):
    """Test CanvasRenderer utility methods"""

    def setUp(self):
        with patch('tkinter.Canvas'):
            self.master_canvas = MagicMock()
            self.renderer = CanvasRenderer(self.master_canvas, width=600, height=700)

    def test_canvas_renderer_clear_all(self):
        """Should have method to clear all canvas items"""
        self.assertTrue(hasattr(self.renderer, 'clear_all'))
        self.assertTrue(callable(self.renderer.clear_all))

    def test_canvas_renderer_draw_text(self):
        """Should have method to draw text"""
        self.assertTrue(hasattr(self.renderer, 'draw_text'))
        self.assertTrue(callable(self.renderer.draw_text))

    def test_canvas_renderer_get_center(self):
        """Should calculate center coordinates"""
        center_x, center_y = self.renderer.get_center()
        self.assertEqual(center_x, 300)
        self.assertEqual(center_y, 350)


if __name__ == '__main__':
    unittest.main()
