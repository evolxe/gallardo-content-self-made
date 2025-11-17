# sheets_url.py
import sys
import os
import shlex
import subprocess
import time
import re
from typing import Any, Optional, List

import requests
import gspread
from google.oauth2.service_account import Credentials

from config import BASE_DIR, get_env
from validation import validate_nextcloud_url, normalize_nextcloud_url, is_nextcloud_url

# ─────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────

SCRIPT_DIR = str(BASE_DIR)

SHEET_URL = get_env("SHEET_URL")
WORKSHEET_NAME = os.environ.get("WORKSHEET_NAME", "VideoMergeData")
SERVICE_ACCOUNT_FILE = get_env("SERVICE_ACCOUNT_FILE")
if not os.path.isabs(SERVICE_ACCOUNT_FILE):
    SERVICE_ACCOUNT_FILE = os.path.join(SCRIPT_DIR, SERVICE_ACCOUNT_FILE)
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def get_temp_dir() -> str:
    """
    Determine the appropriate temp directory based on environment.
    - On SSH/server: Use /tmp for better performance and automatic cleanup
    - On local development: Use temp_videos/ folder relative to script
    """
    # Check if we're on a server/SSH environment
    # Indicators: SSH_CONNECTION env var, or running in /home/ or /var/ directories
    is_server = (
        os.environ.get("SSH_CONNECTION") is not None
        or os.environ.get("SSH_CLIENT") is not None
        or os.environ.get("SSH_TTY") is not None
        or os.getcwd().startswith(("/home/", "/var/", "/opt/"))
    )

    if is_server:
        # On server: use /tmp with a subdirectory for our files
        temp_base = "/tmp/gallardo-video-pipeline"
        os.makedirs(temp_base, exist_ok=True)
        return temp_base
    else:
        # Local development: use temp_videos/ folder
        temp_dir = os.path.join(SCRIPT_DIR, "temp_videos")
        os.makedirs(temp_dir, exist_ok=True)
        return temp_dir


TEMP_DIR = get_temp_dir()
print(f"[Config] Using temp directory: {TEMP_DIR}")

VIDEO_SEARCH_DIRS = [
    TEMP_DIR,  # First check temp directory (where downloads go)
    os.getcwd(),
    SCRIPT_DIR,
    os.path.join(SCRIPT_DIR, "videos"),
]

# Render defaults
RENDER_SIZE = 1080
RENDER_FIT = "crop"  # or "pad"

# Font size: Calculate as percentage of video height for configurability.
# Allow override via env var GALLARDO_FONT_SIZE_PERCENT (e.g., 0.08334 for 90px at 1080p).
# Default: 90px (original size) = 90/1080 ≈ 0.08334 (8.33% of video height)
_font_pct_env = os.environ.get("GALLARDO_FONT_SIZE_PERCENT")
try:
    FONT_SIZE_PERCENT = (
        float(_font_pct_env) if _font_pct_env else 0.08334
    )  # default ≈8.33% = 90px for 1080p (original size)
except Exception:
    FONT_SIZE_PERCENT = 0.08334
# Clamp sane bounds 0.05..0.3
if FONT_SIZE_PERCENT < 0.05:
    FONT_SIZE_PERCENT = 0.05
if FONT_SIZE_PERCENT > 0.3:
    FONT_SIZE_PERCENT = 0.3
FONT_SIZE = max(24, int(RENDER_SIZE * FONT_SIZE_PERCENT))

# Browser-like header for HTTP
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    )
}

# Nextcloud auth for WebDAV + OCS
NC_BASE = get_env("NC_BASE")
NC_USER = get_env("NC_USER")
NC_PASS = get_env("NC_PASS")
NC_REMOTE_DIR = os.environ.get(
    "NC_REMOTE_DIR", "Videos"
)  # remote folder for uploads, e.g. "Videos"


# ─────────────────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────────────────


