"""
ffmpeg_assembler.py — Video assembly with branded outro + watermark
Drop into /root/90minwaffle/scripts/

Replaces or wraps whatever ffmpeg call you currently use in orchestrator.py.

Usage:
    from ffmpeg_assembler import assemble_video
    final_path = assemble_video(
        raw_video_path="/tmp/raw_story.mp4",
        composed_frame_path="/root/90minwaffle/composed/frame_001.png",
        audio_path="/tmp/tts_audio.mp3",
        output_path="/root/90minwaffle/output/final_001.mp4",
        caption_text="HE HASN'T WON IN FOUR. SOMEONE SAY IT."
    )
"""

import subprocess
import os
from pathlib import Path

BASE_DIR    = Path("/root/90minwaffle")
ASSETS_DIR  = BASE_DIR / "assets"
OUTRO_PATH  = ASSETS_DIR / "outro_card.png"
AUDIO_STING = ASSETS_DIR / "outro_sting.mp3"   # 3-second branded audio sting
OUTPUT_DIR  = BASE_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTRO_DURATION = 3   # seconds
FONT_PATH      = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _run(cmd: list[str], label: str):
    print(f"[ffmpeg] {label}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[ffmpeg] ERROR in {label}:\n{result.stderr}")
        raise RuntimeError(f"ffmpeg failed: {label}")
    return result


