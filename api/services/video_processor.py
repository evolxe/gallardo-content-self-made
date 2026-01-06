"""
Video processing service for audio removal and other video operations.
"""

import os
import sys
import shutil
import traceback
from pathlib import Path
from typing import List, Optional, Dict, Tuple
import numpy as np
import random

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

# Configure MoviePy to use system FFMPEG explicitly
# Find FFMPEG binary and set environment variable for MoviePy
ffmpeg_path = os.environ.get("IMAGEIO_FFMPEG_EXE") or shutil.which("ffmpeg")
if ffmpeg_path:
    os.environ["IMAGEIO_FFMPEG_EXE"] = ffmpeg_path
    print(f"MoviePy: Using FFMPEG at {ffmpeg_path}")
    
    # Also verify FFMPEG is executable
    if not os.access(ffmpeg_path, os.X_OK):
        print(f"WARNING: FFMPEG at {ffmpeg_path} is not executable")
    else:
        # Test FFMPEG can be called
        try:
            import subprocess
            result = subprocess.run(
                [ffmpeg_path, "-version"],
                capture_output=True,
                timeout=5,
                text=True
            )
            if result.returncode == 0:
                print(f"MoviePy: FFMPEG verified working - {result.stdout.split(chr(10))[0]}")
            else:
                print(f"WARNING: FFMPEG version check failed with return code {result.returncode}")
        except Exception as e:
            print(f"WARNING: Could not verify FFMPEG: {e}")
else:
    print("WARNING: FFMPEG not found in PATH - MoviePy may fail")

from moviepy import VideoFileClip, AudioFileClip, CompositeAudioClip, ImageClip, CompositeVideoClip
from moviepy import vfx
from scenedetect import VideoManager, SceneManager
from scenedetect.detectors import ContentDetector

# Additional configuration: Ensure imageio-ffmpeg uses the system FFMPEG
try:
    import imageio_ffmpeg
    # Explicitly set the FFMPEG binary path for imageio
    if ffmpeg_path:
        # This ensures MoviePy's audio readers use the correct FFMPEG
        imageio_ffmpeg.get_ffmpeg_exe = lambda: ffmpeg_path
        print(f"MoviePy: Configured imageio-ffmpeg to use {ffmpeg_path}")
except ImportError:
    print("WARNING: imageio-ffmpeg not available, using default FFMPEG detection")
except Exception as e:
    print(f"WARNING: Could not configure imageio-ffmpeg: {e}")


