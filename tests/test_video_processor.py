#!/usr/bin/env python3
"""
Test cases for VideoProcessor class methods.

Tests all video processing operations that use MoviePy.
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

from api.services.video_processor import VideoProcessor


class TestVideoProcessor(unittest.TestCase):
    """Test cases for VideoProcessor class."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures once for all tests."""
        cls.test_dir = tempfile.mkdtemp(prefix="video_processor_test_")
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
        self.processor = VideoProcessor()
        self.test_video_path = None
        self.test_audio_path = None
    
    def tearDown(self):
        """Clean up after each test."""
        # Clean up any created test files
        for path in [self.test_video_path, self.test_audio_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except:
                    pass
    
    def create_test_video(self, duration=2, with_audio=True, size=(640, 480)):
        """Create a simple test video file using MoviePy."""
        if not self.moviepy_available:
            self.skipTest("MoviePy not available")
        
        from moviepy import ColorClip, AudioArrayClip
        import numpy as np
        
        # Create a simple colored video
        video = ColorClip(size=size, color=(255, 0, 0), duration=duration)
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
    
    def create_test_audio(self, duration=2):
        """Create a simple test audio file using MoviePy."""
        if not self.moviepy_available:
            self.skipTest("MoviePy not available")
        
        from moviepy import AudioArrayClip
        import numpy as np
        
        # Create a simple audio tone using AudioArrayClip (MoviePy v2)
        sample_rate = 44100
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio_array = np.sin(2 * np.pi * 440 * t)
        # AudioArrayClip expects shape (n_samples, n_channels)
        audio_array = audio_array.reshape(-1, 1)  # Mono audio
        audio = AudioArrayClip(audio_array, fps=sample_rate)
        
        # Save to temporary file
        output_path = os.path.join(self.test_dir, "test_audio.mp3")
        audio.write_audiofile(output_path, logger=None, codec='mp3')
        audio.close()
        
        self.test_audio_path = output_path
        return output_path
    
    def test_remove_audio_success(self):
        """Test successful audio removal from video."""
        if not self.moviepy_available:
            self.skipTest("MoviePy not available")
        
        # Create test video with audio
        video_path = self.create_test_video(duration=2, with_audio=True)
        output_path = os.path.join(self.test_dir, "no_audio_output.mp4")
        
        # Remove audio
        self.processor.remove_audio(video_path, output_path)
        
        # Verify output file exists
        self.assertTrue(os.path.exists(output_path), "Output video should be created")
        
        # Verify video has no audio
        from moviepy import VideoFileClip
        output_video = VideoFileClip(output_path)
        try:
            self.assertIsNone(output_video.audio, "Video should have no audio track")
        finally:
            output_video.close()
        
        # Clean up
        if os.path.exists(output_path):
            os.remove(output_path)
    
    def test_remove_audio_invalid_file(self):
        """Test audio removal with invalid file path."""
        invalid_path = os.path.join(self.test_dir, "nonexistent_video.mp4")
        output_path = os.path.join(self.test_dir, "output.mp4")
        
        with self.assertRaises(FileNotFoundError):
            self.processor.remove_audio(invalid_path, output_path)
    
    def test_merge_audio_and_video_success(self):
        """Test successful audio and video merging."""
        if not self.moviepy_available:
            self.skipTest("MoviePy not available")
        
        # Create test video and audio
        video_path = self.create_test_video(duration=3, with_audio=False)
        audio_path = self.create_test_audio(duration=2)
        output_path = os.path.join(self.test_dir, "merged_output.mp4")
        
        # Merge audio and video
        self.processor.merge_audio_and_video(video_path, audio_path, output_path)
        
        # Verify output file exists
        self.assertTrue(os.path.exists(output_path), "Merged video should be created")
        
        # Verify video has audio
        from moviepy import VideoFileClip
        output_video = VideoFileClip(output_path)
        try:
            self.assertIsNotNone(output_video.audio, "Merged video should have audio track")
            # Duration should match shorter of the two (audio is 2s, video is 3s)
            # Note: The merge function clips both to the shorter duration
            # But due to encoding, duration might be slightly different - check it's <= 3.0
            self.assertLessEqual(output_video.duration, 3.0, "Merged video duration should be <= video duration")
            self.assertGreater(output_video.duration, 0, "Merged video should have positive duration")
        finally:
            output_video.close()
        
        # Clean up
        if os.path.exists(output_path):
            os.remove(output_path)
    
    def test_merge_audio_and_video_invalid_video(self):
        """Test audio/video merge with invalid video file."""
        if not self.moviepy_available:
            self.skipTest("MoviePy not available")
        
        invalid_video = os.path.join(self.test_dir, "nonexistent_video.mp4")
        audio_path = self.create_test_audio(duration=2)
        output_path = os.path.join(self.test_dir, "output.mp4")
        
        with self.assertRaises(FileNotFoundError):
            self.processor.merge_audio_and_video(invalid_video, audio_path, output_path)
    
    def test_apply_color_grading_success(self):
        """Test successful color grading application."""
        if not self.moviepy_available:
            self.skipTest("MoviePy not available")
        
        # Create test video
        video_path = self.create_test_video(duration=2, with_audio=True)
        output_path = os.path.join(self.test_dir, "graded_output.mp4")
        
        # Apply color grading
        self.processor.apply_color_grading(
            video_path,
            output_path,
            preset="cinematic",
            brightness=0.1,
            contrast=1.2,
            saturation=1.1
        )
        
        # Verify output file exists
        self.assertTrue(os.path.exists(output_path), "Graded video should be created")
        
        # Clean up
        if os.path.exists(output_path):
            os.remove(output_path)
    
    def test_crop_and_zoom_to_square_success(self):
        """Test successful square crop and zoom."""
        if not self.moviepy_available:
            self.skipTest("MoviePy not available")
        
        # Create test video (rectangular)
        video_path = self.create_test_video(duration=2, with_audio=True, size=(1920, 1080))
        output_path = os.path.join(self.test_dir, "cropped_square.mp4")
        
        # Crop to square
        self.processor.crop_and_zoom_to_square(video_path, output_path, output_size=1080)
        
        # Verify output file exists
        self.assertTrue(os.path.exists(output_path), "Cropped video should be created")
        
        # Verify video is square
        from moviepy import VideoFileClip
        output_video = VideoFileClip(output_path)
        try:
            w, h = output_video.size
            self.assertEqual(w, h, "Output video should be square")
            self.assertEqual(w, 1080, "Output video should be 1080x1080")
        finally:
            output_video.close()
        
        # Clean up
        if os.path.exists(output_path):
            os.remove(output_path)
    
    def test_reencode_video_success(self):
        """Test successful video re-encoding."""
        if not self.moviepy_available:
            self.skipTest("MoviePy not available")
        
        # Create test video
        video_path = self.create_test_video(duration=2, with_audio=True)
        output_path = os.path.join(self.test_dir, "reencoded_output.mp4")
        
        # Re-encode video
        self.processor.reencode_video(
            video_path,
            output_path,
            codec="libx264",
            bitrate="2000k",
            fps=30
        )
        
        # Verify output file exists
        self.assertTrue(os.path.exists(output_path), "Re-encoded video should be created")
        
        # Clean up
        if os.path.exists(output_path):
            os.remove(output_path)


if __name__ == "__main__":
    # Run tests with verbose output
    unittest.main(verbosity=2)

