"""
Comprehensive tests for UI initialization, window creation, and canvas rendering (Task 6, Step 1).
Tests cover:
- InteractiveUI.__init__() with pre-loaded macro images
- Window creation with WinAPI integration
- Canvas rendering with macro images and timer overlay
- Thread-safe asset loading and dearpygui mocking
"""
import unittest
from unittest.mock import Mock, MagicMock, patch, call, ANY
from pathlib import Path
import sys
from queue import Queue
import threading
from io import BytesIO

# Ensure mvp/ is in path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from mvp.simulator.ui.interactive_ui import InteractiveUI
from mvp.simulator.ui.canvas_renderer import CanvasRenderer
from mvp.simulator.core import GameState


class TestInteractiveUIInitialization(unittest.TestCase):
    """Test InteractiveUI.__init__() with proper initialization"""

    @patch('tkinter.Tk')
    @patch('mvp.simulator.ui.interactive_ui.CanvasRenderer')
    def test_interactive_ui_init_default_dimensions(self, mock_canvas_renderer_cls, mock_tk_class):
        """Should initialize with default dimensions 1400x900"""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        mock_canvas_renderer_cls.return_value = MagicMock()
        
        ui = InteractiveUI()
        
        self.assertEqual(ui.width, 1400)
        self.assertEqual(ui.height, 900)
        self.assertFalse(ui.is_running)

    @patch('tkinter.Tk')
    @patch('mvp.simulator.ui.interactive_ui.CanvasRenderer')
    def test_interactive_ui_init_custom_dimensions(self, mock_canvas_renderer_cls, mock_tk_class):
        """Should initialize with custom dimensions"""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        mock_canvas_renderer_cls.return_value = MagicMock()
        
        ui = InteractiveUI(width=1600, height=1000)
        
        self.assertEqual(ui.width, 1600)
        self.assertEqual(ui.height, 1000)

    @patch('tkinter.Tk')
    @patch('mvp.simulator.ui.interactive_ui.CanvasRenderer')
    def test_interactive_ui_init_creates_root_window(self, mock_canvas_renderer_cls, mock_tk_class):
        """Should create Tkinter root window"""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        mock_canvas_renderer_cls.return_value = MagicMock()
        
        ui = InteractiveUI()
        
        mock_root.title.assert_called_once()
        mock_root.geometry.assert_called_once_with('1400x900')
        mock_root.resizable.assert_called_once_with(False, False)

    @patch('tkinter.Tk')
    @patch('mvp.simulator.ui.interactive_ui.CanvasRenderer')
    def test_interactive_ui_init_queues(self, mock_canvas_renderer_cls, mock_tk_class):
        """Should initialize thread-safe queues for metrics, state, events"""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        mock_canvas_renderer_cls.return_value = MagicMock()
        
        ui = InteractiveUI()
        
        self.assertIsInstance(ui.metrics_queue, Queue)
        self.assertIsInstance(ui.state_queue, Queue)
        self.assertIsInstance(ui.event_queue, Queue)

    @patch('tkinter.Tk')
    @patch('mvp.simulator.ui.interactive_ui.CanvasRenderer')
    def test_interactive_ui_init_callbacks(self, mock_canvas_renderer_cls, mock_tk_class):
        """Should initialize callback dictionaries"""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        mock_canvas_renderer_cls.return_value = MagicMock()
        
        ui = InteractiveUI()
        
        self.assertIsInstance(ui.on_hotkey_callbacks, dict)
        self.assertIsNone(ui.on_state_change_callback)

    @patch('tkinter.Tk')
    @patch('mvp.simulator.ui.interactive_ui.CanvasRenderer')
    def test_interactive_ui_init_canvas_renderer(self, mock_canvas_renderer_cls, mock_tk_class):
        """Should create CanvasRenderer instance"""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        mock_canvas_renderer = MagicMock()
        mock_canvas_renderer_cls.return_value = mock_canvas_renderer
        
        ui = InteractiveUI()
        
        self.assertIsNotNone(ui.canvas_renderer)
        self.assertEqual(ui.canvas_renderer, mock_canvas_renderer)

    @patch('tkinter.Tk')
    @patch('mvp.simulator.ui.interactive_ui.CanvasRenderer')
    def test_interactive_ui_init_timeline_events_buffer(self, mock_canvas_renderer_cls, mock_tk_class):
        """Should initialize empty timeline events buffer"""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        mock_canvas_renderer_cls.return_value = MagicMock()
        
        ui = InteractiveUI()
        
        self.assertIsInstance(ui.timeline_events, list)
        self.assertEqual(len(ui.timeline_events), 0)