class VideoProcessor:
    """Service for processing videos."""
    
    @staticmethod
    def _handle_write_videofile_error(e: Exception, operation: str = "video encoding") -> Exception:
        """
        Handle errors from write_videofile calls with detailed error messages.
        
        Args:
            e: The exception that was raised
            operation: Description of the operation being performed
            
        Returns:
            A new Exception with detailed error information
        """
        error_type = type(e).__name__
        error_msg = str(e)
        tb = traceback.format_exc()
        
        # Check for specific error types
        if isinstance(e, (OSError, IOError)):
            if "Broken pipe" in error_msg or "errno 32" in error_msg.lower():
                return Exception(
                    f"FFmpeg process was terminated (broken pipe) during {operation}. "
                    f"This may be due to resource constraints (memory/CPU/disk). "
                    f"Original error: {error_msg}"
                )
        
        # Generic error handler for all other exceptions
        return Exception(
            f"{operation} failed ({error_type}): {error_msg}. "
            f"This may be due to FFMPEG subprocess issues, resource constraints, "
            f"or MoviePy compatibility issues. Full traceback: {tb}"
        )
    
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
            except Exception as e:
                raise self._handle_write_videofile_error(e, "audio removal")
            
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
            except Exception as e:
                raise self._handle_write_videofile_error(e, "color grading")
            
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
            except Exception as e:
                raise self._handle_write_videofile_error(e, "crop and zoom")
            
        finally:
            # Clean up
            video.close()
            if 'cropped_video' in locals():
                cropped_video.close()
    
    def crop_to_aspect_ratio_and_pad_to_9_16(
        self, 
        input_path: str, 
        output_path: str, 
        aspect_ratio: str = "1:1",
        background_color: str = "#000000",
        output_width: int = 1080
    ):
        """
        Crop video to specified aspect ratio and output as 9:16 with background padding.
        
        This function:
        1. Crops the video to the desired aspect ratio (centered)
        2. Scales the cropped video to fit into a 9:16 frame
        3. Adds background padding if needed to fill the 9:16 frame
        4. Outputs as 9:16 (1080x1920 by default)
        
        Args:
            input_path: Path to input video file
            output_path: Path to save output video
            aspect_ratio: Desired crop aspect ratio in format "W:H" (e.g., "16:9", "1:1", "4:3")
            background_color: Background color for padding (hex format like "#000000" or named colors)
            output_width: Output width in pixels (default: 1080, creates 1080x1920 9:16 video)
            
        Raises:
            FileNotFoundError: If input file doesn't exist
            ValueError: If aspect ratio format is invalid
            Exception: If video processing fails
        """
        # Validate input file exists
        if not Path(input_path).exists():
            raise FileNotFoundError(f"Input video file not found: {input_path}")
        
        # Parse aspect ratio
        try:
            parts = aspect_ratio.split(":")
            if len(parts) != 2:
                raise ValueError("Aspect ratio must be in format 'W:H' (e.g., '16:9')")
            aspect_w = float(parts[0])
            aspect_h = float(parts[1])
            if aspect_w <= 0 or aspect_h <= 0:
                raise ValueError("Aspect ratio values must be positive")
            target_aspect = aspect_w / aspect_h
        except (ValueError, ZeroDivisionError) as e:
            raise ValueError(f"Invalid aspect ratio format '{aspect_ratio}': {str(e)}")
        
        # Parse background color
        def parse_color(color_str: str) -> Tuple[int, int, int]:
            """Parse color string to RGB tuple."""
            color_str = color_str.strip().lower()
            
            # Named colors
            named_colors = {
                "black": (0, 0, 0),
                "white": (255, 255, 255),
                "red": (255, 0, 0),
                "green": (0, 255, 0),
                "blue": (0, 0, 255),
                "yellow": (255, 255, 0),
                "cyan": (0, 255, 255),
                "magenta": (255, 0, 255),
                "gray": (128, 128, 128),
                "grey": (128, 128, 128),
            }
            
            if color_str in named_colors:
                return named_colors[color_str]
            
            # Hex color
            if color_str.startswith("#"):
                hex_color = color_str[1:]
                if len(hex_color) == 6:
                    try:
                        r = int(hex_color[0:2], 16)
                        g = int(hex_color[2:4], 16)
                        b = int(hex_color[4:6], 16)
                        return (r, g, b)
                    except ValueError:
                        pass
            
            raise ValueError(f"Invalid color format: {color_str}. Use hex (#RRGGBB) or named color.")
        
        bg_color_rgb = parse_color(background_color)
        
        # Calculate 9:16 output dimensions
        output_height = int(output_width * 16 / 9)  # 9:16 aspect ratio
        output_aspect = 9 / 16  # 0.5625
        
        # Ensure output directory exists
        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load video
        video = VideoFileClip(input_path)
        
        try:
            # Get video dimensions
            w, h = video.size
            w, h = int(w), int(h)
            video_aspect = w / h
            
            # Calculate crop dimensions for desired aspect ratio
            if video_aspect > target_aspect:
                # Video is wider than target - crop width
                crop_h = h
                crop_w = int(h * target_aspect)
                crop_x = (w - crop_w) // 2
                crop_y = 0
            else:
                # Video is taller than target - crop height
                crop_w = w
                crop_h = int(w / target_aspect)
                crop_x = 0
                crop_y = (h - crop_h) // 2
            
            # Crop to desired aspect ratio
            cropped_video = video.with_effects([
                vfx.Crop(x1=crop_x, y1=crop_y, x2=crop_x + crop_w, y2=crop_y + crop_h)
            ])
            
            # Calculate scale to fit cropped video into 9:16 frame
            # We want to fit the cropped video inside the 9:16 frame while maintaining aspect ratio
            cropped_aspect = target_aspect  # After crop, this is the aspect ratio
            
            # Calculate scale factors for both dimensions
            scale_w = output_width / crop_w
            scale_h = output_height / crop_h
            
            # Use the smaller scale to ensure the video fits entirely within the frame
            scale = min(scale_w, scale_h)
            scaled_w = int(crop_w * scale)
            scaled_h = int(crop_h * scale)
            
            # Scale the cropped video
            scaled_video = cropped_video.with_effects([
                vfx.Resize((scaled_w, scaled_h))
            ])
            
            # Create background (9:16 frame with background color)
            bg_array = np.full((output_height, output_width, 3), bg_color_rgb, dtype=np.uint8)
            background = ImageClip(bg_array).with_duration(video.duration)
            
            # Composite: place scaled video on background (centered)
            final_video = CompositeVideoClip(
                [background, scaled_video.with_position("center")],
                size=(output_width, output_height)
            )
            
            # Preserve audio if present
            if video.audio is not None:
                final_video = final_video.with_audio(video.audio)
            
            # Write output video
            # Note: This is a long-running operation that can take several minutes
            # FFmpeg encoding at 1080x1920 is CPU-intensive and does not provide progress updates
            # Using "-threads", "0" to utilize all available CPU cores for faster processing
            try:
                final_video.write_videofile(
                    output_path,
                    codec="libx264",
                    ffmpeg_params=["-preset", "medium", "-threads", "0"],  # Use all available cores for faster encoding
                    logger=None,  # Suppress verbose logging
                    audio_codec="aac" if video.audio is not None else None,
                )
            except Exception as e:
                raise self._handle_write_videofile_error(e, "crop to aspect ratio and pad to 9:16")
            
        finally:
            # Clean up
            video.close()
            if 'cropped_video' in locals():
                cropped_video.close()
            if 'scaled_video' in locals():
                scaled_video.close()
            if 'final_video' in locals():
                final_video.close()
            if 'background' in locals():
                background.close()
    
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
            except Exception as e:
                raise self._handle_write_videofile_error(e, "video re-encoding")
            
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
            except Exception as e:
                raise self._handle_write_videofile_error(e, "merge audio and video")
            
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
        crop_aspect_ratio: Optional[str] = None,
        crop_background_color: Optional[str] = None,
        crop_output_size: int = 1080,
        reencode: bool = False,
        codec: str = "libx264",
        bitrate: Optional[str] = None,
        fps: Optional[float] = None,
    ):
        """
        Apply multiple video processing operations in sequence.
        
        Version: 2026-01-06-04:30 - Uses FFMPEG subprocess to preserve original audio.
        
        Processing order:
        1. Load video (and audio if provided)
        2. Merge audio with video (if merge_audio is True)
        3. Remove audio (if remove_audio is True - overrides merge_audio)
        4. Color grading (if color_grading is True)
        5. Crop and zoom to specified aspect ratio, then pad to 9:16 with background color (if crop_zoom is True)
        6. Re-encode (if reencode is True, or always at the end to finalize)
        7. Merge original audio using FFMPEG subprocess (if audio should be preserved)
        
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
            crop_zoom: If True, crop to specified aspect ratio, then pad to 9:16 (1080x1920) with background color
            crop_aspect_ratio: Desired crop aspect ratio in format "W:H" (e.g., "16:9", "1:1", "4:3"). Default: "1:1" if not provided
            crop_background_color: Background color for padding (hex like "#000000" or named color). Default: Random if not provided
            crop_output_size: Not used (kept for backward compatibility; output is always 9:16 format)
            reencode: If True, re-encode with specified settings
            codec: Video codec for re-encoding
            bitrate: Target bitrate for re-encoding
            fps: Target FPS for re-encoding
            
        Raises:
            FileNotFoundError: If input files don't exist
            ValueError: If invalid parameters provided
            Exception: If video processing fails
        """
        # DEBUG: Version identifier for deployment verification
        print("=" * 80)
        print("VIDEO PROCESSOR VERSION: 2026-01-06-04:30 - Audio preservation via FFMPEG")
        print("=" * 80)
        
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
        
        # Load video - load without audio first to avoid audio subprocess issues
        # This prevents the 'NoneType' object has no attribute 'stdout' error
        # when MoviePy's audio reader can't start FFMPEG subprocess
        try:
            # Load video without audio to avoid subprocess issues
            video = VideoFileClip(video_path, audio=False)
            video_has_audio = False
            original_audio = None
            
            # Only try to preserve audio if we're not removing it and not merging new audio
            if not remove_audio and not merge_audio:
                # Try to load audio separately, but don't fail if it doesn't work
                # This is a workaround for MoviePy audio reader subprocess issues
                try:
                    # Use ffprobe to check if video has audio track first (faster than loading)
                    import subprocess
                    probe_result = subprocess.run(
                        [shutil.which("ffprobe") or "ffprobe", "-v", "error", "-select_streams", "a:0",
                         "-show_entries", "stream=codec_type", "-of", "default=noprint_wrappers=1:nokey=1",
                         video_path],
                        capture_output=True,
                        timeout=5,
                        text=True
                    )
                    has_audio_track = probe_result.returncode == 0 and "audio" in probe_result.stdout.lower()
                    
                    if has_audio_track:
                        # Video has audio track, but we'll skip loading it to avoid subprocess issues
                        # The audio will be preserved during encoding if possible
                        video_has_audio = True
                        print(f"Note: Video has audio track, but loading it separately to avoid subprocess issues")
                except Exception as e:
                    # If checking fails, assume no audio or proceed without it
                    print(f"Could not check audio track: {e}")
                    video_has_audio = False
        except Exception as e:
            # Fallback: try loading normally if loading without audio fails
            print(f"Warning: Could not load video without audio, trying normal load: {e}")
            try:
                video = VideoFileClip(video_path, audio=False)  # Still try without audio
                video_has_audio = False
                original_audio = None
            except:
                # Last resort: load with audio (may fail with subprocess error)
                video = VideoFileClip(video_path)
                video_has_audio = video.audio is not None
                original_audio = video.audio if video_has_audio else None
        
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
                # Remove audio track (already done by loading with audio=False)
                if video_has_audio:
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
                
                # Ensure color-graded video has no audio (should already be None, but double-check)
                if hasattr(video, 'audio') and video.audio is not None:
                    video = video.without_audio()
            
            # Step 3: Crop and zoom to specified aspect ratio, then pad to 9:16 with background color
            if crop_zoom:
                # Default aspect ratio to 1:1 if not provided
                if not crop_aspect_ratio:
                    crop_aspect_ratio = "1:1"
                
                # Parse aspect ratio
                try:
                    parts = crop_aspect_ratio.split(":")
                    if len(parts) != 2:
                        raise ValueError("Aspect ratio must be in format 'W:H'")
                    aspect_w = float(parts[0])
                    aspect_h = float(parts[1])
                    if aspect_w <= 0 or aspect_h <= 0:
                        raise ValueError("Aspect ratio values must be positive")
                    target_aspect = aspect_w / aspect_h
                except (ValueError, ZeroDivisionError) as e:
                    raise ValueError(f"Invalid aspect ratio format '{crop_aspect_ratio}': {str(e)}")
                
                # Parse background color
                def parse_color(color_str: str) -> Tuple[int, int, int]:
                    """Parse color string to RGB tuple."""
                    color_str = color_str.strip().lower()
                    
                    # Named colors
                    named_colors = {
                        "black": (0, 0, 0),
                        "white": (255, 255, 255),
                        "red": (255, 0, 0),
                        "green": (0, 255, 0),
                        "blue": (0, 0, 255),
                        "yellow": (255, 255, 0),
                        "cyan": (0, 255, 255),
                        "magenta": (255, 0, 255),
                        "gray": (128, 128, 128),
                        "grey": (128, 128, 128),
                    }
                    
                    if color_str in named_colors:
                        return named_colors[color_str]
                    
                    # Hex color
                    if color_str.startswith("#"):
                        hex_color = color_str[1:]
                        if len(hex_color) == 6:
                            try:
                                r = int(hex_color[0:2], 16)
                                g = int(hex_color[2:4], 16)
                                b = int(hex_color[4:6], 16)
                                return (r, g, b)
                            except ValueError:
                                pass
                    
                    raise ValueError(f"Invalid color format: {color_str}. Use hex (#RRGGBB) or named color.")
                
                # Default to random color if not provided
                if not crop_background_color:
                    bg_color_rgb = (
                        random.randint(0, 255),
                        random.randint(0, 255),
                        random.randint(0, 255)
                    )
                else:
                    bg_color_rgb = parse_color(crop_background_color)
                
                # Don't preserve audio - we load without audio to avoid subprocess issues
                # Explicitly ensure video has no audio before processing
                if hasattr(video, 'audio') and video.audio is not None:
                    video = video.without_audio()
                
                # Get video dimensions
                w, h = video.size
                w, h = int(w), int(h)
                video_aspect = w / h
                
                # Calculate crop dimensions for desired aspect ratio
                if video_aspect > target_aspect:
                    # Video is wider than target - crop width
                    crop_h = h
                    crop_w = int(h * target_aspect)
                    crop_x = (w - crop_w) // 2
                    crop_y = 0
                else:
                    # Video is taller than target - crop height
                    crop_w = w
                    crop_h = int(w / target_aspect)
                    crop_x = 0
                    crop_y = (h - crop_h) // 2
                
                # Crop to desired aspect ratio
                cropped_video = video.with_effects([
                    vfx.Crop(x1=crop_x, y1=crop_y, x2=crop_x + crop_w, y2=crop_y + crop_h)
                ])
                
                # Ensure cropped video has no audio
                if hasattr(cropped_video, 'audio') and cropped_video.audio is not None:
                    cropped_video = cropped_video.without_audio()
                
                # Calculate 9:16 output dimensions (1080x1920)
                output_width = 1080
                output_height = 1920
                
                # Calculate scale to fit cropped video into 9:16 frame
                # Use the smaller scale to ensure the video fits entirely within the frame
                scale_w = output_width / crop_w
                scale_h = output_height / crop_h
                scale = min(scale_w, scale_h)
                scaled_w = int(crop_w * scale)
                scaled_h = int(crop_h * scale)
                
                # Scale the cropped video
                scaled_video = cropped_video.with_effects([
                    vfx.Resize((scaled_w, scaled_h))
                ])
                
                # Ensure scaled video has no audio
                if hasattr(scaled_video, 'audio') and scaled_video.audio is not None:
                    scaled_video = scaled_video.without_audio()
                
                # Create background (9:16 frame with background color)
                bg_array = np.full((output_height, output_width, 3), bg_color_rgb, dtype=np.uint8)
                background = ImageClip(bg_array).with_duration(video.duration)
                
                # Composite: place scaled video on background (centered)
                # Ensure no audio is passed to CompositeVideoClip
                video_no_audio_composite = scaled_video.with_position("center")
                if hasattr(video_no_audio_composite, 'audio') and video_no_audio_composite.audio is not None:
                    video_no_audio_composite = video_no_audio_composite.without_audio()
                
                video = CompositeVideoClip(
                    [background, video_no_audio_composite],
                    size=(output_width, output_height)
                )
                
                # Double-check final composite has no audio
                if hasattr(video, 'audio') and video.audio is not None:
                    video = video.without_audio()
                
                # Skip audio preservation here - we'll handle it during encoding
                # to avoid MoviePy audio reader subprocess issues
                # Audio will be preserved via FFMPEG during write_videofile if video_has_audio is True
                
                # Clean up intermediate clips
                cropped_video.close()
                scaled_video.close()
                background.close()
            
            # Step 4: Apply FPS change if reencoding with FPS
            if reencode and fps and fps > 0:
                video = video.with_fps(fps)
                # Ensure FPS change didn't re-attach audio
                if hasattr(video, 'audio') and video.audio is not None:
                    video = video.without_audio()
            
            # Prepare write_videofile arguments
            write_kwargs = {
                "codec": codec,
                "logger": None,  # Suppress verbose logging
                "ffmpeg_params": ["-preset", "medium", "-threads", "2"],  # Encoding speed/quality balance, limit CPU
            }
            
            # Add bitrate if specified
            if reencode and bitrate:
                write_kwargs["bitrate"] = bitrate
            
            # Handle audio encoding - CRITICAL: Prevent MoviePy audio reader subprocess issues
            # Since MoviePy's audio reader subprocess fails (returns None), we must ensure
            # we don't let MoviePy try to read audio from VideoFileClip objects.
            # We'll handle audio preservation using FFMPEG subprocess after writing the video.
            
            needs_audio_merge = False  # Track if we need to merge audio using FFMPEG
            
            if audio_clip is not None:
                # New audio is being merged from a separate file - this should work
                # since AudioFileClip loads differently than VideoFileClip audio
                write_kwargs["audio_codec"] = "aac"
            elif remove_audio:
                # User explicitly wants audio removed
                if hasattr(video, 'audio') and video.audio is not None:
                    video = video.without_audio()
                    print("Removed audio from video (remove_audio=True)")
            elif video_has_audio and not remove_audio:
                # Original video has audio and user wants to preserve it
                # Remove audio from MoviePy object to prevent subprocess issues
                # We'll merge it back using FFMPEG subprocess after writing
                if hasattr(video, 'audio') and video.audio is not None:
                    video = video.without_audio()
                    print("Removed audio from MoviePy object to avoid subprocess issues. Will preserve via FFMPEG.")
                
                # Mark that we need to merge audio after writing
                needs_audio_merge = True
                # Don't set audio_codec - video will be written without audio, then merged
            else:
                # No audio to preserve
                if hasattr(video, 'audio') and video.audio is not None:
                    video = video.without_audio()
                    print("Removed audio from video (no audio to preserve)")
            
            # Final safety check: verify video has no audio before write_videofile
            # (unless we're merging new audio from a separate file)
            if hasattr(video, 'audio') and video.audio is not None and audio_clip is None:
                raise Exception("CRITICAL: Video object still has audio attached before write_videofile. "
                              "This will cause the 'NoneType' stdout error. Audio must be removed.")
            
            # Write output video with error handling for broken pipe
            try:
                video.write_videofile(
                    output_path,
                    **write_kwargs
                )
            except Exception as e:
                raise self._handle_write_videofile_error(e, "comprehensive video processing")
            
            # If we need to merge audio, do it now using FFMPEG directly (bypasses MoviePy)
            # This preserves original audio without triggering MoviePy's broken audio reader
            if needs_audio_merge:
                try:
                    import subprocess
                    import tempfile
                    import shutil
                    
                    print("Merging audio from original video using FFMPEG subprocess...")
                    
                    # Create temporary file for video with audio
                    temp_output = output_path.replace('.mp4', '_with_audio_temp.mp4')
                    
                    # Use FFMPEG to merge audio from original video file
                    # This bypasses MoviePy's broken audio reader subprocess
                    ffmpeg_cmd = [
                        "ffmpeg",
                        "-i", output_path,      # Video file (no audio) - processed video
                        "-i", video_path,       # Original video (has audio)
                        "-c:v", "copy",         # Copy video stream (no re-encoding)
                        "-c:a", "aac",          # Encode audio to AAC for compatibility
                        "-map", "0:v:0",        # Use video from first input (processed)
                        "-map", "1:a:0?",       # Use audio from second input (original, optional - won't fail if missing)
                        "-shortest",            # End when shortest stream ends
                        "-y",                   # Overwrite output
                        temp_output
                    ]
                    
                    result = subprocess.run(
                        ffmpeg_cmd,
                        capture_output=True,
                        text=True,
                        timeout=300  # 5 minute timeout
                    )
                    
                    if result.returncode == 0:
                        # Replace output with merged version
                        shutil.move(temp_output, output_path)
                        print("Successfully merged audio using FFMPEG subprocess")
                    else:
                        print(f"Warning: Failed to merge audio using FFMPEG: {result.stderr}")
                        # Try to clean up temp file
                        try:
                            if os.path.exists(temp_output):
                                os.remove(temp_output)
                        except:
                            pass
                        # Keep video without audio rather than failing completely
                        print("Video saved without audio due to audio merge failure")
                except subprocess.TimeoutExpired:
                    print("Warning: Audio merge timed out. Video saved without audio.")
                    try:
                        if os.path.exists(temp_output):
                            os.remove(temp_output)
                    except:
                        pass
                except Exception as e:
                    print(f"Warning: Could not merge audio using FFMPEG: {e}. Video saved without audio.")
                    # Don't raise - video processing succeeded, just audio merge failed
            
        finally:
            # Clean up
            video.close()
            if audio_clip:
                audio_clip.close()

