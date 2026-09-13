from dotenv import load_dotenv
import os
from pathlib import Path

DEFAULT_MAX_FILE_SIZE_MB = 300
DEFAULT_GROUP_MAX_FILE_SIZE_MB = 300
DEFAULT_VIDEO_MAX_RESOLUTION = 480

class Config:
    def __init__(self):
        load_dotenv()
        api_id = os.getenv('API_ID')
        if not api_id:
            raise ValueError("API_ID not found in environment variables")
        self.API_ID = int(api_id)
        self.API_HASH = os.getenv('API_HASH')
        self.BOT_TOKEN = os.getenv('BOT_TOKEN')
        self.DOWNLOAD_TIMEOUT = int(os.getenv('DOWNLOAD_TIMEOUT', 600))
        self.MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE', DEFAULT_MAX_FILE_SIZE_MB * 1024 * 1024))
        # Group file size limit (default 300MB)
        self.GROUP_MAX_FILE_SIZE = int(os.getenv('GROUP_MAX_FILE_SIZE', DEFAULT_GROUP_MAX_FILE_SIZE_MB * 1024 * 1024))

        # Short side (in pixels) videos are capped at, e.g. 480 means 480x854 for
        # vertical clips. Lower values mean smaller uploads.
        self.VIDEO_MAX_RESOLUTION = int(os.getenv('VIDEO_MAX_RESOLUTION', DEFAULT_VIDEO_MAX_RESOLUTION))
        if self.VIDEO_MAX_RESOLUTION <= 0:
            raise ValueError("VIDEO_MAX_RESOLUTION must be a positive number of pixels")

        # Cookie file path (optional)
        self.COOKIE_FILE_PATH = os.getenv('COOKIE_FILE_PATH', None)
        
        if not all([self.API_ID, self.API_HASH, self.BOT_TOKEN]):
            raise ValueError("API_ID, API_HASH or BOT_TOKEN not found in environment variables")
        
        self.downloads_dir = Path(__file__).parent.parent / "downloads"
        os.makedirs(self.downloads_dir, exist_ok=True)
        self.sessions_dir = Path(__file__).parent.parent / "sessions"
        os.makedirs(self.sessions_dir, exist_ok=True)