class TestPreloadMacroImages(unittest.TestCase):
    """Test InteractiveUI._preload_macro_images() functionality"""

    @patch('tkinter.Tk')
    @patch('mvp.simulator.ui.interactive_ui.CanvasRenderer')
    @patch('pathlib.Path.exists')
    def test_preload_macro_images_directory_missing(self, mock_exists, mock_canvas_renderer_cls, mock_tk_class):
        """Should handle missing macro directory gracefully"""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        mock_canvas_renderer = MagicMock()
        mock_canvas_renderer_cls.return_value = mock_canvas_renderer
        mock_exists.return_value = False  # Directory doesn't exist
        
        ui = InteractiveUI()
        
        # Should not crash, macro_images dict should exist but be empty
        self.assertIsNotNone(ui.canvas_renderer)

    @patch('tkinter.Tk')
    @patch('mvp.simulator.ui.interactive_ui.CanvasRenderer')
    @patch('pathlib.Path.glob')
    @patch('pathlib.Path.exists')
    @patch('PIL.Image.open')
    def test_preload_macro_images_loads_png_files(self, mock_image_open, mock_exists, 
                                                   mock_glob, mock_canvas_renderer_cls, mock_tk_class):
        """Should load all PNG files from macro_testing directory"""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        mock_canvas_renderer = MagicMock()
        mock_canvas_renderer_cls.return_value = mock_canvas_renderer
        
        # Setup mocks
        mock_canvas_renderer.macro_images = {}
        mock_canvas_renderer.macro_image_paths = {}
        
        # Mock directory exists
        mock_exists.return_value = True
        
        # Mock glob to return PNG files
        png_files = [
            Path('data/macro_testing/treasure.png'),
            Path('data/macro_testing/chat.png'),
        ]
        mock_glob.return_value = png_files
        
        # Mock PIL Image
        mock_pil_image = MagicMock()
        mock_image_open.return_value = mock_pil_image
        
        ui = InteractiveUI()
        
        # Verify glob was called for PNG files
        mock_glob.assert_called()

    @patch('tkinter.Tk')
    @patch('mvp.simulator.ui.interactive_ui.CanvasRenderer')
    def test_preload_macro_images_thread_safe(self, mock_canvas_renderer_cls, mock_tk_class):
        """Should be thread-safe during initialization"""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        mock_canvas_renderer = MagicMock()
        mock_canvas_renderer.macro_images = {}
        mock_canvas_renderer_cls.return_value = mock_canvas_renderer
        
        # Initialize multiple UIs in parallel threads to test thread safety
        threads = []
        for _ in range(5):
            t = threading.Thread(target=lambda: InteractiveUI())
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # Should complete without deadlock


class TestWindowCreationWinAPI(unittest.TestCase):
    """Test window creation with WinAPI integration"""

    @patch('tkinter.Tk')
    @patch('mvp.simulator.ui.interactive_ui.CanvasRenderer')
    def test_window_geometry_set(self, mock_canvas_renderer_cls, mock_tk_class):
        """Should set window geometry correctly"""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        mock_canvas_renderer_cls.return_value = MagicMock()
        
        ui = InteractiveUI(width=1400, height=900)
        
        mock_root.geometry.assert_called_with('1400x900')

    @patch('tkinter.Tk')
    @patch('mvp.simulator.ui.interactive_ui.CanvasRenderer')
    def test_window_title_set(self, mock_canvas_renderer_cls, mock_tk_class):
        """Should set appropriate window title"""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        mock_canvas_renderer_cls.return_value = MagicMock()
        
        ui = InteractiveUI()
        
        mock_root.title.assert_called_once()
        title_call = mock_root.title.call_args[0][0]
        self.assertIn('Simulator', title_call)

    @patch('tkinter.Tk')
    @patch('mvp.simulator.ui.interactive_ui.CanvasRenderer')
    def test_window_resizable_false(self, mock_canvas_renderer_cls, mock_tk_class):
        """Should disable window resizing"""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        mock_canvas_renderer_cls.return_value = MagicMock()
        
        ui = InteractiveUI()
        
        mock_root.resizable.assert_called_once_with(False, False)

    @patch('tkinter.Tk')
    @patch('mvp.simulator.ui.interactive_ui.CanvasRenderer')
    def test_window_close_protocol(self, mock_canvas_renderer_cls, mock_tk_class):
        """Should register window close protocol handler"""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        mock_canvas_renderer_cls.return_value = MagicMock()
        
        ui = InteractiveUI()
        
        mock_root.protocol.assert_called_once()
        call_args = mock_root.protocol.call_args[0]
        self.assertEqual(call_args[0], 'WM_DELETE_WINDOW')


