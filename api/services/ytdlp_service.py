"""
YouTube-DLP service for downloading videos from various platforms.

This service uses subprocess to call yt-dlp binary directly (not Python library),
following the Python backend pattern from the documentation.
"""

import os
import sys
import subprocess
import shutil
import json
from pathlib import Path
from typing import Optional, Dict, Any

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))


def convert_local_video_to_mp3(input_file: str) -> str:
    """
    Extract audio from video file using FFmpeg via subprocess.
    
    Follows the exact pattern from Python backend documentation:
    - Uses subprocess.run() to call FFmpeg directly
    - No Python wrapper packages
    - FFmpeg must be in system PATH
    
    Args:
        input_file: Path to input video file (MP4)
        
    Returns:
        Path to output MP3 file
        
    Raises:
        Exception: If FFmpeg is not found or conversion fails
    """
    output_file = input_file.replace('.mp4', '.mp3')
    
    # Check if FFmpeg is available
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise Exception("FFmpeg not found. Please install FFmpeg system-wide (apt-get, brew, or download from https://ffmpeg.org)")
    
    # Get environment with ffmpeg in PATH
    env = os.environ.copy()
    ffmpeg_dir = os.path.dirname(ffmpeg_bin)
    current_path = env.get('PATH', '')
    if ffmpeg_dir not in current_path:
        separator = ';' if os.name == 'nt' else ':'
        env['PATH'] = current_path + separator + ffmpeg_dir
    
    # Use subprocess.run() exactly as shown in Python backend documentation
    subprocess.run([
        "ffmpeg", "-y", 
        "-i", input_file, 
        "-vn",           # No video
        "-ar", "44100",  # Sample rate
        "-ac", "2",      # Stereo
        "-b:a", "192k",  # Audio bitrate
        output_file
    ], check=True, env=env)
    
    return output_file


def local_video_to_mp3(local_mp4_path: str) -> str:
    """
    Alternative method to extract MP3 from video using FFmpeg via subprocess.
    
    Follows the exact pattern from Python backend documentation.
    
    Args:
        local_mp4_path: Path to input MP4 video file
        
    Returns:
        Path to output MP3 file
        
    Raises:
        Exception: If FFmpeg is not found or conversion fails
    """
    improved_mp3_path = local_mp4_path.replace('.mp4', '.mp3')
    
    # Check if FFmpeg is available
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise Exception("FFmpeg not found. Please install FFmpeg system-wide (apt-get, brew, or download from https://ffmpeg.org)")
    
    # Get environment with ffmpeg in PATH
    env = os.environ.copy()
    ffmpeg_dir = os.path.dirname(ffmpeg_bin)
    current_path = env.get('PATH', '')
    if ffmpeg_dir not in current_path:
        separator = ';' if os.name == 'nt' else ':'
        env['PATH'] = current_path + separator + ffmpeg_dir
    
    # Use subprocess.call() exactly as shown in Python backend documentation
    command = [
        "ffmpeg", "-y", 
        "-i", local_mp4_path, 
        "-vn",                    # No video
        "-acodec", "libmp3lame",  # MP3 codec
        "-f", "mp3",              # Output format
        improved_mp3_path
    ]
    subprocess.call(command, env=env)
    
    return improved_mp3_path


