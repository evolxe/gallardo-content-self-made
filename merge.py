# merge_videos_cli.py
import sys
import argparse
import os
import numpy as np

from moviepy import VideoFileClip, concatenate_videoclips, CompositeVideoClip, vfx
from moviepy.video.VideoClip import ImageClip
from PIL import Image, ImageDraw, ImageFont


# ---------- Helpers: geometry & drawing ----------

LOCATION_NAMES = {
    "top",
    "top-left",
    "top-right",
    "center",
    "center-left",
    "center-right",
    "bottom",
    "bottom-left",
    "bottom-right",
}


def _rounded_box_rgba(width, height, radius=24, rgba=(50, 50, 50, 180)):
    w = max(1, int(round(width)))
    h = max(1, int(round(height)))
    r = max(0, int(round(radius)))
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([(0, 0), (w, h)], radius=r, fill=rgba)
    return np.array(img).astype("uint8")


def _load_font(font_size):
    # Prefer MinionPro-Regular.otf in current dir; fall back to Windows fonts/default
    try:
        if os.path.exists("MinionPro-Regular.otf"):
            return ImageFont.truetype("MinionPro-Regular.otf", font_size)
    except Exception:
        pass

    candidate_fonts = [
        r"C:\Windows\Fonts\MinionPro-Regular.otf",
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\calibri.ttf",
        r"C:\Windows\Fonts\tahoma.ttf",
        r"C:\Windows\Fonts\verdana.ttf",
    ]
    for fp in candidate_fonts:
        try:
            if os.path.exists(fp):
                return ImageFont.truetype(fp, font_size)
        except Exception:
            continue

    return ImageFont.load_default()


def _wrap_to_width(text, font, max_width, draw):
    if not max_width:
        return text
    max_w = int(max_width)
    lines = []
    for para in str(text).split("\n"):
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


