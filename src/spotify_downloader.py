import os
import logging
import re
import asyncio
import yt_dlp
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import random

logger = logging.getLogger(__name__)

class SpotifyDownloader:
    def __init__(self, config):
        self.config = config
        
        # Initialize Spotify client
        client_id = os.environ.get('SPOTIFY_CLIENT_ID')
        client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET')
        
        if not client_id or not client_secret:
            logger.warning("Spotify credentials not found in environment variables")
            self.spotify_client = None
        else:
            try:
                auth_manager = SpotifyClientCredentials(
                    client_id=client_id,
                    client_secret=client_secret
                )
                self.spotify_client = spotipy.Spotify(auth_manager=auth_manager)
                logger.info("Spotify client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Spotify client: {e}")
                self.spotify_client = None
    
    def _extract_spotify_id(self, url):
        """Extract the Spotify ID from a URL"""
        patterns = [
            r'spotify\.com/(?:intl-[a-z]{2}/)?track/([a-zA-Z0-9]+)',
            r'spotify\.com/(?:intl-[a-z]{2}/)?album/([a-zA-Z0-9]+)',
            r'spotify\.com/(?:intl-[a-z]{2}/)?playlist/([a-zA-Z0-9]+)',
            r'spotify\.com/(?:intl-[a-z]{2}/)?artist/([a-zA-Z0-9]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        return None
    
    def _create_youtube_search_query(self, track_info, variation=0):
        """Create a YouTube search query from Spotify track info
        
        Args:
            track_info: Spotify track info
            variation: Which search query variation to use (0-3)
        
        Returns:
            A search query string for YouTube
        """
        if not track_info:
            return None
            
        artist = track_info['artists'][0]['name']
        title = track_info['name']
        
        # Create different variations of the search query
        variations = [
            f"{artist} - {title} audio",  # Standard format
            f"{title} {artist} audio",    # Title first format
            f"{artist} {title} official", # Official content
            f"lyrics {artist} {title}"    # Lyrics videos often have good audio
        ]
        
        variation_idx = variation % len(variations)
        return variations[variation_idx]
    
    async def download(self, url):
        """Download content from Spotify by finding it on YouTube"""
        spotify_id = self._extract_spotify_id(url)
        if not spotify_id:
            raise ValueError("Invalid Spotify URL format")
        
        try:
            # Create a temporary directory for this download
            temp_dir = self.config.downloads_dir / f"spotify_{spotify_id}"
            os.makedirs(temp_dir, exist_ok=True)
            
            # Get track information from Spotify API
            track_info = None
            youtube_search_query = None
            
            if self.spotify_client:
                try:
                    track_info = self.spotify_client.track(spotify_id)
                    artist = track_info['artists'][0]['name']
                    title = track_info['name']
                    logger.info(f"Retrieved track info: {title} by {artist}")
                except Exception as e:
                    logger.warning(f"Failed to get track info from Spotify API: {e}")
            
            # Try up to 3 different search query variations
            for variation in range(3):
                if not track_info:
                    # If we can't get track info, we can't create a search query
                    logger.warning("No track info available, cannot create YouTube search query")
                    raise ValueError("Cannot create YouTube search query without Spotify track info")
                
                # Create a search query with the current variation
                youtube_search_query = self._create_youtube_search_query(track_info, variation)
                if not youtube_search_query:
                    continue
                
                logger.info(f"Using YouTube search query variation {variation}: {youtube_search_query}")
                download_url = f"ytsearch:{youtube_search_query}"
                
                # Set up yt-dlp options
                ydl_opts = {
                    'outtmpl': str(temp_dir / '%(title)s.%(ext)s'),
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '320',
                    }],
                    'quiet': True,
                    'no_warnings': True,
                    'extract_flat': False,
                    'nocheckcertificate': True,
                    'ignoreerrors': True,
                    'no_color': True,
                    # Add YouTube-specific options
                    'default_search': 'ytsearch',
                    'noplaylist': True,
                    # Add random sleep between 1-3 seconds to avoid rate limiting
                    'sleep_interval': random.randint(1, 3),
                    # Add more browser-like headers to avoid bot detection
                    'http_headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Referer': 'https://www.youtube.com/results',
                        'DNT': '1',
                    }
                }
                
                # Try to download using yt-dlp
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        # Extract info to validate URL
                        logger.info(f"Extracting info from {download_url}")
                        info = ydl.extract_info(download_url, download=False)
                        
                        # Check if we got valid info
                        if not info:
                            logger.warning(f"Could not extract information for query: {youtube_search_query}")
                            continue
                        
                        # If we're using a search query, get the first result
                        if 'entries' in info:
                            if not info['entries']:
                                logger.warning(f"No search results found for query: {youtube_search_query}")
                                continue
                            
                            # Get the first entry that is not None
                            found_valid_entry = False
                            for entry in info['entries']:
                                if entry is not None:
                                    info = entry
                                    found_valid_entry = True
                                    logger.info(f"Using search result: {info.get('title', 'Unknown title')}")
                                    break
                            
                            if not found_valid_entry:
                                logger.warning(f"All search results were invalid for query: {youtube_search_query}")
                                continue
                        
                        # Now download the audio
                        webpage_url = info.get('webpage_url')
                        if not webpage_url:
                            logger.warning("No webpage URL found in search result")
                            continue
                            
                        logger.info(f"Downloading audio from {webpage_url}")
                        ydl.download([webpage_url])
                        
                        # Get the filename
                        filename = ydl.prepare_filename(info)
                        
                        # Handle audio files
                        base_filename = os.path.splitext(filename)[0]
                        file_path = f"{base_filename}.mp3"
                        
                        # Verify file exists and has content
                        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
                            logger.warning(f"Downloaded file is empty or does not exist: {file_path}")
                            continue
                        
                        # Move the file to the downloads directory with a better name
                        if track_info:
                            # Use track info for filename if available
                            artist = track_info['artists'][0]['name']
                            title = track_info['name']
                            safe_artist = re.sub(r'[^\w\s-]', '', artist)
                            safe_title = re.sub(r'[^\w\s-]', '', title)
                            target_file = self.config.downloads_dir / f"{safe_artist}_{safe_title}.mp3"
                        else:
                            # Use the original filename without spotify prefix
                            target_file = self.config.downloads_dir / f"{spotify_id}.mp3"
                        
                        # Rename the file
                        os.rename(file_path, target_file)
                        
                        # Clean up the temporary directory
                        for file in temp_dir.glob("*"):
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
                        
                        # Return the path to the downloaded file
                        return str(target_file)
                except Exception as e:
                    logger.warning(f"Failed to download with search variation {variation}: {e}")
                    continue
            
            # If we've tried all variations and none worked, raise an error
            raise ValueError("Failed to download track from YouTube after trying multiple search queries")
                
        except Exception as e:
            logger.error(f"Unexpected error during Spotify download: {e}")
            raise 