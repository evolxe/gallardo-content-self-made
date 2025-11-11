# sheets_url.py
import sys
import os
import shlex
import time
import uuid
import subprocess
from typing import Any, Optional, List, Tuple

import requests
import gspread
from google.oauth2.service_account import Credentials

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

# Render defaults (1:1 output, crop to square, bottom textbox)
RENDER_SIZE = 1080
RENDER_FIT = "crop"   # "crop" or "pad"
TEXTBOX_BOTTOM_MARGIN = 60

# Column to write the final downloadable URL into (auto-created if missing)
DOWNLOAD_URL_COL_NAME = "Download URL"

# Browser-like header for all outbound HTTP requests
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    )
}

# ── Public share upload (DEFAULT path) ────────────────────────────────────────
# Public WebDAV endpoint: https://<host>/public.php/webdav/<FILENAME>
PUBLIC_SHARE_BASE = "https://cloud.targethouse.dk"
PUBLIC_SHARE_TOKEN = "8eHQ4ntJK4yS8ZW"   # your new share token
PUBLIC_SHARE_PASSWORD = ""               # set if the share requires a password
USE_PUBLIC_SHARE_UPLOAD = True           # default = public share first

# ── Authenticated WebDAV (fallback) ───────────────────────────────────────────
# Authenticated WebDAV endpoint: https://<host>/remote.php/dav/files/<USER>/<PATH>
WEBDAV_BASE = "https://cloud.targethouse.dk"
WEBDAV_USER = "videoeditor"
WEBDAV_PASS = "4b@XxvxaqI717wO1"
WEBDAV_REMOTE_DIR = "Videos"             # remote subfolder; created if missing

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

def _mkcol_path_if_needed(base_root: str, remote_path: str, auth: Tuple[str, str]) -> None:
    """
    Ensure intermediate directories exist via MKCOL (idempotent).
    """
    if not remote_path:
        return
    parts = remote_path.strip("/").split("/")
    if len(parts) <= 1:
        return  # file at root
    cur = base_root
    for d in parts[:-1]:
        cur = _ensure_trailing_slash(cur + d)
        r = requests.request("MKCOL", cur, auth=auth, headers=BROWSER_HEADERS, timeout=30)
        if r.status_code not in (201, 405, 301, 302):
            raise RuntimeError(f"MKCOL failed for {cur} (status {r.status_code}): {r.text}")

def public_share_upload_allows_write(base_url: str, share_token: str, share_password: str = "") -> bool:
    """
    Confirm the public share allows uploads:
      - PUT a zero-byte temp file
      - If success, DELETE it
    """
    url_base = base_url.rstrip("/")
    test_name = f"._nc_upload_test_{uuid.uuid4().hex}.txt"
    put_url = f"{url_base}/public.php/webdav/{test_name}"
    auth = (share_token, share_password)

    # zero-byte body
    r = requests.put(put_url, data=b"", auth=auth, headers=BROWSER_HEADERS, timeout=30)
    if r.status_code in (200, 201, 204):
        # try delete the temp file (ignore errors)
        try:
            del_url = put_url
            requests.delete(del_url, auth=auth, headers=BROWSER_HEADERS, timeout=30)
        except Exception:
            pass
        return True
    return False