def optimize_video_for_reels(input_file: str, output_file: Optional[str] = None) -> str:
    """
    Optimize video for Instagram Reels/YouTube Shorts using FFmpeg via subprocess.
    
    Follows the exact pattern from Python backend documentation.
    
    Args:
        input_file: Path to input video file
        output_file: Optional output file path. If None, generates automatically.
        
    Returns:
        Path to optimized output file
        
    Raises:
        Exception: If FFmpeg is not found or optimization fails
    """
    if output_file is None:
        output_file = os.path.join(
            os.path.dirname(input_file),
            'reeloptimized-' + os.path.basename(input_file)
        )
    
    # Check if FFmpeg is available
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise Exception("FFmpeg not found. Please install FFmpeg system-wide (apt-get, brew, or download from https://ffmpeg.org)")
    
    # Get environment with ffmpeg in PATH
    env = os.environ.copy()
    ffmpeg_dir = os.path.dirname(ffmpeg_bin)
    current_path = env.get('PATH', '')
    if ffmpeg_dir not in current_path:
        separator = ';' if os.name == 'nt' else ':'
        env['PATH'] = current_path + separator + ffmpeg_dir
    
    scale_filter = "scale=-2:1080"
    
    # Use subprocess.call() exactly as shown in Python backend documentation
    cmd = [
        "ffmpeg", "-y",
        "-i", input_file,
        "-c:v", "libx264",
        "-brand", "mp42",
        "-pix_fmt", "yuv420p",
        "-profile:v", "main",
        "-level", "3.1",
        "-preset", "medium",
        "-tune", "fastdecode",
        "-movflags", "+faststart",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ac", "2",
        "-ar", "48000",
        "-maxrate", "25M",
        "-bufsize", "30M",
        "-vf", scale_filter,
        "-r", "60",
        "-f", "mp4",
        "-y", output_file
    ]
    
    subprocess.call(cmd, env=env)
    return output_file


