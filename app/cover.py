import base64
import io
import os
import threading

from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

MAIN_GOLD = (255, 222, 26)
TEXT_COLOR = (0, 0, 0)
WIN = (40, 40, 170, 170)
FALLBACK_BOX = (52, 52, 156, 156)

_lock = threading.Lock()


def ensure_font(assets_dir: str) -> str:
    woff = os.path.join(assets_dir, "SBAggroB.woff")
    ttf = os.path.join(assets_dir, "SBAggroB.ttf")
    with _lock:
        if os.path.exists(ttf):
            return ttf
        font = TTFont(woff)
        font.flavor = None
        font.save(ttf)
        return ttf


def _measure_digit_bbox(img) -> tuple:
    px = img.load()
    min_x = min_y = 10**9
    max_x = max_y = -1
    for y in range(WIN[1], WIN[3] + 1):
        for x in range(WIN[0], WIN[2] + 1):
            r, g, b = px[x, y]
            if r + g + b < 250:
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
    if max_x < 0:
        return FALLBACK_BOX
    return (min_x, min_y, max_x, max_y)


def _erase_digit(img) -> None:
    px = img.load()
    for y in range(WIN[1], WIN[3] + 1):
        for x in range(WIN[0], WIN[2] + 1):
            if px[x, y] != MAIN_GOLD:
                px[x, y] = MAIN_GOLD


def _draw_text(img, text: str, bbox: tuple, font_path: str) -> int:
    draw = ImageDraw.Draw(img)
    box_w = bbox[2] - bbox[0] + 1
    box_h = bbox[3] - bbox[1] + 1
    lo, hi, best = 10, 400, 10
    while lo <= hi:
        mid = (lo + hi) // 2
        font = ImageFont.truetype(font_path, mid)
        tb = draw.textbbox((0, 0), text, font=font)
        if tb[2] - tb[0] <= box_w and tb[3] - tb[1] <= box_h:
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1
    font = ImageFont.truetype(font_path, best)
    tb = draw.textbbox((0, 0), text, font=font)
    text_w = tb[2] - tb[0]
    text_h = tb[3] - tb[1]
    center_x = (bbox[0] + bbox[2]) // 2
    center_y = (bbox[1] + bbox[3]) // 2
    draw.text(
        (center_x - text_w // 2 - tb[0], center_y - text_h // 2 - tb[1]),
        text,
        font=font,
        fill=TEXT_COLOR,
    )
    return best


def make_cover(template_path: str, text: str, font_path: str) -> bytes:
    img = Image.open(template_path).convert("RGB")
    bbox = _measure_digit_bbox(img)
    _erase_digit(img)
    _draw_text(img, text, bbox, font_path)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def cover_data_uri(template_path: str, text: str, font_path: str) -> str:
    png = make_cover(template_path, text, font_path)
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")
