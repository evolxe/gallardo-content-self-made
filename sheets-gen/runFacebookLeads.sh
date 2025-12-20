#!/bin/bash

# Script to process Facebook leads and send to Goal Catcher
# Suitable for cron job execution (runs every 5 minutes)

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

# Python executable
PYTHON_BIN="${PYTHON_BIN:-python3}"

# Virtual environment directory
VENV_DIR="$SCRIPT_DIR/venv"

# Logging setup
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

TIMESTAMP="$(date '+%Y%m%d-%H%M%S')"
ERR_LOG="$LOG_DIR/facebook_leads_error_$TIMESTAMP.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

log "Starting runFacebookLeads.sh"
log "Error log: $ERR_LOG (will be created only if an error occurs)"

export GALLARDO_ERR_LOG="$ERR_LOG"

# Check if Python is available
if ! command -v "$PYTHON_BIN" &> /dev/null; then
    log "ERROR: $PYTHON_BIN not found. Please install Python 3."
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    log "Creating virtual environment at $VENV_DIR"
    "$PYTHON_BIN" -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        log "ERROR: Failed to create virtual environment"
        exit 1
    fi
fi

# Activate virtual environment
log "Activating virtual environment"
source "$VENV_DIR/bin/activate"

if [ $? -ne 0 ]; then
    log "ERROR: Failed to activate virtual environment"
    exit 1
fi

# Upgrade pip
log "Upgrading pip"
pip install --quiet --upgrade pip

# Install/upgrade dependencies
if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    log "Installing dependencies from requirements.txt"
    pip install --quiet -r "$SCRIPT_DIR/requirements.txt"
    if [ $? -ne 0 ]; then
        log "ERROR: Failed to install dependencies"
        exit 1
    fi
else
    log "WARNING: requirements.txt not found"
fi

# Run process_facebook_leads.py
log "Running process_facebook_leads.py"
"$VENV_DIR/bin/python" "$SCRIPT_DIR/process_facebook_leads.py"

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    log "process_facebook_leads.py completed successfully"
else
    log "ERROR: process_facebook_leads.py exited with code $EXIT_CODE"
fi

# Deactivate virtual environment
deactivate

log "Finished runFacebookLeads.sh"
exit $EXIT_CODE