def upload_webdav_public(
    base_url: str,
    share_token: str,
    local_path: str,
    remote_filename: str,
    share_password: Optional[str] = None,
) -> str:
    """
    Upload into a Nextcloud/ownCloud public share (ONLY if share allows uploads):
      PUT <base>/public.php/webdav/<remote_filename>
    Auth = (share_token, share_password or "")
    Returns the public WebDAV URL.
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

def public_share_download_url(base_url: str, share_token: str, filename: str, path: str = "/") -> str:
    """
    Build a direct download URL for a file uploaded into a public share folder.
    Most Nextclouds accept: /s/<token>/download?path=<path>&files=<filename>
    """
    base = base_url.rstrip("/")
    p = path if path else "/"
    return f"{base}/s/{share_token}/download?path={p}&files={filename}"

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

def ocs_get_or_create_public_share_link(
    base_url: str,
    username: str,
    password: str,
    remote_path: str,
) -> str:
    """
    Use Nextcloud OCS API to fetch existing public share for `remote_path`,
    or create a new one (read-only). Returns the share `url`.
    """
    base = base_url.rstrip("/")
    auth = (username, password)
    headers = {
        **BROWSER_HEADERS,
        "OCS-APIRequest": "true",
        "Accept": "application/json",
    }

    # 1) Try to find an existing share for this path
    # GET .../ocs/v2.php/apps/files_sharing/api/v1/shares?path=<path>&reshares=true
    params = {"path": f"/{remote_path.lstrip('/')}", "reshares": "true", "format": "json"}
    r = requests.get(f"{base}/ocs/v2.php/apps/files_sharing/api/v1/shares", params=params,
                     auth=auth, headers=headers, timeout=30)
    try:
        data = r.json()
        shares = data.get("ocs", {}).get("data", [])
        if isinstance(shares, dict):
            shares = [shares] if shares else []
        for s in shares:
            url = s.get("url")
            if url:
                return url
    except Exception:
        # ignore parse errors and continue to create
        pass

    # 2) Create a new public share
    # POST .../ocs/v2.php/apps/files_sharing/api/v1/shares
    #   path=<path>, shareType=3(public), permissions=1(read)
    payload = {
        "path": f"/{remote_path.lstrip('/')}",
        "shareType": "3",
        "permissions": "1",
        "format": "json",
    }
    r = requests.post(f"{base}/ocs/v2.php/apps/files_sharing/api/v1/shares",
                      data=payload, auth=auth, headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()
    url = data.get("ocs", {}).get("data", {}).get("url")
    if not url:
        raise RuntimeError(f"OCS share create returned no URL: {data}")
    return url

# ──────────────────────────────────────────────────────────────────────────────
# SHEET HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def ensure_download_url_col(ws) -> int:
    """
    Ensure there is a 'Download URL' column in the sheet header row.
    Returns the 1-based column index for writing.
    """
    headers = ws.row_values(1)
    if DOWNLOAD_URL_COL_NAME in headers:
        return headers.index(DOWNLOAD_URL_COL_NAME) + 1
    # append at the end
    col_index = len(headers) + 1
    try:
        ws.update_cell(1, col_index, DOWNLOAD_URL_COL_NAME)
        print(f"Added header '{DOWNLOAD_URL_COL_NAME}' at column {col_index}.")
    except Exception as e:
        sys.stderr.write(f"[Header Warning] Could not add '{DOWNLOAD_URL_COL_NAME}' header: {e}\n")
    return col_index

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
    required_columns = [
        "Generate",
        "Video File Name",
        "Intro Video File Name/URL",
        "Exit Video File Name/URL",
        "Video Text 1",
        "Video Text 2",
        "Video Text 3",
    ]
    for col in required_columns:
        if col not in headers:
            sys.stderr.write(f"[Error] No '{col}' column found in the sheet header.\n")
            sys.exit(1)

    generate_col_index = headers.index("Generate") + 1
    download_col_index = ensure_download_url_col(ws)
    any_executed = False

    # Confirm public share allows uploads (once)
    if USE_PUBLIC_SHARE_UPLOAD:
        can_upload = public_share_upload_allows_write(PUBLIC_SHARE_BASE, PUBLIC_SHARE_TOKEN, PUBLIC_SHARE_PASSWORD)
        if can_upload:
            print(f"Public share appears to allow uploads: {PUBLIC_SHARE_BASE.rstrip('/')}/s/{PUBLIC_SHARE_TOKEN}")
        else:
            sys.stderr.write("Warning: Public share may not allow uploads (PUT test failed). Will still try and then fall back.\n")

    for idx, row in enumerate(rows, start=2):
        if not truthy_generate(row.get("Generate")):
            continue

        video2_val = str(row.get("Video File Name", "")).strip()
        intro_val  = str(row.get("Intro Video File Name/URL", "")).strip()
        exit_val   = str(row.get("Exit Video File Name/URL", "")).strip()
        text1      = str(row.get("Video Text 1", "")).strip()
        text2      = str(row.get("Video Text 2", "")).strip()
        text3      = str(row.get("Video Text 3", "")).strip()

        if not video2_val or not intro_val or not exit_val:
            sys.stderr.write(f"[Row {idx}] Skipping: missing one or more required file fields.\n")
            continue

        intro_path = resolve_path(intro_val)
        main_path  = resolve_path(video2_val)
        exit_path  = resolve_path(exit_val)

        missing: List[str] = []
        if not intro_path:
            missing.append(f"Intro '{intro_val}'")
        if not main_path:
            missing.append(f"Video2 '{video2_val}'")
        if not exit_path:
            missing.append(f"Exit '{exit_val}'")
        if missing:
            sys.stderr.write(f"[Row {idx}] Skipping: could not find file(s): {', '.join(missing)}\n"
                             f"  Searched: {', '.join(VIDEO_SEARCH_DIRS)}\n")
            continue

        any_executed = True

        # Derive output filename based on video2 basename
        base_filename = os.path.basename(main_path)
        filename_no_ext, _ = os.path.splitext(base_filename)
        output_file = f"{filename_no_ext}_merged.mp4"

        # ── Render via your merge script (no upload here) ─────────────────────
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
            "--bottom", str(TEXTBOX_BOTTOM_MARGIN),
        ]
        display_cmd = " ".join(quote_for_display(a) for a in cmd_parts)
        print(f"Executing: {display_cmd}")

        try:
            subprocess.run(cmd_parts, check=True)
            print(f"Row {idx}: Rendered -> {output_file}")
        except subprocess.CalledProcessError as e:
            sys.stderr.write(f"[Row {idx}] ERROR: merge_videos_cli.py failed for '{os.path.basename(main_path)}' "
                             f"(exit {e.returncode}).\n")
            continue  # do not flip Generate on render failure

        # ── Upload AFTER rendering: try PUBLIC first (default), then AUTH fallback ─
        final_download_url: Optional[str] = None

        # 1) Public share upload
        if USE_PUBLIC_SHARE_UPLOAD:
            try:
                remote_name = output_file
                print("Uploading to PUBLIC share (WebDAV)...")
                public_webdav_url = upload_webdav_public(
                    base_url=PUBLIC_SHARE_BASE,
                    share_token=PUBLIC_SHARE_TOKEN,
                    local_path=output_file,
                    remote_filename=remote_name,
                    share_password=PUBLIC_SHARE_PASSWORD or None,
                )
                print(f"Public upload complete: {public_webdav_url}")
                # Build a direct download URL for the uploaded file
                final_download_url = public_share_download_url(
                    base_url=PUBLIC_SHARE_BASE,
                    share_token=PUBLIC_SHARE_TOKEN,
                    filename=remote_name,
                    path="/"
                )
                print(f"Public direct download URL: {final_download_url}")
            except Exception as e_pub:
                sys.stderr.write(f"[Row {idx}] Warning: Public upload failed: {e_pub}\n")

        # 2) If public failed or disabled, authenticated fallback + create share via OCS
        if not final_download_url:
            try:
                remote_name = output_file
                remote_path = remote_name
                if WEBDAV_REMOTE_DIR:
                    remote_path = f"{WEBDAV_REMOTE_DIR.strip('/')}/{remote_name}"

                print("Uploading via AUTHENTICATED WebDAV fallback...")
                auth_webdav_url = upload_webdav_authenticated(
                    base_url=WEBDAV_BASE,
                    username=WEBDAV_USER,
                    password=WEBDAV_PASS,
                    local_path=output_file,
                    remote_path=remote_path,
                )
                print(f"Authenticated upload complete: {auth_webdav_url}")

                # Create or fetch a public share link for this file (OCS API)
                print("Creating or fetching public share link (OCS API)...")
                share_url = ocs_get_or_create_public_share_link(
                    base_url=WEBDAV_BASE,
                    username=WEBDAV_USER,
                    password=WEBDAV_PASS,
                    remote_path=remote_path,
                )
                final_download_url = f"{share_url.rstrip('/')}/download"
                print(f"OCS direct download URL: {final_download_url}")
            except Exception as e_auth:
                sys.stderr.write(f"[Row {idx}] ERROR: Authenticated upload + OCS share failed:\n{e_auth}\n")
                # Do NOT flip Generate if both uploads failed
                continue

        # ── Flip Generate to FALSE and write download URL ─────────────────────
        try:
            ws.update_cell(idx, generate_col_index, "FALSE")
            if final_download_url:
                ws.update_cell(idx, download_col_index, final_download_url)
            print(f"Row {idx}: Updated 'Generate' -> FALSE; wrote 'Download URL'.")
        except Exception as e:
            sys.stderr.write(f"[Row {idx}] Warning: Failed to update sheet cells:\n{e}\n")

    if not any_executed:
        print("No rows processed (either Generate != TRUE or files missing).")

# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    main()