def assemble_video(
    raw_video_path: str,
    composed_frame_path: str,
    audio_path: str,
    output_path: str,
    caption_text: str = "",
    hook_text: str = "",
) -> str:
    """
    Full assembly pipeline:
    1. Composite the branded frame over the raw video (frame as border overlay)
    2. Burn captions + hook text
    3. Watermark overlay pass (corner logo)
    4. Append 3-second outro card
    5. Output final MP4

    Args:
        raw_video_path:     path to the raw story video (no branding)
        composed_frame_path: path to the composited frame PNG (from brand_compositor)
        audio_path:         TTS audio file
        output_path:        final output MP4 path
        caption_text:       burned-in caption (uppercase, bold)
        hook_text:          hook text shown at video start

    Returns:
        str: path to final output MP4
    """
    tmp_branded   = "/tmp/wfl_branded.mp4"
    tmp_captioned = "/tmp/wfl_captioned.mp4"
    tmp_watermarked = "/tmp/wfl_watermarked.mp4"
    tmp_outro     = "/tmp/wfl_outro.mp4"
    tmp_list      = "/tmp/wfl_concat.txt"
    watermark_img = str(ASSETS_DIR / "watermark_white.png")

    # ── Step 1: Overlay branded frame onto raw video ──────────────────────
    # The composed_frame_path is 1080x1920 with the slot transparent
    # We scale raw video to fit the slot, then composite the frame on top
    slot_w, slot_h = 864, 760
    slot_x, slot_y = 108, 560

    _run([
        "ffmpeg", "-y",
        "-i", raw_video_path,
        "-i", composed_frame_path,
        "-filter_complex",
        f"[0:v]scale={slot_w}:{slot_h}:force_original_aspect_ratio=increase,"
        f"crop={slot_w}:{slot_h}[vid];"
        f"[1:v][vid]overlay={slot_x}:{slot_y}[branded]",
        "-map", "[branded]",
        "-map", "0:a?" ,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac",
        tmp_branded
    ], "Brand frame overlay")

    # ── Step 2: Burn captions and hook text ───────────────────────────────
    vf_filters = []

    if hook_text:
        # Hook — top of frame, large, mint green
        safe_hook = hook_text.replace("'", "\\'").replace(":", "\\:")
        vf_filters.append(
            f"drawtext=fontfile={FONT_PATH}:text='{safe_hook}':"
            f"fontsize=52:fontcolor=0x00E87A:x=(w-text_w)/2:y=80:"
            f"box=1:boxcolor=black@0.6:boxborderw=12:"
            f"enable='between(t,0,2)'"
        )

    if caption_text:
        # Captions — lower third, white bold
        safe_cap = caption_text.replace("'", "\\'").replace(":", "\\:")
        vf_filters.append(
            f"drawtext=fontfile={FONT_PATH}:text='{safe_cap}':"
            f"fontsize=44:fontcolor=white:x=(w-text_w)/2:y=h*0.78:"
            f"box=1:boxcolor=black@0.75:boxborderw=10"
        )

    if vf_filters:
        vf_string = ",".join(vf_filters)
        _run([
            "ffmpeg", "-y",
            "-i", tmp_branded,
            "-vf", vf_string,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "copy",
            tmp_captioned
        ], "Burn captions")
    else:
        os.rename(tmp_branded, tmp_captioned)

    # ── Step 3: Corner watermark overlay ─────────────────────────────────
    if os.path.exists(watermark_img):
        _run([
            "ffmpeg", "-y",
            "-i", tmp_captioned,
            "-i", watermark_img,
            "-filter_complex",
            "overlay=main_w-overlay_w-40:main_h-overlay_h-80",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "copy",
            tmp_watermarked
        ], "Watermark overlay")
    else:
        print("[ffmpeg] No watermark_white.png found — skipping corner wm")
        os.rename(tmp_captioned, tmp_watermarked)

    # ── Step 4: Append TTS audio ─────────────────────────────────────────
    tmp_with_audio = "/tmp/wfl_audio.mp4"
    _run([
        "ffmpeg", "-y",
        "-i", tmp_watermarked,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-map", "0:v:0", "-map", "1:a:0",
        "-shortest",
        tmp_with_audio
    ], "Add TTS audio")

    # ── Step 5: Build outro card video (3 seconds) ────────────────────────
    if os.path.exists(str(OUTRO_PATH)):
        outro_audio = str(AUDIO_STING) if os.path.exists(str(AUDIO_STING)) else "anullsrc"

        if outro_audio == "anullsrc":
            _run([
                "ffmpeg", "-y",
                "-loop", "1",
                "-i", str(OUTRO_PATH),
                "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                "-t", str(OUTRO_DURATION),
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "aac", "-ar", "44100",
                "-pix_fmt", "yuv420p",
                tmp_outro
            ], "Build outro (silent)")
        else:
            _run([
                "ffmpeg", "-y",
                "-loop", "1",
                "-i", str(OUTRO_PATH),
                "-i", outro_audio,
                "-t", str(OUTRO_DURATION),
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "aac",
                "-pix_fmt", "yuv420p",
                tmp_outro
            ], "Build outro (with sting)")

        # ── Step 6: Concat main + outro ───────────────────────────────────
        with open(tmp_list, "w") as f:
            f.write(f"file '{tmp_with_audio}'\n")
            f.write(f"file '{tmp_outro}'\n")

        _run([
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", tmp_list,
            "-c", "copy",
            output_path
        ], "Concat main + outro")

    else:
        print("[ffmpeg] No outro card found — skipping concat")
        os.rename(tmp_with_audio, output_path)

    print(f"[ffmpeg] Final video: {output_path}")
    return output_path


def prepare_watermark_overlay(source_logo_path: str) -> str:
    """
    Convert the dark logo PNG to a white version for ffmpeg overlay.
    Saves to assets/watermark_white.png.
    Run once during setup.
    """
    from PIL import Image
    import numpy as np

    out_path = str(ASSETS_DIR / "watermark_white.png")
    img  = Image.open(source_logo_path).convert("RGBA")
    data = np.array(img)

    # Make non-transparent pixels white, set to 18% opacity
    mask = data[..., 3] > 10
    data[mask, 0] = 255
    data[mask, 1] = 255
    data[mask, 2] = 255
    data[mask, 3] = 45   # 18% opacity

    # Resize to corner size
    result = Image.fromarray(data)
    result = result.resize((160, int(160 * img.height / img.width)), Image.LANCZOS)
    result.save(out_path, "PNG")
    print(f"[ffmpeg] Watermark overlay saved: {out_path}")
    return out_path


if __name__ == "__main__":
    # Generate the white watermark from Image 1
    logo_src = str(ASSETS_DIR / "watermark.png")
    if os.path.exists(logo_src):
        prepare_watermark_overlay(logo_src)
    else:
        print(f"[ffmpeg] Place your watermark logo at: {logo_src}")
