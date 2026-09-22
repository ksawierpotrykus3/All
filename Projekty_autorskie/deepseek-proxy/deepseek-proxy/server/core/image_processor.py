"""Image processing and extraction module for OpenAI Vision requests."""

import base64
import binascii
from dataclasses import dataclass
import re
from typing import Any

from server.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ExtractedImage:
    data: bytes
    filename: str = "image.png"
    mime_type: str = "image/png"
    file_size: int = 0

    def __post_init__(self):
        if not self.file_size and self.data:
            self.file_size = len(self.data)


_DATA_URI_RE = re.compile(r"^data:(image\/[a-zA-Z0-9\+\-\.]+);base64,(.+)$", re.DOTALL)


def _extension_for_mime(mime_type: str) -> str:
    mime = mime_type.lower().strip()
    if "jpeg" in mime or "jpg" in mime:
        return "jpg"
    if "webp" in mime:
        return "webp"
    if "gif" in mime:
        return "gif"
    if "bmp" in mime:
        return "bmp"
    return "png"


def extract_images_from_messages(
    messages: list[dict[str, Any]],
    only_last_turn: bool = True,
) -> tuple[list[ExtractedImage], list[dict[str, Any]]]:
    """Extract image_url blocks from user messages and return cleaned messages.
    
    If only_last_turn is True, only extracts images from the last user message
    (images in earlier turns were already uploaded in those turns).
    
    Returns:
        tuple of (extracted_images, cleaned_messages)
    """
    extracted_images: list[ExtractedImage] = []
    cleaned_messages: list[dict[str, Any]] = []

    last_user_idx = -1
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") == "user":
            last_user_idx = i
            break

    seen_hashes: set[str] = set()
    for i, m in enumerate(messages):
        role = m.get("role", "")
        content = m.get("content")

        # Only inspect user messages
        if role != "user" or not isinstance(content, list):
            cleaned_messages.append(m)
            continue

        # If only_last_turn is requested, skip processing earlier turns
        if only_last_turn and i != last_user_idx:
            cleaned_messages.append(m)
            continue

        new_content_parts = []
        for part in content:
            if not isinstance(part, dict) or part.get("type") != "image_url":
                new_content_parts.append(part)
                continue

            # Process image_url
            img_info = part.get("image_url", {})
            url = img_info.get("url", "") if isinstance(img_info, dict) else str(img_info)

            parsed_img = _parse_image_url(url, img_idx=len(extracted_images) + 1)
            if parsed_img:
                import hashlib
                img_hash = hashlib.sha256(parsed_img.data).hexdigest()
                if img_hash not in seen_hashes:
                    seen_hashes.add(img_hash)
                    extracted_images.append(parsed_img)
            else:
                logger.warning(f"[VISION] Failed to extract image from url prefix: {url[:50]}...")

        # Build clean message without image_url parts
        m_copy = dict(m)
        if len(new_content_parts) == 1 and new_content_parts[0].get("type") == "text":
            m_copy["content"] = new_content_parts[0].get("text", "")
        else:
            m_copy["content"] = new_content_parts
        cleaned_messages.append(m_copy)

    return extracted_images, cleaned_messages


def _parse_image_url(url: str, img_idx: int = 1) -> ExtractedImage | None:
    if not url:
        return None

    if url.startswith("data:"):
        match = _DATA_URI_RE.match(url)
        if not match:
            # Fallback for lenient data: parsing
            parts = url.split(",", 1)
            if len(parts) == 2:
                header, b64_str = parts
                mime = header.split(";")[0].replace("data:", "").strip() or "image/png"
            else:
                return None
        else:
            mime = match.group(1).lower()
            b64_str = match.group(2)

        try:
            # Remove any whitespace or newlines inside base64
            clean_b64 = re.sub(r"\s+", "", b64_str)
            data = base64.b64decode(clean_b64, validate=False)
            ext = _extension_for_mime(mime)
            filename = f"image_{img_idx}.{ext}"
            return ExtractedImage(
                data=data,
                filename=filename,
                mime_type=mime,
                file_size=len(data),
            )
        except (binascii.Error, ValueError) as e:
            logger.error(f"[VISION] Base64 decode failed for image {img_idx}: {e}")
            return None

    elif url.startswith("http://") or url.startswith("https://"):
        try:
            import urllib.request
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read()
                mime = resp.headers.get_content_type() or "image/png"
                ext = _extension_for_mime(mime)
                filename = f"image_{img_idx}.{ext}"
                return ExtractedImage(
                    data=data,
                    filename=filename,
                    mime_type=mime,
                    file_size=len(data),
                )
        except Exception as e:
            logger.error(f"[VISION] Failed to download image from {url}: {e}")
            return None

    return None
