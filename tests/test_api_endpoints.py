#!/usr/bin/env python3
"""
Test cases for API endpoints.

Tests the FastAPI endpoints to ensure they work correctly with MoviePy.
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

try:
    from fastapi.testclient import TestClient
    from api.main import app
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    print("WARNING: FastAPI TestClient not available - API tests will be skipped")


class TestAPIEndpoints(unittest.TestCase):
    """Test cases for API endpoints."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures once for all tests."""
        if not FASTAPI_AVAILABLE:
            return
        
        cls.client = TestClient(app)
        cls.test_dir = tempfile.mkdtemp(prefix="api_test_")
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
        if hasattr(cls, 'test_dir') and os.path.exists(cls.test_dir):
            shutil.rmtree(cls.test_dir)
            print(f"\nCleaned up test directory: {cls.test_dir}")
    
    def setUp(self):
        """Set up before each test."""
        if not FASTAPI_AVAILABLE:
            self.skipTest("FastAPI TestClient not available")
    
    def create_test_video_file(self, duration=2, with_audio=True):
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
            audio_array = audio_array.reshape(-1, 1)  # Mono audio
            audio = AudioArrayClip(audio_array, fps=sample_rate)
            video = video.with_audio(audio)
        
        # Save to temporary file
        output_path = os.path.join(self.test_dir, "test_video.mp4")
        video.write_videofile(output_path, logger=None, codec="libx264", audio_codec="aac")
        video.close()
        if with_audio:
            audio.close()
        
        return output_path
    
    def test_health_endpoint(self):
        """Test health check endpoint."""
        if not FASTAPI_AVAILABLE:
            self.skipTest("FastAPI TestClient not available")
        
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        self.assertIn("status", response.json())
    
    def test_remove_audio_endpoint_file_upload(self):
        """Test remove-audio endpoint with file upload."""
        if not FASTAPI_AVAILABLE or not self.moviepy_available:
            self.skipTest("FastAPI or MoviePy not available")
        
        # Create test video file
        video_path = self.create_test_video_file(duration=2, with_audio=True)
        
        # Upload file and process
        with open(video_path, "rb") as f:
            response = self.client.post(
                "/api/v1/videos/remove-audio",
                files={"video": ("test_video.mp4", f, "video/mp4")},
                data={}
            )
        
        # Should return job_id
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("job_id", data)
        self.assertIn("status", data)
        self.assertEqual(data["status"], "pending")
    
    def test_remove_audio_endpoint_no_file(self):
        """Test remove-audio endpoint without file or URL."""
        if not FASTAPI_AVAILABLE:
            self.skipTest("FastAPI TestClient not available")
        
        # Request without file or URL
        response = self.client.post(
            "/api/v1/videos/remove-audio",
            files={},
            data={}
        )
        
        # Should return 400 Bad Request
        self.assertEqual(response.status_code, 400)
    
    def test_color_grade_endpoint_file_upload(self):
        """Test color-grade endpoint with file upload."""
        if not FASTAPI_AVAILABLE or not self.moviepy_available:
            self.skipTest("FastAPI or MoviePy not available")
        
        # Create test video file
        video_path = self.create_test_video_file(duration=2, with_audio=True)
        
        # Upload file and process
        with open(video_path, "rb") as f:
            response = self.client.post(
                "/api/v1/videos/color-grade",
                files={"video": ("test_video.mp4", f, "video/mp4")},
                data={"preset": "cinematic", "brightness": "0.1", "contrast": "1.2"}
            )
        
        # Should return job_id
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("job_id", data)
        self.assertIn("status", data)
    
    def test_crop_zoom_endpoint_file_upload(self):
        """Test crop-zoom endpoint with file upload."""
        if not FASTAPI_AVAILABLE or not self.moviepy_available:
            self.skipTest("FastAPI or MoviePy not available")
        
        # Create test video file
        video_path = self.create_test_video_file(duration=2, with_audio=True)
        
        # Upload file and process
        with open(video_path, "rb") as f:
            response = self.client.post(
                "/api/v1/videos/crop-zoom",
                files={"video": ("test_video.mp4", f, "video/mp4")},
                data={"aspect_ratio": "1:1", "background_color": "#000000"}
            )
        
        # Should return job_id
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("job_id", data)
        self.assertIn("status", data)
    
    def test_merge_audio_video_endpoint_file_upload(self):
        """Test merge-audio-video endpoint with file uploads."""
        if not FASTAPI_AVAILABLE or not self.moviepy_available:
            self.skipTest("FastAPI or MoviePy not available")
        
        # Create test video and audio files
        video_path = self.create_test_video_file(duration=3, with_audio=False)
        
        from moviepy import AudioArrayClip
        import numpy as np
        sample_rate = 44100
        duration = 2
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio_array = np.sin(2 * np.pi * 440 * t)
        audio_array = audio_array.reshape(-1, 1)  # Mono audio
        audio = AudioArrayClip(audio_array, fps=sample_rate)
        audio_path = os.path.join(self.test_dir, "test_audio.mp3")
        audio.write_audiofile(audio_path, logger=None, codec='mp3')
        audio.close()
        
        # Upload files and process
        with open(video_path, "rb") as vf, open(audio_path, "rb") as af:
            response = self.client.post(
                "/api/v1/videos/merge-audio-video",
                files={
                    "video": ("test_video.mp4", vf, "video/mp4"),
                    "audio": ("test_audio.mp3", af, "audio/mpeg")
                },
                data={}
            )
        
        # Should return job_id
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("job_id", data)
        self.assertIn("status", data)
        
        # Clean up
        if os.path.exists(audio_path):
            os.remove(audio_path)


if __name__ == "__main__":
    # Run tests with verbose output
    unittest.main(verbosity=2)

