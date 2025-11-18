# sheets_url.py
import sys
import os
import shlex
import subprocess
import time
import re
import mimetypes
from datetime import datetime
from urllib.parse import parse_qs, unquote, urlparse
from typing import Any, Optional, List

import requests
import gspread
from google.oauth2.service_account import Credentials

from config import BASE_DIR, get_env
from log_utils import (
    attach_log_streams,
    flush_error_log,
    get_logger,
    log_call,
    record_error,
    write_sheet_value,
)
from late_post import post_video_to_all_accounts
from validation import validate_nextcloud_url, normalize_nextcloud_url, is_nextcloud_url

attach_log_streams("sheet")
logger = get_logger("gallardo.sheet")

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
LATE_TIMEZONE = os.environ.get("LATE_TIMEZONE", "UTC")
SCHEDULE_INPUT_FORMATS = [
    ("%Y-%m-%d %H:%M:%S", "YYYY-MM-DD HH:MM:SS (e.g., 2025-01-17 14:30:00)"),
    ("%m/%d/%Y %H:%M:%S", "M/D/YYYY HH:MM:SS (e.g., 1/17/2025 14:30:00)"),
]
SCHEDULE_DT_FORMAT = "%Y-%m-%dT%H:%M:%S"
SCHEDULE_DT_FORMAT_DESC = "YYYY-MM-DDTHH:MM:SS (e.g., 2025-01-17T14:30:00)"


# ─────────────────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────────────────


