# Test Suite for Video Processing API

This directory contains comprehensive test cases for the video processing functionality.

## Test Files

- **`test_moviepy_functions.py`** - Tests for MoviePy-based functions that replaced direct FFmpeg subprocess calls:
  - `convert_local_video_to_mp3()` - Audio extraction from video
  - `local_video_to_mp3()` - Alias function
  - `optimize_video_for_reels()` - Video optimization for social media

- **`test_video_processor.py`** - Tests for VideoProcessor class methods:
  - `remove_audio()` - Remove audio track from video
  - `merge_audio_and_video()` - Merge separate audio with video
  - `apply_color_grading()` - Apply color grading presets
  - `crop_and_zoom_to_square()` - Crop and resize videos
  - `reencode_video()` - Re-encode videos with different settings

- **`test_api_endpoints.py`** - Tests for FastAPI endpoints:
  - Health check endpoint
  - Remove audio endpoint
  - Color grade endpoint
  - Crop zoom endpoint
  - Merge audio/video endpoint

- **`test_ffmpeg.py`** - Tests for FFmpeg availability (legacy, kept for reference)

- **`run_all_tests.py`** - Script to run all test suites at once

## Prerequisites

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Ensure FFmpeg is installed:**
   - FFmpeg is required by MoviePy for video encoding/decoding
   - MoviePy uses FFmpeg internally (no direct subprocess calls)
   - See `test_ffmpeg.py` to verify FFmpeg availability

3. **MoviePy must be available:**
   - Tests will skip if MoviePy is not installed
   - MoviePy is listed in `requirements.txt`

## Running Tests

### Run Individual Test Files

```bash
# Test MoviePy functions
python tests/test_moviepy_functions.py

# Test VideoProcessor class
python tests/test_video_processor.py

# Test API endpoints
python tests/test_api_endpoints.py

# Test FFmpeg availability
python tests/test_ffmpeg.py
```

### Run All Tests

```bash
# Using the test runner script
python tests/run_all_tests.py

# Or using unittest discovery
python -m unittest discover -s tests -p "test_*.py" -v

# Or using pytest (if installed)
pytest tests/ -v
```

## Test Coverage

### MoviePy Functions Tests
- ✅ Successful audio extraction from video
- ✅ Audio extraction from video without audio track (error handling)
- ✅ Audio extraction with invalid file path (error handling)
- ✅ Alias function verification
- ✅ Video optimization with default output filename
- ✅ Video optimization with custom output filename
- ✅ Video optimization with invalid file path (error handling)

### VideoProcessor Tests
- ✅ Remove audio from video
- ✅ Remove audio with invalid file (error handling)
- ✅ Merge audio and video
- ✅ Merge with invalid video file (error handling)
- ✅ Apply color grading
- ✅ Crop and zoom to square
- ✅ Re-encode video

### API Endpoint Tests
- ✅ Health check endpoint
- ✅ Remove audio endpoint with file upload
- ✅ Remove audio endpoint without file/URL (error handling)
- ✅ Color grade endpoint with file upload
- ✅ Crop zoom endpoint with file upload
- ✅ Merge audio/video endpoint with file uploads

## Test Environment

Tests create temporary files in system temp directories:
- Test files are automatically cleaned up after each test
- Test directories are removed after test suites complete
- No permanent files are created during testing

## Expected Behavior

### Successful Tests
- All tests should pass when MoviePy and FFmpeg are properly installed
- Test output files are verified for existence and basic properties
- Video properties (dimensions, FPS, duration) are validated where applicable

### Skipped Tests
- Tests are automatically skipped if MoviePy is not available
- Tests are skipped if required dependencies are missing
- Skipped tests are reported but don't fail the test suite

### Failed Tests
- Tests fail if functionality doesn't work as expected
- Error messages provide details about what went wrong
- Check that FFmpeg is installed and accessible if encoding tests fail

## Troubleshooting

### "MoviePy not available" Warnings
- Install MoviePy: `pip install moviepy`
- Verify installation: `python -c "from moviepy import VideoFileClip; print('OK')"`

### "FFmpeg not found" Errors
- Install FFmpeg system-wide (see `test_ffmpeg.py` for instructions)
- Verify FFmpeg is in PATH: `ffmpeg -version`
- MoviePy requires FFmpeg to be accessible

### Import Errors
- Ensure project root is in Python path
- Run tests from project root directory
- Check that all dependencies in `requirements.txt` are installed

### Test Timeouts
- Video processing can be slow on some systems
- Tests use short-duration videos (2-3 seconds) to minimize runtime
- If tests timeout, check system resources (CPU, memory, disk)

## Notes

- Tests use `unittest` framework (Python built-in)
- Tests can also be run with `pytest` if preferred
- All video/audio files created during tests are temporary and cleaned up
- Tests verify both success cases and error handling
- API endpoint tests use FastAPI's `TestClient` for HTTP testing
