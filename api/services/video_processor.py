"""
Video processing service for audio removal and other video operations.
"""

import os
import sys
from pathlib import Path
from typing import List, Optional, Dict, Tuple
import numpy as np
import random

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from moviepy import VideoFileClip, AudioFileClip, CompositeAudioClip
from moviepy import vfx
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
            try:
                video_no_audio.write_videofile(
                    output_path,
                    codec="libx264",
                    ffmpeg_params=["-preset", "medium", "-threads", "2"],  # Encoding speed/quality balance, limit CPU
                    logger=None,  # Suppress verbose logging
                )
            except (OSError, IOError) as e:
                if "Broken pipe" in str(e) or "errno 32" in str(e).lower():
                    raise Exception(
                        f"FFmpeg process was terminated (broken pipe). "
                        f"This may be due to resource constraints (memory/CPU/disk). "
                        f"Original error: {str(e)}"
                    )
                raise
            
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
    
    @staticmethod
    def generate_random_color_grading() -> Tuple[str, float, float, float]:
        """
        Generate random color grading parameters.
        
        Returns:
            Tuple of (preset, brightness, contrast, saturation)
        """
        valid_presets = ["cinematic", "warm", "cool", "vintage", "vivid", "bw", "natural"]
        
        # Randomly select a preset
        preset = random.choice(valid_presets)
        
        # Generate random adjustments within reasonable ranges
        # Brightness: slightly darker to slightly brighter (-0.2 to 0.2)
        brightness = random.uniform(-0.2, 0.2)
        
        # Contrast: normal to high (0.9 to 1.4)
        contrast = random.uniform(0.9, 1.4)
        
        # Saturation: low to high (0.7 to 1.5)
        saturation = random.uniform(0.7, 1.5)
        
        return preset, brightness, contrast, saturation
    
    def apply_color_grading(
        self,
        input_path: str,
        output_path: str,
        preset: str = "cinematic",
        brightness: float = 0.0,
        contrast: float = 1.0,
        saturation: float = 1.0,
    ):
        """
        Apply color grading to a video file.
        
        Args:
            input_path: Path to input video file
            output_path: Path to save output video
            preset: Color grading preset name
                Options: "cinematic", "warm", "cool", "vintage", "vivid", "bw", "natural"
            brightness: Brightness adjustment (-1.0 to 1.0, 0.0 = no change)
            contrast: Contrast adjustment (0.0 to 2.0, 1.0 = no change)
            saturation: Saturation adjustment (0.0 to 2.0, 1.0 = no change)
            
        Raises:
            FileNotFoundError: If input file doesn't exist
            ValueError: If preset is invalid
            Exception: If video processing fails
        """
        # Validate input file exists
        if not Path(input_path).exists():
            raise FileNotFoundError(f"Input video file not found: {input_path}")
        
        # Validate preset
        valid_presets = ["cinematic", "warm", "cool", "vintage", "vivid", "bw", "natural"]
        if preset not in valid_presets:
            raise ValueError(
                f"Invalid preset '{preset}'. Valid options: {', '.join(valid_presets)}"
            )
        
        # Ensure output directory exists
        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load video
        video = VideoFileClip(input_path)
        
        try:
            # Define preset adjustments (can be combined with manual adjustments)
            preset_settings = {
                "cinematic": {
                    "brightness": 0.0,
                    "contrast": 1.2,
                    "saturation": 1.1,
                    "color_temperature": "cool",  # Slight blue shift
                },
                "warm": {
                    "brightness": 0.1,
                    "contrast": 1.1,
                    "saturation": 1.2,
                    "color_temperature": "warm",  # Orange/red shift
                },
                "cool": {
                    "brightness": 0.0,
                    "contrast": 1.1,
                    "saturation": 1.1,
                    "color_temperature": "cool",  # Blue/cyan shift
                },
                "vintage": {
                    "brightness": 0.15,
                    "contrast": 1.15,
                    "saturation": 0.7,
                    "color_temperature": "warm",  # Sepia-like
                },
                "vivid": {
                    "brightness": 0.0,
                    "contrast": 1.3,
                    "saturation": 1.5,
                    "color_temperature": "neutral",
                },
                "bw": {
                    "brightness": 0.0,
                    "contrast": 1.2,
                    "saturation": 0.0,  # Grayscale
                    "color_temperature": "neutral",
                },
                "natural": {
                    "brightness": 0.0,
                    "contrast": 1.0,
                    "saturation": 1.0,
                    "color_temperature": "neutral",
                },
            }
            
            # Get preset settings
            preset_config = preset_settings[preset]
            
            # Combine preset with manual adjustments (manual takes precedence if != default)
            final_brightness = brightness if brightness != 0.0 else preset_config["brightness"]
            final_contrast = contrast if contrast != 1.0 else preset_config["contrast"]
            final_saturation = saturation if saturation != 1.0 else preset_config["saturation"]
            color_temp = preset_config["color_temperature"]
            
            # Capture video reference before transformation to avoid recursion
            source_video = video
            
            # Apply color grading using numpy operations on each frame
            def apply_grading_to_frame(t):
                """
                Apply color grading to a frame at time t.
                This function is called for each frame in the video.
                
                Args:
                    t: time in seconds (float)
                    
                Returns:
                    Processed frame as numpy array with dtype uint8
                """
                # Get the original frame at time t (use source_video to avoid recursion)
                frame = source_video.get_frame(t)
                
                # Convert to float for processing
                frame_float = frame.astype(np.float32) / 255.0
                
                # Apply brightness (add/subtract value)
                frame_float = np.clip(frame_float + final_brightness, 0, 1)
                
                # Apply contrast (center at 0.5, multiply, then shift back)
                frame_float = np.clip((frame_float - 0.5) * final_contrast + 0.5, 0, 1)
                
                # Apply saturation
                if final_saturation != 1.0:
                    # Calculate grayscale version
                    gray = np.mean(frame_float, axis=2, keepdims=True)
                    # Blend between grayscale and color based on saturation
                    frame_float = np.clip(gray + (frame_float - gray) * final_saturation, 0, 1)
                
                # Apply color temperature adjustment
                if color_temp == "warm":
                    # Add warm tones (increase red, decrease blue)
                    frame_float[:, :, 0] = np.clip(frame_float[:, :, 0] * 1.1, 0, 1)  # Red
                    frame_float[:, :, 2] = np.clip(frame_float[:, :, 2] * 0.95, 0, 1)  # Blue
                elif color_temp == "cool":
                    # Add cool tones (increase blue, decrease red)
                    frame_float[:, :, 0] = np.clip(frame_float[:, :, 0] * 0.95, 0, 1)  # Red
                    frame_float[:, :, 2] = np.clip(frame_float[:, :, 2] * 1.1, 0, 1)  # Blue
                
                # Convert back to uint8
                frame_processed = (frame_float * 255.0).astype(np.uint8)
                
                return frame_processed
            
            # Apply the color grading effect using with_updated_frame_function (MoviePy v2 API)
            # This method takes a function: func(t: float) -> ndarray that returns the processed frame
            graded_video = video.with_updated_frame_function(apply_grading_to_frame)
            
            # Write output video
            try:
                graded_video.write_videofile(
                    output_path,
                    codec="libx264",
                    ffmpeg_params=["-preset", "medium", "-threads", "2"],  # Encoding speed/quality balance, limit CPU
                    logger=None,  # Suppress verbose logging
                )
            except (OSError, IOError) as e:
                if "Broken pipe" in str(e) or "errno 32" in str(e).lower():
                    raise Exception(
                        f"FFmpeg process was terminated (broken pipe). "
                        f"This may be due to resource constraints (memory/CPU/disk). "
                        f"Original error: {str(e)}"
                    )
                raise
            
        finally:
            # Clean up
            video.close()
            if 'graded_video' in locals():
                graded_video.close()
    
    def crop_and_zoom_to_square(self, input_path: str, output_path: str, output_size: int = 1080):
        """
        Crop video to center 1:1 (square) aspect ratio and optionally resize.
        
        This function:
        1. Crops the center square from the video (maintains original resolution of cropped area)
        2. Optionally resizes to specified output_size x output_size
        
        Args:
            input_path: Path to input video file
            output_path: Path to save output video
            output_size: Output square size in pixels (default: 1080x1080)
                        Set to 0 or None to keep original cropped resolution
            
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
            # Get video dimensions
            w, h = video.size
            w, h = int(w), int(h)
            
            # Calculate center crop dimensions for 1:1 aspect ratio
            # Take the shorter dimension as the square size
            square_size = min(w, h)
            
            # Calculate crop coordinates (center crop)
            crop_x = (w - square_size) // 2
            crop_y = (h - square_size) // 2
            
            # Crop to center square: (x1, y1, x2, y2) - top-left and bottom-right corners
            # Note: MoviePy v2 uses with_effects for crop
            cropped_video = video.with_effects([
                vfx.Crop(x1=crop_x, y1=crop_y, x2=crop_x + square_size, y2=crop_y + square_size)
            ])
            
            # Resize to output_size if specified and different from cropped size
            if output_size and output_size > 0 and output_size != square_size:
                cropped_video = cropped_video.with_effects([
                    vfx.Resize((output_size, output_size))
                ])
            
            # Write output video
            try:
                cropped_video.write_videofile(
                    output_path,
                    codec="libx264",
                    ffmpeg_params=["-preset", "medium", "-threads", "2"],  # Encoding speed/quality balance, limit CPU
                    logger=None,  # Suppress verbose logging
                )
            except (OSError, IOError) as e:
                if "Broken pipe" in str(e) or "errno 32" in str(e).lower():
                    raise Exception(
                        f"FFmpeg process was terminated (broken pipe). "
                        f"This may be due to resource constraints (memory/CPU/disk). "
                        f"Original error: {str(e)}"
                    )
                raise
            
        finally:
            # Clean up
            video.close()
            if 'cropped_video' in locals():
                cropped_video.close()
    
    def reencode_video(
        self,
        input_path: str,
        output_path: str,
        codec: str = "libx264",
        bitrate: Optional[str] = None,
        fps: Optional[float] = None,
    ):
        """
        Re-encode a video file with specified settings.
        
        Args:
            input_path: Path to input video file
            output_path: Path to save output video
            codec: Video codec to use (default: "libx264")
            bitrate: Target bitrate (e.g., "5000k") - optional
            fps: Target FPS - optional, uses original if not specified
            
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
            # Apply FPS change if specified
            if fps and fps > 0:
                video = video.with_fps(fps)
            
            # Prepare write_videofile arguments
            write_kwargs = {
                "codec": codec,
            }
            
            # Add bitrate if specified
            if bitrate:
                write_kwargs["bitrate"] = bitrate
            
            # Write output video (re-encoded)
            # Add encoding parameters for robustness
            write_kwargs.setdefault("logger", None)  # Suppress verbose logging
            
            # Add FFmpeg parameters for encoding efficiency and resource management
            ffmpeg_params = ["-preset", "medium", "-threads", "2"]
            if "ffmpeg_params" in write_kwargs:
                ffmpeg_params.extend(write_kwargs["ffmpeg_params"])
            write_kwargs["ffmpeg_params"] = ffmpeg_params
            
            try:
                video.write_videofile(
                    output_path,
                    **write_kwargs
                )
            except (OSError, IOError) as e:
                if "Broken pipe" in str(e) or "errno 32" in str(e).lower():
                    raise Exception(
                        f"FFmpeg process was terminated (broken pipe). "
                        f"This may be due to resource constraints (memory/CPU/disk). "
                        f"Original error: {str(e)}"
                    )
                raise
            
        finally:
            # Clean up
            video.close()
    
    def merge_audio_and_video(
        self,
        video_path: str,
        audio_path: str,
        output_path: str,
    ):
        """
        Merge an audio file with a video file.
        
        The longer of the two will be clipped to match the shorter duration.
        
        Args:
            video_path: Path to input video file
            audio_path: Path to input audio file
            output_path: Path to save output video with merged audio
            
        Raises:
            FileNotFoundError: If input files don't exist
            Exception: If video processing fails
        """
        # Validate input files exist
        if not Path(video_path).exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        if not Path(audio_path).exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        # Ensure output directory exists
        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load video and audio
        video = VideoFileClip(video_path)
        audio = AudioFileClip(audio_path)
        
        try:
            # Get durations
            video_duration = video.duration
            audio_duration = audio.duration
            
            # Determine shorter duration
            target_duration = min(video_duration, audio_duration)
            
            # Clip both to match the shorter duration
            if video_duration > target_duration:
                # MoviePy v2: use subclipped() or slicing syntax
                try:
                    video = video.subclipped(0, target_duration)
                except AttributeError:
                    # Fallback: use slicing syntax
                    video = video[:target_duration]
            
            if audio_duration > target_duration:
                # MoviePy v2: use subclipped() or slicing syntax
                try:
                    audio = audio.subclipped(0, target_duration)
                except AttributeError:
                    # Fallback: use slicing syntax
                    audio = audio[:target_duration]
            
            # Set audio to video
            video_with_audio = video.with_audio(audio)
            
            # Write output video with merged audio
            try:
                video_with_audio.write_videofile(
                    output_path,
                    codec="libx264",
                    audio_codec="aac",
                    ffmpeg_params=["-preset", "medium", "-threads", "2"],  # Encoding speed/quality balance, limit CPU
                    logger=None,  # Suppress verbose logging
                )
            except (OSError, IOError) as e:
                if "Broken pipe" in str(e) or "errno 32" in str(e).lower():
                    raise Exception(
                        f"FFmpeg process was terminated (broken pipe). "
                        f"This may be due to resource constraints (memory/CPU/disk). "
                        f"Original error: {str(e)}"
                    )
                raise
            
        finally:
            # Clean up
            video.close()
            audio.close()
            if 'video_with_audio' in locals():
                video_with_audio.close()
    
    def process_video_comprehensive(
        self,
        video_path: str,
        output_path: str,
        audio_path: Optional[str] = None,
        remove_audio: bool = False,
        merge_audio: bool = False,
        color_grading: bool = False,
        color_preset: str = "cinematic",
        color_brightness: float = 0.0,
        color_contrast: float = 1.0,
        color_saturation: float = 1.0,
        crop_zoom: bool = False,
        crop_output_size: int = 1080,
        reencode: bool = False,
        codec: str = "libx264",
        bitrate: Optional[str] = None,
        fps: Optional[float] = None,
    ):
        """
        Apply multiple video processing operations in sequence.
        
        Processing order:
        1. Load video (and audio if provided)
        2. Merge audio with video (if merge_audio is True)
        3. Remove audio (if remove_audio is True - overrides merge_audio)
        4. Color grading (if color_grading is True)
        5. Crop and zoom to square (if crop_zoom is True)
        6. Re-encode (if reencode is True, or always at the end to finalize)
        
        Args:
            video_path: Path to input video file
            output_path: Path to save output video
            audio_path: Optional path to audio file for merging
            remove_audio: If True, remove audio track
            merge_audio: If True, merge audio file with video (requires audio_path)
            color_grading: If True, apply color grading
            color_preset: Color grading preset (if color_grading is True)
            color_brightness: Brightness adjustment (-1.0 to 1.0)
            color_contrast: Contrast adjustment (0.0 to 2.0)
            color_saturation: Saturation adjustment (0.0 to 2.0)
            crop_zoom: If True, crop to center square
            crop_output_size: Output square size (if crop_zoom is True)
            reencode: If True, re-encode with specified settings
            codec: Video codec for re-encoding
            bitrate: Target bitrate for re-encoding
            fps: Target FPS for re-encoding
            
        Raises:
            FileNotFoundError: If input files don't exist
            ValueError: If invalid parameters provided
            Exception: If video processing fails
        """
        # Validate input file exists
        if not Path(video_path).exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        # Validate merge_audio requires audio_path
        if merge_audio and not audio_path:
            raise ValueError("merge_audio requires audio_path to be provided")
        
        if merge_audio and not Path(audio_path).exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        # Ensure output directory exists
        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load video
        video = VideoFileClip(video_path)
        audio_clip = None
        
        try:
            # Step 1: Handle audio merging or removal
            if merge_audio and not remove_audio:
                # Merge audio with video
                audio_clip = AudioFileClip(audio_path)
                
                # Get durations
                video_duration = video.duration
                audio_duration = audio_clip.duration
                
                # Determine shorter duration
                target_duration = min(video_duration, audio_duration)
                
                # Clip both to match the shorter duration
                if video_duration > target_duration:
                    # MoviePy v2: use subclipped() or slicing syntax
                    try:
                        video = video.subclipped(0, target_duration)
                    except AttributeError:
                        # Fallback: use slicing syntax
                        video = video[:target_duration]
                
                if audio_duration > target_duration:
                    # MoviePy v2: use subclipped() or slicing syntax
                    try:
                        audio_clip = audio_clip.subclipped(0, target_duration)
                    except AttributeError:
                        # Fallback: use slicing syntax
                        audio_clip = audio_clip[:target_duration]
                
                # Set audio to video
                video = video.with_audio(audio_clip)
            
            elif remove_audio:
                # Remove audio track
                video = video.without_audio()
            
            # Step 2: Apply color grading
            if color_grading:
                # Capture the current video reference BEFORE applying transformations
                # This prevents circular references in the frame function
                source_video = video
                
                # Use random preset if preset is "random"
                if color_preset == "random":
                    preset, brightness, contrast, saturation = self.generate_random_color_grading()
                else:
                    preset = color_preset
                    brightness = color_brightness if color_brightness != 0.0 else None
                    contrast = color_contrast if color_contrast != 1.0 else None
                    saturation = color_saturation if color_saturation != 1.0 else None
                
                # Get preset settings
                preset_settings = {
                    "cinematic": {"brightness": 0.0, "contrast": 1.2, "saturation": 1.1, "color_temperature": "cool"},
                    "warm": {"brightness": 0.1, "contrast": 1.1, "saturation": 1.2, "color_temperature": "warm"},
                    "cool": {"brightness": 0.0, "contrast": 1.1, "saturation": 1.1, "color_temperature": "cool"},
                    "vintage": {"brightness": 0.15, "contrast": 1.15, "saturation": 0.7, "color_temperature": "warm"},
                    "vivid": {"brightness": 0.0, "contrast": 1.3, "saturation": 1.5, "color_temperature": "neutral"},
                    "bw": {"brightness": 0.0, "contrast": 1.2, "saturation": 0.0, "color_temperature": "neutral"},
                    "natural": {"brightness": 0.0, "contrast": 1.0, "saturation": 1.0, "color_temperature": "neutral"},
                }
                
                preset_config = preset_settings.get(preset, preset_settings["cinematic"])
                final_brightness = brightness if brightness is not None else preset_config["brightness"]
                final_contrast = contrast if contrast is not None else preset_config["contrast"]
                final_saturation = saturation if saturation is not None else preset_config["saturation"]
                color_temp = preset_config["color_temperature"]
                
                # Apply color grading - use source_video to avoid recursion
                def apply_grading_to_frame(t):
                    # Use source_video (captured before transformation) to get original frame
                    frame = source_video.get_frame(t)
                    frame_float = frame.astype(np.float32) / 255.0
                    
                    # Apply brightness
                    frame_float = np.clip(frame_float + final_brightness, 0, 1)
                    
                    # Apply contrast
                    frame_float = np.clip((frame_float - 0.5) * final_contrast + 0.5, 0, 1)
                    
                    # Apply saturation
                    if final_saturation != 1.0:
                        gray = np.mean(frame_float, axis=2, keepdims=True)
                        frame_float = np.clip(gray + (frame_float - gray) * final_saturation, 0, 1)
                    
                    # Apply color temperature
                    if color_temp == "warm":
                        frame_float[:, :, 0] = np.clip(frame_float[:, :, 0] * 1.1, 0, 1)
                        frame_float[:, :, 2] = np.clip(frame_float[:, :, 2] * 0.95, 0, 1)
                    elif color_temp == "cool":
                        frame_float[:, :, 0] = np.clip(frame_float[:, :, 0] * 0.95, 0, 1)
                        frame_float[:, :, 2] = np.clip(frame_float[:, :, 2] * 1.1, 0, 1)
                    
                    frame_processed = (frame_float * 255.0).astype(np.uint8)
                    return frame_processed
                
                video = video.with_updated_frame_function(apply_grading_to_frame)
            
            # Step 3: Crop and zoom to square
            if crop_zoom:
                w, h = video.size
                w, h = int(w), int(h)
                square_size = min(w, h)
                crop_x = (w - square_size) // 2
                crop_y = (h - square_size) // 2
                
                video = video.with_effects([
                    vfx.Crop(x1=crop_x, y1=crop_y, x2=crop_x + square_size, y2=crop_y + square_size)
                ])
                
                if crop_output_size and crop_output_size > 0 and crop_output_size != square_size:
                    video = video.with_effects([
                        vfx.Resize((crop_output_size, crop_output_size))
                    ])
            
            # Step 4: Apply FPS change if reencoding with FPS
            if reencode and fps and fps > 0:
                video = video.with_fps(fps)
            
            # Prepare write_videofile arguments
            write_kwargs = {
                "codec": codec,
                "logger": None,  # Suppress verbose logging
                "ffmpeg_params": ["-preset", "medium", "-threads", "2"],  # Encoding speed/quality balance, limit CPU
            }
            
            # Add bitrate if specified
            if reencode and bitrate:
                write_kwargs["bitrate"] = bitrate
            
            # Add audio codec only if video has audio
            if video.audio is not None:
                write_kwargs["audio_codec"] = "aac"
            
            # Write output video with error handling for broken pipe
            try:
                video.write_videofile(
                    output_path,
                    **write_kwargs
                )
            except (OSError, IOError) as e:
                if "Broken pipe" in str(e) or "errno 32" in str(e).lower():
                    raise Exception(
                        f"FFmpeg process was terminated (broken pipe). "
                        f"This may be due to resource constraints (memory/CPU/disk). "
                        f"Try reducing video resolution, bitrate, or processing fewer operations at once. "
                        f"Original error: {str(e)}"
                    )
                raise
            
        finally:
            # Clean up
            video.close()
            if audio_clip:
                audio_clip.close()