@log_call(logger)
def truthy_generate(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False

    s = _coerce_cell_value(value).strip().lower()
    return s in {"true", "yes", "y", "1", "on"}


@log_call(logger)
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


@log_call(logger)
def _filename_from_content_disposition(header: Optional[str]) -> Optional[str]:
    if not header:
        return None
    parts = [p.strip() for p in header.split(";")]
    for part in parts[1:]:
        if not part:
            continue
        lower = part.lower()
        if lower.startswith("filename*="):
            value = part.split("=", 1)[1].strip().strip('"')
            if "''" in value:
                value = value.split("''", 1)[1]
            candidate = os.path.basename(unquote(value))
            if candidate:
                return candidate
        elif lower.startswith("filename="):
            value = part.split("=", 1)[1].strip().strip('"')
            candidate = os.path.basename(unquote(value))
            if candidate:
                return candidate
    return None


@log_call(logger)
def _filename_from_query(url: str) -> Optional[str]:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    files = query.get("files")
    if files:
        candidate = os.path.basename(unquote(files[0]))
        if candidate:
            return candidate
    return None


@log_call(logger)
def _guess_extension_from_content_type(
    content_type: Optional[str], fallback: str
) -> str:
    if not content_type:
        return fallback
    main = content_type.split(";", 1)[0].strip().lower()
    guessed = mimetypes.guess_extension(main)
    if not guessed:
        if "quicktime" in main:
            return ".mov"
        return fallback
    if guessed == ".jpe":
        return ".jpg"
    if guessed == ".qt" and "quicktime" in main:
        return ".mov"
    return guessed


@log_call(logger)
def _determine_download_filename(
    url: str,
    response: Optional[requests.Response],
    *,
    default_basename: str = "tempfile",
    default_ext: str = ".bin",
) -> str:
    candidate = _filename_from_content_disposition(
        response.headers.get("Content-Disposition", "") if response else None
    )
    if not candidate:
        candidate = _filename_from_query(url)
    if not candidate:
        candidate = os.path.basename(urlparse(url).path.rstrip("/"))

    candidate = candidate or default_basename

    name, ext = os.path.splitext(candidate)
    if not ext:
        content_type = response.headers.get("Content-Type") if response else None
        ext = _guess_extension_from_content_type(content_type, fallback=default_ext)
        candidate = candidate + ext

    return candidate


@log_call(logger)
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


@log_call(logger)
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


@log_call(logger)
def parse_schedule_datetime(raw_value: str, row_idx: int) -> Optional[str]:
    for fmt, _ in SCHEDULE_INPUT_FORMATS:
        try:
            dt = datetime.strptime(raw_value, fmt)
            return dt.strftime(SCHEDULE_DT_FORMAT)
        except ValueError:
            continue
    allowed = "; ".join(desc for _, desc in SCHEDULE_INPUT_FORMATS)
    sys.stderr.write(
        f"[Row {row_idx}] Invalid 'Schedule DateTime' value '{raw_value}'. "
        f"Expected format(s): {allowed}\n"
    )
    return None


@log_call(logger)
def download_nextcloud_public_file(
    url: str, *, default_ext: str = ".mp4"
) -> Optional[str]:
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
        logger.info(
            "[HTTP] GET %s status=%s headers=%s",
            base_url,
            r1.status_code,
            dict(r1.headers),
        )
        r1.raise_for_status()

        # Step 2 — request the actual file
        print(f"[NC] Downloading with session cookies: {url}")
        r2 = session.get(url, stream=True, timeout=120)
        logger.info(
            "[HTTP] GET %s status=%s headers=%s",
            url,
            r2.status_code,
            dict(r2.headers),
        )
        r2.raise_for_status()

        filename = _determine_download_filename(
            url, r2, default_basename="tempfile", default_ext=default_ext
        )

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


@log_call(logger)
def download_from_url(url: str, *, default_ext: str = ".mp4") -> Optional[str]:
    # Normalize Nextcloud URLs to standard format
    if is_nextcloud_url(url):
        normalized_url = normalize_nextcloud_url(url)
        if normalized_url != url:
            print(f"[NC] Normalized Nextcloud URL: {url} → {normalized_url}")
        url = normalized_url

    # Detect Nextcloud public share link and use cookie-based method
    if "cloud.targethouse.dk" in url and "/s/" in url:
        print("[NC] Detected Nextcloud public-share URL → using cookie method")
        return download_nextcloud_public_file(url, default_ext=default_ext)

    # Normal HTTP download
    try:
        print(f"Downloading from URL: {url}")
        r = requests.get(url, headers=BROWSER_HEADERS, stream=True, timeout=60)
        logger.info(
            "[HTTP] GET %s status=%s headers=%s",
            url,
            r.status_code,
            dict(r.headers),
        )
        r.raise_for_status()
        filename = _determine_download_filename(
            url, r, default_basename="tempfile", default_ext=default_ext
        )
        dest = os.path.join(TEMP_DIR, filename)
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        print(f"Downloaded to {dest}")
        return dest
    except Exception as e:
        sys.stderr.write(f"[URL Download Error] Could not fetch {url}:\n{e}\n")
        return None


@log_call(logger)
def resolve_path(user_value: str, *, default_ext: str = ".mp4") -> Optional[str]:
    if not user_value:
        return None
    val = user_value.strip().strip('"')
    if is_url(val):
        dl = download_from_url(val, default_ext=default_ext)
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


@log_call(logger)
def set_generate_state(
    worksheet, row_idx: int, col_idx: int, state: str, *, log_prefix: str = "Generate"
) -> None:
    logger.info("[Row %s] Setting '%s' to %s", row_idx, log_prefix, state)
    write_sheet_value(
        logger,
        worksheet,
        row_idx,
        col_idx,
        state,
        context=log_prefix,
    )


def quote_for_display(arg: str) -> str:
    return f'"{arg}"' if os.name == "nt" else shlex.quote(arg)


# ─────────────────────────────────────────────────────────
# Nextcloud WebDAV + OCS helpers
# ─────────────────────────────────────────────────────────


@log_call(logger)
def _ensure_trailing_slash(url: str) -> str:
    return url if url.endswith("/") else url + "/"


@log_call(logger)
def _webdav_root(base: str, username: str) -> str:
    return _ensure_trailing_slash(
        base.rstrip("/") + f"/remote.php/dav/files/{username}"
    )


@log_call(logger)
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
        logger.info("[HTTP] MKCOL %s status=%s", cur, r.status_code)
        if r.status_code not in (201, 405, 301, 302):
            raise RuntimeError(
                f"MKCOL failed for {cur} (status {r.status_code}): {r.text}"
            )


@log_call(logger)
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
    logger.info(
        "[HTTP] PUT %s status=%s headers=%s",
        target_url,
        r.status_code,
        dict(r.headers),
    )
    if r.status_code not in (200, 201, 204):
        raise RuntimeError(f"Upload failed (status {r.status_code}): {r.text}")
    return target_url


@log_call(logger)
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
    logger.info(
        "[HTTP] POST %s status=%s payload=%s response=%s",
        url,
        resp.status_code,
        data,
        resp.text,
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
        "Schedule DateTime",
        "Post Text",
        "Video Text 1",
        "Video Text 2",
        "Video Text 3",
        "Text 1 Location",
        "Text 2 Location",
        "Text 3 Location",
        "Overlay Element 1",
        "Overlay 1 Location",
        "Error Message",
    ]

    for col in required_columns:
        if col not in headers:
            sys.stderr.write(f"[Error] No '{col}' column found in the sheet header.\n")
            sys.exit(1)
    allowed_desc = "; ".join(desc for _, desc in SCHEDULE_INPUT_FORMATS)
    print(
        f"[Info] 'Schedule DateTime' values must use one of: {allowed_desc}. "
        f"Values are auto-converted to {SCHEDULE_DT_FORMAT_DESC} for the Late API."
    )

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
    error_col_index = headers.index("Error Message") + 1
    print(f"[Info] 'Generate' column found at index {generate_col_index}")

    any_executed = False

    for idx, row in enumerate(rows, start=2):
        if not truthy_generate(row.get("Generate")):
            continue

        logger.info("[Row %s] Raw row data: %s", idx, row)
        write_sheet_value(logger, ws, idx, error_col_index, "", context="error clear")
        video2_val = str(row.get("Video File Name", "")).strip()
        intro_val = str(row.get("Intro Video File Name/URL", "")).strip()
        exit_val = str(row.get("Exit Video File Name/URL", "")).strip()
        overlay_elem_1 = str(row.get("Overlay Element 1", "")).strip()
        schedule_raw = str(row.get("Schedule DateTime", "")).strip()
        post_text_custom = str(row.get("Post Text", "")).strip()
        logger.info(
            "[Row %s] Values video2=%s intro=%s exit=%s overlay=%s schedule=%s post_text=%s",
            idx,
            video2_val,
            intro_val,
            exit_val,
            overlay_elem_1,
            schedule_raw,
            post_text_custom,
        )

        # Validate Nextcloud URLs and provide helpful error messages
        url_fields = [
            ("Video File Name", video2_val),
            ("Intro Video File Name/URL", intro_val),
            ("Exit Video File Name/URL", exit_val),
        ]
        if overlay_elem_1:
            url_fields.append(("Overlay Element 1", overlay_elem_1))

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
        logger.info(
            "[Row %s] Text fields: t1=%s t2=%s t3=%s",
            idx,
            text1,
            text2,
            text3,
        )

        text1_loc = normalize_location(row.get("Text 1 Location", ""), default="bottom")
        text2_loc = normalize_location(row.get("Text 2 Location", ""), default="bottom")
        text3_loc = normalize_location(row.get("Text 3 Location", ""), default="bottom")

        overlay_loc_1 = normalize_location(
            row.get("Overlay 1 Location", ""), default="top-right"
        )
        schedule_value = None
        if schedule_raw:
            schedule_value = parse_schedule_datetime(schedule_raw, idx)
            if not schedule_value:
                record_error(
                    logger,
                    ws,
                    idx,
                    error_col_index,
                    f"Schedule DateTime '{schedule_raw}' is invalid. Use YYYY-MM-DD HH:MM:SS or M/D/YYYY HH:MM:SS.",
                )
                set_generate_state(ws, idx, generate_col_index, "TRUE")
                continue
        logger.info("[Row %s] Normalized schedule datetime: %s", idx, schedule_value)
        post_text_payload = (
            post_text_custom
            or " ".join(part for part in [text1, text2, text3] if part).strip()
        )

        if not video2_val or not intro_val or not exit_val:
            message = "Missing required video references. Intro, Video File Name, and Exit values must be provided."
            sys.stderr.write(f"[Row {idx}] {message}\n")
            record_error(logger, ws, idx, error_col_index, message)
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
            message = (
                f"Could not locate file(s): {', '.join(missing)}. "
                f"Checked folders: {', '.join(VIDEO_SEARCH_DIRS)}."
            )
            sys.stderr.write(f"[Row {idx}] {message}\n")
            record_error(logger, ws, idx, error_col_index, message)
            continue

        set_generate_state(ws, idx, generate_col_index, "LOADING")

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

            overlay_elem_path = resolve_path(overlay_elem_1, default_ext=".png") or ""
            if not overlay_elem_path:
                sys.stderr.write(
                    f"[Row {idx}] Warning: could not resolve 'Overlay Element 1': {overlay_elem_1}; continuing without overlay.\n"
                )

        any_executed = True

        base_filename = os.path.basename(main_path)
        filename_no_ext, _ = os.path.splitext(base_filename)
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        merged_name = f"{filename_no_ext}_{timestamp}_merged.mp4"
        # Ensure output_file is an absolute path in TEMP_DIR
        output_file = os.path.abspath(os.path.join(TEMP_DIR, merged_name))

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
            record_error(
                logger,
                ws,
                idx,
                error_col_index,
                "Video rendering failed. Please review merge.py logs.",
                exception=e,
            )
            set_generate_state(ws, idx, generate_col_index, "TRUE")
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
            record_error(
                logger,
                ws,
                idx,
                error_col_index,
                "Upload to Nextcloud failed. Please verify storage space and credentials.",
                exception=e,
            )
            set_generate_state(ws, idx, generate_col_index, "TRUE")
            continue

        # ---------- Create share link and write Download URL ----------
        share_url = None
        download_url = None
        try:
            share_url = create_nextcloud_share_link(
                base_url=NC_BASE,
                username=NC_USER,
                password=NC_PASS,
                remote_path=remote_path,
            )
            download_url = share_url.rstrip("/")
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
                    logger.info(
                        "[HTTP] HEAD %s status=%s headers=%s",
                        download_url,
                        resp.status_code,
                        dict(resp.headers),
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
                        f"[Row {idx}] ⚠ WARNING: Download URL write verification failed. Expected: {download_url}, Got: {verify_value}"
                    )
                # Set state to DONE after URL upload to sheet (even if verification failed, the write was attempted)
                set_generate_state(ws, idx, generate_col_index, "DONE")
            else:
                print(
                    f"[Row {idx}] Note: 'Download URL' column not found; "
                    f"share link not written back to sheet."
                )
                # Even if column not found, we created the share link, so mark as DONE
                set_generate_state(ws, idx, generate_col_index, "DONE")
        except Exception as e:
            error_msg = f"[Row {idx}] Failed to create/write share link for {remote_path}:\n{e}\n"
            sys.stderr.write(error_msg)
            print(error_msg)  # Also print to stdout so it's visible
            share_url = None
            download_url = None
            record_error(
                logger,
                ws,
                idx,
                error_col_index,
                "Could not create a Nextcloud share link. Please try again later.",
                exception=e,
            )

        # ---------- Social posting via Late ----------
        if share_url:
            try:
                post_text = post_text_payload or ""
                print(
                    f"[Row {idx}] Posting to Late with share URL: {share_url} "
                    f"(scheduled_for={schedule_value or 'immediate'}, timezone={LATE_TIMEZONE})"
                )
                late_response = post_video_to_all_accounts(
                    nextcloud_share_url=share_url,
                    post_text=post_text,
                    scheduled_for=schedule_value,
                    timezone=LATE_TIMEZONE,
                )
                print(f"[Row {idx}] Late post created successfully: {late_response}")
                # Set state to POSTED after successful social media post
                set_generate_state(ws, idx, generate_col_index, "POSTED")
            except Exception as e:
                sys.stderr.write(f"[Row {idx}] Late posting failed:\n{e}\n")
                record_error(
                    logger,
                    ws,
                    idx,
                    error_col_index,
                    "Late social posting failed. Please review Late API credentials/logs.",
                    exception=e,
                )
                # If posting fails but URL was uploaded, state remains DONE (already set above)

    if not any_executed:
        print("No rows processed (Generate not set or files missing).")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Flush all buffered logs to error log file
        flush_error_log(e)
        # Re-raise to maintain exit code behavior
        raise
