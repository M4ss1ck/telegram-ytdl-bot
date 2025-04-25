import yt_dlp
import os
import asyncio
import re
import logging
from .instagram_downloader import InstagramDownloader
from .spotify_downloader import SpotifyDownloader
from .youtube_api_downloader import YouTubeAPIDownloader
from .browser_downloader import BrowserDownloader

logger = logging.getLogger(__name__)

class Downloader:
    def __init__(self, config):
        self.config = config
        self.instagram_downloader = InstagramDownloader(config)
        self.spotify_downloader = SpotifyDownloader(config)
        self.youtube_api_downloader = YouTubeAPIDownloader(config)
        self.browser_downloader = BrowserDownloader(config)
        
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
        elif is_youtube:
            # Handle YouTube URLs based on the configured strategy
            return await self._handle_youtube_download(url)
        else:
            # Use yt-dlp for other URLs
            return await self._download_with_ytdlp(url)
            
    async def _handle_youtube_download(self, url):
        """Handle YouTube downloads based on configured strategy"""
        strategy = self.config.YOUTUBE_STRATEGY.lower()
        
        # Define the order of methods to try based on strategy
        methods = []
        last_error = None
        
        if strategy == 'api_first':
            methods = [
                self._try_api_download,
                self._try_proxy_download,
                self._try_browser_download,
                self._try_alternate_frontends
            ]
        elif strategy == 'proxy_first':
            methods = [
                self._try_proxy_download,
                self._try_api_download,
                self._try_browser_download,
                self._try_alternate_frontends
            ]
        elif strategy == 'browser_first':
            methods = [
                self._try_browser_download,
                self._try_api_download,
                self._try_proxy_download,
                self._try_alternate_frontends
            ]
        elif strategy == 'alt_frontends_first':
            methods = [
                self._try_alternate_frontends,
                self._try_api_download,
                self._try_proxy_download,
                self._try_browser_download
            ]
        else:
            # Default strategy: Prioritize proxy and API, then alt frontends, then browser
            methods = [
                self._try_proxy_download,
                self._try_api_download,
                self._try_alternate_frontends,
                self._try_browser_download
            ]
        
        # Try each method in the determined order
        for method in methods:
            try:
                return await method(url)
            except Exception as e:
                last_error = e
                logger.warning(f"YouTube download method {method.__name__} failed: {e}")
                continue
        
        # If all methods fail, raise the last error
        if last_error:
            raise last_error
        else:
            raise Exception("All YouTube download methods failed")
    
    async def _try_api_download(self, url):
        """Try downloading YouTube content via API service"""
        logger.info(f"Attempting YouTube download via API service: {url}")
        
        # Check if any API keys are configured
        has_api_key = bool(self.config.RAPIDAPI_KEY or self.config.YOUTUBE_API_KEY)
        
        if not has_api_key:
            logger.warning("No YouTube API keys configured. Skipping API download method.")
            raise Exception(
                "YouTube API download method skipped: No API keys configured. "
                "Configure RAPIDAPI_KEY or YOUTUBE_API_KEY in your .env file to use this method."
            )
            
        try:    
            return await self.youtube_api_downloader.download(url)
        except Exception as e:
            # Add more context to the error for debugging
            error_msg = str(e)
            logger.error(f"YouTube API downloader failed: {error_msg}")
            
            # Provide more helpful error message
            if "API Error: 429" in error_msg or "rate limit" in error_msg.lower():
                raise Exception("YouTube API rate limit exceeded. Try again later or use a different download method.")
            elif "API Error: 403" in error_msg:
                raise Exception("YouTube API access forbidden. Your API key may be invalid or expired.")
            elif "No download link" in error_msg or "Invalid API response" in error_msg:
                raise Exception("YouTube API service couldn't process this video. It may be restricted or unavailable.")
            else:
                raise
    
    async def _try_proxy_download(self, url):
        """Try downloading YouTube content via proxy"""
        logger.info(f"Attempting YouTube download via proxy: {url}")
        
        # Only try if a proxy is configured
        if not self.config.PROXY_URL:
            raise Exception("No proxy URL configured")
            
        # Set up yt-dlp options with proxy
        ydl_opts = self._get_base_ytdlp_options()
        ydl_opts['proxy'] = self.config.PROXY_URL
        
        # Add extra options that might help when behind a proxy
        ydl_opts['youtube_include_dash_manifest'] = False
        ydl_opts['youtube_include_hls_manifest'] = False
        # Consider adding cookie options if needed: ydl_opts['cookiesfrombrowser'] = ('firefox',) or ydl_opts['cookiefile'] = 'path/to/cookies.txt'
        
        # Add "proxy" to filename to help identify the method used
        downloads_dir = self.config.downloads_dir
        ydl_opts['outtmpl'] = str(downloads_dir / 'proxy_%(title)s.%(ext)s')
        
        # Try the download
        try:
            return await asyncio.to_thread(self._download_video, url, ydl_opts)
        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e)
            logger.error(f"yt-dlp proxy download error: {error_msg}")
            if "Failed to extract any player response" in error_msg:
                raise Exception("Proxy download failed: YouTube blocked request even via proxy. The proxy IP might be flagged.")
            elif "Sign in to confirm" in error_msg:
                raise Exception("Proxy download failed: YouTube requires login/cookies even via proxy.")
            else:
                raise Exception(f"Proxy download failed with yt-dlp error: {error_msg}")
        except Exception as e:
            # Catch other potential errors during the threaded execution
            logger.error(f"Unexpected error during proxy download: {str(e)}")
            raise
    
    async def _try_browser_download(self, url):
        """Try downloading YouTube content via browser automation"""
        logger.info(f"Attempting YouTube download via browser automation: {url}")
        
        # Check if browser downloader is enabled in config
        if not self.config.BROWSER_ENABLED:
            raise Exception("Browser downloader is not enabled in configuration")
            
        try:
            return await self.browser_downloader.download(url)
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Browser download failed: {error_msg}")
            
            if "missing required dependencies" in error_msg.lower():
                raise Exception("Browser automation requires additional dependencies. "
                                "Install playwright or selenium to use this method.")
            else:
                raise
    
    async def _try_alternate_frontends(self, url):
        """Try downloading YouTube content via alternate frontends"""
        logger.info(f"Attempting YouTube download via alternate frontends: {url}")
        
        # Set up base options
        ydl_opts = self._get_base_ytdlp_options()
        
        # Add "alt" to filename to help identify the method used
        downloads_dir = self.config.downloads_dir
        ydl_opts['outtmpl'] = str(downloads_dir / 'alt_%(title)s.%(ext)s')
        
        # Get video ID
        video_id = None
        match = re.search(r'(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})', url)
        if match:
            video_id = match.group(1)
        
        if not video_id:
            raise Exception(f"Could not extract video ID from URL: {url}")
        
        # List of alternate YouTube frontends to try
        alt_sources = [
            f"https://invidious.snopyta.org/watch?v={video_id}",
            f"https://inv.tux.pizza/latest_version?id={video_id}",
            f"https://vid.puffyan.us/watch?v={video_id}",
            f"https://y.com.sb/watch?v={video_id}",
            f"https://yewtu.be/watch?v={video_id}",
            f"https://invidio.xamh.de/watch?v={video_id}",
            f"https://inv.riverside.rocks/watch?v={video_id}",
            f"https://yt.artemislena.eu/watch?v={video_id}",
            f"https://invidious.flokinet.to/watch?v={video_id}",
            f"https://invidious.esmailelbob.xyz/watch?v={video_id}"
        ]
        
        # Try each source
        last_error = None
        for alt_url in alt_sources:
            try:
                logger.info(f"Trying alternate frontend: {alt_url}")
                return await asyncio.to_thread(self._download_video, alt_url, ydl_opts)
            except Exception as e:
                last_error = e
                logger.warning(f"Failed with alternate frontend {alt_url}: {str(e)}")
                continue
        
        # If all alternate sources fail, raise the last error
        if last_error:
            raise last_error
        else:
            raise Exception("All alternate YouTube frontends failed")
    
    def _get_base_ytdlp_options(self):
        """Get base yt-dlp options for YouTube downloads"""
        return {
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
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Connection': 'keep-alive',
            },
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
        }
    
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
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
        }
        
        # If a proxy is configured, use it for YouTube content
        if is_youtube and self.config.PROXY_URL:
            logger.info(f"Using proxy for YouTube URL: {url}")
            ydl_opts['proxy'] = self.config.PROXY_URL
        
        # Add YouTube specific options
        if is_youtube:
            # Use higher user-agent rotation and retry options for YouTube
            ydl_opts.update({
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Connection': 'keep-alive',
                },
                'retries': 10,
                'fragment_retries': 10,
                'skip_unavailable_fragments': True,
            })
        
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
            
            # Add Instagram-specific headers to mimic a browser
            ydl_opts['http_headers'] = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Connection': 'keep-alive',
            }
        
        # Add Spotify-specific options if this is a Spotify URL
        if is_spotify:
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                }],
                # Add Spotify-specific headers
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Connection': 'keep-alive',
                },
                # Try to extract audio from Spotify URLs
                'extractor_args': {
                    'spotify': {
                        'extract_audio': True,
                    }
                }
            })
        
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