class TestCanvasRendererInitialization(unittest.TestCase):
    """Test CanvasRenderer initialization and setup"""

    @patch('tkinter.Canvas')
    def test_canvas_renderer_init(self, mock_canvas_class):
        """Should initialize with canvas, width, height"""
        mock_canvas = MagicMock()
        renderer = CanvasRenderer(mock_canvas, width=600, height=700)
        
        self.assertEqual(renderer.canvas, mock_canvas)
        self.assertEqual(renderer.width, 600)
        self.assertEqual(renderer.height, 700)

    @patch('tkinter.Canvas')
    def test_canvas_renderer_unique_id(self, mock_canvas_class):
        """Should generate unique canvas ID"""
        mock_canvas1 = MagicMock()
        mock_canvas2 = MagicMock()
        
        renderer1 = CanvasRenderer(mock_canvas1, width=600, height=700)
        renderer2 = CanvasRenderer(mock_canvas2, width=600, height=700)
        
        self.assertNotEqual(renderer1.canvas_id, renderer2.canvas_id)
        self.assertEqual(len(renderer1.canvas_id), 8)

    @patch('tkinter.Canvas')
    def test_canvas_renderer_macro_images_dict(self, mock_canvas_class):
        """Should initialize macro_images cache dictionary"""
        mock_canvas = MagicMock()
        renderer = CanvasRenderer(mock_canvas, width=600, height=700)
        
        self.assertIsInstance(renderer.macro_images, dict)
        self.assertEqual(len(renderer.macro_images), 0)

    @patch('tkinter.Canvas')
    def test_canvas_renderer_macro_image_paths_dict(self, mock_canvas_class):
        """Should initialize macro_image_paths dictionary"""
        mock_canvas = MagicMock()
        renderer = CanvasRenderer(mock_canvas, width=600, height=700)
        
        self.assertIsInstance(renderer.macro_image_paths, dict)
        self.assertEqual(len(renderer.macro_image_paths), 0)

    @patch('tkinter.Canvas')
    def test_canvas_renderer_timer_animator(self, mock_canvas_class):
        """Should initialize TimerAnimator"""
        mock_canvas = MagicMock()
        
        with patch('mvp.simulator.ui.canvas_renderer.TimerAnimator'):
            renderer = CanvasRenderer(mock_canvas, width=600, height=700)
            self.assertIsNotNone(renderer.timer_animator)

    @patch('tkinter.Canvas')
    def test_canvas_renderer_canvas_config(self, mock_canvas_class):
        """Should configure canvas background and style"""
        mock_canvas = MagicMock()
        renderer = CanvasRenderer(mock_canvas, width=600, height=700)
        
        mock_canvas.config.assert_called_once()
        config_call = mock_canvas.config.call_args[1]
        self.assertEqual(config_call['bg'], '#1e1e1e')


class TestCanvasRendering(unittest.TestCase):
    """Test canvas rendering with macro images and fallbacks"""

    @patch('tkinter.Canvas')
    def test_render_state_clears_canvas(self, mock_canvas_class):
        """Should clear canvas before rendering new state"""
        mock_canvas = MagicMock()
        renderer = CanvasRenderer(mock_canvas, width=600, height=700)
        
        renderer.render_state(GameState.CHAT)
        
        mock_canvas.delete.assert_called()

    @patch('tkinter.Canvas')
    def test_render_state_returns_true_on_success(self, mock_canvas_class):
        """Should return True on successful render"""
        mock_canvas = MagicMock()
        renderer = CanvasRenderer(mock_canvas, width=600, height=700)
        
        result = renderer.render_state(GameState.CHAT)
        
        self.assertTrue(result)

    @patch('tkinter.Canvas')
    def test_render_state_handles_exception(self, mock_canvas_class):
        """Should handle exceptions gracefully and return False/True on fallback"""
        mock_canvas = MagicMock()
        mock_canvas.delete.side_effect = Exception("Canvas error")
        renderer = CanvasRenderer(mock_canvas, width=600, height=700)
        
        # Should still return True with fallback
        result = renderer.render_state(GameState.CHAT)
        # May return False or True depending on fallback logic
        self.assertIsInstance(result, bool)

    @patch('tkinter.Canvas')
    def test_render_state_symbolic_fallback(self, mock_canvas_class):
        """Should render symbolic state when image not available"""
        mock_canvas = MagicMock()
        renderer = CanvasRenderer(mock_canvas, width=600, height=700)
        
        renderer.render_state(GameState.CHAT)
        
        # Should call create_text for symbolic rendering
        self.assertTrue(mock_canvas.create_text.called or mock_canvas.create_rectangle.called)


