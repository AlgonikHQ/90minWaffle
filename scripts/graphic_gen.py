import os
import textwrap
import sqlite3
import urllib.request
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timezone

DB_PATH = "/root/90minwaffle/data/waffle.db"
ASSETS_DIR = "/root/90minwaffle/assets"
OUTPUT_DIR = "/root/90minwaffle/data"

# Brand colours from spec
NAVY      = (14, 30, 58)       # #0E1E3A
WHITE     = (255, 255, 255)    # #FFFFFF
RED       = (230, 57, 70)      # #E63946
GREEN     = (0, 255, 135)      # #00FF87
GREY      = (138, 153, 181)    # #8A99B5

# Vertical video dimensions (9:16)
W, H = 1080, 1920

def ensure_fonts():
    """Download fonts if not present."""
    fonts = {
        "Anton-Regular.ttf": "https://github.com/google/fonts/raw/main/ofl/anton/Anton-Regular.ttf",
        "Inter-Bold.ttf": "https://github.com/google/fonts/raw/main/ofl/inter/Inter%5Bslnt%2Cwght%5D.ttf",
    }
    os.makedirs(ASSETS_DIR, exist_ok=True)
    for fname, url in fonts.items():
        path = os.path.join(ASSETS_DIR, fname)
        if not os.path.exists(path):
            print(f"Downloading font: {fname}")
            try:
                urllib.request.urlretrieve(url, path)
                print(f"  ✅ {fname}")
            except Exception as e:
                print(f"  ⚠️  Could not download {fname}: {e}")

def load_font(name, size):
    path = os.path.join(ASSETS_DIR, name)
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()

def draw_gradient_bg(draw):
    """Navy gradient background."""
    for y in range(H):
        ratio = y / H
        r = int(NAVY[0] + (20 - NAVY[0]) * ratio * 0.3)
        g = int(NAVY[1] + (40 - NAVY[1]) * ratio * 0.2)
        b = int(NAVY[2] + (80 - NAVY[2]) * ratio * 0.15)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

def draw_watermark(draw, position="top-left"):
    """90minWaffle text watermark."""
    font = load_font("Anton-Regular.ttf", 36)
    text = "90minWaffle"
    if position == "top-left":
        x, y = 40, 50
    else:
        bbox = draw.textbbox((0, 0), text, font=font)
        x = W - (bbox[2] - bbox[0]) - 40
        y = H - 100
    # Semi-transparent effect via grey colour at 60% opacity approximation
    draw.text((x+2, y+2), text, font=font, fill=(0, 0, 0, 100))
    draw.text((x, y), text, font=font, fill=(*WHITE, 153))

