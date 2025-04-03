import os
import logging
import instaloader
import re
from pathlib import Path
import asyncio
import time

logger = logging.getLogger(__name__)

class SimpleRateController:
    """A simple rate controller for Instaloader that uses time.sleep"""
    def __init__(self, sleep_time=2):
        self.sleep_time = sleep_time
        
    def wait_before_query(self, *args, **kwargs):
        """Wait before making a query"""
        time.sleep(self.sleep_time)
        
    def wait_before_download(self, *args, **kwargs):
        """Wait before downloading"""
        time.sleep(self.sleep_time)

class InstagramDownloader:
    def __init__(self, config):
        self.config = config
        self.loader = instaloader.Instaloader(
            download_videos=True,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False,
            post_metadata_txt_pattern="",
            max_connection_attempts=3,
            request_timeout=30,
            rate_controller=SimpleRateController(sleep_time=2),
        )
        
        # Try to load session if available
        self._load_session()
        
    def _load_session(self):
        """Try to load an existing Instagram session if available"""
        session_file = self.config.downloads_dir / "instagram_session"
        if session_file.exists():
            try:
                self.loader.load_session_from_file(None, str(session_file))
                logger.info("Loaded Instagram session from file")
            except Exception as e:
                logger.warning(f"Failed to load Instagram session: {e}")
    
    def _extract_shortcode(self, url):
        """Extract the shortcode from an Instagram URL"""
        # Handle different Instagram URL formats
        patterns = [
            r'instagram.com/p/([^/]+)',
            r'instagram.com/reel/([^/]+)',
            r'instagram.com/tv/([^/]+)',
            r'instagram.com/stories/[^/]+/([^/]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    async def download(self, url):
        """Download content from Instagram using Instaloader"""
        shortcode = self._extract_shortcode(url)
        if not shortcode:
            raise ValueError("Invalid Instagram URL format")
        
        try:
            # Create a temporary directory for this download
            temp_dir = self.config.downloads_dir / f"instagram_{shortcode}"
            os.makedirs(temp_dir, exist_ok=True)
            
            # Set the download directory
            self.loader.dirname_pattern = str(temp_dir)
            
            # Download the post - use asyncio.to_thread to run in a separate thread
            # since Instaloader is not async-compatible
            post = await asyncio.to_thread(
                instaloader.Post.from_shortcode, 
                self.loader.context, 
                shortcode
            )
            
            # Download the post
            await asyncio.to_thread(
                self.loader.download_post, 
                post, 
                target=shortcode
            )
            
            # Find the downloaded video file
            video_files = list(temp_dir.glob("*.mp4"))
            if not video_files:
                raise ValueError("No video file found in downloaded content")
            
            # Get the largest video file (usually the highest quality)
            video_file = max(video_files, key=lambda f: f.stat().st_size)
            
            # Move the file to the downloads directory with a better name
            target_file = self.config.downloads_dir / f"instagram_{shortcode}.mp4"
            os.rename(video_file, target_file)
            
            # Clean up the temporary directory
            for file in temp_dir.glob("*"):
                if file != video_file:  # Don't try to delete the file we just moved
                    try:
                        if file.is_file():
                            os.remove(file)
                        elif file.is_dir():
                            import shutil
                            shutil.rmtree(file)
                    except Exception as e:
                        logger.warning(f"Failed to clean up {file}: {e}")
            
            # Remove the temporary directory
            try:
                os.rmdir(temp_dir)
            except Exception as e:
                logger.warning(f"Failed to remove temporary directory {temp_dir}: {e}")
            
            return str(target_file)
            
        except instaloader.exceptions.InstaloaderException as e:
            logger.error(f"Instaloader error: {e}")
            raise ValueError(f"Instagram download failed: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during Instagram download: {e}")
            raise 