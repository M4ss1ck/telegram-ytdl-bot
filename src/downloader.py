import yt_dlp
import os
import asyncio

class Downloader:
    def __init__(self, config):
        self.config = config
        
    async def download(self, url):
        ydl_opts = {
            'outtmpl': str(self.config.downloads_dir / '%(title)s.%(ext)s'),
            'format': 'best',
        }
        
        try:
            return await asyncio.to_thread(self._download_video, url, ydl_opts)
        except Exception as e:
            raise Exception(f"Download failed: {str(e)}")
            
    def _download_video(self, url, ydl_opts):
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return os.path.join(self.config.downloads_dir, ydl.prepare_filename(info))