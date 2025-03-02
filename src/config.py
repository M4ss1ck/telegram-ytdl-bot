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
        
        if not all([self.API_ID, self.API_HASH, self.BOT_TOKEN]):
            raise ValueError("API_ID, API_HASH or BOT_TOKEN not found in environment variables")
        
        self.downloads_dir = Path(__file__).parent.parent / "downloads"
        os.makedirs(self.downloads_dir, exist_ok=True)