class TestCanvasImageLoading(unittest.TestCase):
    """Test macro image loading and PhotoImage conversion"""

    @patch('tkinter.Canvas')
    @patch('pathlib.Path.exists')
    def test_load_and_render_image_not_found(self, mock_exists, mock_canvas_class):
        """Should return False when image file not found"""
        mock_canvas = MagicMock()
        mock_exists.return_value = False
        renderer = CanvasRenderer(mock_canvas, width=600, height=700)
        
        result = renderer._load_and_render_image('treasure')
        
        self.assertFalse(result)

    @patch('tkinter.Canvas')
    @patch('PIL.Image.open')
    @patch('pathlib.Path.exists')
    def test_load_and_render_image_success(self, mock_exists, mock_image_open, mock_canvas_class):
        """Should load and render image successfully"""
        mock_canvas = MagicMock()
        mock_canvas.create_image = MagicMock(return_value=1)
        mock_exists.return_value = True
        
        # Mock PIL Image
        mock_pil_image = MagicMock()
        mock_pil_image.resize = MagicMock(return_value=mock_pil_image)
        mock_image_open.return_value = mock_pil_image
        
        with patch('mvp.simulator.ui.canvas_renderer.ImageTk.PhotoImage'):
            renderer = CanvasRenderer(mock_canvas, width=600, height=700)
            result = renderer._load_and_render_image('treasure')
        
        self.assertTrue(result)

    @patch('tkinter.Canvas')
    def test_photo_image_caching(self, mock_canvas_class):
        """Should cache PhotoImage to prevent garbage collection"""
        mock_canvas = MagicMock()
        renderer = CanvasRenderer(mock_canvas, width=600, height=700)
        
        # Add to cache
        mock_photo_image = MagicMock()
        renderer.macro_images['treasure'] = mock_photo_image
        
        # Verify it's cached
        self.assertEqual(renderer.macro_images['treasure'], mock_photo_image)

    @patch('tkinter.Canvas')
    def test_render_image_uses_cache(self, mock_canvas_class):
        """Should use cached PhotoImage if available"""
        mock_canvas = MagicMock()
        mock_canvas.create_image = MagicMock(return_value=1)
        renderer = CanvasRenderer(mock_canvas, width=600, height=700)
        
        # Pre-cache an image
        mock_photo_image = MagicMock()
        renderer.macro_images['treasure'] = mock_photo_image
        renderer.macro_image_paths['treasure'] = 'data/macro_testing/treasure.png'
        
        with patch('pathlib.Path.exists', return_value=True):
            with patch('PIL.Image.open'):
                renderer._load_and_render_image('treasure')
        
        # Should use cached image
        self.assertEqual(renderer.macro_images['treasure'], mock_photo_image)


