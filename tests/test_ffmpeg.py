#!/usr/bin/env python3
"""
Test script to verify FFmpeg availability in the Python environment.

This script follows the Python backend pattern from documentation:
- Assumes FFmpeg is installed at system level (via apt-get, brew, etc.)
- Available via system PATH
- Uses subprocess to call FFmpeg directly (no Python wrapper packages)

Run: python test_ffmpeg.py
"""

import sys
import shutil
import subprocess
from pathlib import Path


def test_ffmpeg_availability():
    """Test FFmpeg availability using subprocess, following Python backend pattern."""
    print("=" * 80)
    print("FFmpeg Availability Test (Python Backend Pattern)")
    print("=" * 80)
    print()
    
    # Test 1: Check if FFmpeg is in PATH
    print("1. Testing FFmpeg availability in system PATH...")
    ffmpeg_path = shutil.which("ffmpeg")
    
    if not ffmpeg_path:
        print("   [FAIL] FFmpeg NOT found in system PATH")
        print()
        print("   Please install FFmpeg system-wide:")
        print("   - Linux: sudo apt-get install ffmpeg")
        print("   - macOS: brew install ffmpeg")
        print("   - Windows: Download from https://ffmpeg.org/download.html")
        return False
    
    print(f"   [OK] FFmpeg found: {ffmpeg_path}")
    print(f"   [OK] Path exists: {Path(ffmpeg_path).exists()}")
    print()
    
    # Test 2: Test FFmpeg version using subprocess (Python backend pattern)
    print("2. Testing FFmpeg version using subprocess...")
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            print(f"   [OK] {version_line}")
        else:
            print(f"   [FAIL] FFmpeg version check failed: {result.stderr}")
            return False
    except FileNotFoundError:
        print("   [FAIL] FFmpeg executable not found")
        return False
    except Exception as e:
        print(f"   [FAIL] Error running FFmpeg: {str(e)}")
        return False
    
    print()
    
    # Test 3: Test FFprobe using subprocess (Python backend pattern)
    print("3. Testing FFprobe using subprocess...")
    ffprobe_path = shutil.which("ffprobe")
    
    if not ffprobe_path:
        print("   [WARN] FFprobe not found in PATH (may still work if in same directory as FFmpeg)")
    else:
        try:
            result = subprocess.run(
                ["ffprobe", "-version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                version_line = result.stdout.split('\n')[0]
                print(f"   [OK] {version_line}")
            else:
                print(f"   [WARN] FFprobe found but version check failed")
        except Exception as e:
            print(f"   [WARN] Error running FFprobe: {str(e)}")
    
    print()
    
    # Test 4: Test subprocess.call() pattern (exactly as in Python backend)
    print("4. Testing subprocess.call() pattern (Python backend style)...")
    try:
        # Test with a simple command that should always work
        result = subprocess.call(
            ["ffmpeg", "-version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        if result == 0:
            print("   [OK] subprocess.call() works correctly")
        else:
            print(f"   [WARN] subprocess.call() returned non-zero: {result}")
    except Exception as e:
        print(f"   [FAIL] Error with subprocess.call(): {str(e)}")
        return False
    
    print()
    
    # Test 5: Test subprocess.run() pattern (exactly as in Python backend)
    print("5. Testing subprocess.run() pattern (Python backend style)...")
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            print("   [OK] subprocess.run() works correctly")
        else:
            print(f"   [WARN] subprocess.run() returned non-zero: {result.returncode}")
    except Exception as e:
        print(f"   [FAIL] Error with subprocess.run(): {str(e)}")
        return False
    
    print()
    print("=" * 80)
    print("[SUCCESS] FFmpeg is available and ready to use via subprocess!")
    print("=" * 80)
    return True


if __name__ == "__main__":
    success = test_ffmpeg_availability()
    sys.exit(0 if success else 1)

