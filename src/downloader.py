import yt_dlp
import os
import asyncio
import re
import logging

logger = logging.getLogger(__name__)

class Downloader:
    def __init__(self, config):
        self.config = config
        
    async def download(self, url):
        # Determine if this is an Instagram URL
        is_instagram = 'instagram.com' in url or 'instagr.am' in url
        
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
        
        # Add Instagram-specific options
        if is_instagram:
            ydl_opts.update({
                'cookiesfrombrowser': ('chrome',),  # Use cookies from Chrome browser
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
                file_path = os.path.join(self.config.downloads_dir, filename)
                
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