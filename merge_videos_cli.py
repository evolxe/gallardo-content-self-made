# merge_videos_cli.py
import sys
import argparse
import numpy as np
from urllib.parse import unquote

from moviepy import VideoFileClip, concatenate_videoclips, CompositeVideoClip, vfx
from moviepy.video.VideoClip import ImageClip
from PIL import Image, ImageDraw, ImageFont

# ---------- Helpers ----------
def _rounded_box_rgba(width, height, radius=24, rgba=(50, 50, 50, 180)):
    w = max(1, int(round(width)))
    h = max(1, int(round(height)))
    r = max(0, int(round(radius)))
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([(0, 0), (w, h)], radius=r, fill=rgba)
    return np.array(img).astype("uint8")

def _wrap_to_width(text, font, max_width, draw):
    if not max_width:
        return text
    max_w = int(max_width)
    lines = []
    for para in text.split("\n"):
        words = para.split()
        if not words:
            lines.append("")
            continue
        line = words[0]
        for w in words[1:]:
            test = f"{line} {w}"
            if draw.textlength(test, font=font) <= max_w:
                line = test
            else:
                lines.append(line)
                line = w
        lines.append(line)
    return "\n".join(lines)

def _parse_hex_color(s, default=(0, 0, 0)):
    try:
        s = s.strip()
        if s.startswith("#"):
            s = s[1:]
        if len(s) == 6:
            return tuple(int(s[i:i+2], 16) for i in (0, 2, 4))
    except Exception:
        pass
    return default

def _to_square(clip, size=1080, fit="crop", bg_color=(0, 0, 0)):
    size = int(size)
    w, h = map(int, clip.size)
    if fit == "pad":
        scale = size / max(w, h)
        new_w = int(round(w * scale))
        new_h = int(round(h * scale))
        resized = clip.with_effects([vfx.Resize((new_w, new_h))])
        bg_arr = np.zeros((size, size, 3), dtype=np.uint8)
        bg_arr[:, :] = np.array(bg_color, dtype=np.uint8)
        bg = ImageClip(bg_arr).with_duration(clip.duration)
        return CompositeVideoClip([bg, resized.with_position(("center", "center"))], size=(size, size))
    else:
        scale = size / min(w, h)
        new_w = int(round(w * scale))
        new_h = int(round(h * scale))
        resized = clip.with_effects([vfx.Resize((new_w, new_h))])
        return CompositeVideoClip([resized.with_position(("center", "center"))], size=(size, size))

