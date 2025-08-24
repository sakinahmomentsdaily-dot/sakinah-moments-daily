# main.py
# Python 3.12+
# pip install Flask==3.0.2 "Pillow>=11"
# (Optional, if you want RAQM to show as True: brew install freetype harfbuzz fribidi libraqm
#  then: pip install --no-binary :all: --compile pillow)

import os
import uuid
import unicodedata
from PIL import Image, ImageDraw, ImageFont
from flask import Flask, request, send_file, abort

app = Flask(__name__)

# -------- Paths / assets --------
SCRIPT_DIR   = os.path.dirname(os.path.realpath(__file__))
RES_DIR      = os.path.join(SCRIPT_DIR, "res")
TEMPLATE_PATH = os.path.join(RES_DIR, "template.jpg")

# Your preferred font (put the TTF in res/)
FONT_PATH    = os.path.join(RES_DIR, "(A) Arslan Wessam A (A) Arslan Wessam A.ttf")
if not os.path.exists(FONT_PATH):
    # fallback for macOS if custom font missing
    FONT_PATH = "/System/Library/Fonts/Supplemental/GeezaPro.ttc"

OUTPUT_DIR = os.path.join(SCRIPT_DIR, "generated")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# -------- Layout (same as your working version) --------
TEXT_IMG_MAX_W = 830
TEXT_IMG_MAX_H = 750
CANVAS_X = 100
CANVAS_Y = 340
LINE_SPACING = 10

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
    # NBSP-like spaces -> normal space
    0x00A0: 0x0020, 0x202F: 0x0020, 0x2007: 0x0020,
    # Latin -> Arabic punctuation
    ord(","): ord("،"), ord(";"): ord("؛"), ord("?"): ord("؟"),
}
def _clean(s: str) -> str:
    # Normalize, replace punctuation/spaces, drop format controls (Cf)
    s = s.translate(_TRANSLATE)
    s = unicodedata.normalize("NFC", s)
    return "".join(ch for ch in s if unicodedata.category(ch) != "Cf" or ch in ("\t", "\n", "\r"))

# -------- Core rendering --------
def _generate_image(text: str) -> str:
    if not os.path.exists(TEMPLATE_PATH):
        raise FileNotFoundError(f"Template not found: {TEMPLATE_PATH}")
    if not os.path.exists(FONT_PATH):
        raise FileNotFoundError(f"Font not found: {FONT_PATH}")

    bg_img = Image.open(TEMPLATE_PATH).convert("RGBA")
    text_img = _text_to_png(text)
    text_w, text_h = text_img.size

    offset = (
        CANVAS_X + (TEXT_IMG_MAX_W - text_w) // 2,
        CANVAS_Y + (TEXT_IMG_MAX_H - text_h) // 2,
    )
    bg_img.paste(text_img, offset, text_img)

    filename = f"{uuid.uuid4().hex}.png"
    filepath = os.path.join(OUTPUT_DIR, filename)
    bg_img.save(filepath, "PNG")
    return filepath

def _text_to_png(text: str) -> Image.Image:
    text = _clean(text)

    def load_font(size: int) -> ImageFont.FreeTypeFont:
        return ImageFont.truetype(FONT_PATH, size, **_font_kwargs)

    def wrap_text(draw: ImageDraw.ImageDraw, font: ImageFont.FreeTypeFont, raw_text: str):
        words = raw_text.split()
        lines, line = [], ""
        for word in words:
            candidate = (line + " " + word) if line else word
            bbox = draw.textbbox((0, 0), candidate, font=font, **_draw_kwargs)
            w = bbox[2] - bbox[0]
            if w <= TEXT_IMG_MAX_W - 20:
                line = candidate
            else:
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)
        return lines

    def calc_size(draw: ImageDraw.ImageDraw, font: ImageFont.FreeTypeFont, lines: list[str]):
        total_h, max_w = 0, 0
        for i, l in enumerate(lines):
            bbox = draw.textbbox((0, 0), l, font=font, **_draw_kwargs)
            w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            max_w = max(max_w, w)
            total_h += h + (LINE_SPACING if i < len(lines) - 1 else 0)
        total_h += 40  # padding
        return max_w, total_h

    # pick a font size that fits
    dummy = Image.new("RGBA", (TEXT_IMG_MAX_W, 1))
    draw = ImageDraw.Draw(dummy)
    font_size, min_size = 100, 12
    while font_size >= min_size:
        font = load_font(font_size)
        lines = wrap_text(draw, font, text)
        tw, th = calc_size(draw, font, lines)
        if tw <= TEXT_IMG_MAX_W and th <= TEXT_IMG_MAX_H:
            break
        font_size -= 2
    else:
        font = load_font(min_size)
        lines = wrap_text(draw, font, text)
        _, th = calc_size(draw, font, lines)

    # render
    _, th = calc_size(draw, font, lines)
    img = Image.new("RGBA", (TEXT_IMG_MAX_W, min(th, TEXT_IMG_MAX_H)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    y = 20
    for l in lines:
        bbox = d.textbbox((0, 0), l, font=font, **_draw_kwargs)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = (TEXT_IMG_MAX_W - w) // 2
        d.text((x, y), l, font=font, fill=(0, 0, 0, 255), **_draw_kwargs)
        y += h + LINE_SPACING
    return img

# -------- API --------
@app.route("/generate", methods=["POST"])
def generate():
    text = request.json.get("text") if request.is_json else (
        request.form.get("text") or request.data.decode("utf-8")
    )
    if not text:
        abort(400, "No text provided")
    try:
        path = _generate_image(text)
    except FileNotFoundError as e:
        abort(500, str(e))
    except OSError as e:
        abort(500, f"Rendering error: {e}")

    return send_file(path, mimetype="image/png")

def test():
    sample = "اللهم إني أعوذ بك من العجز والكسل، والجبن والبخل، والهرم وعذاب القبر."
    _generate_image(sample)

if __name__ == "__main__":
    print(f"RAQM available: {RAQM_AVAILABLE}")
    print(f"Using font: {FONT_PATH}")
    app.run(host="0.0.0.0", port=5123, debug=True)