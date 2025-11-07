# merge_videos_cli.py
import sys
import os
import argparse
import numpy as np
import requests

from moviepy import VideoFileClip, concatenate_videoclips, CompositeVideoClip, vfx
from moviepy.video.VideoClip import ImageClip
from PIL import Image, ImageDraw, ImageFont


# ---------- Helpers: drawing ----------
def _rounded_box_rgba(width, height, radius=24, rgba=(50, 50, 50, 180)):
    """Return an RGBA numpy array of a rounded rectangle (all dims cast to int)."""
    w = max(1, int(round(width)))
    h = max(1, int(round(height)))
    r = max(0, int(round(radius)))

    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([(0, 0), (w, h)], radius=r, fill=rgba)
    return np.array(img).astype("uint8")


def _wrap_to_width(text, font, max_width, draw):
    """Greedy wrap to fit within max_width (pixels)."""
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
    """'#RRGGBB' -> (R, G, B)."""
    try:
        s = s.strip()
        if s.startswith("#"):
            s = s[1:]
        if len(s) == 6:
            return tuple(int(s[i:i+2], 16) for i in (0, 2, 4))
    except Exception:
        pass
    return default


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
        # Scale so the longer side == size
        scale = size / max(w, h)
        new_w = int(round(w * scale))
        new_h = int(round(h * scale))
        resized = clip.with_effects([vfx.Resize((new_w, new_h))])

        # Square background
        bg_arr = np.zeros((size, size, 3), dtype=np.uint8)
        bg_arr[:, :] = np.array(bg_color, dtype=np.uint8)
        bg = ImageClip(bg_arr).with_duration(clip.duration)

        return CompositeVideoClip(
            [bg, resized.with_position(("center", "center"))],
            size=(size, size)
        )

    else:  # 'crop'
        # Scale so the *shorter* side == size (no letterboxing)
        scale = size / min(w, h)
        new_w = int(round(w * scale))
        new_h = int(round(h * scale))
        resized = clip.with_effects([vfx.Resize((new_w, new_h))])

        # Place centered on a square canvas; extra area is cropped
        return CompositeVideoClip(
            [resized.with_position(("center", "center"))],
            size=(size, size)
        )


