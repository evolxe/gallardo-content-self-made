# Tests

This directory contains all test files for the video processing API.

## Test Files

### `test_ffmpeg.py`
Test script to verify FFmpeg availability in the Python environment.

**Purpose:**
- Verifies FFmpeg is available in system PATH
- Tests FFmpeg version using subprocess
- Tests FFprobe availability
- Validates subprocess.call() and subprocess.run() patterns

**Usage:**
```bash
python tests/test_ffmpeg.py
```

## Running Tests

To run all tests:
```bash
# From project root
python -m pytest tests/
```

Or run individual test files:
```bash
python tests/test_ffmpeg.py
```

## Test Results

Test result files (if any) should be stored in this directory or a `results/` subdirectory.

