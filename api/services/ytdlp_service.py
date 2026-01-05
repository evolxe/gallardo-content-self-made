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
    Extract audio from video file using MoviePy.
    
    Args:
        input_file: Path to input video file (any format supported by MoviePy)
        
    Returns:
        Path to output MP3 file
        
    Raises:
        Exception: If conversion fails
    """
    from moviepy import VideoFileClip
    
    output_file = input_file.rsplit('.', 1)[0] + '.mp3'
    
    video = VideoFileClip(input_file)
    try:
        if video.audio is None:
            raise Exception("Video file has no audio track")
        
        audio = video.audio
        audio.write_audiofile(
            output_file,
            codec='mp3',
            bitrate='192k',
            logger=None  # Suppress verbose logging
        )
        audio.close()
    finally:
        video.close()
    
    return output_file


def local_video_to_mp3(local_mp4_path: str) -> str:
    """
    Extract MP3 from video using MoviePy.
    
    This is an alias for convert_local_video_to_mp3() for backward compatibility.
    
    Args:
        local_mp4_path: Path to input video file (any format supported by MoviePy)
        
    Returns:
        Path to output MP3 file
        
    Raises:
        Exception: If conversion fails
    """
    return convert_local_video_to_mp3(local_mp4_path)


def optimize_video_for_reels(input_file: str, output_file: Optional[str] = None) -> str:
    """
    Optimize video for Instagram Reels/YouTube Shorts using MoviePy.
    
    Args:
        input_file: Path to input video file
        output_file: Optional output file path. If None, generates automatically.
        
    Returns:
        Path to optimized output file
        
    Raises:
        Exception: If optimization fails
    """
    from moviepy import VideoFileClip, vfx
    
    if output_file is None:
        output_file = os.path.join(
            os.path.dirname(input_file),
            'reeloptimized-' + os.path.basename(input_file)
        )
    
    video = VideoFileClip(input_file)
    try:
        # Resize to height 1080 (maintain aspect ratio)
        video = video.with_effects([vfx.Resize(height=1080)])
        
        # Set FPS to 60
        video = video.with_fps(60)
        
        # Write optimized video
        video.write_videofile(
            output_file,
            codec="libx264",
            audio_codec="aac",
            bitrate="5000k",
            preset="medium",
            ffmpeg_params=[
                "-brand", "mp42",
                "-pix_fmt", "yuv420p",
                "-profile:v", "main",
                "-level", "3.1",
                "-tune", "fastdecode",
                "-movflags", "+faststart",
                "-maxrate", "25M",
                "-bufsize", "30M",
            ],
            logger=None  # Suppress verbose logging
        )
    finally:
        video.close()
    
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
        
        This ensures yt-dlp subprocess calls can find FFmpeg (yt-dlp uses FFmpeg
        internally for merging video+audio streams and audio extraction).
        
        Dynamically discovers FFmpeg location to work across different environments
        (Docker, Render.com, local development, etc.)
        
        Note: We no longer call FFmpeg directly via subprocess - all video/audio
        processing uses MoviePy. This function is only needed for yt-dlp subprocess calls.
        
        Returns:
            Dictionary of environment variables with ffmpeg in PATH
        """
        env = os.environ.copy()
        current_path = env.get('PATH', '')
        separator = ';' if os.name == 'nt' else ':'
        
        # Method 1: Try to find FFmpeg using which (checks current PATH)
        ffmpeg_bin = shutil.which("ffmpeg")
        if ffmpeg_bin:
            ffmpeg_dir = os.path.dirname(ffmpeg_bin)
            if ffmpeg_dir and ffmpeg_dir not in current_path:
                current_path = ffmpeg_dir + separator + current_path if current_path else ffmpeg_dir
        else:
            # Method 2: Try to find FFmpeg by checking common installation locations
            # Use subprocess to query package manager (works in Docker/Render.com)
            common_ffmpeg_paths = [
                "/usr/bin",           # Most common Linux location
                "/usr/local/bin",     # Alternative location
                "/bin",               # Core system binaries
            ]
            
            # Try to use dpkg to find actual FFmpeg location (Debian/Ubuntu)
            if os.path.exists("/usr/bin/dpkg"):
                try:
                    result = subprocess.run(
                        ["dpkg", "-L", "ffmpeg"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        for line in result.stdout.split('\n'):
                            if '/bin/ffmpeg' in line:
                                discovered_path = os.path.dirname(line.strip())
                                if discovered_path and discovered_path not in current_path:
                                    common_ffmpeg_paths.insert(0, discovered_path)
                                break
                except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError):
                    pass  # Fall back to common paths
            
            # Check each path and add the first one that contains ffmpeg
            for ffmpeg_path in common_ffmpeg_paths:
                ffmpeg_exe = os.path.join(ffmpeg_path, "ffmpeg")
                if os.path.exists(ffmpeg_exe):
                    if ffmpeg_path not in current_path:
                        current_path = ffmpeg_path + separator + current_path if current_path else ffmpeg_path
                    break
        
        env['PATH'] = current_path
        
        # Final verification: ensure FFmpeg is now accessible
        ffmpeg_bin = shutil.which("ffmpeg", path=env['PATH'])
        if not ffmpeg_bin:
            # Last resort: try direct file system check
            for check_path in ["/usr/bin", "/usr/local/bin", "/bin"]:
                test_ffmpeg = os.path.join(check_path, "ffmpeg")
                if os.path.exists(test_ffmpeg) and os.access(test_ffmpeg, os.X_OK):
                    if check_path not in env['PATH']:
                        env['PATH'] = check_path + separator + env['PATH']
                    ffmpeg_bin = test_ffmpeg
                    break
            
            if not ffmpeg_bin:
                # Critical error - FFmpeg must be available
                raise RuntimeError(
                    f"FFmpeg not found. Searched in PATH: {env.get('PATH', 'N/A')}. "
                    f"Please ensure FFmpeg is installed via 'apt-get install ffmpeg' in Dockerfile."
                )
        
        # Note: Node.js and Deno are installed for yt-dlp Python library's JS runtime,
        # but the Python library handles finding them internally. We don't need to
        # add them to PATH for subprocess calls - only FFmpeg is needed.
        
        return env
    
    def download_video(
        self,
        url: str,
        output_filename: Optional[str] = None,
        quality: str = "best",
        format_type: str = "mp4",
        audio_only: bool = False,
        cookies_file: Optional[str] = None,
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
            cookies_file: Optional path to cookies.txt file for authentication
            
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
        
        # Add cookies if provided (helps with bot detection and authentication)
        if cookies_file and Path(cookies_file).exists():
            cmd.extend(['--cookies', cookies_file])
        
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
            # Add cookies if provided (helps with bot detection and authentication)
            if cookies_file and Path(cookies_file).exists():
                info_cmd.extend(['--cookies', cookies_file])
            # Add dump-json and no-download flags
            info_cmd.extend(['--dump-json', '--no-download', url])
            
            try:
                info_result = subprocess.run(
                    info_cmd,
                    capture_output=True,
                    text=True,
                    check=True,
                    env=env,
                    timeout=60  # Add timeout to prevent hanging
                )
                
                # Safety check: ensure result is not None and has stdout
                if info_result is None:
                    raise Exception("Subprocess call returned None. This should not happen.")
                if not hasattr(info_result, 'stdout') or info_result.stdout is None:
                    raise Exception(
                        f"Subprocess result has no stdout. "
                        f"Return code: {info_result.returncode if hasattr(info_result, 'returncode') else 'unknown'}, "
                        f"stderr: {info_result.stderr if hasattr(info_result, 'stderr') else 'unknown'}"
                    )
                
                info = json.loads(info_result.stdout)
            except FileNotFoundError as e:
                raise Exception(
                    f"Command not found. yt-dlp or FFmpeg may not be installed or not in PATH. "
                    f"Original error: {str(e)}"
                )
            except subprocess.TimeoutExpired as e:
                raise Exception(f"Command timed out after 60 seconds: {str(e)}")
            except subprocess.CalledProcessError as e:
                # Get error from stderr or stdout, with safety checks
                error_output = ""
                if hasattr(e, 'stderr') and e.stderr:
                    error_output = e.stderr
                elif hasattr(e, 'stdout') and e.stdout:
                    error_output = e.stdout
                else:
                    error_output = str(e)
                error_msg = f"Failed to get video info: {error_output}"
                
                # Check for common issues
                error_lower = error_msg.lower()
                if "sign in to confirm" in error_lower or "not a bot" in error_lower:
                    error_msg += "\n\nThis video requires authentication (YouTube bot detection). Some videos may not be accessible without cookies."
                elif "javascript runtime" in error_lower or "js-runtimes" in error_lower:
                    error_msg += "\n\nJavaScript runtime (deno) should be installed. If this error persists, the video may require additional authentication."
                
                raise Exception(error_msg)
            
            # Download the video using subprocess (following Python backend pattern)
            try:
                download_result = subprocess.run(
                    cmd, 
                    capture_output=True, 
                    text=True, 
                    check=True, 
                    env=env,
                    timeout=600  # 10 minute timeout for downloads
                )
            except FileNotFoundError as e:
                raise Exception(
                    f"Command not found. yt-dlp or FFmpeg may not be installed or not in PATH. "
                    f"Original error: {str(e)}"
                )
            except subprocess.TimeoutExpired as e:
                raise Exception(f"Download timed out after 10 minutes: {str(e)}")
            except subprocess.CalledProcessError as e:
                error_output = ""
                if hasattr(e, 'stderr') and e.stderr:
                    error_output = e.stderr
                elif hasattr(e, 'stdout') and e.stdout:
                    error_output = e.stdout
                else:
                    error_output = str(e)
                raise Exception(f"Download failed: {error_output}")
            
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
    
    def get_video_info(self, url: str, cookies_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Get video information without downloading using subprocess.
        
        Args:
            url: URL of the video
            cookies_file: Optional path to cookies.txt file for authentication
            
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
        # Add cookies if provided (helps with bot detection and authentication)
        if cookies_file and Path(cookies_file).exists():
            cmd.extend(['--cookies', cookies_file])
        # Add dump-json and no-download flags
        cmd.extend(['--dump-json', '--no-download', url])
        
        try:
            # Get environment with ffmpeg in PATH
            env = self._get_env_with_ffmpeg()
            
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=True,
                    env=env,
                    timeout=60  # Add timeout to prevent hanging
                )
            except FileNotFoundError as e:
                raise Exception(
                    f"Command not found. This usually means yt-dlp or FFmpeg is not installed. "
                    f"Please ensure both are available in PATH. Original error: {str(e)}"
                )
            except subprocess.TimeoutExpired as e:
                raise Exception(f"Command timed out after 60 seconds: {str(e)}")
            
            # Safety check: ensure result is not None and has stdout
            if result is None:
                raise Exception("Subprocess call returned None. This should not happen.")
            if not hasattr(result, 'stdout') or result.stdout is None:
                raise Exception(
                    f"Subprocess result has no stdout. "
                    f"Return code: {result.returncode if hasattr(result, 'returncode') else 'unknown'}, "
                    f"stderr: {result.stderr if hasattr(result, 'stderr') else 'unknown'}"
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
            error_msg = "Error getting video info"
            if hasattr(e, 'stderr') and e.stderr:
                error_msg += f": {e.stderr}"
            elif hasattr(e, 'stdout') and e.stdout:
                error_msg += f": {e.stdout}"
            else:
                error_msg += f": {str(e)}"
            raise Exception(error_msg)
        except FileNotFoundError as e:
            raise Exception(
                f"Command not found. yt-dlp or FFmpeg may not be installed or not in PATH. "
                f"Original error: {str(e)}"
            )
        except json.JSONDecodeError as e:
            raise Exception(f"Error parsing video info JSON: {str(e)}")
        except Exception as e:
            raise Exception(f"Error getting video info: {str(e)}")

