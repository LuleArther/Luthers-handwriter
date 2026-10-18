"""Images people insert into the editor: validated, re-encoded and stored by content hash."""
from __future__ import annotations

import hashlib
import io
import re
from functools import lru_cache

from PIL import Image, ImageOps

from .fonts import DATA_DIR

IMAGE_DIR = DATA_DIR / "editor_images"
MAX_UPLOAD_BYTES = 15 * 1024 * 1024
MAX_SIDE = 2000                      # stored images are at most this many pixels on the long side
IMAGE_ID = re.compile(r"^[0-9a-f]{16}\.(jpg|png)$")
Image.MAX_IMAGE_PIXELS = 50_000_000  # refuse decompression bombs


def save(data: bytes) -> str:
    """Store an uploaded image; returns its id (e.g. 'ab12….jpg'). Raises ValueError if unusable."""
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("Image is larger than 15 MB.")
    try:
        img = Image.open(io.BytesIO(data), formats=["PNG", "JPEG", "WEBP", "GIF", "BMP"])
        img.load()
    except Exception as e:
        raise ValueError("That file isn't an image we can read (use PNG, JPG, WEBP or GIF).") from e
    img = ImageOps.exif_transpose(img)
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
    buf = io.BytesIO()
    if has_alpha:
        img.convert("RGBA").save(buf, "PNG", optimize=True)
        ext = "png"
    else:
        img.convert("RGB").save(buf, "JPEG", quality=90)
        ext = "jpg"
    out = buf.getvalue()
    image_id = f"{hashlib.sha256(out).hexdigest()[:16]}.{ext}"
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    path = IMAGE_DIR / image_id
    if not path.exists():
        path.write_bytes(out)
    return image_id


def path_for(image_id: str):
    if not IMAGE_ID.match(image_id or ""):
        return None
    path = IMAGE_DIR / image_id
    return path if path.exists() else None


@lru_cache(maxsize=32)
def load_rgb_on_white(image_id: str) -> Image.Image | None:
    """The image flattened onto white (transparent areas become paper)."""
    path = path_for(image_id)
    if not path:
        return None
    img = Image.open(path)
    img.load()
    if img.mode == "RGBA":
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.getchannel("A"))
        return bg
    return img.convert("RGB")
