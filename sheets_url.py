# sheets_url.py
import sys
import os
import shlex
import subprocess
from typing import Any, Optional, List

import requests
import gspread
from google.oauth2.service_account import Credentials
from urllib.parse import quote

# ──────────────────────────────────────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────────────────────────────────────

# Google Sheet
SHEET_URL = "https://docs.google.com/spreadsheets/d/1yIZuIjtbQNVgQaY3OvDKDcpyQm90amiMSGHpfFwTTgI/edit?gid=0#gid=0"
WORKSHEET_NAME = "VideoMergeData"
SERVICE_ACCOUNT_FILE = "service-key-laserrens-video.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_DIR = os.path.join(SCRIPT_DIR, "temp_videos")
os.makedirs(TEMP_DIR, exist_ok=True)
VIDEO_SEARCH_DIRS = [
    os.getcwd(),
    SCRIPT_DIR,
    os.path.join(SCRIPT_DIR, "videos"),
]

# Render defaults (1:1 output, crop to square)
RENDER_SIZE = 1080
RENDER_FIT = "crop"   # "crop" or "pad"
DEFAULT_BOTTOM_MARGIN = 60
DEFAULT_FONT_SIZE = 90

# Browser-like header for HTTP
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    )
}

# ── Public share upload (DEFAULT path) ────────────────────────────────────────
# Public WebDAV endpoint: https://<host>/public.php/webdav/<FILENAME>
PUBLIC_SHARE_BASE = "https://cloud.targethouse.dk"
PUBLIC_SHARE_TOKEN = "8eHQ4ntJK4yS8ZW"   # new share token
PUBLIC_SHARE_PASSWORD = ""               # set if the share is password-protected
USE_PUBLIC_SHARE_UPLOAD = True           # default to public-share upload first

# ── Authenticated WebDAV (fallback) ───────────────────────────────────────────
# Authenticated WebDAV endpoint: https://<host>/remote.php/dav/files/<USER>/<PATH>
WEBDAV_BASE = "https://cloud.targethouse.dk"
WEBDAV_USER = "videoeditor"
WEBDAV_PASS = "4b@XxvxaqI717wO1"
WEBDAV_REMOTE_DIR = "Videos"             # remote subfolder for fallback

# ──────────────────────────────────────────────────────────────────────────────
# UTILITIES
# ──────────────────────────────────────────────────────────────────────────────

