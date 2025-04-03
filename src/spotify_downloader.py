import os
import logging
import re
import asyncio
import yt_dlp
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from pathlib import Path
import urllib.parse
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
        # Parse URL to handle query parameters
        parsed_url = urllib.parse.urlparse(url)
        
        # Handle different Spotify URL formats
        patterns = [
            r'spotify\.com/track/([a-zA-Z0-9]+)',
            r'spotify\.com/album/([a-zA-Z0-9]+)',
            r'spotify\.com/playlist/([a-zA-Z0-9]+)',
            r'spotify\.com/artist/([a-zA-Z0-9]+)',
            # Add support for regional URLs with /intl-xx/ in the path
            r'spotify\.com/intl-[a-z]{2}/track/([a-zA-Z0-9]+)',
            r'spotify\.com/intl-[a-z]{2}/album/([a-zA-Z0-9]+)',
            r'spotify\.com/intl-[a-z]{2}/playlist/([a-zA-Z0-9]+)',
            r'spotify\.com/intl-[a-z]{2}/artist/([a-zA-Z0-9]+)',
        ]
        
        path = parsed_url.path
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    def _create_youtube_search_query(self, track_info):
        """Create a YouTube search query from Spotify track info"""
        if not track_info:
            return None
            
        artist = track_info['artists'][0]['name']
        title = track_info['name']
        
        # Create a YouTube search query
        return f"{artist} - {title} audio"
    
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
                    youtube_search_query = self._create_youtube_search_query(track_info)
                    logger.info(f"Retrieved track info: {title} by {artist}")
                    logger.info(f"Using YouTube search query: {youtube_search_query}")
                except Exception as e:
                    logger.warning(f"Failed to get track info from Spotify API: {e}")
            
            if not youtube_search_query:
                # Fallback if we couldn't get track info
                logger.warning("Using Spotify URL directly as fallback")
                download_url = url
            else:
                # Use the YouTube search query
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
            }
            
            # Download using yt-dlp
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract info to validate URL
                logger.info(f"Extracting info from {download_url}")
                info = ydl.extract_info(download_url, download=False)
                
                # Check if we got valid info
                if not info:
                    raise Exception("Could not extract information from URL")
                
                # If we're using a search query, get the first result
                if 'entries' in info:
                    logger.info(f"Found {len(info['entries'])} search results")
                    if not info['entries']:
                        raise Exception("No search results found")
                    
                    # Use the first search result
                    info = info['entries'][0]
                    logger.info(f"Using search result: {info.get('title', 'Unknown title')}")
                
                # Now download the audio
                logger.info(f"Downloading audio from {info.get('webpage_url', download_url)}")
                ydl.download([info.get('webpage_url', download_url)])
                
                # Get the filename
                filename = ydl.prepare_filename(info)
                
                # Handle audio files
                base_filename = os.path.splitext(filename)[0]
                file_path = f"{base_filename}.mp3"
                
                # Verify file exists and has content
                if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
                    raise Exception("Downloaded file is empty or does not exist")
                
                # Move the file to the downloads directory with a better name
                if track_info:
                    # Use track info for filename if available
                    artist = track_info['artists'][0]['name']
                    title = track_info['name']
                    safe_artist = re.sub(r'[^\w\s-]', '', artist)
                    safe_title = re.sub(r'[^\w\s-]', '', title)
                    target_file = self.config.downloads_dir / f"spotify_{safe_artist}_{safe_title}.mp3"
                else:
                    # Use the original filename
                    target_file = self.config.downloads_dir / f"spotify_{spotify_id}.mp3"
                
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
                
                return str(target_file)
                
        except Exception as e:
            logger.error(f"Unexpected error during Spotify download: {e}")
            raise 