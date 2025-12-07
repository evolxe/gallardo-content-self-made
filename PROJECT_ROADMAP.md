# Gallardo Content Pipeline - Complete Project Roadmap

## 📋 Table of Contents
1. [File Structure Overview](#file-structure-overview)
2. [Core Python Files](#core-python-files)
3. [Supporting Files](#supporting-files)
4. [Documentation](#documentation)
5. [System Architecture Diagram](#system-architecture-diagram)
6. [Data Flow Diagram](#data-flow-diagram)
7. [File Dependencies](#file-dependencies)

---

## 📁 File Structure Overview

```
gallardo-content-self-made/
│
├── 🐍 CORE PYTHON FILES
│   ├── sheet.py          # Main orchestrator (ENTRY POINT)
│   ├── merge.py          # Video processing engine
│   ├── late_post.py      # Social media posting
│   ├── config.py         # Environment configuration
│   ├── validation.py     # Input validation
│   ├── log_utils.py      # Logging utilities
│   ├── webhook_make.py   # Webhook integration
│   └── webtest.py         # Webhook testing
│
├── 📄 CONFIGURATION
│   ├── requirements.txt  # Python dependencies
│   ├── .env              # Environment variables (not in repo)
│   └── runPython.sh      # Cron job wrapper script
│
├── 📚 DOCUMENTATION
│   └── docs/
│       ├── README.md
│       ├── user_instructions.md
│       ├── next_cloud_notes.md
│       ├── social_posting.md
│       ├── temp_file_management.md
│       ├── setup_linux.md
│       └── chron.md
│
└── 🎨 ASSETS
    ├── fonts/
    │   └── MinionPro-Regular.otf
    └── assets/
        └── rocLogo.png
```

---

## 🐍 Core Python Files

### 1. **sheet.py** - Main Orchestrator (ENTRY POINT)
**Purpose:** The central controller that coordinates the entire workflow.

**Key Responsibilities:**
- Reads job specifications from Google Sheets
- Downloads videos from Nextcloud or local files
- Calls `merge.py` to process videos
- Uploads results to Nextcloud
- Creates share links
- Calls `late_post.py` for social media posting
- Updates Google Sheet with status

**Imports:**
- `config.py` - Environment variables
- `log_utils.py` - Logging functions
- `late_post.py` - Social posting function
- `validation.py` - URL/text validation
- `merge.py` - Called as subprocess

**Key Functions:**
- `main()` - Entry point, processes all sheet rows
- `download_from_url()` - Downloads videos
- `upload_webdav_authenticated()` - Uploads to Nextcloud
- `create_nextcloud_share_link()` - Creates public links
- `resolve_path()` - Finds local files or downloads URLs

---

### 2. **merge.py** - Video Processing Engine
**Purpose:** Handles all video manipulation and rendering.

**Key Responsibilities:**
- Concatenates 3 videos (intro, main, exit)
- Converts videos to square format (1:1 aspect ratio)
- Adds text overlays with custom positioning
- Adds graphic overlays (logos/images)
- Applies crossfade transitions
- Renders final video file

**Imports:**
- `moviepy` - Video processing library
- `PIL/Pillow` - Image and text rendering
- `numpy` - Array operations

**Key Functions:**
- `concatenate_videos()` - Main video processing function
- `_make_textbox_clip()` - Creates text overlay graphics
- `_to_square()` - Converts videos to square format
- `_load_font()` - Loads custom or system fonts
- `_wrap_to_width()` - Text wrapping for long messages

**Called By:**
- `sheet.py` (via subprocess)

---

### 3. **late_post.py** - Social Media Posting
**Purpose:** Posts videos to social media platforms via Late API.

**Key Responsibilities:**
- Converts Nextcloud share URLs to download URLs
- Posts videos to all linked accounts on Late profile
- Supports scheduled posting with timezone
- Handles immediate or scheduled posts

**Imports:**
- `config.py` - API credentials
- `log_utils.py` - Logging
- `requests` - HTTP API calls

**Key Functions:**
- `post_video_to_all_accounts()` - Main posting function
- `build_nextcloud_download_url()` - URL conversion

**Called By:**
- `sheet.py` (after video upload)

---

### 4. **config.py** - Configuration Manager
**Purpose:** Centralized environment variable management.

**Key Responsibilities:**
- Loads `.env` file
- Provides `get_env()` helper function
- Validates required environment variables
- Sets up base directory paths

**Key Functions:**
- `get_env()` - Gets environment variable with validation

**Used By:**
- `sheet.py`
- `late_post.py`
- `webhook_make.py`
- `webtest.py`

---

### 5. **validation.py** - Input Validator
**Purpose:** Validates and normalizes user inputs.

**Key Responsibilities:**
- Validates Nextcloud URL formats
- Normalizes URLs to standard format
- Validates text color (hex codes)
- Validates text size (pixel values)
- Extracts share IDs from URLs

**Key Functions:**
- `validate_nextcloud_url()` - URL validation
- `normalize_nextcloud_url()` - URL normalization
- `validate_text_color()` - Color validation (#RRGGBB)
- `validate_text_size()` - Size validation (12-300px)
- `is_nextcloud_url()` - URL type detection

**Used By:**
- `sheet.py` (before processing)

---

### 6. **log_utils.py** - Logging System
**Purpose:** Comprehensive logging and error handling.

**Key Responsibilities:**
- Buffers stdout/stderr in memory
- Creates error log files on exceptions
- Provides logging decorators
- Writes status to Google Sheets
- Records errors with full tracebacks

**Key Functions:**
- `attach_log_streams()` - Sets up logging
- `flush_error_log()` - Creates error log file
- `get_logger()` - Gets logger instance
- `write_sheet_value()` - Updates Google Sheet cells
- `record_error()` - Records errors to sheet
- `log_call()` - Decorator for function logging

**Used By:**
- `sheet.py`
- `late_post.py`

---

### 7. **webhook_make.py** - Webhook Integration
**Purpose:** Sends video URLs to external webhooks (Make.com integration).

**Key Responsibilities:**
- Sends Nextcloud video URLs to webhook endpoints
- Used for external automation triggers

**Key Functions:**
- `send_nextcloud_video_url_to_webhook()` - HTTP POST to webhook

**Used By:**
- Can be called independently or integrated into workflow

---

### 8. **webtest.py** - Webhook Testing
**Purpose:** Test script for webhook functionality.

**Key Responsibilities:**
- Tests webhook connectivity
- Validates webhook responses

**Used By:**
- Manual testing only

---

## 📄 Supporting Files

### **requirements.txt**
Lists all Python dependencies:
- `numpy` - Numerical operations
- `moviepy` - Video processing
- `Pillow` - Image processing
- `requests` - HTTP requests
- `gspread` - Google Sheets API
- `google-auth` - Google authentication
- `python-dotenv` - Environment variables

### **runPython.sh**
Bash script for automated execution (cron jobs).

**Responsibilities:**
- Creates/activates Python virtual environment
- Installs dependencies
- Runs `sheet.py`
- Handles error logging
- Sets environment variables

**Used By:**
- Cron scheduler (automated runs)

---

## 📚 Documentation Files

### **docs/README.md**
Project overview and basic setup instructions.

### **docs/user_instructions.md**
User guide for filling out Google Sheets correctly.

### **docs/next_cloud_notes.md**
Technical details about Nextcloud integration.

### **docs/social_posting.md**
Documentation for social media posting features.

### **docs/temp_file_management.md**
Explains temporary file handling.

### **docs/setup_linux.md**
Linux server setup instructions.

### **docs/chron.md**
Cron job setup instructions.

---

## 🏗️ System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    EXTERNAL SERVICES                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Google Sheets│  │  Nextcloud   │  │  Late API    │          │
│  │   (Input)    │  │  (Storage)   │  │  (Social)    │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                  │                  │                   │
└─────────┼──────────────────┼──────────────────┼──────────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PYTHON APPLICATION                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    sheet.py                               │  │
│  │              (Main Orchestrator)                           │  │
│  │                                                            │  │
│  │  • Reads Google Sheets                                    │  │
│  │  • Downloads videos                                       │  │
│  │  • Calls merge.py                                         │  │
│  │  • Uploads to Nextcloud                                   │  │
│  │  • Calls late_post.py                                     │  │
│  │  • Updates Google Sheets                                  │  │
│  └───────┬────────────────────────────────────────────────────┘  │
│          │                                                        │
│          ├──────────────────────────────────────────┐           │
│          │                                            │           │
│          ▼                                            ▼           │
│  ┌──────────────┐                          ┌──────────────┐     │
│  │  merge.py    │                          │ late_post.py │     │
│  │              │                          │              │     │
│  │ Video Engine │                          │ Social Post  │     │
│  │              │                          │              │     │
│  │ • Concatenate│                          │ • Post video │     │
│  │ • Text overlay│                         │ • Schedule   │     │
│  │ • Square conv│                          │ • All accts  │     │
│  └──────────────┘                          └──────────────┘     │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              SUPPORTING MODULES                           │  │
│  │                                                            │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │  │
│  │  │  config.py   │  │ validation.py│  │ log_utils.py │   │  │
│  │  │              │  │              │  │              │   │  │
│  │  │ Env vars     │  │ URL/text     │  │ Logging      │   │  │
│  │  │              │  │ validation   │  │ Error handle │   │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘   │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        WORKFLOW STEPS                            │
└─────────────────────────────────────────────────────────────────┘

1. CRON JOB / MANUAL TRIGGER
   │
   ▼
   runPython.sh
   │
   ▼
   ┌─────────────────────────────────────────────────────────┐
   │ sheet.py (main())                                        │
   │                                                           │
   │ 1. Authenticate with Google Sheets API                    │
   │ 2. Read all rows from worksheet                          │
   │ 3. Filter rows where Generate = TRUE                      │
   └─────────────────────────────────────────────────────────┘
   │
   │ For each row:
   │
   ├─► VALIDATION PHASE
   │   │
   │   ├─► validation.py
   │   │   • Validate Nextcloud URLs
   │   │   • Validate text color/size
   │   │   • Normalize URLs
   │   │
   │   └─► If validation fails → Write error to sheet → Skip row
   │
   ├─► DOWNLOAD PHASE
   │   │
   │   ├─► sheet.py::download_from_url()
   │   │   • Check if URL or local file
   │   │   • Download from Nextcloud (cookie-based)
   │   │   • Save to temp_videos/ or /tmp/
   │   │
   │   └─► If download fails → Write error to sheet → Skip row
   │
   ├─► VIDEO PROCESSING PHASE
   │   │
   │   ├─► sheet.py calls merge.py (subprocess)
   │   │
   │   ├─► merge.py::concatenate_videos()
   │   │   • Load 3 video files
   │   │   • Convert each to square (1080x1080)
   │   │   • Add text overlays to middle video
   │   │   • Add graphic overlay
   │   │   • Apply crossfades
   │   │   • Concatenate intro → main → exit
   │   │   • Render to output file
   │   │
   │   └─► If processing fails → Write error to sheet → Skip row
   │
   ├─► UPLOAD PHASE
   │   │
   │   ├─► sheet.py::upload_webdav_authenticated()
   │   │   • Upload merged video to Nextcloud via WebDAV
   │   │   • Create directory structure if needed
   │   │
   │   ├─► sheet.py::create_nextcloud_share_link()
   │   │   • Use Nextcloud OCS API to create public share
   │   │   • Get share URL
   │   │
   │   └─► Write Download URL to Google Sheet
   │
   ├─► SOCIAL POSTING PHASE
   │   │
   │   ├─► late_post.py::post_video_to_all_accounts()
   │   │   • Convert share URL to download URL
   │   │   • POST to Late API
   │   │   • Schedule or post immediately
   │   │
   │   └─► Update sheet status to "POSTED"
   │
   └─► CLEANUP
       │
       └─► Update Generate column to FALSE
          Update status to DONE/POSTED/ERROR
```

---

## 🔗 File Dependencies Graph

```
┌─────────────────────────────────────────────────────────────┐
│                    DEPENDENCY TREE                           │
└─────────────────────────────────────────────────────────────┘

runPython.sh
    │
    └─► sheet.py (ENTRY POINT)
            │
            ├─► config.py
            │       └─► .env file
            │
            ├─► log_utils.py
            │       └─► (creates logs/ directory)
            │
            ├─► validation.py
            │       └─► (standalone, no deps)
            │
            ├─► merge.py (subprocess call)
            │       ├─► moviepy
            │       ├─► PIL/Pillow
            │       ├─► numpy
            │       └─► fonts/MinionPro-Regular.otf
            │
            └─► late_post.py
                    ├─► config.py
                    └─► log_utils.py

webhook_make.py
    │
    ├─► config.py
    └─► requests

webtest.py
    │
    ├─► config.py
    └─► requests
```

---

## 📊 Module Interaction Matrix

| Module | Uses | Used By |
|--------|------|---------|
| **sheet.py** | config, log_utils, validation, late_post, merge (subprocess) | runPython.sh |
| **merge.py** | moviepy, PIL, numpy | sheet.py (subprocess) |
| **late_post.py** | config, log_utils, requests | sheet.py |
| **config.py** | os, dotenv | sheet.py, late_post.py, webhook_make.py, webtest.py |
| **validation.py** | urllib.parse | sheet.py |
| **log_utils.py** | logging, sys, io | sheet.py, late_post.py |
| **webhook_make.py** | config, requests | (standalone) |
| **webtest.py** | config, requests | (standalone) |

---

## 🎯 Key Integration Points

### 1. **Google Sheets → sheet.py**
- **Connection:** Google Sheets API (gspread)
- **Data Flow:** Sheet rows → Python dictionaries
- **Columns Read:** Generate, Video URLs, Text, Locations, etc.
- **Columns Written:** Generate, Download URL, Error Message

### 2. **sheet.py → merge.py**
- **Connection:** Subprocess call
- **Data Flow:** Command-line arguments
- **Input:** Video file paths, text, locations, output path
- **Output:** Merged video file

### 3. **sheet.py → Nextcloud**
- **Connection:** WebDAV (upload) + OCS API (sharing)
- **Data Flow:** HTTP requests
- **Upload:** Merged video files
- **Download:** Source videos from share links

### 4. **sheet.py → late_post.py**
- **Connection:** Direct function call
- **Data Flow:** Function parameters
- **Input:** Nextcloud share URL, post text, schedule
- **Output:** Late API response

### 5. **All modules → config.py**
- **Connection:** `get_env()` function
- **Purpose:** Centralized credential management
- **Variables:** API keys, URLs, paths, credentials

### 6. **All modules → log_utils.py**
- **Connection:** Logging functions
- **Purpose:** Unified logging and error handling
- **Features:** File logging, sheet error writing, buffered output

---

## 🚀 Execution Flow Summary

1. **Trigger:** Cron job runs `runPython.sh` OR manual execution
2. **Setup:** Script activates venv, installs deps
3. **Entry:** `sheet.py::main()` starts
4. **Read:** Fetches Google Sheet data
5. **Process:** For each row with Generate=TRUE:
   - Validate inputs
   - Download videos
   - Process videos (merge.py)
   - Upload result
   - Create share link
   - Post to social media (late_post.py)
   - Update sheet status
6. **Complete:** All rows processed, script exits

---

## 📝 Notes

- **Environment Variables:** All sensitive data in `.env` file (not in repo)
- **Error Handling:** Errors written to both logs and Google Sheet
- **Status Tracking:** Generate column tracks: TRUE → LOADING → DONE/POSTED/ERROR
- **Temporary Files:** Auto-cleaned (server uses /tmp, local uses temp_videos/)
- **Fonts:** Custom font in `fonts/` directory, falls back to system fonts
- **Assets:** Logo/images in `assets/` directory for overlays

---

## 🗺️ Complete Connection Map

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         EXTERNAL WORLD                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│   ┌──────────────┐      ┌──────────────┐      ┌──────────────┐        │
│   │ Google Sheets│      │  Nextcloud   │      │  Late API    │        │
│   │   (Input)    │      │  (Storage)   │      │  (Social)    │        │
│   └──────┬───────┘      └──────┬───────┘      └──────┬───────┘        │
│          │                      │                      │                 │
│          │ Read rows            │ Download/Upload      │ Post videos     │
│          │ Write status         │ Create shares        │ Schedule posts  │
│          │                      │                      │                 │
└──────────┼──────────────────────┼──────────────────────┼─────────────────┘
           │                      │                      │
           │                      │                      │
           ▼                      ▼                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      PYTHON APPLICATION LAYER                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│                          ┌──────────────────┐                           │
│                          │  runPython.sh    │                           │
│                          │  (Cron Wrapper)  │                           │
│                          └────────┬─────────┘                           │
│                                   │                                      │
│                                   │ Executes                            │
│                                   ▼                                      │
│                    ┌───────────────────────────────────┐                │
│                    │         sheet.py                  │                │
│                    │    ⭐ MAIN ORCHESTRATOR ⭐        │                │
│                    │                                    │                │
│                    │  ┌────────────────────────────┐  │                │
│                    │  │ 1. Read Google Sheets      │  │                │
│                    │  │ 2. Validate inputs         │  │                │
│                    │  │ 3. Download videos         │  │                │
│                    │  │ 4. Process videos          │  │                │
│                    │  │ 5. Upload to Nextcloud    │  │                │
│                    │  │ 6. Post to social media   │  │                │
│                    │  │ 7. Update sheet status     │  │                │
│                    │  └────────────────────────────┘  │                │
│                    └─────┬───────────────────┬────────┘                │
│                          │                   │                          │
│        ┌─────────────────┼───────────────────┼─────────────────┐       │
│        │                 │                   │                 │       │
│        ▼                 ▼                   ▼                 ▼       │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────┐  ┌──────────┐  │
│  │ config.py│    │ validation.py│    │ late_post.py │  │log_utils │  │
│  │          │    │              │    │              │  │          │  │
│  │ • Env    │    │ • URL check  │    │ • Post video │  │ • Log    │  │
│  │ • Creds  │    │ • Text valid │    │ • Schedule   │  │ • Errors │  │
│  │ • Paths  │    │ • Normalize  │    │ • All accts  │  │ • Sheet  │  │
│  └──────────┘    └──────────────┘    └──────────────┘  └──────────┘  │
│        │                                                               │
│        │                                                               │
│        └───────────────────┐                                          │
│                            │                                          │
│                            ▼                                          │
│                    ┌──────────────┐                                   │
│                    │  merge.py    │                                   │
│                    │  (Subprocess)│                                   │
│                    │              │                                   │
│                    │ • Concatenate│                                   │
│                    │ • Text overlay│                                  │
│                    │ • Square conv│                                   │
│                    │ • Crossfades │                                   │
│                    └──────────────┘                                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Connection Types Legend:

```
───► Direct import/function call
═══► Subprocess call (separate process)
───► HTTP API call
═══► File I/O operation
```

### Detailed File Connections:

```
sheet.py
├──► config.py (get_env for credentials)
├──► log_utils.py (logging, error handling)
├──► validation.py (validate URLs, text, colors)
├──► late_post.py (post_video_to_all_accounts function)
├──► merge.py (subprocess call with CLI args)
├──► Google Sheets API (read/write via gspread)
├──► Nextcloud WebDAV (upload files)
└──► Nextcloud OCS API (create share links)

merge.py
├──► moviepy (video processing)
├──► PIL/Pillow (text rendering)
├──► numpy (array operations)
└──► fonts/MinionPro-Regular.otf (custom font)

late_post.py
├──► config.py (API keys)
├──► log_utils.py (logging)
└──► Late API (HTTP POST requests)

config.py
└──► .env file (environment variables)

log_utils.py
├──► logging (Python standard library)
└──► Google Sheets (write errors via gspread)

webhook_make.py
├──► config.py (webhook URL)
└──► HTTP webhook (POST request)

webtest.py
├──► config.py (test URLs)
└──► HTTP webhook (test POST)
```

---

**Last Updated:** Based on current codebase structure
**Main Entry Point:** `sheet.py` (via `runPython.sh` for automation)