def _compute_xy_for_position(W, H, box_w, box_h, pos: str, margin: int) -> tuple:
    """
    Map strings like: bottom, bottom-left, bottom-right, top, top-left, top-right,
    center, center-left, center-right OR "x,y" numeric pixels.
    """
    s = (pos or "").strip().lower()
    if "," in s:
        parts = [p.strip() for p in s.split(",")]
        try:
            x = int(parts[0]); y = int(parts[1])
            return max(0, x), max(0, y)
        except Exception:
            pass

    # named positions
    if s in ("bottom", "bottom-center", "bottom middle"):
        return ("center", H - box_h - margin)
    if s in ("top", "top-center", "top middle"):
        return ("center", margin)
    if s in ("center", "middle", "centre"):
        return ("center", "center")
    if s in ("bottom-left", "left-bottom"):
        return (margin, H - box_h - margin)
    if s in ("bottom-right", "right-bottom"):
        return (W - box_w - margin, H - box_h - margin)
    if s in ("top-left", "left-top"):
        return (margin, margin)
    if s in ("top-right", "right-top"):
        return (W - box_w - margin, margin)
    if s in ("center-left", "left-center"):
        return (margin, (H - box_h) // 2)
    if s in ("center-right", "right-center"):
        return (W - box_w - margin, (H - box_h) // 2)

    # default
    return ("center", H - box_h - margin)

def _make_positioned_textbox_overlay(
    frame_size, text, duration, font_size=90,
    text_color=(255, 255, 255, 255), box_rgba=(50, 50, 50, 180),
    radius=24, padding=32, max_width_px=None, pos_str="bottom",
    margin=60
):
    """
    Build a full-frame overlay with a rounded textbox at a named or absolute position.
    """
    W, H = int(frame_size[0]), int(frame_size[1])
    font_size = int(font_size); padding = int(padding); radius = int(radius); margin = int(margin)
    max_width_px = int(max_width_px) if max_width_px else None

    text = unquote(text)

    # Load font
    try:
        font = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()

    # Measure & wrap
    probe_w = max_width_px if max_width_px else W
    probe_h = max(font_size * 12, 200)
    probe = Image.new("RGBA", (int(probe_w), int(probe_h)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(probe)

    wrapped = _wrap_to_width(text, font, max_width_px, draw)
    spacing = max(4, int(round(font_size * 0.2)))

    bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, align="center", spacing=spacing)
    text_w = int(bbox[2] - bbox[0]); text_h = int(bbox[3] - bbox[1])

    # Metrics/padding
    try:
        ascent, descent = font.getmetrics()
        ascent, descent = int(ascent), int(descent)
    except Exception:
        ascent, descent = font_size, int(round(font_size * 0.25))
    extra_bottom = max(12, descent + 8)
    upward_shift = max(6, descent // 2)

    box_w = int(text_w + padding * 2)
    box_h = int(text_h + padding * 2 + extra_bottom)

    # Background
    bg_arr = _rounded_box_rgba(box_w, box_h, radius=radius, rgba=box_rgba)

    # Text image
    canvas = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
    draw2 = ImageDraw.Draw(canvas)
    try:
        draw2.multiline_text(
            (box_w // 2, box_h // 2 - int(upward_shift)),
            wrapped, font=font, fill=text_color,
            align="center", spacing=spacing, anchor="mm"
        )
    except TypeError:
        tx = int((box_w - text_w) // 2)
        ty = int((box_h - text_h) // 2 - upward_shift)
        draw2.multiline_text((tx, ty), wrapped, font=font, fill=text_color, align="center", spacing=spacing)

    # Position
    x, y = _compute_xy_for_position(W, H, box_w, box_h, pos_str, margin)

    # Convert to clips
    box_clip = ImageClip(bg_arr).with_duration(duration).with_position((x, y) if isinstance(x, int) else (x, y))
    txt_clip = ImageClip(np.array(canvas).astype("uint8")).with_duration(duration).with_position((x, y) if isinstance(x, int) else (x, y))

    # Full-frame overlay
    return CompositeVideoClip([box_clip, txt_clip], size=(W, H)).with_duration(duration)

# ---------- Video pipeline ----------
def concatenate_videos(video1, video2, video3, texts, positions, output_file,
                       fade_duration=1.0, font_size=90,
                       square_size=1080, fit="crop", bg_color=(0, 0, 0),
                       bottom_margin=60):
    """
    Merge three videos and export a square (1:1) final.
    On video2, show three textboxes at per-segment positions (pos1/pos2/pos3).
    """
    video_files = [video1, video2, video3]
    clips = []
    final = None

    try:
        for i, file in enumerate(video_files):
            base = VideoFileClip(file)
            sq_base = _to_square(base, size=square_size, fit=fit, bg_color=bg_color)

            if i == 1:
                W = H = int(square_size)
                third = sq_base.duration / 3.0
                max_w = int(W * 0.8)
                txt_fade = min(0.6, third / 4.0)

                overlays = []
                for idx, message in enumerate(texts):
                    start_t = idx * third
                    pos_str = positions[idx] if idx < len(positions) else "bottom"
                    overlay = _make_positioned_textbox_overlay(
                        (W, H), message, third, font_size=font_size,
                        text_color=(255, 255, 255, 255), box_rgba=(50, 50, 50, 180),
                        radius=24, padding=32, max_width_px=max_w,
                        pos_str=pos_str, margin=bottom_margin
                    ).with_start(start_t).with_effects([vfx.FadeIn(txt_fade), vfx.FadeOut(txt_fade)])
                    overlays.append(overlay)

                sq_base = CompositeVideoClip([sq_base, *overlays], size=(W, H))

            if i > 0:
                sq_base = sq_base.with_effects([vfx.CrossFadeIn(fade_duration)])
            if i < len(video_files) - 1:
                sq_base = sq_base.with_effects([vfx.CrossFadeOut(fade_duration)])

            clips.append(sq_base)

        final = concatenate_videoclips(clips, padding=-fade_duration, method="compose")
        final.write_videofile(output_file, codec="libx264", audio_codec="aac")

    finally:
        for c in clips:
            try:
                c.close()
            except Exception:
                pass
        if final:
            try:
                final.close()
            except Exception:
                pass

# ---------- CLI ----------
def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Merge three videos to 1:1 and overlay 3 textboxes on video2 at per-segment positions."
    )
    p.add_argument("video1")
    p.add_argument("video2")
    p.add_argument("video3")
    p.add_argument("text1")
    p.add_argument("text2")
    p.add_argument("text3")
    p.add_argument("-o", "--output", default="merged_video.mp4")
    p.add_argument("--fade", type=float, default=1.0)
    p.add_argument("--fontsize", type=int, default=90)
    p.add_argument("--size", type=int, default=1080, help="Square output size (e.g., 1080)")
    p.add_argument("--fit", choices=["crop", "pad"], default="crop", help="Square conversion: crop or pad")
    p.add_argument("--bg", default="#000000", help="Background color for pad mode, hex like #000000")
    p.add_argument("--bottom", type=int, default=60, help="Margin used for bottom/edges placement")

    # Per-segment positions (named like 'bottom', 'top-left', 'center-right', or 'x,y')
    p.add_argument("--pos1", default="bottom", help="Textbox position for segment 1")
    p.add_argument("--pos2", default="bottom", help="Textbox position for segment 2")
    p.add_argument("--pos3", default="bottom", help="Textbox position for segment 3")

    return p.parse_args(argv)

if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    texts = [args.text1, args.text2, args.text3]
    positions = [args.pos1, args.pos2, args.pos3]
    concatenate_videos(
        args.video1, args.video2, args.video3,
        texts=texts, positions=positions,
        output_file=args.output,
        fade_duration=args.fade, font_size=args.fontsize,
        square_size=args.size, fit=args.fit,
        bottom_margin=args.bottom
    )


