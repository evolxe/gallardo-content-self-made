# sheets_url.py
import sys
import os
import shlex
import subprocess
from typing import Any, Optional, List

import requests
import gspread
from google.oauth2.service_account import Credentials

# ─────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────

SHEET_URL = "https://docs.google.com/spreadsheets/d/1yIZuIjtbQNVgQaY3OvDKDcpyQm90amiMSGHpfFwTTgI/edit?gid=0#gid=0"
WORKSHEET_NAME = "VideoMergeData"
SERVICE_ACCOUNT_FILE = "service-key-laserrens-video.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_DIR = os.path.join(SCRIPT_DIR, "temp_videos")
os.makedirs(TEMP_DIR, exist_ok=True)

VIDEO_SEARCH_DIRS = [
    os.getcwd(),
    SCRIPT_DIR,
    os.path.join(SCRIPT_DIR, "videos"),
]

# Render defaults
RENDER_SIZE = 1080
RENDER_FIT = "crop"  # or "pad"

# Browser-like header for HTTP
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    )
}

# Nextcloud auth for WebDAV + OCS
NC_BASE = "https://cloud.targethouse.dk"
NC_USER = "videoeditor"
NC_PASS = "4b@XxvxaqI717wO1"
NC_REMOTE_DIR = "Videos"  # remote folder for uploads, e.g. "Videos"


# ─────────────────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────────────────

def truthy_generate(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    s = str(value).strip().lower()
    return s in {"true", "yes", "y", "1", "on"}


def is_url(s: str) -> bool:
    return isinstance(s, str) and (s.startswith("http://") or s.startswith("https://"))


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
    return _ensure_trailing_slash(base.rstrip("/") + f"/remote.php/dav/files/{username}")


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
        r = requests.put(target_url, data=f, auth=auth, headers=BROWSER_HEADERS, timeout=180)
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

    resp = requests.post(url, auth=(username, password), headers=headers, data=data, params=params, timeout=30)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"OCS share API failed (status {resp.status_code}): {resp.text}")

    payload = resp.json()
    ocs = payload.get("ocs", {})
    meta = ocs.get("meta", {})
    if meta.get("status") != "ok":
        raise RuntimeError(f"OCS share API error: {meta.get('message', 'unknown error')}")

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

    generate_col_index = headers.index("Generate") + 1

    any_executed = False

    for idx, row in enumerate(rows, start=2):
        if not truthy_generate(row.get("Generate")):
            continue

        video2_val = str(row.get("Video File Name", "")).strip()
        intro_val = str(row.get("Intro Video File Name/URL", "")).strip()
        exit_val = str(row.get("Exit Video File Name/URL", "")).strip()

        text1 = str(row.get("Video Text 1", "")).strip()
        text2 = str(row.get("Video Text 2", "")).strip()
        text3 = str(row.get("Video Text 3", "")).strip()

        text1_loc = str(row.get("Text 1 Location", "")).strip() or "bottom"
        text2_loc = str(row.get("Text 2 Location", "")).strip() or "bottom"
        text3_loc = str(row.get("Text 3 Location", "")).strip() or "bottom"

        overlay_elem_1 = str(row.get("Overlay Element 1", "")).strip()
        overlay_loc_1 = str(row.get("Overlay 1 Location", "")).strip() or "top-right"

        if not video2_val or not intro_val or not exit_val:
            sys.stderr.write(f"[Row {idx}] Skipping: missing one or more required file fields.\n")
            continue

        intro_path = resolve_path(intro_val)
        main_path = resolve_path(video2_val)
        exit_path = resolve_path(exit_val)

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
            overlay_elem_path = resolve_path(overlay_elem_1) or ""
            if not overlay_elem_path:
                sys.stderr.write(
                    f"[Row {idx}] Warning: could not resolve 'Overlay Element 1': {overlay_elem_1}; continuing without overlay.\n"
                )

        any_executed = True

        base_filename = os.path.basename(main_path)
        filename_no_ext, _ = os.path.splitext(base_filename)
        output_file = f"{filename_no_ext}_merged.mp4"

        # ---------- Render via merge.py ----------
        cmd_parts = [
            sys.executable,
            "merge.py",
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
        ]
        display_cmd = " ".join(quote_for_display(a) for a in cmd_parts)
        print(f"Executing: {display_cmd}")

        try:
            subprocess.run(cmd_parts, check=True)
            print(f"[Row {idx}] Rendered successfully: {output_file}")
        except subprocess.CalledProcessError as e:
            sys.stderr.write(
                f"[Row {idx}] merge.py failed for '{os.path.basename(main_path)}' "
                f"with exit code {e.returncode}.\n"
            )
            continue

        # ---------- Upload via WebDAV ----------
        try:
            remote_name = output_file
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

            if download_col_index is not None:
                ws.update_cell(idx, download_col_index, download_url)
            else:
                print(
                    f"[Row {idx}] Note: 'Download URL' column not found; "
                    f"share link not written back to sheet."
                )
        except Exception as e:
            sys.stderr.write(
                f"[Row {idx}] Failed to create/write share link for {remote_path}:\n{e}\n"
            )
            # still continue and flip Generate

        # ---------- Flip Generate to FALSE ----------
        try:
            ws.update_cell(idx, generate_col_index, "FALSE")
            print(f"[Row {idx}] Updated 'Generate' to FALSE.")
        except Exception as e:
            sys.stderr.write(f"[Row {idx}] Failed to update 'Generate' cell:\n{e}\n")

    if not any_executed:
        print("No rows processed (Generate not set or files missing).")


if __name__ == "__main__":
    main()


