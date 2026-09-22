"""Unit tests for image_processor module."""

import base64
from server.core.image_processor import extract_images_from_messages, ExtractedImage


def test_extract_single_data_uri_png():
    raw_bytes = b"fake_png_header_and_data_12345"
    b64 = base64.b64encode(raw_bytes).decode("ascii")
    data_uri = f"data:image/png;base64,{b64}"

    messages = [
        {"role": "system", "content": "You are assistant."},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe this image."},
                {"type": "image_url", "image_url": {"url": data_uri}},
            ],
        },
    ]

    images, cleaned = extract_images_from_messages(messages)

    assert len(images) == 1
    assert images[0].data == raw_bytes
    assert images[0].mime_type == "image/png"
    assert images[0].filename == "image_1.png"
    assert images[0].file_size == len(raw_bytes)

    # Cleaned message text should be intact and not contain [Image]
    assert cleaned[1]["role"] == "user"
    assert cleaned[1]["content"] == "Describe this image."


def test_extract_jpeg_extension():
    raw_bytes = b"jpeg_bytes"
    b64 = base64.b64encode(raw_bytes).decode("ascii")
    data_uri = f"data:image/jpeg;base64,{b64}"

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": data_uri}},
            ],
        },
    ]

    images, cleaned = extract_images_from_messages(messages)
    assert len(images) == 1
    assert images[0].filename == "image_1.jpg"
    assert images[0].mime_type == "image/jpeg"
    assert cleaned[0]["content"] == []


def test_multiple_images_in_last_turn():
    raw1 = b"img1"
    raw2 = b"img2"
    uri1 = f"data:image/png;base64,{base64.b64encode(raw1).decode()}"
    uri2 = f"data:image/webp;base64,{base64.b64encode(raw2).decode()}"

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Compare both images."},
                {"type": "image_url", "image_url": {"url": uri1}},
                {"type": "image_url", "image_url": {"url": uri2}},
            ],
        }
    ]

    images, cleaned = extract_images_from_messages(messages)
    assert len(images) == 2
    assert images[0].filename == "image_1.png"
    assert images[1].filename == "image_2.webp"
    assert cleaned[0]["content"] == "Compare both images."


def test_only_last_turn_flag():
    raw1 = b"turn1"
    raw2 = b"turn2"
    uri1 = f"data:image/png;base64,{base64.b64encode(raw1).decode()}"
    uri2 = f"data:image/png;base64,{base64.b64encode(raw2).decode()}"

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "First"},
                {"type": "image_url", "image_url": {"url": uri1}},
            ],
        },
        {"role": "assistant", "content": "Seen first."},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Second"},
                {"type": "image_url", "image_url": {"url": uri2}},
            ],
        },
    ]

    images, cleaned = extract_images_from_messages(messages, only_last_turn=True)
    assert len(images) == 1
    assert images[0].data == raw2


def test_deduplicate_identical_images():
    raw = b"identical_image_bytes"
    uri = f"data:image/png;base64,{base64.b64encode(raw).decode()}"

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Repeated image"},
                {"type": "image_url", "image_url": {"url": uri}},
                {"type": "text", "text": "Same image again"},
                {"type": "image_url", "image_url": {"url": uri}},
            ],
        },
    ]

    images, cleaned = extract_images_from_messages(messages)
    assert len(images) == 1
    assert images[0].data == raw
