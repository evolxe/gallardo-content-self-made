import sys
import json
import subprocess
import gspread
from typing import Any, Optional, List
from google.oauth2.service_account import Credentials
import os
import shlex
import requests

# ── Config ────────────────────────────────────────────────
SHEET_URL = "https://docs.google.com/spreadsheets/d/1yIZuIjtbQNVgQaY3OvDKDcpyQm90amiMSGHpfFwTTgI/edit?gid=0#gid=0"
WORKSHEET_NAME = "VideoMergeData"
SERVICE_ACCOUNT_FILE = "service-key-laserrens-video.json"

# Directories to search for video files
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEO_SEARCH_DIRS = [
    os.getcwd(),
    SCRIPT_DIR,
    os.path.join(SCRIPT_DIR, "videos"),
]

TEMP_DIR = os.path.join(SCRIPT_DIR, "temp_videos")
os.makedirs(TEMP_DIR, exist_ok=True)

# Google Sheets scope (read/write)
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


# ── Helper functions ────────────────────────────────────────────────
def truthy_generate(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    s = str(value).strip().lower()
    return s in {"true", "yes", "y", "1", "on"}

def is_url(s: str) -> bool:
    return s.startswith("http://") or s.startswith("https://")

def download_from_url(url: str) -> Optional[str]:
    try:
        filename = os.path.basename(url.split("?")[0]) or "tempfile.mp4"
        dest = os.path.join(TEMP_DIR, filename)
        print(f"🌐 Downloading from URL: {url}")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        }
        r = requests.get(url, headers=headers, stream=True, timeout=30)
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"✅ Downloaded to {dest}")
        return dest
    except Exception as e:
        sys.stderr.write(f"[URL Download Error] Could not fetch {url}:\n{e}\n")
        return None

def resolve_path(user_value: str) -> Optional[str]:
    if not user_value:
        return None
    val = user_value.strip().strip('"')
    if is_url(val):
        downloaded = download_from_url(val)
        if downloaded and os.path.exists(downloaded):
            return downloaded
        else:
            sys.stderr.write(f"[Warning] Failed to retrieve URL: {val}\n")
            return None
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

# ── Main workflow ────────────────────────────────────────────────
def main() -> None:
    try:
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        client = gspread.authorize(creds)
    except Exception as e:
        sys.stderr.write(f"[Auth Error] Could not authorize service account:\n{e}\n")
        sys.exit(1)

    try:
        sheet = client.open_by_url(SHEET_URL)
        ws = sheet.worksheet(WORKSHEET_NAME)
    except Exception as e:
        sys.stderr.write(f"[Open Error] Could not open Google Sheet or worksheet '{WORKSHEET_NAME}':\n{e}\n")
        sys.exit(1)

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
        "Video Text 1", "Video Text 2", "Video Text 3"
    ]
    for col in required_columns:
        if col not in headers:
            sys.stderr.write(f"[Error] No '{col}' column found in the sheet header.\n")
            sys.exit(1)

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

        if not video2_val:
            sys.stderr.write(f"[Row {idx}] Skipping: missing 'Video File Name'.\n")
            continue
        if not intro_val:
            sys.stderr.write(f"[Row {idx}] Skipping: missing 'Intro Video File Name/URL'.\n")
            continue
        if not exit_val:
            sys.stderr.write(f"[Row {idx}] Skipping: missing 'Exit Video File Name/URL'.\n")
            continue

        intro_path = resolve_path(intro_val)
        main_path = resolve_path(video2_val)
        exit_path = resolve_path(exit_val)

        missing: List[str] = []
        if not intro_path:
            missing.append(f"Intro Video '{intro_val}'")
        if not main_path:
            missing.append(f"Video File '{video2_val}'")
        if not exit_path:
            missing.append(f"Exit Video '{exit_val}'")
        if missing:
            sys.stderr.write(f"[Row {idx}] Skipping: could not find file(s): {', '.join(missing)}\n"
                             f"  Searched: {', '.join(VIDEO_SEARCH_DIRS)}\n")
            continue

        any_executed = True

        # Generate filename from video2's basename:
        base_filename = os.path.basename(main_path)
        filename_no_ext, _ = os.path.splitext(base_filename)
        output_file = f"{filename_no_ext}_merged.mp4"

        cmd_parts = [
            sys.executable,
            "merge_videos_cli.py",
            intro_path,
            main_path,
            exit_path,
            text1,
            text2,
            text3,
            "-o",
            output_file,
            "--size",
            "1080",
            "--fit",
            "crop",
            "--bottom",
            "60",
            "--upload",
            "--webdav-base",
            "https://cloud.targethouse.dk",
            "--webdav-user",
            "videoeditor",
            "--webdav-pass",
            "4b@XxvxaqI717wO1",
            "--remote-path",
            f"Videos/{output_file}",
        ]

        display_cmd = " ".join(quote_for_display(a) for a in cmd_parts)
        print(f"Executing: {display_cmd}")

        try:
            subprocess.run(cmd_parts, check=True)
            print(f"✅ Row {idx}: Successfully processed {os.path.basename(main_path)}")
            # Mark the row as processed
            ws.update_cell(idx, generate_col_index, "FALSE")
            print(f"📝 Row {idx}: Updated 'Generate' to FALSE.")
        except subprocess.CalledProcessError as e:
            sys.stderr.write(f"[Row {idx}] ❌ merge_videos_cli.py failed for '{os.path.basename(main_path)}' "
                             f"with exit code {e.returncode}.\n")

    if not any_executed:
        print("No rows processed (either no Generate=TRUE or missing files).")

if __name__ == "__main__":
    main()


