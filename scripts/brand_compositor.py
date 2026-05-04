"""
brand_compositor.py — 90minWaffle brand pipeline v3 (clean editorial)
No duotone. Full bright images. Minimal clean brand overlay + watermark.
"""

import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from pathlib import Path

BASE_DIR       = Path("/root/90minwaffle")
ASSETS_DIR     = BASE_DIR / "assets"
WATERMARK_PATH = ASSETS_DIR / "watermark_orig.png"
OUTRO_PATH     = ASSETS_DIR / "outro_card.png"
OUTPUT_DIR     = BASE_DIR / "composed"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FRAME_W = 1080
FRAME_H = 1920
MINT    = (0, 232, 122)
WHITE   = (255, 255, 255)
BAR_H           = 30
HOOK_Y          = BAR_H + 15
HOOK_H          = 80
CAPTION_H       = 100
LOGO_BAR_H      = 70
WM_OPACITY      = 8
CORNER_WM_SIZE  = 200
CORNER_WM_OPACITY = 180

def _font(size, bold=True):
    for path in [str(ASSETS_DIR / "Anton-Regular.ttf"),
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
        try: return ImageFont.truetype(path, size)
        except: continue
    return ImageFont.load_default()

def prepare_image(img):
    img = img.convert("RGB")
    ratio = img.width / img.height
    target = FRAME_W / FRAME_H
    if ratio > target:
        new_h = FRAME_H; new_w = int(new_h * ratio)
    else:
        new_w = FRAME_W; new_h = int(new_w / ratio)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - FRAME_W) // 2; top = (new_h - FRAME_H) // 2
    img = img.crop((left, top, left + FRAME_W, top + FRAME_H))
    # No enhancement — pure unmodified images
    return img

