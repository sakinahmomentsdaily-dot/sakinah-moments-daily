# main.py
# Python 3.12+
# pip install Flask==3.0.2 "Pillow>=11"

import os
import uuid
import unicodedata
from PIL import Image, ImageDraw, ImageFont, ImageOps
from flask import Flask, request, send_file, abort

app = Flask(__name__)

# -------- Paths / assets --------
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
RES_DIR    = os.path.join(SCRIPT_DIR, "res")

TEMPLATE_MAP = {
    "post":  "IG-post-template.jpg",
    "story": "IG-story-template.jpg",
}

# Your preferred font (put the TTF in res/)
FONT_PATH = os.path.join(RES_DIR, "(A) Arslan Wessam A (A) Arslan Wessam A.ttf")
if not os.path.exists(FONT_PATH):
    # fallback for macOS if custom font missing
    FONT_PATH = "/System/Library/Fonts/Supplemental/GeezaPro.ttc"

OUTPUT_DIR = os.path.join(SCRIPT_DIR, "generated")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# -------- Legacy post layout (unchanged) --------
TEXT_IMG_MAX_W = 830
TEXT_IMG_MAX_H = 750
CANVAS_X = 100
CANVAS_Y = 340

# -------- Story layout (percent-of-image safe area) --------
# Tweak if you want more/less whitespace or to avoid a watermark at the bottom.
STORY_MARGINS_LEFT   = 0.10
STORY_MARGINS_RIGHT  = 0.10
STORY_MARGINS_TOP    = 0.16
STORY_MARGINS_BOTTOM = 0.20

# -------- RAQM probe (best for Arabic shaping) --------
RAQM_AVAILABLE = False
try:
    ImageFont.truetype(
        "/System/Library/Fonts/Supplemental/GeezaPro.ttc", 16,
        layout_engine=ImageFont.LAYOUT_RAQM
    )
    RAQM_AVAILABLE = True
except Exception:
    RAQM_AVAILABLE = False

_draw_kwargs = {"direction": "rtl"} if RAQM_AVAILABLE else {}
_font_kwargs = {"layout_engine": ImageFont.LAYOUT_RAQM} if RAQM_AVAILABLE else {}

# -------- Sanitize / normalize Arabic input --------
_TRANSLATE = {
    0x00A0: 0x0020, 0x202F: 0x0020, 0x2007: 0x0020,   # NBSP-like spaces -> space
    ord(","): ord("،"), ord(";"): ord("؛"), ord("?"): ord("؟"),  # Latin -> Arabic punctuation
}
def _clean(s: str) -> str:
    s = s.translate(_TRANSLATE)
    s = unicodedata.normalize("NFC", s)
    return "".join(ch for ch in s if unicodedata.category(ch) != "Cf" or ch in ("\t", "\n", "\r"))

