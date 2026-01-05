#!/usr/bin/env python3
"""
Test cases for MoviePy-based video/audio processing functions.

Tests the functions that replaced direct FFmpeg subprocess calls:
- convert_local_video_to_mp3
- local_video_to_mp3
- optimize_video_for_reels
"""

import unittest
import os
import sys
import tempfile
import shutil
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from api.services.ytdlp_service import (
    convert_local_video_to_mp3,
    local_video_to_mp3,
    optimize_video_for_reels
)


class TestMoviePyFunctions(unittest.TestCase):
    """Test cases for MoviePy-based video processing functions."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures once for all tests."""
        cls.test_dir = tempfile.mkdtemp(prefix="video_test_")
        print(f"\nTest directory: {cls.test_dir}")
        
        # Check if MoviePy is available
        try:
            from moviepy import VideoFileClip
            cls.moviepy_available = True
        except ImportError:
            cls.moviepy_available = False
            print("WARNING: MoviePy not available - some tests will be skipped")
    
    @classmethod
    def tearDownClass(cls):
        """Clean up test directory."""
        if os.path.exists(cls.test_dir):
            shutil.rmtree(cls.test_dir)
            print(f"\nCleaned up test directory: {cls.test_dir}")
    
    def setUp(self):
        """Set up before each test."""
        self.test_video_path = None
    
    def tearDown(self):
        """Clean up after each test."""
        # Clean up any created test files
        if self.test_video_path and os.path.exists(self.test_video_path):
            try:
                os.remove(self.test_video_path)
            except:
                pass
    
    def create_test_video(self, duration=2, with_audio=True):
        """Create a simple test video file using MoviePy."""
        if not self.moviepy_available:
            self.skipTest("MoviePy not available")
        
        from moviepy import ColorClip, AudioArrayClip
        import numpy as np
        
        # Create a simple colored video
        video = ColorClip(size=(640, 480), color=(255, 0, 0), duration=duration)
        video = video.with_fps(30)
        
        if with_audio:
            # Create a simple audio tone using AudioArrayClip (MoviePy v2)
            sample_rate = 44100
            t = np.linspace(0, duration, int(sample_rate * duration))
            audio_array = np.sin(2 * np.pi * 440 * t)
            # AudioArrayClip expects shape (n_samples, n_channels)
            audio_array = audio_array.reshape(-1, 1)  # Mono audio
            audio = AudioArrayClip(audio_array, fps=sample_rate)
            video = video.with_audio(audio)
        
        # Save to temporary file
        output_path = os.path.join(self.test_dir, f"test_video_{duration}s.mp4")
        video.write_videofile(output_path, logger=None, codec="libx264", audio_codec="aac")
        video.close()
        if with_audio:
            audio.close()
        
        self.test_video_path = output_path
        return output_path
    
    def test_convert_local_video_to_mp3_success(self):
        """Test successful audio extraction from video."""
        if not self.moviepy_available:
            self.skipTest("MoviePy not available")
        
        # Create test video with audio
        video_path = self.create_test_video(duration=2, with_audio=True)
        
        # Extract audio
        mp3_path = convert_local_video_to_mp3(video_path)
        
        # Verify output file exists
        self.assertTrue(os.path.exists(mp3_path), "MP3 file should be created")
        self.assertTrue(mp3_path.endswith('.mp3'), "Output should be MP3 file")
        self.assertGreater(os.path.getsize(mp3_path), 0, "MP3 file should not be empty")
        
        # Clean up
        if os.path.exists(mp3_path):
            os.remove(mp3_path)
    
    def test_convert_local_video_to_mp3_no_audio(self):
        """Test audio extraction from video without audio track."""
        if not self.moviepy_available:
            self.skipTest("MoviePy not available")
        
        # Create test video without audio
        video_path = self.create_test_video(duration=2, with_audio=False)
        
        # Should raise exception
        with self.assertRaises(Exception) as context:
            convert_local_video_to_mp3(video_path)
        
        self.assertIn("no audio track", str(context.exception).lower())
    
    def test_convert_local_video_to_mp3_invalid_file(self):
        """Test audio extraction with invalid file path."""
        if not self.moviepy_available:
            self.skipTest("MoviePy not available")
        
        invalid_path = os.path.join(self.test_dir, "nonexistent_video.mp4")
        
        with self.assertRaises(Exception):
            convert_local_video_to_mp3(invalid_path)
    
    def test_local_video_to_mp3_alias(self):
        """Test that local_video_to_mp3 is an alias for convert_local_video_to_mp3."""
        if not self.moviepy_available:
            self.skipTest("MoviePy not available")
        
        # Create test video with audio
        video_path = self.create_test_video(duration=2, with_audio=True)
        
        # Both functions should produce the same result
        mp3_path1 = convert_local_video_to_mp3(video_path)
        mp3_path2 = local_video_to_mp3(video_path)
        
        # Both should create MP3 files
        self.assertTrue(os.path.exists(mp3_path1))
        self.assertTrue(os.path.exists(mp3_path2))
        
        # Clean up
        for path in [mp3_path1, mp3_path2]:
            if os.path.exists(path):
                os.remove(path)
    
    def test_optimize_video_for_reels_default_output(self):
        """Test video optimization with default output filename."""
        if not self.moviepy_available:
            self.skipTest("MoviePy not available")
        
        # Create test video
        video_path = self.create_test_video(duration=2, with_audio=True)
        
        # Optimize video
        output_path = optimize_video_for_reels(video_path)
        
        # Verify output file exists
        self.assertTrue(os.path.exists(output_path), "Optimized video should be created")
        self.assertTrue(output_path.startswith(os.path.dirname(video_path)))
        self.assertIn("reeloptimized", output_path)
        
        # Verify video properties (basic check)
        from moviepy import VideoFileClip
        output_video = VideoFileClip(output_path)
        try:
            # Should be resized to height 1080
            self.assertEqual(output_video.h, 1080, "Video should be resized to height 1080")
            # Should have 60 FPS
            self.assertEqual(output_video.fps, 60, "Video should have 60 FPS")
        finally:
            output_video.close()
        
        # Clean up
        if os.path.exists(output_path):
            os.remove(output_path)
    
    def test_optimize_video_for_reels_custom_output(self):
        """Test video optimization with custom output filename."""
        if not self.moviepy_available:
            self.skipTest("MoviePy not available")
        
        # Create test video
        video_path = self.create_test_video(duration=2, with_audio=True)
        custom_output = os.path.join(self.test_dir, "custom_optimized.mp4")
        
        # Optimize video
        output_path = optimize_video_for_reels(video_path, custom_output)
        
        # Verify output file exists at custom location
        self.assertEqual(output_path, custom_output)
        self.assertTrue(os.path.exists(output_path))
        
        # Clean up
        if os.path.exists(output_path):
            os.remove(output_path)
    
    def test_optimize_video_for_reels_invalid_file(self):
        """Test video optimization with invalid file path."""
        if not self.moviepy_available:
            self.skipTest("MoviePy not available")
        
        invalid_path = os.path.join(self.test_dir, "nonexistent_video.mp4")
        
        with self.assertRaises(Exception):
            optimize_video_for_reels(invalid_path)


if __name__ == "__main__":
    # Run tests with verbose output
    unittest.main(verbosity=2)