# ---------- Bottom textbox overlay ----------
def _make_bottom_textbox_overlay(frame_size, text, duration, font_size=90,
                                 text_color=(255, 255, 255, 255), box_rgba=(50, 50, 50, 180),
                                 radius=24, padding=32, max_width_px=None, bottom_margin=60):
    """
    Build a full-frame overlay with a horizontally centered rounded textbox near the bottom.
    Geometry cast to int to satisfy Pillow.
    """
    W, H = int(frame_size[0]), int(frame_size[1])
    font_size = int(font_size)
    padding = int(padding)
    radius = int(radius)
    bottom_margin = int(bottom_margin)
    max_width_px = int(max_width_px) if max_width_px else None

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
    text_w = int(bbox[2] - bbox[0])
    text_h = int(bbox[3] - bbox[1])

    # Metrics for safe padding and visual balance
    try:
        ascent, descent = font.getmetrics()
        ascent, descent = int(ascent), int(descent)
    except Exception:
        ascent, descent = font_size, int(round(font_size * 0.25))

    extra_bottom = max(12, descent + 8)
    upward_shift = max(6, descent // 2)

    box_w = int(text_w + padding * 2)
    box_h = int(text_h + padding * 2 + extra_bottom)

    # Rounded background
    bg_arr = _rounded_box_rgba(box_w, box_h, radius=radius, rgba=box_rgba)

    # Render centered text inside the box
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

    # Convert to clips
    y_pos = int(H - box_h - bottom_margin)
    box_clip = ImageClip(bg_arr).with_duration(duration).with_position(("center", y_pos))
    txt_clip = ImageClip(np.array(canvas).astype("uint8")).with_duration(duration).with_position(("center", y_pos))

    return CompositeVideoClip([box_clip, txt_clip], size=(W, H)).with_duration(duration)


# ---------- Upload (WebDAV) ----------
def _ensure_trailing_slash(url: str) -> str:
    return url if url.endswith("/") else url + "/"

def upload_webdav_authenticated(
    base_url: str, username: str, password: str, local_path: str, remote_path: str
) -> str:
    """
    Upload using authenticated WebDAV:
      PUT https://<host>/remote.php/dav/files/<username>/<remote_path>
    Creates intermediate directories via MKCOL if needed.
    Returns the WebDAV file URL.
    """
    base_url = base_url.rstrip("/")
    webdav_root = f"{base_url}/remote.php/dav/files/{username}"
    webdav_root = _ensure_trailing_slash(webdav_root)

    # Create directories (MKCOL) for remote_path
    remote_path = remote_path.lstrip("/")
    parts = remote_path.split("/")
    if len(parts) > 1:
        cur = webdav_root
        for d in parts[:-1]:
            cur = _ensure_trailing_slash(cur + d)
            r = requests.request("MKCOL", cur, auth=(username, password))
            if r.status_code not in (201, 405, 301, 302):  # 405 = exists
                raise RuntimeError(f"MKCOL failed for {cur} (status {r.status_code}): {r.text}")

    # PUT the file
    target_url = webdav_root + remote_path
    with open(local_path, "rb") as f:
        r = requests.put(target_url, data=f, auth=(username, password))
    if r.status_code not in (200, 201, 204):
        raise RuntimeError(f"Upload failed (status {r.status_code}): {r.text}")
    return target_url

def upload_webdav_public(
    base_url: str, share_token: str, local_path: str, remote_filename: str, share_password: str | None = None
) -> str:
    """
    Upload into a public share (ONLY if upload is enabled for that share):
      PUT https://<host>/public.php/webdav/<remote_filename>
    Auth = (share_token, share_password or "")
    Returns public WebDAV URL (not the pretty /s/<token> URL).
    """
    base_url = base_url.rstrip("/")
    url = f"{base_url}/public.php/webdav/{remote_filename.lstrip('/')}"
    auth = (share_token, share_password or "")
    with open(local_path, "rb") as f:
        r = requests.put(url, data=f, auth=auth)
    if r.status_code not in (200, 201, 204):
        raise RuntimeError(f"Public upload failed (status {r.status_code}): {r.text}")
    return url


# ---------- Video pipeline ----------
def concatenate_videos(video1, video2, video3, texts, output_file,
                       fade_duration=1.0, font_size=90,
                       square_size=1080, fit="crop", bg_color=(0, 0, 0),
                       bottom_margin=60):
    """
    Merge three videos and export a square (1:1) final.
    - All clips are converted to square with _to_square().
    - On video2, show three bottom-anchored, centered textboxes (each 1/3 duration).
    """
    video_files = [video1, video2, video3]
    clips = []
    final = None

    try:
        for i, file in enumerate(video_files):
            base = VideoFileClip(file)

            # Convert each base clip to square first (so overlays use square coords)
            sq_base = _to_square(base, size=square_size, fit=fit, bg_color=bg_color)

            if i == 1:
                W = H = int(square_size)
                third = sq_base.duration / 3.0
                max_w = int(W * 0.8)
                txt_fade = min(0.6, third / 4.0)

                overlays = []
                for idx, message in enumerate(texts):
                    start_t = idx * third
                    overlay = _make_bottom_textbox_overlay(
                        (W, H), message, third, font_size=font_size,
                        text_color=(255, 255, 255, 255), box_rgba=(50, 50, 50, 180),
                        radius=24, padding=32, max_width_px=max_w, bottom_margin=bottom_margin
                    ).with_start(start_t).with_effects([vfx.FadeIn(txt_fade), vfx.FadeOut(txt_fade)])
                    overlays.append(overlay)

                # Compose overlays over the squared base
                sq_base = CompositeVideoClip([sq_base, *overlays], size=(W, H))

            # Crossfades between squared clips
            if i > 0:
                sq_base = sq_base.with_effects([vfx.CrossFadeIn(fade_duration)])
            if i < len(video_files) - 1:
                sq_base = sq_base.with_effects([vfx.CrossFadeOut(fade_duration)])

            clips.append(sq_base)

        # Overlap for crossfades, export square
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
        description="Merge three videos to a 1:1 square output; add 3 bottom textboxes on video2; upload to Nextcloud via WebDAV."
    )
    # Inputs
    p.add_argument("video1")
    p.add_argument("video2")
    p.add_argument("video3")
    p.add_argument("text1")
    p.add_argument("text2")
    p.add_argument("text3")
    # Output render
    p.add_argument("-o", "--output", default="merged_video.mp4")
    p.add_argument("--fade", type=float, default=1.0)
    p.add_argument("--fontsize", type=int, default=90)
    p.add_argument("--size", type=int, default=1080, help="Square output size (e.g., 1080)")
    p.add_argument("--fit", choices=["crop", "pad"], default="crop", help="Square conversion: crop or pad")
    p.add_argument("--bg", default="#000000", help="Background color for pad mode, hex like #000000")
    p.add_argument("--bottom", type=int, default=60, help="Bottom margin in px for the textbox")

    # Upload options (authenticated)
    p.add_argument("--upload", action="store_true", help="Upload the rendered file via authenticated WebDAV")
    p.add_argument("--webdav-base", default="https://cloud.targethouse.dk", help="Base URL of Nextcloud (no trailing slash)")
    p.add_argument("--webdav-user", help="WebDAV username")
    p.add_argument("--webdav-pass", help="WebDAV password")
    p.add_argument("--remote-path", help="Remote path under your account (e.g., 'Videos/merged_video.mp4'). Defaults to output filename at root.")

    # Public share token upload (optional alternative)
    p.add_argument("--public-token", help="Public share token (if uploading into a public share)")
    p.add_argument("--public-pass", help="Public share password (optional)")
    p.add_argument("--public-name", help="Filename to use in the public share (default: output filename)")

    return p.parse_args(argv)


