import hashlib
import io
import uuid
from pathlib import Path

from fastapi import HTTPException
from PIL import Image, ImageDraw, ImageFont

from .config import settings

CONTENT_TYPE_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}


def save_avatar_bytes(data: bytes, content_type: str) -> str:
    """Validates the image and saves it under media_root/avatars, returns a /media URL."""
    extension = CONTENT_TYPE_EXTENSIONS.get(content_type)
    if extension is None:
        raise HTTPException(status_code=400, detail="Unsupported image type.")

    max_bytes = int(settings.max_avatar_mb * 1024 * 1024)
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=400, detail=f"Image is larger than {settings.max_avatar_mb}MB."
        )

    try:
        Image.open(io.BytesIO(data)).verify()
    except Exception:
        raise HTTPException(status_code=400, detail="File is not a valid image.")

    filename = f"{uuid.uuid4()}.{extension}"
    avatars_dir = Path(settings.media_root) / "avatars"
    avatars_dir.mkdir(parents=True, exist_ok=True)
    (avatars_dir / filename).write_bytes(data)

    return f"/media/avatars/{filename}"


PALETTE = [
    "#ef5350", "#ec407a", "#ab47bc", "#5c6bc0", "#42a5f5",
    "#26a69a", "#66bb6a", "#fdd835", "#ffa726", "#8d6e63",
]


def generate_placeholder_avatar_bytes(username: str) -> bytes:
    """A deterministic, dependency-free placeholder: an initial on a flat color."""
    color = PALETTE[int(hashlib.sha256(username.encode()).hexdigest(), 16) % len(PALETTE)]
    image = Image.new("RGB", (256, 256), color)
    draw = ImageDraw.Draw(image)
    letter = username[0].upper() if username else "?"
    font = ImageFont.load_default(size=140)
    bbox = draw.textbbox((0, 0), letter, font=font)
    width, height = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        ((256 - width) / 2 - bbox[0], (256 - height) / 2 - bbox[1]),
        letter,
        font=font,
        fill="white",
    )
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