def apply_brand_overlay(img, hook_text="", caption_text=""):
    overlay = Image.new("RGBA", (FRAME_W, FRAME_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle([0, 0, FRAME_W, BAR_H], fill=(0, 0, 0, 255))
    draw.rectangle([0, BAR_H, FRAME_W, BAR_H + 2], fill=(255, 255, 255, 180))
    draw.rectangle([0, FRAME_H - BAR_H, FRAME_W, FRAME_H], fill=(0, 0, 0, 255))
    logo_bar_y = FRAME_H - BAR_H - LOGO_BAR_H
    cx = FRAME_W // 2
    if hook_text:
        hook_font = _font(54)
        ty = HOOK_Y + HOOK_H // 2
        # Gradient fade behind hook text using stepped rectangles
        grad_h = HOOK_H + 20
        grad_y = HOOK_Y - 10
        steps = 12
        for i in range(steps):
            alpha = int(160 * (1 - i/steps))
            draw.rectangle([0, grad_y + i*(grad_h//steps), FRAME_W, grad_y + (i+1)*(grad_h//steps)], fill=(0,0,0,alpha))
        # Shadow pass
        for ox, oy in [(-2,2),(2,2),(0,3)]:
            draw.text((cx+ox, ty+oy), hook_text.upper(), font=hook_font, fill=(0,0,0,220), anchor="mm")
        # Main text
        draw.text((cx, ty), hook_text.upper(), font=hook_font, fill=(*WHITE, 255), anchor="mm")
    if caption_text:
        cap_font = _font(44)
        cap_h = 85
        cap_y = FRAME_H - BAR_H - cap_h - 8
        # Gradient fade up from bottom bar
        steps = 14
        for i in range(steps):
            alpha = int(200 * (1 - i/steps))
            draw.rectangle([0, cap_y + i*(cap_h//steps), FRAME_W, cap_y + (i+1)*(cap_h//steps)], fill=(0,0,0,alpha))
        # Shadow
        draw.text((cx+1, cap_y + cap_h//2 + 1), caption_text.upper(), font=cap_font, fill=(0,0,0,200), anchor="mm")
        draw.text((cx, cap_y + cap_h//2), caption_text.upper(), font=cap_font, fill=(*WHITE, 255), anchor="mm")
    result = img.convert("RGBA")
    return Image.alpha_composite(result, overlay)

def add_watermark(img):
    wm_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    wm_draw = ImageDraw.Draw(wm_layer)
    wm_font = _font(55)
    for y in range(-FRAME_H, FRAME_H * 2, 340):
        for x in range(-FRAME_W, FRAME_W * 2, 520):
            wm_draw.text((x, y), "90minWaffle", font=wm_font, fill=(255, 255, 255, WM_OPACITY))
    wm_layer = wm_layer.rotate(-25, resample=Image.BICUBIC, expand=False)
    result = Image.alpha_composite(img.convert("RGBA"), wm_layer)
    if WATERMARK_PATH.exists():
        wm_logo = Image.open(WATERMARK_PATH).convert("RGBA")
        data = np.array(wm_logo)
        mask = data[..., 3] > 10
        data[mask, 0] = 255; data[mask, 1] = 255; data[mask, 2] = 255; data[mask, 3] = CORNER_WM_OPACITY
        wm_logo = Image.fromarray(data)
        wm_w = CORNER_WM_SIZE; wm_h = int(wm_w * wm_logo.height / wm_logo.width)
        wm_logo = wm_logo.resize((wm_w, wm_h), Image.LANCZOS)
        margin = 35
        x = FRAME_W - wm_w - margin; y = FRAME_H - wm_h - margin - BAR_H - 20
        result.paste(wm_logo, (x, y), wm_logo)
    return result

def compose_frame(player_image_path, output_filename, hook_text="", caption_text="", force_colour=None):
    img = Image.open(player_image_path).convert("RGB")
    img = prepare_image(img)
    img = apply_brand_overlay(img, hook_text=hook_text, caption_text=caption_text)
    img = add_watermark(img)
    out_path = str(OUTPUT_DIR / output_filename)
    img.convert("RGB").save(out_path, "PNG", quality=95)
    print(f"[compositor] Saved: {out_path}")
    return out_path

def build_outro_card():
    img = Image.new("RGB", (FRAME_W, FRAME_H), (8, 8, 8))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, FRAME_W, BAR_H], fill=MINT)
    draw.rectangle([0, FRAME_H - BAR_H, FRAME_W, FRAME_H], fill=MINT)
    cx = FRAME_W // 2; cy = FRAME_H // 2
    draw.rectangle([cx - 120, cy - 160, cx + 120, cy - 154], fill=MINT)
    draw.text((cx, cy - 100), "FOLLOW FOR DAILY TAKES", font=_font(48, bold=False), fill=MINT, anchor="mm")
    draw.text((cx, cy + 10), "@90minwaffle", font=_font(100), fill=WHITE, anchor="mm")
    draw.rectangle([cx - 120, cy + 80, cx + 120, cy + 86], fill=MINT)
    draw.text((cx, cy + 130), "Football. Opinion. No filter.", font=_font(40, bold=False), fill=(180, 180, 180), anchor="mm")
    draw.rectangle([0, FRAME_H - BAR_H - LOGO_BAR_H, FRAME_W, FRAME_H - BAR_H], fill=(20, 20, 20))
    draw.text((cx, FRAME_H - BAR_H - LOGO_BAR_H // 2 - 8), "90min", font=_font(48), fill=WHITE, anchor="mm")
    draw.text((cx, FRAME_H - BAR_H - LOGO_BAR_H // 2 + 30), "Waffle", font=_font(32, bold=False), fill=MINT, anchor="mm")
    result = add_watermark(img.convert("RGBA"))
    out_path = str(OUTRO_PATH)
    result.convert("RGB").save(out_path, "PNG")
    print(f"[compositor] Outro card saved: {out_path}")
    return out_path

if __name__ == "__main__":
    print("[compositor] Building outro card...")
    build_outro_card()
    print("[compositor] Done.")