if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    bg_color = _parse_hex_color(args.bg, default=(0, 0, 0))
    texts = [args.text1, args.text2, args.text3]

    # 1) Render
    concatenate_videos(
        args.video1, args.video2, args.video3,
        texts, args.output,
        fade_duration=args.fade, font_size=args.fontsize,
        square_size=args.size, fit=args.fit, bg_color=bg_color,
        bottom_margin=args.bottom
    )

    # 2) Upload (if requested)
    if args.upload:
        local_file = args.output
        if not os.path.exists(local_file):
            print(f"[ERROR] Rendered file not found: {local_file}")
            sys.exit(2)

        # Prefer authenticated upload if creds provided
        if args.webdav_user and args.webdav_pass:
            remote_path = args.remote_path or os.path.basename(local_file)
            try:
                url = upload_webdav_authenticated(
                    base_url=args.webdav_base,
                    username=args.webdav_user,
                    password=args.webdav_pass,
                    local_path=local_file,
                    remote_path=remote_path,
                )
                print(f"✅ Uploaded via WebDAV (authenticated): {url}")
                print("Note: That is the WebDAV URL. For a share link, create a public share in Nextcloud UI.")
            except Exception as e:
                print(f"[ERROR] Authenticated WebDAV upload failed: {e}")
                sys.exit(3)

        # Or: public share token upload (if provided and share allows uploads)
        elif args.public_token:
            public_name = args.public_name or os.path.basename(local_file)
            try:
                url = upload_webdav_public(
                    base_url=args.webdav_base,
                    share_token=args.public_token,
                    local_path=local_file,
                    remote_filename=public_name,
                    share_password=args.public_pass,
                )
                print(f"✅ Uploaded to public share WebDAV: {url}")
                print("Tip: The corresponding share page is usually at /s/<token> (if enabled).")
            except Exception as e:
                print(f"[ERROR] Public WebDAV upload failed: {e}")
                sys.exit(4)

        else:
            print("[INFO] --upload was set, but no credentials or public token provided; skipping upload.")


