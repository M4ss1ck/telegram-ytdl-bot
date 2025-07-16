import yt_dlp
import os
import asyncio
import re
import logging
from .instagram_downloader import InstagramDownloader
from .spotify_downloader import SpotifyDownloader

logger = logging.getLogger(__name__)

class Downloader:
    def __init__(self, config):
        self.config = config
        self.instagram_downloader = InstagramDownloader(config)
        self.spotify_downloader = SpotifyDownloader(config)
        
    def is_youtube_url(self, url):
        """Check if the URL is from YouTube"""
        youtube_patterns = [
            r'(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com\/playlist\?list=([a-zA-Z0-9_-]+)',
            r'youtube\.com\/channel\/([a-zA-Z0-9_-]+)',
            r'youtube\.com\/user\/([a-zA-Z0-9_-]+)',
            r'music\.youtube\.com\/',
            r'youtube\.com\/shorts\/([a-zA-Z0-9_-]+)'
        ]
        
        for pattern in youtube_patterns:
            if re.search(pattern, url):
                return True
        return False
        
    async def download(self, url):
        # Determine the type of URL
        is_instagram = 'instagram.com' in url or 'instagr.am' in url
        is_spotify = 'spotify.com' in url or 'spotify:' in url
        is_youtube = self.is_youtube_url(url)
        
        if is_instagram:
            try:
                # Try using Instaloader first
                logger.info(f"Attempting to download Instagram URL with Instaloader: {url}")
                return await self.instagram_downloader.download(url)
            except Exception as e:
                logger.warning(f"Instaloader failed for Instagram URL: {e}. Falling back to yt-dlp.")
                # Fall back to yt-dlp if Instaloader fails
                return await self._download_with_ytdlp(url, is_instagram=True)
        elif is_spotify:
            try:
                # Try using Spotify downloader
                logger.info(f"Attempting to download Spotify URL: {url}")
                return await self.spotify_downloader.download(url)
            except Exception as e:
                logger.warning(f"Spotify downloader failed: {e}. Falling back to yt-dlp.")
                # Fall back to yt-dlp if Spotify downloader fails
                return await self._download_with_ytdlp(url, is_spotify=True)
        else:
            # Use yt-dlp for YouTube and other URLs
            return await self._download_with_ytdlp(url, is_youtube=is_youtube)
    
    async def _download_with_ytdlp(self, url, is_instagram=False, is_spotify=False, is_youtube=False):
        """Download using yt-dlp with appropriate options"""
        # Base options for all downloads
        ydl_opts = {
            'outtmpl': str(self.config.downloads_dir / '%(title)s.%(ext)s'),
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'merge_output_format': 'mp4',
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'nocheckcertificate': True,
            'ignoreerrors': True,
            'no_color': True,
            'retries': 10,
            'fragment_retries': 10,
            'skip_unavailable_fragments': True,
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
        }
        
        # Add general headers
        ydl_opts['http_headers'] = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        }
        
        # Add Instagram-specific options if this is an Instagram URL
        if is_instagram:
            ydl_opts.update({
                'extractor_args': {
                    'instagram': {
                        'include_feeds': True,
                    }
                },
                'format': 'best',  # Instagram often has limited format options
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',
                }],
            })
        
        # Add Spotify-specific options if this is a Spotify URL
        if is_spotify:
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                }],
                # Try to extract audio from Spotify URLs
                'extractor_args': {
                    'spotify': {
                        'extract_audio': True,
                    }
                }
            })
        
        # Add cookie file if configured and exists
        if self.config.COOKIE_FILE_PATH and os.path.exists(self.config.COOKIE_FILE_PATH):
            logger.info(f"Using cookie file: {self.config.COOKIE_FILE_PATH}")
            ydl_opts['cookiefile'] = self.config.COOKIE_FILE_PATH
        elif self.config.COOKIE_FILE_PATH:
            logger.warning(f"Cookie file specified but not found: {self.config.COOKIE_FILE_PATH}")
        
        try:
            return await asyncio.to_thread(self._download_video, url, ydl_opts)
        except Exception as e:
            logger.error(f"Download failed for {url}: {str(e)}")
            raise Exception(f"Download failed: {str(e)}")
            
    def _download_video(self, url, ydl_opts):
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # First extract info to validate URL
                info = ydl.extract_info(url, download=False)
                
                # Check if we got valid info
                if not info:
                    raise Exception("Could not extract information from URL")
                
                # Now download the video
                ydl.download([url])
                
                # Get the filename
                filename = ydl.prepare_filename(info)
                
                # Handle audio files (for Spotify)
                if 'FFmpegExtractAudio' in [p['key'] for p in ydl_opts.get('postprocessors', [])]:
                    base_filename = os.path.splitext(filename)[0]
                    file_path = f"{base_filename}.mp3"
                else:
                    file_path = filename
                
                # Verify file exists and has content
                if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
                    raise Exception("Downloaded file is empty or does not exist")
                
                return file_path
        except yt_dlp.utils.DownloadError as e:
            logger.error(f"yt-dlp download error: {str(e)}")
            raise Exception(f"Download error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during download: {str(e)}")
            raise