def truthy_generate(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False

    s = _coerce_cell_value(value).strip().lower()
    return s in {"true", "yes", "y", "1", "on"}


def is_url(s: str) -> bool:
    return isinstance(s, str) and (s.startswith("http://") or s.startswith("https://"))


VALID_LOCATIONS = {
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


def _coerce_cell_value(value: Any) -> str:
    """
    Normalize values coming from dropdowns or objects (dicts) to a plain string.
    """
    if isinstance(value, dict):
        # Common keys returned by Sheets API or data validation objects
        for key in ("value", "effectiveValue", "userEnteredValue"):
            if key in value:
                inner = value[key]
                if isinstance(inner, dict):
                    for inner_key in ("stringValue", "effectiveValue"):
                        if inner_key in inner:
                            inner_val = inner[inner_key]
                            if isinstance(inner_val, str):
                                return inner_val
                    continue
                if inner is not None:
                    return str(inner)
    return "" if value is None else str(value)


def normalize_location(raw_value: Any, *, default: str) -> str:
    """
    Accept user-friendly dropdown labels (e.g., 'Top Center') and convert them
    to the canonical merge.py values (e.g., 'top').
    """
    value = _coerce_cell_value(raw_value).strip()
    if not value:
        return default

    original_value = value
    value = value.lower()
    # Replace underscores and multiple spaces with hyphens for consistent parsing
    value = value.replace("_", "-")
    value = re.sub(r"\s+", "-", value)

    # Direct match
    if value in VALID_LOCATIONS:
        return value

    synonyms = {
        "top-center": "top",
        "top-middle": "top",
        "bottom-center": "bottom",
        "bottom-middle": "bottom",
        "middle": "center",
        "middle-center": "center",
        "center-center": "center",
        "middle-left": "center-left",
        "middle-right": "center-right",
        "center-middle": "center",
    }
    if value in synonyms:
        normalized = synonyms[value]
    else:
        parts = value.split("-")
        parts = [p for p in parts if p]
        normalized = None

        if len(parts) == 2:
            left = parts[0]
            right = parts[1]

            if right == "center" and left in {"top", "bottom"}:
                normalized = left
            else:
                left = "center" if left == "middle" else left
                right = "center" if right == "middle" else right
                candidate = f"{left}-{right}"
                if candidate in VALID_LOCATIONS:
                    normalized = candidate
        elif len(parts) == 1 and parts[0] == "center":
            normalized = "center"

    if normalized and normalized in VALID_LOCATIONS:
        if normalized != original_value.lower():
            print(f"[Location] Normalized '{original_value}' → '{normalized}'")
        return normalized

    if original_value:
        print(
            f"[Location] Warning: '{original_value}' not recognized. "
            f"Defaulting to '{default}'."
        )
    return default


def download_nextcloud_public_file(url: str) -> Optional[str]:
    """
    Handles Nextcloud public-share links that require a strict cookie.
    1. GET the base share page to obtain cookies
    2. Reuse session cookies to request /download
    """
    try:
        # Build session with browser-like headers
        session = requests.Session()
        session.headers.update(BROWSER_HEADERS)

        # Step 1 — visit base share page (no /download)
        base_url = url.replace("/download", "")
        print(f"[NC] Visiting share page to obtain cookies: {base_url}")
        r1 = session.get(base_url, timeout=30)
        r1.raise_for_status()

        # Step 2 — request the actual file
        print(f"[NC] Downloading with session cookies: {url}")
        r2 = session.get(url, stream=True, timeout=120)
        r2.raise_for_status()

        # Determine filename
        filename = os.path.basename(url.split("?", 1)[0]) or "tempfile"
        if "." not in filename:
            filename += ".mp4"

        dest = os.path.join(TEMP_DIR, filename)

        with open(dest, "wb") as f:
            for chunk in r2.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        print(f"[NC] Download complete: {dest}")
        return dest

    except Exception as e:
        sys.stderr.write(f"[Nextcloud Cookie Download Error] {e}\n")
        return None


def download_from_url(url: str) -> Optional[str]:
    # Normalize Nextcloud URLs to standard format
    if is_nextcloud_url(url):
        normalized_url = normalize_nextcloud_url(url)
        if normalized_url != url:
            print(f"[NC] Normalized Nextcloud URL: {url} → {normalized_url}")
        url = normalized_url

    # Detect Nextcloud public share link and use cookie-based method
    if "cloud.targethouse.dk" in url and "/s/" in url:
        print("[NC] Detected Nextcloud public-share URL → using cookie method")
        return download_nextcloud_public_file(url)

    # Normal HTTP download
    try:
        filename = os.path.basename(url.split("?", 1)[0]) or "tempfile"
        if "." not in filename:
            filename += ".mp4"
        dest = os.path.join(TEMP_DIR, filename)
        print(f"Downloading from URL: {url}")
        r = requests.get(url, headers=BROWSER_HEADERS, stream=True, timeout=60)
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


# ─────────────────────────────────────────────────────────
# Nextcloud WebDAV + OCS helpers
# ─────────────────────────────────────────────────────────


def _ensure_trailing_slash(url: str) -> str:
    return url if url.endswith("/") else url + "/"


def _webdav_root(base: str, username: str) -> str:
    return _ensure_trailing_slash(
        base.rstrip("/") + f"/remote.php/dav/files/{username}"
    )


def _mkcol_path_if_needed(base_root: str, remote_path: str, auth: tuple) -> None:
    """
    Ensure intermediate directories exist via MKCOL (idempotent).
    """
    remote_path = (remote_path or "").strip("/")
    if not remote_path:
        return
    parts = remote_path.split("/")
    if len(parts) <= 1:
        return
    cur = base_root
    for d in parts[:-1]:
        cur = _ensure_trailing_slash(cur + d)
        r = requests.request(
            "MKCOL", cur, auth=auth, headers=BROWSER_HEADERS, timeout=30
        )
        if r.status_code not in (201, 405, 301, 302):
            raise RuntimeError(
                f"MKCOL failed for {cur} (status {r.status_code}): {r.text}"
            )


def upload_webdav_authenticated(
    base_url: str,
    username: str,
    password: str,
    local_path: str,
    remote_path: str,
) -> str:
    """
    Upload using authenticated WebDAV:
      PUT <base>/remote.php/dav/files/<username>/<remote_path>
    Returns the WebDAV file URL.
    """
    if not os.path.exists(local_path):
        raise FileNotFoundError(local_path)

    base_root = _webdav_root(base_url, username)
    auth = (username, password)

    _mkcol_path_if_needed(base_root, remote_path, auth=auth)

    target_url = base_root + remote_path.lstrip("/")
    with open(local_path, "rb") as f:
        r = requests.put(
            target_url, data=f, auth=auth, headers=BROWSER_HEADERS, timeout=180
        )
    if r.status_code not in (200, 201, 204):
        raise RuntimeError(f"Upload failed (status {r.status_code}): {r.text}")
    return target_url


def create_nextcloud_share_link(
    base_url: str,
    username: str,
    password: str,
    remote_path: str,
) -> str:
    """
    Use the Nextcloud OCS Share API to create a public link for the file at remote_path.
    Returns the share URL (without /download).
    """
    # OCS Share API endpoint
    url = base_url.rstrip("/") + "/ocs/v2.php/apps/files_sharing/api/v1/shares"

    headers = dict(BROWSER_HEADERS)
    headers["OCS-APIREQUEST"] = "true"

    # path is relative to the user's files root, must start with '/'
    path_value = "/" + remote_path.lstrip("/")

    data = {
        "path": path_value,
        "shareType": "3",  # 3 = public link
    }

    params = {"format": "json"}

    resp = requests.post(
        url,
        auth=(username, password),
        headers=headers,
        data=data,
        params=params,
        timeout=30,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"OCS share API failed (status {resp.status_code}): {resp.text}"
        )

    payload = resp.json()
    ocs = payload.get("ocs", {})
    meta = ocs.get("meta", {})
    if meta.get("status") != "ok":
        raise RuntimeError(
            f"OCS share API error: {meta.get('message', 'unknown error')}"
        )

    data_block = ocs.get("data")
    # Some NC versions return a single dict, some a list
    if isinstance(data_block, list) and data_block:
        data_block = data_block[0]
    if not isinstance(data_block, dict) or "url" not in data_block:
        raise RuntimeError("OCS share API response missing 'url'")

    return data_block["url"]


# ─────────────────────────────────────────────────────────
# MAIN WORKFLOW
# ─────────────────────────────────────────────────────────


def main() -> None:
    # Google auth
    try:
        creds = Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        client = gspread.authorize(creds)
    except Exception as e:
        sys.stderr.write(f"[Auth Error] Could not authorize service account:\n{e}\n")
        sys.exit(1)

    # Open sheet
    try:
        sheet = client.open_by_url(SHEET_URL)
        print(f"[Info] Opened sheet: {sheet.title}")
        ws = sheet.worksheet(WORKSHEET_NAME)
        print(f"[Info] Opened worksheet: {ws.title}")

        # Test write permissions by trying to read a cell (this verifies access)
        try:
            test_cell = ws.cell(1, 1).value
            print(f"[Info] ✓ Read access confirmed (header cell value: '{test_cell}')")
        except Exception as e:
            print(f"[Warning] Could not read test cell: {e}")

    except Exception as e:
        error_msg = f"[Open Error] Could not open Google Sheet or worksheet '{WORKSHEET_NAME}':\n{e}\n"
        sys.stderr.write(error_msg)
        print(error_msg)
        sys.exit(1)

    # Read data
    try:
        rows = ws.get_all_records()
    except Exception as e:
        sys.stderr.write(f"[Read Error] Failed to read worksheet data:\n{e}\n")
        sys.exit(1)

    headers = ws.row_values(1)

    # Required headers (with correct capitalization)
    required_columns = [
        "Generate",
        "Video File Name",
        "Intro Video File Name/URL",
        "Exit Video File Name/URL",
        "Video Text 1",
        "Video Text 2",
        "Video Text 3",
        "Text 1 Location",
        "Text 2 Location",
        "Text 3 Location",
        "Overlay Element 1",
        "Overlay 1 Location",
    ]

    for col in required_columns:
        if col not in headers:
            sys.stderr.write(f"[Error] No '{col}' column found in the sheet header.\n")
            sys.exit(1)

    # Optional Download URL column (for writing share links)
    download_col_index = None
    if "Download URL" in headers:
        download_col_index = headers.index("Download URL") + 1
        print(f"[Info] Found 'Download URL' column at index {download_col_index}")
    else:
        print(
            f"[Info] 'Download URL' column not found in headers. Available columns: {headers}"
        )

    generate_col_index = headers.index("Generate") + 1
    print(f"[Info] 'Generate' column found at index {generate_col_index}")

    any_executed = False

    for idx, row in enumerate(rows, start=2):
        if not truthy_generate(row.get("Generate")):
            continue

        video2_val = str(row.get("Video File Name", "")).strip()
        intro_val = str(row.get("Intro Video File Name/URL", "")).strip()
        exit_val = str(row.get("Exit Video File Name/URL", "")).strip()

        # Validate Nextcloud URLs and provide helpful error messages
        url_fields = [
            ("Video File Name", video2_val),
            ("Intro Video File Name/URL", intro_val),
            ("Exit Video File Name/URL", exit_val),
        ]

        for field_name, field_value in url_fields:
            if field_value and field_value.startswith(("http://", "https://")):
                is_valid, error_msg = validate_nextcloud_url(field_value)
                if not is_valid:
                    sys.stderr.write(
                        f"[Row {idx}] Validation error in '{field_name}': {error_msg}\n"
                        f"  Value: {field_value}\n"
                        f"  See docs/user_instructions.md for correct URL format.\n"
                    )
                    # Continue processing but log the error - let resolve_path handle the actual failure

        text1 = str(row.get("Video Text 1", "")).strip()
        text2 = str(row.get("Video Text 2", "")).strip()
        text3 = str(row.get("Video Text 3", "")).strip()

        text1_loc = normalize_location(row.get("Text 1 Location", ""), default="bottom")
        text2_loc = normalize_location(row.get("Text 2 Location", ""), default="bottom")
        text3_loc = normalize_location(row.get("Text 3 Location", ""), default="bottom")

        overlay_elem_1 = str(row.get("Overlay Element 1", "")).strip()
        overlay_loc_1 = normalize_location(
            row.get("Overlay 1 Location", ""), default="top-right"
        )

        if not video2_val or not intro_val or not exit_val:
            sys.stderr.write(
                f"[Row {idx}] Skipping: missing one or more required file fields.\n"
            )
            continue

        intro_path = resolve_path(intro_val)
        main_path = resolve_path(video2_val)
        exit_path = resolve_path(exit_val)

        # Ensure all paths are absolute for subprocess call
        if intro_path:
            intro_path = os.path.abspath(intro_path)
        if main_path:
            main_path = os.path.abspath(main_path)
        if exit_path:
            exit_path = os.path.abspath(exit_path)

        missing: List[str] = []
        if not intro_path:
            missing.append(f"Intro '{intro_val}'")
        if not main_path:
            missing.append(f"Video2 '{video2_val}'")
        if not exit_path:
            missing.append(f"Exit '{exit_val}'")

        if missing:
            sys.stderr.write(
                f"[Row {idx}] Skipping: could not find file(s): {', '.join(missing)}\n"
                f"  Searched: {', '.join(VIDEO_SEARCH_DIRS)}\n"
            )
            continue

        # Overlay element may be URL or path
        overlay_elem_path = ""
        if overlay_elem_1:
            # Validate overlay URL if it's a Nextcloud URL
            if overlay_elem_1.startswith(("http://", "https://")):
                is_valid, error_msg = validate_nextcloud_url(overlay_elem_1)
                if not is_valid:
                    sys.stderr.write(
                        f"[Row {idx}] Validation warning for 'Overlay Element 1': {error_msg}\n"
                        f"  Value: {overlay_elem_1}\n"
                    )

            overlay_elem_path = resolve_path(overlay_elem_1) or ""
            if not overlay_elem_path:
                sys.stderr.write(
                    f"[Row {idx}] Warning: could not resolve 'Overlay Element 1': {overlay_elem_1}; continuing without overlay.\n"
                )

        any_executed = True

        base_filename = os.path.basename(main_path)
        filename_no_ext, _ = os.path.splitext(base_filename)
        # Ensure output_file is an absolute path in TEMP_DIR
        output_file = os.path.abspath(
            os.path.join(TEMP_DIR, f"{filename_no_ext}_merged.mp4")
        )

        # Ensure merge.py path is absolute
        merge_script = os.path.abspath(os.path.join(SCRIPT_DIR, "merge.py"))

        # ---------- Render via merge.py ----------
        cmd_parts = [
            sys.executable,
            merge_script,
            intro_path,
            main_path,
            exit_path,
            text1,
            text2,
            text3,
            text1_loc,
            text2_loc,
            text3_loc,
            overlay_elem_path,
            overlay_loc_1,
            "-o",
            output_file,
            "--size",
            str(RENDER_SIZE),
            "--fit",
            RENDER_FIT,
            "--fontsize",
            str(FONT_SIZE),
        ]
        display_cmd = " ".join(quote_for_display(a) for a in cmd_parts)
        print(f"Executing: {display_cmd}")
        print(f"[Row {idx}] Output will be saved to: {output_file}")
        print(
            f"[Row {idx}] Using font size: {FONT_SIZE}px ({FONT_SIZE_PERCENT*100:.1f}% of {RENDER_SIZE}x{RENDER_SIZE} video)"
        )

        try:
            # Run merge.py from TEMP_DIR to ensure MoviePy temp files are created there
            subprocess.run(cmd_parts, check=True, cwd=TEMP_DIR)
            print(f"[Row {idx}] Rendered successfully: {output_file}")

            # Verify the file was created in the correct location
            if not os.path.exists(output_file):
                sys.stderr.write(
                    f"[Row {idx}] WARNING: Output file not found at expected location: {output_file}\n"
                )
        except subprocess.CalledProcessError as e:
            sys.stderr.write(
                f"[Row {idx}] merge.py failed for '{os.path.basename(main_path)}' "
                f"with exit code {e.returncode}.\n"
            )
            continue

        # ---------- Upload via WebDAV ----------
        try:
            # Use just the filename for remote path (not full local path)
            remote_name = os.path.basename(output_file)
            if NC_REMOTE_DIR:
                remote_path = f"{NC_REMOTE_DIR.strip('/')}/{remote_name}"
            else:
                remote_path = remote_name

            print(f"[Row {idx}] Uploading via WebDAV to {NC_BASE} as {remote_path} ...")
            webdav_url = upload_webdav_authenticated(
                base_url=NC_BASE,
                username=NC_USER,
                password=NC_PASS,
                local_path=output_file,
                remote_path=remote_path,
            )
            print(f"[Row {idx}] Upload complete: {webdav_url}")
        except Exception as e:
            sys.stderr.write(f"[Row {idx}] Upload failed for {output_file}:\n{e}\n")
            # do not flip Generate if upload fails
            continue

        # ---------- Create share link and write Download URL ----------
        try:
            share_url = create_nextcloud_share_link(
                base_url=NC_BASE,
                username=NC_USER,
                password=NC_PASS,
                remote_path=remote_path,
            )
            download_url = share_url.rstrip("/") + "/download"
            print(f"[Row {idx}] Share link: {share_url}")
            print(f"[Row {idx}] Download URL: {download_url}")

            # Verify the download URL is accessible with retry logic
            # (Nextcloud may need a moment to make the share available)
            max_retries = 3
            url_accessible = False
            for attempt in range(max_retries):
                try:
                    resp = requests.head(
                        download_url,
                        headers=BROWSER_HEADERS,
                        timeout=10,
                        allow_redirects=True,
                    )
                    if resp.status_code == 200:
                        url_accessible = True
                        print(
                            f"[Row {idx}] ✓ Download URL verified as accessible (attempt {attempt + 1})"
                        )
                        break
                    elif attempt < max_retries - 1:
                        wait_time = 2 * (attempt + 1)  # Exponential backoff: 2s, 4s, 6s
                        print(
                            f"[Row {idx}] ⚠ Download URL returned status {resp.status_code}, "
                            f"retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})..."
                        )
                        time.sleep(wait_time)
                except requests.exceptions.RequestException as e:
                    if attempt < max_retries - 1:
                        wait_time = 2 * (attempt + 1)
                        print(
                            f"[Row {idx}] ⚠ Error verifying download URL: {e}, "
                            f"retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})..."
                        )
                        time.sleep(wait_time)
                    else:
                        print(
                            f"[Row {idx}] ⚠ WARNING: Could not verify download URL after {max_retries} attempts: {e}"
                        )

            if not url_accessible:
                print(
                    f"[Row {idx}] ⚠ WARNING: Download URL may not be immediately accessible. "
                    f"Nextcloud may need time to process the share. URL: {download_url}"
                )

            if download_col_index is not None:
                print(
                    f"[Row {idx}] Writing Download URL to column {download_col_index}..."
                )
                ws.update_cell(idx, download_col_index, download_url)
                # Verify the write
                verify_value = ws.cell(idx, download_col_index).value
                if verify_value == download_url:
                    print(f"[Row {idx}] ✓ Download URL successfully written to sheet.")
                else:
                    print(
                        f"[Row {idx}] ⚠ WARNING: Download URL write may have failed. Expected: {download_url}, Got: {verify_value}"
                    )
            else:
                print(
                    f"[Row {idx}] Note: 'Download URL' column not found; "
                    f"share link not written back to sheet."
                )
        except Exception as e:
            error_msg = f"[Row {idx}] Failed to create/write share link for {remote_path}:\n{e}\n"
            sys.stderr.write(error_msg)
            print(error_msg)  # Also print to stdout so it's visible
            # still continue and flip Generate

        # ---------- Flip Generate to FALSE ----------
        try:
            print(
                f"[Row {idx}] Setting 'Generate' to FALSE in column {generate_col_index}..."
            )
            ws.update_cell(idx, generate_col_index, "FALSE")
            # Verify the write
            verify_value = ws.cell(idx, generate_col_index).value
            if str(verify_value).upper() in ("FALSE", "0", ""):
                print(f"[Row {idx}] ✓ 'Generate' successfully set to FALSE in sheet.")
            else:
                print(
                    f"[Row {idx}] ⚠ WARNING: Generate write may have failed. Expected: FALSE, Got: {verify_value}"
                )
        except Exception as e:
            error_msg = f"[Row {idx}] Failed to update 'Generate' cell:\n{e}\n"
            sys.stderr.write(error_msg)
            print(error_msg)  # Also print to stdout so it's visible

    if not any_executed:
        print("No rows processed (Generate not set or files missing).")


if __name__ == "__main__":
    main()