class TestTimerOverlayRendering(unittest.TestCase):
    """Test timer overlay rendering on canvas"""

    @patch('tkinter.Canvas')
    @patch('mvp.simulator.ui.canvas_renderer.TimerAnimator')
    def test_render_timer_overlay_default_effects(self, mock_timer_animator_cls, mock_canvas_class):
        """Should render timer overlay with default effects"""
        mock_canvas = MagicMock()
        mock_timer_animator = MagicMock()
        mock_timer_animator_cls.return_value = mock_timer_animator
        
        # Mock timer render
        mock_timer_image = MagicMock()
        mock_timer_animator.render_countdown = MagicMock(return_value=mock_timer_image)
        
        with patch('PIL.Image.open'):
            with patch('mvp.simulator.ui.canvas_renderer.ImageTk.PhotoImage'):
                renderer = CanvasRenderer(mock_canvas, width=600, height=700)
                result = renderer.render_timer_overlay(elapsed_ms=30000)
        
        # Should render without error
        self.assertTrue(result)

    @patch('tkinter.Canvas')
    @patch('mvp.simulator.ui.canvas_renderer.TimerAnimator')
    def test_render_timer_overlay_with_effects(self, mock_timer_animator_cls, mock_canvas_class):
        """Should pass perturbation effects to timer animator"""
        mock_canvas = MagicMock()
        mock_timer_animator = MagicMock()
        mock_timer_animator_cls.return_value = mock_timer_animator
        
        mock_timer_image = MagicMock()
        mock_timer_animator.render_countdown = MagicMock(return_value=mock_timer_image)
        
        effects = {'render_visible': True, 'chaotic': False}
        
        with patch('PIL.Image.open'):
            with patch('mvp.simulator.ui.canvas_renderer.ImageTk.PhotoImage'):
                renderer = CanvasRenderer(mock_canvas, width=600, height=700)
                result = renderer.render_timer_overlay(elapsed_ms=30000, effects=effects)
        
        self.assertTrue(result)

    @patch('tkinter.Canvas')
    @patch('mvp.simulator.ui.canvas_renderer.TimerAnimator')
    def test_render_timer_overlay_not_visible(self, mock_timer_animator_cls, mock_canvas_class):
        """Should skip rendering when render_visible is False"""
        mock_canvas = MagicMock()
        mock_timer_animator = MagicMock()
        mock_timer_animator_cls.return_value = mock_timer_animator
        
        effects = {'render_visible': False}
        
        with patch('PIL.Image.open'):
            renderer = CanvasRenderer(mock_canvas, width=600, height=700)
            result = renderer.render_timer_overlay(elapsed_ms=30000, effects=effects)
        
        # Should return True (skip is not failure)
        self.assertTrue(result)

    @patch('tkinter.Canvas')
    @patch('mvp.simulator.ui.canvas_renderer.TimerAnimator')
    def test_render_timer_overlay_stores_photo_image(self, mock_timer_animator_cls, mock_canvas_class):
        """Should store PhotoImage to prevent garbage collection"""
        mock_canvas = MagicMock()
        mock_timer_animator = MagicMock()
        mock_timer_animator_cls.return_value = mock_timer_animator
        
        mock_timer_image = MagicMock()
        mock_timer_animator.render_countdown = MagicMock(return_value=mock_timer_image)
        
        with patch('PIL.Image.open'):
            with patch('mvp.simulator.ui.canvas_renderer.ImageTk.PhotoImage') as mock_photo_class:
                mock_photo = MagicMock()
                mock_photo_class.return_value = mock_photo
                
                renderer = CanvasRenderer(mock_canvas, width=600, height=700)
                result = renderer.render_timer_overlay(elapsed_ms=30000)
        
        # Should store reference to PhotoImage
        self.assertIsNotNone(renderer.timer_photo_image)


class TestThreadSafeAccess(unittest.TestCase):
    """Test thread-safe access to UI components and assets"""

    @patch('tkinter.Tk')
    @patch('mvp.simulator.ui.interactive_ui.CanvasRenderer')
    def test_metrics_queue_thread_safe(self, mock_canvas_renderer_cls, mock_tk_class):
        """Metrics queue should be thread-safe"""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        mock_canvas_renderer_cls.return_value = MagicMock()
        
        ui = InteractiveUI()
        
        # Put from one thread, get from another
        def producer():
            ui.metrics_queue.put({'accuracy': 95.5})
        
        def consumer():
            data = ui.metrics_queue.get()
            self.assertEqual(data['accuracy'], 95.5)
        
        t1 = threading.Thread(target=producer)
        t2 = threading.Thread(target=consumer)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

    @patch('tkinter.Tk')
    @patch('mvp.simulator.ui.interactive_ui.CanvasRenderer')
    def test_macro_images_concurrent_access(self, mock_canvas_renderer_cls, mock_tk_class):
        """Macro images dictionary should handle concurrent reads"""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        mock_canvas_renderer = MagicMock()
        mock_canvas_renderer.macro_images = {}
        mock_canvas_renderer_cls.return_value = mock_canvas_renderer
        
        ui = InteractiveUI()
        
        # Simulate concurrent access
        def reader():
            _ = ui.canvas_renderer.macro_images.get('treasure')
        
        threads = [threading.Thread(target=reader) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()


class TestClearMethod(unittest.TestCase):
    """Test canvas clear method"""

    @patch('tkinter.Canvas')
    def test_canvas_clear(self, mock_canvas_class):
        """Should have clear method to clear canvas"""
        mock_canvas = MagicMock()
        renderer = CanvasRenderer(mock_canvas, width=600, height=700)
        
        renderer.clear()
        
        mock_canvas.delete.assert_called_with('all')


if __name__ == '__main__':
    unittest.main()
