"""
Video processing service for audio removal and other video operations.
"""

import os
import sys
from pathlib import Path
from typing import List, Optional, Dict

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from moviepy import VideoFileClip
from scenedetect import VideoManager, SceneManager
from scenedetect.detectors import ContentDetector


class VideoProcessor:
    """Service for processing videos."""
    
    def remove_audio(self, input_path: str, output_path: str):
        """
        Remove audio track from a video file.
        
        Args:
            input_path: Path to input video file
            output_path: Path to save output video (without audio)
            
        Raises:
            FileNotFoundError: If input file doesn't exist
            Exception: If video processing fails
        """
        # Validate input file exists
        if not Path(input_path).exists():
            raise FileNotFoundError(f"Input video file not found: {input_path}")
        
        # Ensure output directory exists
        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load video
        video = VideoFileClip(input_path)
        
        try:
            # Remove audio by creating a new clip without audio
            video_no_audio = video.without_audio()
            
            # Write output video (no audio track)
            # Since we used without_audio(), the clip has no audio stream
            video_no_audio.write_videofile(
                output_path,
                codec="libx264",
            )
            
        finally:
            # Clean up
            video.close()
            if 'video_no_audio' in locals():
                video_no_audio.close()
    
    def detect_scenes(self, video_path: str) -> List[Dict]:
        """
        Detect scene cuts in a video and return timestamps.
        
        Args:
            video_path: Path to input video file
            
        Returns:
            List of dicts with scene information:
            {
                'scene_number': int,
                'start_time': float (seconds),
                'end_time': float (seconds),
                'duration': float (seconds),
                'start_time_formatted': str (HH:MM:SS.mmm),
                'end_time_formatted': str (HH:MM:SS.mmm),
            }
            
        Raises:
            FileNotFoundError: If input file doesn't exist
            Exception: If scene detection fails
        """
        # Validate input file exists
        if not Path(video_path).exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        video_manager = VideoManager([video_path])
        scene_manager = SceneManager()
        
        try:
            # Add ContentDetector - detects cuts based on content changes
            scene_manager.add_detector(ContentDetector())
            
            # Start detection
            video_manager.set_duration()
            video_manager.start()
            scene_manager.detect_scenes(frame_source=video_manager)
            
            # Get scene list
            scene_list = scene_manager.get_scene_list()
            
            # Convert to list of dicts
            scenes = []
            for i, (start_time, end_time) in enumerate(scene_list):
                start_seconds = start_time.get_seconds()
                end_seconds = end_time.get_seconds()
                
                scenes.append({
                    'scene_number': i + 1,
                    'start_time': start_seconds,
                    'end_time': end_seconds,
                    'duration': end_seconds - start_seconds,
                    'start_time_formatted': str(start_time),
                    'end_time_formatted': str(end_time),
                })
            
            return scenes
            
        finally:
            video_manager.release()

