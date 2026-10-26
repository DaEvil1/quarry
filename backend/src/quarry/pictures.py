"""Making a picture from an uploaded file (docs/SPEC.md §17.4): opened to find out what it is (never by its name),
turned the way its camera says it was held, stripped of its metadata, scaled down to 2400 px and given a 1600 px
view copy and a 400 px thumb in WebP. Done once, on upload or on Restore; a picture's files never change after.

The container has 256 MB of memory: JPEGs are decoded at a reduced scale (Pillow's draft mode), PNGs and WebPs over
30 megapixels are refused, and one picture is worked on at a time.
"""

from __future__ import annotations

import io
import re
import threading
import uuid
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.orm import Session

from .models import Picture, PictureFile

MAX_BYTES = 25 * 1024 * 1024
MAX_PIXELS = 50_000_000
# a PNG or WebP is decoded whole: past this it would not fit in the container's memory
MAX_PIXELS_LOSSLESS = 30_000_000
FULL_SIDE = 2400
VIEW_SIDE = 1600
THUMB_SIDE = 400
FORMATS = {"JPEG": "jpeg", "PNG": "png", "WEBP": "webp"}
MEDIA_TYPES = {"jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
EXTENSIONS = {"jpeg": "jpg", "png": "png", "webp": "webp"}
REFUSED = "Quarry takes JPEG, PNG or WebP pictures."
TOO_BIG = "A picture may be up to 25 MB."
TOO_MANY_PIXELS = "That picture is too large (at most 50 megapixels, 30 for PNG and WebP)."

# one picture at a time: a second upload waits its turn rather than doubling the memory
_one_at_a_time = threading.Lock()


class PictureError(ValueError):
    """A file Quarry doesn't take, with the sentence to show."""


@dataclass
class Made:
    format: str
    width: int
    height: int
    full: bytes
    view: bytes
    thumb: bytes


def name_from_file(filename: str | None) -> str:
    """A picture's name from its file name: `harbour-at-dusk.jpg` is `harbour-at-dusk`."""
    base = re.split(r"[\\/]", filename or "")[-1]
    stem = base.rsplit(".", 1)[0] if "." in base.lstrip(".") else base
    return " ".join(stem.split())[:200] or "picture"


def _scaled(img: Image.Image, side: int) -> Image.Image:
    if max(img.size) <= side:
        return img
    out = img.copy()
    out.thumbnail((side, side), Image.Resampling.LANCZOS)
    return out


def _webp(img: Image.Image, quality: int = 82) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "WEBP", quality=quality, method=4)
    return buf.getvalue()


def make(data: bytes) -> Made:
    """The three files of a picture from an uploaded file's bytes; PictureError when Quarry doesn't take it."""
    if len(data) > MAX_BYTES:
        raise PictureError(TOO_BIG)
    with _one_at_a_time:
        try:
            img = Image.open(io.BytesIO(data))
        except (UnidentifiedImageError, OSError, ValueError):
            raise PictureError(REFUSED) from None
        fmt = FORMATS.get(img.format or "")
        if fmt is None:
            raise PictureError(REFUSED)
        w, h = img.size
        if w * h > MAX_PIXELS or (fmt != "jpeg" and w * h > MAX_PIXELS_LOSSLESS):
            raise PictureError(TOO_MANY_PIXELS)
        icc = img.info.get("icc_profile")
        try:
            if fmt == "jpeg":
                # decoded at a half, a quarter or an eighth of its size when that still covers 2400 px
                scale = min(1.0, FULL_SIDE / max(w, h))
                img.draft("RGB", (max(1, round(w * scale)), max(1, round(h * scale))))
            img.seek(0)  # an animated WebP keeps its first frame
            img.load()
            # turned the way its camera held it; the orientation tag goes with the rest of the metadata
            img = ImageOps.exif_transpose(img)
        except (OSError, ValueError, SyntaxError, Image.DecompressionBombError):
            raise PictureError(REFUSED) from None
        if fmt == "jpeg" and img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        elif fmt != "jpeg" and img.mode not in ("RGB", "RGBA", "L", "LA"):
            img = img.convert("RGBA" if "transparency" in img.info or img.mode in ("P", "PA") else "RGB")
        full_img = _scaled(img, FULL_SIDE)
        buf = io.BytesIO()
        # saved fresh: nothing of the file's metadata (location, camera, date) comes along, only its colour profile
        extra = {"icc_profile": icc} if icc else {}
        if fmt == "jpeg":
            full_img.save(buf, "JPEG", quality=90, optimize=True, **extra)
        elif fmt == "png":
            full_img.save(buf, "PNG", **extra)
        else:
            full_img.save(buf, "WEBP", quality=90, method=4, **extra)
        full = buf.getvalue()
        view_img = _scaled(full_img, VIEW_SIDE)
        view = _webp(view_img)
        thumb = _webp(_scaled(view_img, THUMB_SIDE), 78)
        return Made(format=fmt, width=full_img.width, height=full_img.height, full=full, view=view, thumb=thumb)


def store(db: Session, world_id: uuid.UUID, user_id: uuid.UUID, made: Made, name: str,
          picture_id: uuid.UUID | None = None) -> Picture:
    """Keep a made picture in the world, its files flushed straight away (so they don't pile up in memory)."""
    p = Picture(id=picture_id or uuid.uuid4(), world_id=world_id, name=name, format=made.format, width=made.width,
                height=made.height, size=len(made.full), created_by=user_id)
    db.add(p)
    db.flush()
    files = [PictureFile(picture_id=p.id, kind=kind, data=data)
             for kind, data in (("full", made.full), ("view", made.view), ("thumb", made.thumb))]
    db.add_all(files)
    db.flush()
    for f in files:
        db.expunge(f)
    return p


def file_name(p: Picture) -> str:
    """`harbour-at-dusk-3f2a9c1e.jpg`: the name lower-cased and hyphened, so paths need no escaping."""
    slug = re.sub(r"[^a-z0-9]+", "-", p.name.lower()).strip("-")[:60] or "picture"
    return f"{slug}-{str(p.id)[:8]}.{EXTENSIONS[p.format]}"