def truthy_generate(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    s = str(value).strip().lower()
    return s in {"true", "yes", "y", "1", "on"}

def is_url(s: str) -> bool:
    return isinstance(s, str) and (s.startswith("http://") or s.startswith("https://"))

def download_from_url(url: str) -> Optional[str]:
    try:
        filename = os.path.basename(url.split("?")[0]) or "tempfile"
        if "." not in filename:
            filename += ".mp4"
        dest = os.path.join(TEMP_DIR, filename)
        print(f"Downloading from URL: {url}")
        r = requests.get(url, headers=BROWSER_HEADERS, stream=True, timeout=45)
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        print(f"Downloaded to {dest}")
        return dest
    except Exception as e:
        sys.stderr.write(f"[URL Download Error] Could not fetch {url}:\n{e}\n")
        return None

def resolve_path(user_value: str) -> Optional[str]:
    if not user_value:
        return None
    val = user_value.strip().strip('"')
    if is_url(val):
        dl = download_from_url(val)
        return dl if dl and os.path.exists(dl) else None
    if os.path.isabs(val) and os.path.exists(val):
        return os.path.abspath(val)
    if os.path.exists(val):
        return os.path.abspath(val)
    for base in VIDEO_SEARCH_DIRS:
        candidate = os.path.abspath(os.path.join(base, val))
        if os.path.exists(candidate):
            return candidate
    return None

def quote_for_display(arg: str) -> str:
    return f'"{arg}"' if os.name == "nt" else shlex.quote(arg)

# ──────────────────────────────────────────────────────────────────────────────
# WEBDAV HELPERS (Public & Authenticated)
# ──────────────────────────────────────────────────────────────────────────────

def _ensure_trailing_slash(url: str) -> str:
    return url if url.endswith("/") else url + "/"

def _webdav_root(base: str, username: str) -> str:
    return _ensure_trailing_slash(base.rstrip("/") + f"/remote.php/dav/files/{username}")

def _mkcol_path_if_needed(base_root: str, remote_path: str, auth: tuple[str, str]) -> None:
    # Create folders via MKCOL (idempotent)
    if not remote_path:
        return
    parts = remote_path.strip("/").split("/")
    if len(parts) <= 1:
        return
    cur = base_root
    for d in parts[:-1]:
        cur = _ensure_trailing_slash(cur + d)
        r = requests.request("MKCOL", cur, auth=auth, headers=BROWSER_HEADERS, timeout=30)
        if r.status_code not in (201, 405, 301, 302):
            raise RuntimeError(f"MKCOL failed for {cur} (status {r.status_code}): {r.text}")

def upload_webdav_authenticated(
    base_url: str,
    username: str,
    password: str,
    local_path: str,
    remote_path: str,
) -> str:
    if not os.path.exists(local_path):
        raise FileNotFoundError(local_path)
    base_root = _webdav_root(base_url, username)
    auth = (username, password)
    _mkcol_path_if_needed(base_root, remote_path, auth=auth)
    target_url = base_root + remote_path.lstrip("/")
    with open(local_path, "rb") as f:
        r = requests.put(target_url, data=f, auth=auth, headers=BROWSER_HEADERS, timeout=180)
    if r.status_code not in (200, 201, 204):
        raise RuntimeError(f"Upload failed (status {r.status_code}): {r.text}")
    return target_url

def upload_webdav_public(
    base_url: str,
    share_token: str,
    local_path: str,
    remote_filename: str,
    share_password: Optional[str] = None,
) -> str:
    """
    PUT to: <base>/public.php/webdav/<remote_filename>
    Auth: (share_token, share_password or "")
    Returns the public WebDAV URL (not the /s/ page).
    """
    if not os.path.exists(local_path):
        raise FileNotFoundError(local_path)
    url = base_url.rstrip("/") + "/public.php/webdav/" + remote_filename.lstrip("/")
    auth = (share_token, share_password or "")
    with open(local_path, "rb") as f:
        r = requests.put(url, data=f, auth=auth, headers=BROWSER_HEADERS, timeout=180)
    if r.status_code not in (200, 201, 204):
        raise RuntimeError(f"Public upload failed (status {r.status_code}): {r.text}")
    return url

def build_public_download_url(base_url: str, token: str, filename: str) -> str:
    """
    Typical direct download link for a file inside a public share:
    <base>/s/<token>/download?path=/&files=<urlencoded_filename>
    """
    return f"{base_url.rstrip('/')}/s/{token}/download?path=/&files={quote(filename)}"

# ──────────────────────────────────────────────────────────────────────────────
# MAIN WORKFLOW
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    # Google auth
    try:
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        client = gspread.authorize(creds)
    except Exception as e:
        sys.stderr.write(f"[Auth Error] Could not authorize service account:\n{e}\n")
        sys.exit(1)

    # Open sheet
    try:
        sheet = client.open_by_url(SHEET_URL)
        ws = sheet.worksheet(WORKSHEET_NAME)
    except Exception as e:
        sys.stderr.write(f"[Open Error] Could not open Google Sheet or worksheet '{WORKSHEET_NAME}':\n{e}\n")
        sys.exit(1)

    # Read rows
    try:
        rows = ws.get_all_records()
    except Exception as e:
        sys.stderr.write(f"[Read Error] Failed to read worksheet data:\n{e}\n")
        sys.exit(1)

    headers = ws.row_values(1)
    # Required columns
    required_columns = [
        "Generate",
        "Video File Name",
        "Intro Video File Name/URL",
        "Exit Video File Name/URL",
        "Video Text 1",
        "Video Text 2",
        "Video Text 3",
        # New: positions for each text segment on video2
        "Text 1 Location",
        "Text 2 Location",
        "Text 3 Location",
    ]
    for col in required_columns:
        if col not in headers:
            # Allow missing location columns; we'll default later
            if "Location" in col:
                continue
            sys.stderr.write(f"[Error] No '{col}' column found in the sheet header.\n")
            sys.exit(1)

    # Ensure "Download URL" column exists (create if missing)
    if "Download URL" not in headers:
        try:
            col_index_new = len(headers) + 1
            ws.update_cell(1, col_index_new, "Download URL")
            headers = ws.row_values(1)  # refresh
            print('Added "Download URL" column.')
        except Exception as e:
            sys.stderr.write(f'[Warn] Could not create "Download URL" column automatically: {e}\n')

    generate_col_index = headers.index("Generate") + 1
    download_col_index = headers.index("Download URL") + 1 if "Download URL" in headers else None

    any_executed = False

    for idx, row in enumerate(rows, start=2):
        if not truthy_generate(row.get("Generate")):
            continue

        video2_val = str(row.get("Video File Name", "")).strip()
        intro_val  = str(row.get("Intro Video File Name/URL", "")).strip()
        exit_val   = str(row.get("Exit Video File Name/URL", "")).strip()
        text1      = str(row.get("Video Text 1", "")).strip()
        text2      = str(row.get("Video Text 2", "")).strip()
        text3      = str(row.get("Video Text 3", "")).strip()
        pos1       = str(row.get("Text 1 Location", "")).strip() or "bottom"
        pos2       = str(row.get("Text 2 Location", "")).strip() or "bottom"
        pos3       = str(row.get("Text 3 Location", "")).strip() or "bottom"

        if not video2_val or not intro_val or not exit_val:
            sys.stderr.write(f"[Row {idx}] Skipping: missing one or more required file fields.\n")
            continue

        intro_path = resolve_path(intro_val)
        main_path  = resolve_path(video2_val)
        exit_path  = resolve_path(exit_val)

        missing: List[str] = []
        if not intro_path: missing.append(f"Intro '{intro_val}'")
        if not main_path:  missing.append(f"Video2 '{video2_val}'")
        if not exit_path:  missing.append(f"Exit '{exit_val}'")
        if missing:
            sys.stderr.write(f"[Row {idx}] Skipping: could not find file(s): {', '.join(missing)}\n"
                             f"  Searched: {', '.join(VIDEO_SEARCH_DIRS)}\n")
            continue

        any_executed = True

        # Derive output filename based on video2 basename
        base_filename = os.path.basename(main_path)
        filename_no_ext, _ = os.path.splitext(base_filename)
        output_file = f"{filename_no_ext}_merged.mp4"

        # ── Render (no upload flags here) ─────────────────────────────────────
        cmd_parts = [
            sys.executable,
            "merge_videos_cli.py",
            intro_path,
            main_path,
            exit_path,
            text1, text2, text3,
            "-o", output_file,
            "--size", str(RENDER_SIZE),
            "--fit", RENDER_FIT,
            "--fontsize", str(DEFAULT_FONT_SIZE),
            # per-segment positions for video2 textboxes:
            "--pos1", pos1,
            "--pos2", pos2,
            "--pos3", pos3,
            # optional: set bottom margin globally if any "bottom" placement is used
            "--bottom", str(DEFAULT_BOTTOM_MARGIN),
        ]
        display_cmd = " ".join(quote_for_display(a) for a in cmd_parts)
        print(f"Executing: {display_cmd}")

        try:
            subprocess.run(cmd_parts, check=True)
            print(f"Row {idx}: Rendered → {output_file}")
        except subprocess.CalledProcessError as e:
            sys.stderr.write(f"[Row {idx}] merge_videos_cli.py failed for '{os.path.basename(main_path)}' "
                             f"(exit {e.returncode}).\n")
            continue  # do not flip Generate on render failure

        # ── Upload: try PUBLIC first, then AUTH fallback ──────────────────────
        download_url_to_write = None
        try:
            remote_name = output_file  # filename as stored remotely
            if USE_PUBLIC_SHARE_UPLOAD:
                print("Uploading to PUBLIC share (WebDAV)…")
                public_webdav_url = upload_webdav_public(
                    base_url=PUBLIC_SHARE_BASE,
                    share_token=PUBLIC_SHARE_TOKEN,
                    local_path=output_file,
                    remote_filename=remote_name,
                    share_password=PUBLIC_SHARE_PASSWORD or None,
                )
                print(f"Public upload complete: {public_webdav_url}")
                # Build a direct downloadable URL via public share
                download_url_to_write = build_public_download_url(PUBLIC_SHARE_BASE, PUBLIC_SHARE_TOKEN, remote_name)
            else:
                raise RuntimeError("Public upload disabled by config; forcing authenticated fallback.")
        except Exception as e_pub:
            sys.stderr.write(f"[Row {idx}] Public upload failed: {e_pub}\n")
            # Authenticated fallback
            try:
                remote_path = remote_name
                if WEBDAV_REMOTE_DIR:
                    remote_path = f"{WEBDAV_REMOTE_DIR.strip('/')}/{remote_name}"
                print("Uploading via AUTHENTICATED WebDAV fallback…")
                auth_url = upload_webdav_authenticated(
                    base_url=WEBDAV_BASE,
                    username=WEBDAV_USER,
                    password=WEBDAV_PASS,
                    local_path=output_file,
                    remote_path=remote_path,
                )
                print(f"Authenticated upload complete: {auth_url}")
                # We do NOT auto-create a share via OCS here; write the WebDAV URL as-is
                # (If you want auto-share creation via OCS, say the word and I'll add it.)
                download_url_to_write = auth_url
            except Exception as e_auth:
                sys.stderr.write(f"[Row {idx}] Authenticated upload also failed:\n{e_auth}\n")
                # Do NOT flip Generate if both uploads failed
                continue

        # ── Flip Generate to FALSE and write Download URL ─────────────────────
        try:
            ws.update_cell(idx, generate_col_index, "FALSE")
            print(f"Row {idx}: Updated 'Generate' → FALSE")
        except Exception as e:
            sys.stderr.write(f"[Row {idx}] Failed to update 'Generate' cell:\n{e}\n")

        if download_col_index and download_url_to_write:
            try:
                ws.update_cell(idx, download_col_index, download_url_to_write)
                print(f"Row {idx}: Wrote Download URL → {download_url_to_write}")
            except Exception as e:
                sys.stderr.write(f"[Row {idx}] Failed to write Download URL:\n{e}\n")

    if not any_executed:
        print("No rows processed (either Generate!=TRUE or files missing).")

# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    main()