def draw_accent_stripe(draw, colour=RED):
    """Horizontal accent stripe."""
    draw.rectangle([0, H//2 - 3, W, H//2 + 3], fill=colour)

def wrap_text(text, font, max_width, draw):
    """Wrap text to fit within max_width pixels."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines

def template_b_stat_card(story_id, title, hook, thumbnail_text, accent=RED):
    """
    Template B — Stat Card
    Big hook text + title descriptor + source attribution
    Used for F1, F2, F3, F4, F6
    """
    img = Image.new("RGB", (W, H), NAVY)
    draw = ImageDraw.Draw(img)

    draw_gradient_bg(draw)

    # Top accent bar
    draw.rectangle([0, 0, W, 8], fill=accent)

    # Watermark top-left
    wm_font = load_font("Anton-Regular.ttf", 38)
    draw.text((42, 62), "90minWaffle", font=wm_font, fill=(*WHITE, 153))

    # Format badge
    badge_font = load_font("Anton-Regular.ttf", 28)
    draw.rectangle([40, 120, 220, 160], fill=accent)
    draw.text((52, 124), "BREAKING", font=badge_font, fill=WHITE)

    # Main hook text — Anton, large, centred
    hook_font = load_font("Anton-Regular.ttf", 96)
    hook_lines = wrap_text(hook.upper(), hook_font, W - 80, draw)

    # Calculate total height for vertical centering
    line_h = 100
    total_h = len(hook_lines) * line_h
    start_y = (H // 2) - (total_h // 2) - 80

    for i, line in enumerate(hook_lines):
        bbox = draw.textbbox((0, 0), line, font=hook_font)
        lw = bbox[2] - bbox[0]
        x = (W - lw) // 2
        y = start_y + (i * line_h)
        # Shadow
        draw.text((x+3, y+3), line, font=hook_font, fill=(0, 0, 0))
        draw.text((x, y), line, font=hook_font, fill=WHITE)

    # Accent divider
    div_y = start_y + total_h + 20
    draw.rectangle([80, div_y, W - 80, div_y + 4], fill=accent)

    # Title descriptor — Inter, smaller
    desc_font = load_font("Anton-Regular.ttf", 48)
    desc_lines = wrap_text(title, desc_font, W - 100, draw)
    desc_y = div_y + 30
    for line in desc_lines[:3]:
        bbox = draw.textbbox((0, 0), line, font=desc_font)
        lw = bbox[2] - bbox[0]
        x = (W - lw) // 2
        draw.text((x, desc_y), line, font=desc_font, fill=GREY)
        desc_y += 58

    # Bottom CTA
    cta_font = load_font("Anton-Regular.ttf", 42)
    cta = "DROP YOUR TAKE BELOW 👇"
    bbox = draw.textbbox((0, 0), cta, font=cta_font)
    lw = bbox[2] - bbox[0]
    draw.text(((W - lw) // 2, H - 180), cta, font=cta_font, fill=accent)

    # Bottom accent bar
    draw.rectangle([0, H - 8, W, H], fill=accent)

    # Save
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, f"graphic_{story_id}.png")
    img.save(out_path, "PNG")
    print(f"✅ Graphic saved: {out_path}")
    return out_path

def template_g_hot_take(story_id, hook, accent=RED):
    """
    Template G — Hot Take Banner
    Full-frame text with red accent. Used for F7.
    """
    img = Image.new("RGB", (W, H), RED)
    draw = ImageDraw.Draw(img)

    # Dark overlay strips
    draw.rectangle([0, 0, W, 120], fill=NAVY)
    draw.rectangle([0, H - 120, W, H], fill=NAVY)

    # Watermark
    wm_font = load_font("Anton-Regular.ttf", 38)
    draw.text((42, 42), "90minWaffle", font=wm_font, fill=WHITE)

    # Big hook
    hook_font = load_font("Anton-Regular.ttf", 110)
    hook_lines = wrap_text(hook.upper(), hook_font, W - 60, draw)
    line_h = 116
    total_h = len(hook_lines) * line_h
    start_y = (H // 2) - (total_h // 2)

    for i, line in enumerate(hook_lines):
        bbox = draw.textbbox((0, 0), line, font=hook_font)
        lw = bbox[2] - bbox[0]
        x = (W - lw) // 2
        y = start_y + (i * line_h)
        draw.text((x+3, y+3), line, font=hook_font, fill=(0, 0, 0))
        draw.text((x, y), line, font=hook_font, fill=WHITE)

    out_path = os.path.join(OUTPUT_DIR, f"graphic_{story_id}.png")
    img.save(out_path, "PNG")
    print(f"✅ Hot Take graphic saved: {out_path}")
    return out_path

def generate_graphic(story_id, title, hook, thumbnail_text, fmt):
    ensure_fonts()
    accent = RED
    if fmt == "F7":
        return template_g_hot_take(story_id, hook, accent)
    elif fmt in ["F5"]:
        accent = GREEN
        return template_b_stat_card(story_id, title, hook, thumbnail_text, accent)
    else:
        return template_b_stat_card(story_id, title, hook, thumbnail_text, accent)

if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT id, title, winning_hook, format
        FROM stories WHERE status='scripted'
        ORDER BY score DESC LIMIT 1
    """)
    r = c.fetchone()
    conn.close()

    if r:
        story_id, title, hook, fmt = r
        thumbnail_text = title[:40]
        path = generate_graphic(story_id, title, hook, thumbnail_text, fmt)
        print(f"Generated: {path}")
    else:
        print("No scripted stories found.")
