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
DIGITS = "0123456789"
MAX_TEXT_WIDTH = 130

_lock = threading.Lock()
_geom_cache = {}


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


def _fit_size(font_path: str, text: str, target_h: int = None, target_w: int = None) -> int:
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    best = 10

    def fits(size, by_h, by_w):
        font = ImageFont.truetype(font_path, size)
        tb = probe.textbbox((0, 0), text, font=font)
        if by_h is not None and tb[3] - tb[1] > by_h:
            return False
        if by_w is not None and tb[2] - tb[0] > by_w:
            return False
        return True

    lo, hi = 10, 400
    while lo <= hi:
        mid = (lo + hi) // 2
        if fits(mid, target_h, target_w):
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def _draw_centered(img, text: str, font_path: str, size: int, center: tuple) -> None:
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(font_path, size)
    tb = draw.textbbox((0, 0), text, font=font)
    text_w = tb[2] - tb[0]
    text_h = tb[3] - tb[1]
    draw.text(
        (center[0] - text_w // 2 - tb[0], center[1] - text_h // 2 - tb[1]),
        text,
        font=font,
        fill=TEXT_COLOR,
    )


def _number_geometry(templates_dir: str, font_path: str) -> tuple:
    key = ("num", templates_dir, font_path)
    with _lock:
        if key in _geom_cache:
            return _geom_cache[key]
        heights = []
        sum_x = sum_y = 0.0
        for i in range(15):
            path = os.path.join(templates_dir, f"s{i:02d}.png")
            if not os.path.exists(path):
                continue
            img = Image.open(path).convert("RGB")
            bbox = _measure_digit_bbox(img)
            heights.append(bbox[3] - bbox[1] + 1)
            sum_x += (bbox[0] + bbox[2]) / 2
            sum_y += (bbox[1] + bbox[3]) / 2
        if heights:
            target_h = round(sum(heights) / len(heights))
            center = (round(sum_x / len(heights)), round(sum_y / len(heights)))
        else:
            target_h, center = 80, (104, 106)
        size = _fit_size(font_path, DIGITS, target_h=target_h)
        _geom_cache[key] = (size, center)
        return _geom_cache[key]


def make_number_cover(templates_dir: str, star: int, font_path: str) -> bytes:
    size, center = _number_geometry(templates_dir, font_path)
    text = str(star)
    size = min(size, _fit_size(font_path, text, target_w=MAX_TEXT_WIDTH))
    template = os.path.join(templates_dir, f"s{min(star, 14):02d}.png")
    img = Image.open(template).convert("RGB")
    _erase_digit(img)
    _draw_centered(img, text, font_path, size, center)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def make_special_cover(template_path: str, text: str, font_path: str) -> bytes:
    img = Image.open(template_path).convert("RGB")
    bbox = _measure_digit_bbox(img)
    target_h = bbox[3] - bbox[1] + 1
    center = ((bbox[0] + bbox[2]) // 2, (bbox[1] + bbox[3]) // 2)
    size = _fit_size(font_path, text, target_h=target_h, target_w=MAX_TEXT_WIDTH)
    _erase_digit(img)
    _draw_centered(img, text, font_path, size, center)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def number_cover_data_uri(templates_dir: str, star: int, font_path: str) -> str:
    png = make_number_cover(templates_dir, star, font_path)
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def special_cover_data_uri(template_path: str, text: str, font_path: str) -> str:
    png = make_special_cover(template_path, text, font_path)
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")
