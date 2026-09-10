"""Screenshot generation for mock game testing"""

from io import BytesIO
from typing import List, Optional
from PIL import Image, ImageDraw, ImageFont


class ScreenshotGenerator:
    """Generate mock game screenshots with UI elements"""

    def __init__(self, width: int = 1024, height: int = 768):
        self.width = width
        self.height = height
        self.bg_color = (20, 20, 30)  # Dark blue game background
        self.text_color = (255, 255, 255)  # White text
        self.dialog_bg = (40, 40, 60)  # Darker dialog background

    def _create_base_image(self) -> Image.Image:
        """Create base game screenshot"""
        return Image.new("RGB", (self.width, self.height), self.bg_color)

    def _get_font(self, size: int = 20) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        """Get a font for rendering text"""
        try:
            # Try to use a system font
            return ImageFont.truetype("arial.ttf", size)
        except (OSError, IOError):
            try:
                # Try alternative Windows font
                return ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", size)
            except (OSError, IOError):
                # Fallback to default font
                return ImageFont.load_default()

    def generate_timer_image(self, minutes: int = 5, seconds: int = 0) -> bytes:
        """Generate image with timer text"""
        img = self._create_base_image()
        draw = ImageDraw.Draw(img)

        # Format timer text
        timer_text = f"{minutes:02d}:{seconds:02d}"
        font = self._get_font(size=60)

        # Draw timer in center-top of screen
        bbox = draw.textbbox((0, 0), timer_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_x = (self.width - text_width) // 2
        text_y = 50

        draw.text((text_x, text_y), timer_text, fill=self.text_color, font=font)

        # Return as PNG bytes
        return self._image_to_bytes(img)

    def generate_chat_image(self, messages: List[str]) -> bytes:
        """Generate image with chat messages"""
        img = self._create_base_image()
        draw = ImageDraw.Draw(img)
        font = self._get_font(size=16)

        # Draw chat box
        chat_box = [50, 500, self.width - 50, self.height - 50]
        draw.rectangle(chat_box, fill=self.dialog_bg, outline=self.text_color)

        # Draw messages
        y = 520
        for msg in messages:
            draw.text((70, y), msg, fill=self.text_color, font=font)
            y += 30

        return self._image_to_bytes(img)

    def generate_dialog_image(self, title: str, text: str) -> bytes:
        """Generate dialog box image"""
        img = self._create_base_image()
        draw = ImageDraw.Draw(img)

        # Draw dialog background
        dialog_box = [200, 200, self.width - 200, self.height - 200]
        draw.rectangle(dialog_box, fill=self.dialog_bg, outline=self.text_color, width=2)

        # Draw title
        title_font = self._get_font(size=24)
        draw.text((220, 220), title, fill=self.text_color, font=title_font)

        # Draw text
        text_font = self._get_font(size=18)
        draw.text((220, 270), text, fill=self.text_color, font=text_font)

        return self._image_to_bytes(img)

    def generate_text_image(self, text: str, x: int = 100, y: int = 100) -> bytes:
        """Generate image with specific text at position"""
        img = self._create_base_image()
        draw = ImageDraw.Draw(img)
        font = self._get_font(size=32)

        draw.text((x, y), text, fill=self.text_color, font=font)

        return self._image_to_bytes(img)

    def generate_game_screenshot(
        self,
        timer_minutes: int = 5,
        timer_seconds: int = 0,
        chat_messages: Optional[List[str]] = None,
        dialog_title: Optional[str] = None,
    ) -> bytes:
        """Generate complete game screenshot with multiple elements"""
        img = self._create_base_image()
        draw = ImageDraw.Draw(img)

        # Draw timer
        timer_text = f"{timer_minutes:02d}:{timer_seconds:02d}"
        timer_font = self._get_font(size=40)
        draw.text((20, 20), timer_text, fill=self.text_color, font=timer_font)

        # Draw chat if provided
        if chat_messages:
            chat_font = self._get_font(size=14)
            y = self.height - 120
            draw.rectangle([10, y - 5, self.width - 10, self.height - 10], fill=self.dialog_bg)
            for msg in chat_messages[:3]:
                draw.text((20, y), msg, fill=self.text_color, font=chat_font)
                y += 30

        # Draw dialog if provided
        if dialog_title:
            dialog_font = self._get_font(size=18)
            dialog_y = (self.height - 100) // 2
            draw.rectangle(
                [100, dialog_y, self.width - 100, dialog_y + 100], fill=self.dialog_bg
            )
            draw.text((120, dialog_y + 20), dialog_title, fill=self.text_color, font=dialog_font)

        return self._image_to_bytes(img)

    def _image_to_bytes(self, img: Image.Image) -> bytes:
        """Convert PIL Image to PNG bytes"""
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()