def _template_path_for(fmt: str) -> str:
    filename = TEMPLATE_MAP.get(fmt)
    if not filename:
        raise ValueError(f"Unsupported format '{fmt}'. Allowed: {', '.join(TEMPLATE_MAP)}")
    path = os.path.join(RES_DIR, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Template not found: {path}")
    return path

# -------- Core rendering --------
def _generate_image_post(text: str, template_path: str) -> str:
    """Existing 'post' behavior: draw within the fixed canvas rectangle."""
    if not os.path.exists(FONT_PATH):
        raise FileNotFoundError(f"Font not found: {FONT_PATH}")

    bg_img = Image.open(template_path).convert("RGBA")
    # Reuse legacy max W/H
    text_img = _text_to_png(text, TEXT_IMG_MAX_W, TEXT_IMG_MAX_H)
    text_w, text_h = text_img.size
    offset = (
        CANVAS_X + (TEXT_IMG_MAX_W - text_w) // 2,
        CANVAS_Y + (TEXT_IMG_MAX_H - text_h) // 2,
    )
    bg_img.paste(text_img, offset, text_img)
    return _save(bg_img)

def _generate_image_story(text: str, template_path: str) -> str:
    """Story behavior: center the text in a safe rect derived from image size."""
    if not os.path.exists(FONT_PATH):
        raise FileNotFoundError(f"Font not found: {FONT_PATH}")

    # Respect EXIF orientation (phone camera images)
    bg_img = ImageOps.exif_transpose(Image.open(template_path)).convert("RGBA")
    W, H = bg_img.size

    # Safe area (percent margins)
    x0 = int(W * STORY_MARGINS_LEFT)
    x1 = int(W * (1.0 - STORY_MARGINS_RIGHT))
    y0 = int(H * STORY_MARGINS_TOP)
    y1 = int(H * (1.0 - STORY_MARGINS_BOTTOM))

    max_w = max(50, x1 - x0)
    max_h = max(50, y1 - y0)

    text_img = _text_to_png(text, max_w, max_h)  # this guarantees it fits
    tw, th = text_img.size

    # Center inside the safe area
    offset = (x0 + (max_w - tw) // 2, y0 + (max_h - th) // 2)
    bg_img.paste(text_img, offset, text_img)
    return _save(bg_img)

def _save(bg_img: Image.Image) -> str:
    filename = f"{uuid.uuid4().hex}.png"
    filepath = os.path.join(OUTPUT_DIR, filename)
    bg_img.save(filepath, "PNG")
    return filepath

def _text_to_png(text: str, max_w: int, max_h: int) -> Image.Image:
    """
    Render Arabic text into an RGBA image that fits within (max_w, max_h),
    centered line-by-line. Chooses font size by binary search (no clipping).
    """
    text = _clean(text)

    def load_font(size: int) -> ImageFont.FreeTypeFont:
        return ImageFont.truetype(FONT_PATH, size, **_font_kwargs)

    def wrap_lines(draw: ImageDraw.ImageDraw, font: ImageFont.FreeTypeFont, raw: str):
        words = raw.split()
        lines, line = [], ""
        for word in words:
            candidate = (line + " " + word) if line else word
            w = _line_width(draw, font, candidate)
            if w <= max_w - 20:  # a little horizontal padding for nice edges
                line = candidate
            else:
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)
        return lines

    def _line_width(draw, font, s):
        bbox = draw.textbbox((0, 0), s, font=font, **_draw_kwargs)
        return bbox[2] - bbox[0]

    def measure(draw, font, lines, line_spacing):
        total_h, max_line_w = 0, 0
        for i, l in enumerate(lines):
            bbox = draw.textbbox((0, 0), l, font=font, **_draw_kwargs)
            w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            max_line_w = max(max_line_w, w)
            total_h += h
            if i < len(lines) - 1:
                total_h += line_spacing
        # vertical padding for breathing room
        total_h += int(font.size * 0.35)
        return max_line_w, total_h

    # Binary search for the largest font that fits both width and height
    dummy = Image.new("RGBA", (max_w, 1))
    draw = ImageDraw.Draw(dummy)

    lo, hi = 6, 160  # search range; bump hi if you want larger single-line text
    best = None
    best_lines = None
    while lo <= hi:
        mid = (lo + hi) // 2
        font = load_font(mid)
        line_spacing = max(4, int(mid * 0.27))  # scale spacing with size
        lines = wrap_lines(draw, font, text)
        tw, th = measure(draw, font, lines, line_spacing)
        if tw <= max_w and th <= max_h:
            best = (font, line_spacing)
            best_lines = lines
            lo = mid + 1  # try bigger
        else:
            hi = mid - 1   # too big

    if best is None:
        # Extremely constrained area: fall back to smallest size and allow tighter spacing
        font = load_font(6)
        line_spacing = 4
        best = (font, line_spacing)
        best_lines = wrap_lines(draw, font, text)

    font, line_spacing = best
    # Final measure with chosen font
    tw, th = measure(draw, font, best_lines, line_spacing)
    th = min(th, max_h)  # just in case

    # Render centered line-by-line
    img = Image.new("RGBA", (max_w, th), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    y = int(font.size * 0.175)  # top padding matches 'measure'
    for l in best_lines:
        bbox = d.textbbox((0, 0), l, font=font, **_draw_kwargs)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = (max_w - w) // 2
        d.text((x, y), l, font=font, fill=(0, 0, 0, 255), **_draw_kwargs)
        y += h + line_spacing
    return img

# -------- API --------
@app.route("/generate", methods=["POST"])
def generate():
    # accept JSON, form, or raw text (for text); JSON/form for format
    if request.is_json:
        text = request.json.get("text")
        fmt  = request.json.get("format", "post")
    else:
        text = request.form.get("text") or request.data.decode("utf-8")
        fmt  = request.form.get("format", "post")

    if not text:
        abort(400, "No text provided")

    fmt = (fmt or "post").strip().lower()
    if fmt not in TEMPLATE_MAP:
        abort(400, f"Invalid format '{fmt}'. Allowed values: {', '.join(TEMPLATE_MAP)}")

    try:
        template_path = _template_path_for(fmt)
        if fmt == "story":
            path = _generate_image_story(text, template_path)
        else:
            path = _generate_image_post(text, template_path)
    except (ValueError, FileNotFoundError) as e:
        abort(500, str(e))
    except OSError as e:
        abort(500, f"Rendering error: {e}")

    return send_file(path, mimetype="image/png")

def test():
    sample = "اللهم إني أعوذ بك من العجز والكسل، والجبن والبخل، والهرم وعذاب القبر."
    print(_generate_image_post(sample, _template_path_for("post")))
    print(_generate_image_story(sample, _template_path_for("story")))

if __name__ == "__main__":
    print(f"RAQM available: {RAQM_AVAILABLE}")
    print(f"Using font: {FONT_PATH}")
    app.run(host="0.0.0.0", port=5123, debug=True)