def _make_textbox_clip(
    text,
    duration,
    frame_size,
    location="bottom",
    font_size=90,
    box_color=(50, 50, 50, 180),
    text_color=(255, 255, 255, 255),
    padding=32,
    radius=24,
    max_width_frac=0.8,
    margin=40,
):
    """
    Build a small rounded textbox image (ImageClip) for given text and place it
    at 'location' within a frame of size frame_size (W, H).
    """
    W, H = int(frame_size[0]), int(frame_size[1])
    font_size = int(font_size)
    padding = int(padding)
    margin = int(margin)

    font = _load_font(font_size)

    probe_w = int(W * max_width_frac)
    probe_h = max(font_size * 10, 200)
    probe = Image.new("RGBA", (probe_w, probe_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(probe)

    wrapped = _wrap_to_width(text, font, probe_w - 2 * padding, draw)
    spacing = max(4, int(round(font_size * 0.2)))

    bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, align="center", spacing=spacing)
    text_w = int(bbox[2] - bbox[0])
    text_h = int(bbox[3] - bbox[1])

    try:
        ascent, descent = font.getmetrics()
        ascent, descent = int(ascent), int(descent)
    except Exception:
        ascent, descent = font_size, int(round(font_size * 0.25))

    extra_bottom = max(12, descent + 8)
    upward_shift = max(6, descent // 2)

    box_w = int(text_w + padding * 2)
    box_h = int(text_h + padding * 2 + extra_bottom)

    bg_arr = _rounded_box_rgba(box_w, box_h, radius=radius, rgba=box_color)

    # Render text centered inside the box
    canvas = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
    draw2 = ImageDraw.Draw(canvas)
    try:
        draw2.multiline_text(
            (box_w // 2, box_h // 2 - int(upward_shift)),
            wrapped,
            font=font,
            fill=text_color,
            align="center",
            spacing=spacing,
            anchor="mm",
        )
    except TypeError:
        tx = int((box_w - text_w) // 2)
        ty = int((box_h - text_h) // 2 - upward_shift)
        draw2.multiline_text(
            (tx, ty),
            wrapped,
            font=font,
            fill=text_color,
            align="center",
            spacing=spacing,
        )

    # Position in frame
    loc = (location or "bottom").strip().lower()
    if loc not in LOCATION_NAMES:
        loc = "bottom"

    box_w_i, box_h_i = box_w, box_h

    if loc == "top-left":
        x = margin
        y = margin
    elif loc == "top":
        x = (W - box_w_i) // 2
        y = margin
    elif loc == "top-right":
        x = W - box_w_i - margin
        y = margin
    elif loc == "center-left":
        x = margin
        y = (H - box_h_i) // 2
    elif loc == "center":
        x = (W - box_w_i) // 2
        y = (H - box_h_i) // 2
    elif loc == "center-right":
        x = W - box_w_i - margin
        y = (H - box_h_i) // 2
    elif loc == "bottom-left":
        x = margin
        y = H - box_h_i - margin
    elif loc == "bottom-right":
        x = W - box_w_i - margin
        y = H - box_h_i - margin
    else:  # "bottom"
        x = (W - box_w_i) // 2
        y = H - box_h_i - margin

    x = int(x)
    y = int(y)

    box_clip = ImageClip(bg_arr).with_duration(duration).with_position((x, y))
    txt_clip = ImageClip(np.array(canvas).astype("uint8")).with_duration(duration).with_position((x, y))

    return CompositeVideoClip([box_clip, txt_clip], size=(W, H)).with_duration(duration)


def _compute_overlay_position(frame_size, elem_size, location="top-right", margin=40):
    W, H = int(frame_size[0]), int(frame_size[1])
    w, h = int(elem_size[0]), int(elem_size[1])
    margin = int(margin)

    loc = (location or "top-right").strip().lower()
    if loc not in LOCATION_NAMES:
        loc = "top-right"

    if loc == "top-left":
        x = margin
        y = margin
    elif loc == "top":
        x = (W - w) // 2
        y = margin
    elif loc == "top-right":
        x = W - w - margin
        y = margin
    elif loc == "center-left":
        x = margin
        y = (H - h) // 2
    elif loc == "center":
        x = (W - w) // 2
        y = (H - h) // 2
    elif loc == "center-right":
        x = W - w - margin
        y = (H - h) // 2
    elif loc == "bottom-left":
        x = margin
        y = H - h - margin
    elif loc == "bottom-right":
        x = W - w - margin
        y = H - h - margin
    else:  # "bottom"
        x = (W - w) // 2
        y = H - h - margin

    return int(x), int(y)


# ---------- Square conversion (MoviePy v2 API) ----------

def _to_square(clip, size=1080, fit="crop", bg_color=(0, 0, 0)):
    """
    Convert any clip to a square (size x size) using MoviePy v2 effects.
    - fit='crop': scale so the shorter side == size, then center-crop via square canvas
    - fit='pad' : scale so the longer side == size, then pad with bg_color
    """
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

        return CompositeVideoClip(
            [bg, resized.with_position(("center", "center"))],
            size=(size, size),
        )

    # fit == "crop"
    scale = size / min(w, h)
    new_w = int(round(w * scale))
    new_h = int(round(h * scale))
    resized = clip.with_effects([vfx.Resize((new_w, new_h))])

    return CompositeVideoClip(
        [resized.with_position(("center", "center"))],
        size=(size, size),
    )


# ---------- Main video pipeline ----------

def concatenate_videos(
    video1,
    video2,
    video3,
    texts,
    text_locations,
    overlay_element_1,
    overlay_1_location,
    output_file,
    fade_duration=1.0,
    font_size=90,
    square_size=1080,
    fit="crop",
):
    video_files = [video1, video2, video3]
    clips = []
    final = None

    try:
        for i, file in enumerate(video_files):
            base = VideoFileClip(file)
            sq_base = _to_square(base, size=square_size, fit=fit, bg_color=(0, 0, 0))

            if i == 1:
                W, H = sq_base.size
                W, H = int(W), int(H)
                duration = sq_base.duration
                third = duration / 3.0
                txt_fade = min(0.6, third / 4.0)

                overlays = []

                # Three timed text segments at their respective locations
                for idx, message in enumerate(texts):
                    start_t = idx * third
                    loc = text_locations[idx] if idx < len(text_locations) else "bottom"
                    overlay = _make_textbox_clip(
                        text=message,
                        duration=third,
                        frame_size=(W, H),
                        location=loc,
                        font_size=font_size,
                        box_color=(50, 50, 50, 180),
                        text_color=(255, 255, 255, 255),
                        padding=32,
                        radius=24,
                        max_width_frac=0.8,
                        margin=40,
                    ).with_start(start_t).with_effects(
                        [vfx.FadeIn(txt_fade), vfx.FadeOut(txt_fade)]
                    )
                    overlays.append(overlay)

                # Overlay graphic element (across the whole of video2)
                if overlay_element_1 and os.path.exists(overlay_element_1):
                    elem_clip = ImageClip(overlay_element_1)
                    # scale overlay to max 25% of frame width
                    max_w = int(W * 0.25)
                    if elem_clip.w > max_w:
                        scale = max_w / float(elem_clip.w)
                        elem_clip = elem_clip.with_effects([vfx.Resize(scale)])
                    x, y = _compute_overlay_position(
                        (W, H),
                        elem_clip.size,
                        location=overlay_1_location,
                        margin=40,
                    )
                    elem_clip = elem_clip.with_duration(duration).with_position((x, y))
                    overlays.append(elem_clip)

                sq_base = CompositeVideoClip([sq_base, *overlays], size=(W, H))

            # Crossfades
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
        description="Merge three videos to a 1:1 square output; add 3 text boxes and one overlay graphic on video2."
    )
    p.add_argument("video1")
    p.add_argument("video2")
    p.add_argument("video3")
    p.add_argument("text1")
    p.add_argument("text2")
    p.add_argument("text3")
    p.add_argument("text1_location")
    p.add_argument("text2_location")
    p.add_argument("text3_location")
    p.add_argument("overlay_element_1")
    p.add_argument("overlay_1_location")
    p.add_argument("-o", "--output", default="merged_video.mp4")
    p.add_argument("--fade", type=float, default=1.0)
    p.add_argument("--fontsize", type=int, default=90)
    p.add_argument("--size", type=int, default=1080, help="Square output size (e.g., 1080)")
    p.add_argument("--fit", choices=["crop", "pad"], default="crop", help="Square conversion: crop or pad")
    return p.parse_args(argv)


if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    texts = [args.text1, args.text2, args.text3]
    text_locations = [args.text1_location, args.text2_location, args.text3_location]

    concatenate_videos(
        args.video1,
        args.video2,
        args.video3,
        texts=texts,
        text_locations=text_locations,
        overlay_element_1=args.overlay_element_1,
        overlay_1_location=args.overlay_1_location,
        output_file=args.output,
        fade_duration=args.fade,
        font_size=args.fontsize,
        square_size=args.size,
        fit=args.fit,
    )


