from dotenv import load_dotenv
import os
from pathlib import Path

class Config:
    def __init__(self):
        load_dotenv()
        self.API_ID = int(os.getenv('API_ID'))  # Convert to integer
        self.API_HASH = os.getenv('API_HASH')
        self.BOT_TOKEN = os.getenv('BOT_TOKEN')
        self.DOWNLOAD_TIMEOUT = int(os.getenv('DOWNLOAD_TIMEOUT', 600))
        self.MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE', 1.9 * 1024 * 1024 * 1024))
        self.LAST_PROGRESS = 0.0
        self.PROXY_URL = os.getenv('PROXY_URL', None)
        
        # YouTube-specific API configurations
        self.YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY', None)
        self.YOUTUBE_API_URL = os.getenv('YOUTUBE_API_URL', None)
        self.RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY', None)
        
        # Browser downloader settings
        self.BROWSER_ENABLED = os.getenv('BROWSER_ENABLED', 'false').lower() == 'true'
        self.BROWSER_TYPE = os.getenv('BROWSER_TYPE', 'firefox')  # 'firefox' or 'chrome'
        
        # Specify YouTube download strategy preference
        # Options: 'api_first', 'proxy_first', 'alt_frontends_first', 'browser_first'
        self.YOUTUBE_STRATEGY = os.getenv('YOUTUBE_STRATEGY', 'api_first')
        
        if not all([self.API_ID, self.API_HASH, self.BOT_TOKEN]):
            raise ValueError("API_ID, API_HASH or BOT_TOKEN not found in environment variables")
        
        if self.PROXY_URL and not (self.PROXY_URL.startswith('http://') or self.PROXY_URL.startswith('https://') or self.PROXY_URL.startswith('socks')):
            raise ValueError("Invalid PROXY_URL format. Should start with http://, https:// or socks")
        
        self.downloads_dir = Path(__file__).parent.parent / "downloads"
        os.makedirs(self.downloads_dir, exist_ok=True)