class YTDLPService:
    """Service for downloading videos using yt-dlp."""
    
    def __init__(self, output_dir: Optional[Path] = None):
        """
        Initialize YT-DLP service.
        
        Args:
            output_dir: Directory to save downloaded videos. If None, uses default.
        """
        if output_dir is None:
            output_dir = project_root / "temp_videos" / "output" / "ytdlp_downloads"
        
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def _find_ytdlp_binary() -> str:
        """
        Find yt-dlp binary in multiple locations.
        
        Checks in order:
        1. System PATH (for Docker/system-wide installations)
        2. Virtual environment (venv/bin or venv/Scripts)
        3. Python site-packages bin directory (for pip installs)
        4. User local bin directory (~/.local/bin)
        
        Returns:
            Path to yt-dlp binary
            
        Raises:
            Exception: If yt-dlp binary is not found in any location
        """
        # Check system PATH first (works for Docker and system-wide installs)
        ytdlp_binary = shutil.which("yt-dlp")
        if ytdlp_binary:
            return ytdlp_binary
        
        # Try alternative name
        ytdlp_binary = shutil.which("ytdlp")
        if ytdlp_binary:
            return ytdlp_binary
        
        # Check virtual environment (common for local development)
        venv_scripts = project_root / "venv" / ("Scripts" if os.name == "nt" else "bin")
        venv_ytdlp = venv_scripts / ("yt-dlp.exe" if os.name == "nt" else "yt-dlp")
        if venv_ytdlp.exists():
            return str(venv_ytdlp)
        
        # Check Python site-packages bin directory (for pip installs in Python environment)
        # This is where Render.com and other cloud platforms install pip packages
        try:
            import site
            for site_packages in site.getsitepackages():
                # site-packages is typically in .../lib/pythonX.X/site-packages
                # bin directory is typically in .../bin (parent of lib)
                bin_dir = Path(site_packages).parent.parent / ("Scripts" if os.name == "nt" else "bin")
                ytdlp_path = bin_dir / ("yt-dlp.exe" if os.name == "nt" else "yt-dlp")
                if ytdlp_path.exists():
                    return str(ytdlp_path)
        except (AttributeError, ImportError):
            pass
        
        # Check user local bin directory (~/.local/bin on Linux/Mac, %USERPROFILE%\.local\bin on Windows)
        # This is where pip installs user packages
        if os.name == "nt":
            user_local_bin = Path.home() / ".local" / "bin"
        else:
            user_local_bin = Path.home() / ".local" / "bin"
        
        user_ytdlp = user_local_bin / ("yt-dlp.exe" if os.name == "nt" else "yt-dlp")
        if user_ytdlp.exists():
            return str(user_ytdlp)
        
        # Also check if we can find it via sys.executable's directory
        # This handles cases where Python is in a virtual environment
        python_dir = Path(sys.executable).parent
        python_bin_ytdlp = python_dir / ("yt-dlp.exe" if os.name == "nt" else "yt-dlp")
        if python_bin_ytdlp.exists():
            return str(python_bin_ytdlp)
        
        # If still not found, raise exception
        raise Exception(
            "yt-dlp binary not found. Please install yt-dlp: pip install yt-dlp\n"
            "The binary was checked in:\n"
            "- System PATH\n"
            "- Virtual environment (venv/bin or venv/Scripts)\n"
            "- Python site-packages bin directory\n"
            "- User local bin directory (~/.local/bin)\n"
            "- Python executable directory"
        )
    
    def _get_env_with_ffmpeg(self):
        """
        Get environment variables with ffmpeg in PATH.
        This ensures subprocess calls can find ffmpeg even if the Python
        process was started before PATH was updated.
        
        Returns:
            Dictionary of environment variables with ffmpeg in PATH
        """
        env = os.environ.copy()
        current_path = env.get('PATH', '')
        separator = ';' if os.name == 'nt' else ':'
        
        # Try to find ffmpeg using shutil.which (checks current PATH)
        ffmpeg_bin = shutil.which("ffmpeg")
        if ffmpeg_bin:
            ffmpeg_dir = os.path.dirname(ffmpeg_bin)
            if ffmpeg_dir not in current_path:
                env['PATH'] = current_path + separator + ffmpeg_dir
            return env
        
        # If not found in PATH, check common locations
        ffmpeg_paths = [
            r"C:\Users\ACER\developer\ffmpeg-2025-12-28-git-9ab2a437a1-essentials_build\bin",
            r"C:\ffmpeg\bin",
            r"C:\Program Files\ffmpeg\bin",
            r"C:\Program Files (x86)\ffmpeg\bin",
        ]
        
        # Also check system and user environment variables (may have been updated)
        # On Windows, check user environment variable directly
        if os.name == 'nt':
            try:
                import winreg
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment")
                user_path = winreg.QueryValueEx(key, "Path")[0]
                winreg.CloseKey(key)
                if user_path and user_path not in current_path:
                    env['PATH'] = current_path + separator + user_path
                    current_path = env['PATH']
            except (FileNotFoundError, OSError, ImportError):
                pass
        
        # Check known locations and add if they exist
        for ffmpeg_path in ffmpeg_paths:
            if os.path.exists(ffmpeg_path):
                exe_path = os.path.join(ffmpeg_path, "ffmpeg.exe" if os.name == 'nt' else "ffmpeg")
                if os.path.exists(exe_path) and ffmpeg_path not in current_path:
                    env['PATH'] = current_path + separator + ffmpeg_path
                    break
        
        return env
    
    def download_video(
        self,
        url: str,
        output_filename: Optional[str] = None,
        quality: str = "best",
        format_type: str = "mp4",
        audio_only: bool = False,
    ) -> Dict[str, Any]:
        """
        Download a video from a URL using yt-dlp.
        
        For post-processing (audio extraction, merging), yt-dlp uses FFmpeg
        which must be available in system PATH (installed via apt-get, brew, etc.).
        
        Args:
            url: URL of the video to download (YouTube, Vimeo, etc.)
            output_filename: Optional custom filename (without extension).
                           If None, uses video title.
            quality: Video quality ('best', 'worst', '720p', '1080p', etc.)
            format_type: Output format ('mp4', 'webm', etc.)
            audio_only: If True, download audio only (as mp3/m4a)
            
        Returns:
            Dictionary with download information:
            - output_path: Path to downloaded file
            - filename: Name of downloaded file
            - title: Video title
            - duration: Video duration in seconds
            - format: Video format/quality
            
        Raises:
            Exception: If download fails or FFmpeg is not found when needed
        """
        # Note: FFmpeg is required for audio extraction and video+audio merging
        # We'll let yt-dlp handle FFmpeg detection and provide better error messages
        # if it's not found, rather than pre-checking here
        
        # Find yt-dlp binary (checks multiple locations for compatibility)
        ytdlp_binary = self._find_ytdlp_binary()
        
        # Build yt-dlp command using subprocess (following Python backend pattern)
        cmd = [ytdlp_binary]
        
        # Enable EJS challenge solver scripts from GitHub (required for YouTube)
        # This allows yt-dlp to download EJS scripts automatically
        # Must be specified before other options
        cmd.extend(['--remote-components', 'ejs:github'])
        
        # Add JavaScript runtime for YouTube extraction (required for YouTube)
        # Check if deno is available
        deno_binary = shutil.which("deno")
        if deno_binary:
            cmd.extend(['--js-runtimes', 'deno'])
        
        # Set output template
        if output_filename:
            outtmpl = str(self.output_dir / f'{output_filename}.%(ext)s')
        else:
            outtmpl = str(self.output_dir / '%(title)s.%(ext)s')
        cmd.extend(['-o', outtmpl])
        
        # Configure format selection
        if audio_only:
            cmd.extend(['-f', 'bestaudio/best', '--extract-audio', '--audio-format', 'mp3', '--audio-quality', '192'])
        else:
            if quality == "best":
                cmd.extend(['-f', f'bestvideo[ext={format_type}]+bestaudio[ext=m4a]/best[ext={format_type}]/best'])
            elif quality == "worst":
                cmd.extend(['-f', f'worst[ext={format_type}]/worst'])
            else:
                # For specific quality like '720p', '1080p'
                height = quality.replace("p", "")
                cmd.extend(['-f', f'bestvideo[height<={height}][ext={format_type}]+bestaudio/best[height<={height}][ext={format_type}]/best'])
        
        # Add URL
        cmd.append(url)
        
        try:
            # Get environment with ffmpeg in PATH
            env = self._get_env_with_ffmpeg()
            
            # Track files before download
            files_before = set(self.output_dir.glob("*"))
            
            # Get video info first (for metadata)
            info_cmd = [ytdlp_binary]
            # Enable EJS challenge solver scripts from GitHub (must come before other options)
            info_cmd.extend(['--remote-components', 'ejs:github'])
            # Add JavaScript runtime if available (required for YouTube)
            if deno_binary:
                info_cmd.extend(['--js-runtimes', 'deno'])
            # Add dump-json and no-download flags
            info_cmd.extend(['--dump-json', '--no-download', url])
            
            try:
                info_result = subprocess.run(
                    info_cmd,
                    capture_output=True,
                    text=True,
                    check=True,
                    env=env
                )
                info = json.loads(info_result.stdout)
            except subprocess.CalledProcessError as e:
                # Get error from stderr or stdout
                error_output = e.stderr if e.stderr else (e.stdout if e.stdout else str(e))
                error_msg = f"Failed to get video info: {error_output}"
                
                # Check for common issues
                error_lower = error_msg.lower()
                if "sign in to confirm" in error_lower or "not a bot" in error_lower:
                    error_msg += "\n\nThis video requires authentication (YouTube bot detection). Some videos may not be accessible without cookies."
                elif "javascript runtime" in error_lower or "js-runtimes" in error_lower:
                    error_msg += "\n\nJavaScript runtime (deno) should be installed. If this error persists, the video may require additional authentication."
                
                raise Exception(error_msg)
            
            # Download the video using subprocess (following Python backend pattern)
            download_result = subprocess.run(cmd, capture_output=True, text=True, check=True, env=env)
            
            # Find the newly created file
            files_after = set(self.output_dir.glob("*"))
            new_files = files_after - files_before
            
            if new_files:
                # Use the most recently created file
                output_path = max(new_files, key=lambda p: p.stat().st_mtime)
            else:
                # Fallback: try to find file matching expected name pattern
                if output_filename:
                    pattern = f"{output_filename}.*"
                else:
                    title = info.get('title', 'video')
                    safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                    pattern = f"{safe_title}.*"
                
                matching_files = list(self.output_dir.glob(pattern))
                if matching_files:
                    output_path = matching_files[0]
                else:
                    raise Exception("Downloaded file not found")
            
            return {
                "output_path": str(output_path),
                "filename": output_path.name,
                "title": info.get('title', 'Unknown'),
                "duration": info.get('duration', 0),
                "format": info.get('format', 'Unknown'),
                "uploader": info.get('uploader', 'Unknown'),
                "url": url,
            }
                
        except subprocess.CalledProcessError as e:
            error_output = e.stderr if hasattr(e, 'stderr') and e.stderr else (e.stdout if hasattr(e, 'stdout') and e.stdout else str(e))
            error_msg = f"Download failed: {error_output}"
            
            # Check for common YouTube issues
            error_lower = error_msg.lower()
            if "sign in to confirm" in error_lower or "not a bot" in error_lower or "cookies" in error_lower:
                error_msg += "\n\nThis video requires authentication (YouTube bot detection). "
                error_msg += "Some videos may not be accessible without cookies. "
                error_msg += "Try a different video or use cookies if available."
            elif "ffmpeg" in error_lower or "ffprobe" in error_lower:
                error_msg += "\n\nFFmpeg is required for audio extraction. Please install FFmpeg system-wide:\n"
                error_msg += "- Windows: Download from https://ffmpeg.org/download.html and add to PATH\n"
                error_msg += "- Linux: sudo apt-get install ffmpeg\n"
                error_msg += "- macOS: brew install ffmpeg"
            elif "javascript runtime" in error_lower or "js-runtimes" in error_lower:
                error_msg += "\n\nJavaScript runtime (deno) should be installed. If this error persists, the video may require additional authentication."
            
            raise Exception(error_msg)
        except json.JSONDecodeError as e:
            raise Exception(f"Error parsing video info: {str(e)}")
        except Exception as e:
            raise Exception(f"Error downloading video: {str(e)}")
    
    def get_video_info(self, url: str) -> Dict[str, Any]:
        """
        Get video information without downloading using subprocess.
        
        Args:
            url: URL of the video
            
        Returns:
            Dictionary with video information (title, duration, formats, etc.)
            
        Raises:
            Exception: If info extraction fails
        """
        # Find yt-dlp binary (checks multiple locations for compatibility)
        ytdlp_binary = self._find_ytdlp_binary()
        
        # Check if deno (JavaScript runtime) is available for YouTube extraction
        deno_binary = shutil.which("deno")
        
        # Use subprocess to get video info (following Python backend pattern)
        cmd = [ytdlp_binary]
        # Enable EJS challenge solver scripts from GitHub (must come before other options)
        cmd.extend(['--remote-components', 'ejs:github'])
        # Add JavaScript runtime if available (required for YouTube)
        if deno_binary:
            cmd.extend(['--js-runtimes', 'deno'])
        # Add dump-json and no-download flags
        cmd.extend(['--dump-json', '--no-download', url])
        
        try:
            # Get environment with ffmpeg in PATH
            env = self._get_env_with_ffmpeg()
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                env=env
            )
            
            info = json.loads(result.stdout)
            
            description = info.get('description')
            if description:
                description = description[:500]  # First 500 chars
            else:
                description = ''
            
            return {
                "title": info.get('title', 'Unknown'),
                "duration": info.get('duration', 0),
                "uploader": info.get('uploader', 'Unknown'),
                "view_count": info.get('view_count', 0),
                "description": description,
                "thumbnail": info.get('thumbnail', ''),
                "formats": len(info.get('formats', [])),
                "url": url,
            }
        except subprocess.CalledProcessError as e:
            raise Exception(f"Error getting video info: {e.stderr if hasattr(e, 'stderr') else str(e)}")
        except json.JSONDecodeError as e:
            raise Exception(f"Error parsing video info: {str(e)}")
        except Exception as e:
            raise Exception(f"Error getting video info: {str(e)}")

