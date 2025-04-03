import os
import logging
import re
import asyncio
import yt_dlp
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from pathlib import Path

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
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    async def download(self, url):
        """Download content from Spotify"""
        spotify_id = self._extract_spotify_id(url)
        if not spotify_id:
            raise ValueError("Invalid Spotify URL format")
        
        try:
            # Create a temporary directory for this download
            temp_dir = self.config.downloads_dir / f"spotify_{spotify_id}"
            os.makedirs(temp_dir, exist_ok=True)
            
            # Get track information if possible
            track_info = None
            if self.spotify_client:
                try:
                    track_info = self.spotify_client.track(spotify_id)
                    logger.info(f"Retrieved track info: {track_info['name']} by {track_info['artists'][0]['name']}")
                except Exception as e:
                    logger.warning(f"Failed to get track info from Spotify API: {e}")
            
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
            }
            
            # Download using yt-dlp
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # First extract info to validate URL
                info = ydl.extract_info(url, download=False)
                
                # Check if we got valid info
                if not info:
                    raise Exception("Could not extract information from URL")
                
                # Now download the audio
                ydl.download([url])
                
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