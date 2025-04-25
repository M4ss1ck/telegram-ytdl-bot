import os
import json
import asyncio
import aiohttp
import logging
import time
import urllib.parse
from pathlib import Path

logger = logging.getLogger(__name__)

class YouTubeAPIDownloader:
    """YouTube downloader that uses a third-party API service instead of direct YouTube access"""
    
    def __init__(self, config):
        self.config = config
        self.api_key = config.YOUTUBE_API_KEY
        self.base_url = config.YOUTUBE_API_URL or 'https://rapidapi.com/ytjar/api/youtube-mp36'
        self.rapidapi_key = config.RAPIDAPI_KEY
        self.download_dir = config.downloads_dir
        
        # Validate keys on initialization and log their status
        self.has_rapidapi = self._validate_rapidapi_key()
        self.has_custom_api = self._validate_custom_api_key()
        
        if self.has_rapidapi:
            logger.info("RapidAPI key configured for YouTube downloads")
        if self.has_custom_api:
            logger.info(f"Custom YouTube API configured at {self.base_url}")
        if not (self.has_rapidapi or self.has_custom_api):
            logger.warning("No API keys configured for YouTube API Downloader. Will use public APIs only.")
        
    def _validate_rapidapi_key(self):
        """Validate that a RapidAPI key is properly configured"""
        return bool(self.rapidapi_key and len(self.rapidapi_key) > 10)
    
    def _validate_custom_api_key(self):
        """Validate that a custom API key and URL are properly configured"""
        if not self.api_key:
            return False
        
        # Ensure the URL is a valid API endpoint URL
        valid_url = (self.base_url and 
                    (self.base_url.startswith('http://') or self.base_url.startswith('https://')) and 
                    len(self.base_url) > 10)
        
        return bool(valid_url and self.api_key)
        
    async def download(self, url):
        """Download video from YouTube URL using a third-party API service"""
        logger.info(f"Attempting YouTube download via API for: {url}")
        
        # Extract video ID
        video_id = self._extract_video_id(url)
        if not video_id:
            raise ValueError(f"Could not extract video ID from URL: {url}")
        
        # Check which API method to use based on available credentials
        methods = []
        last_error = None
        
        # Build a list of methods to try, in order
        if self.has_rapidapi:
            methods.append(("RapidAPI", self._download_via_rapidapi))
        if self.has_custom_api:
            methods.append(("Custom API", self._download_with_custom_api))
        
        # Always include public APIs as a fallback
        methods.append(("Public APIs", lambda vid_id: self._download_via_public_api(url, vid_id)))
        
        # Try each method in order
        for method_name, method_func in methods:
            try:
                logger.info(f"Attempting to download with {method_name}: {url}")
                return await method_func(video_id)
            except Exception as e:
                last_error = e
                logger.warning(f"{method_name} download failed: {str(e)}")
                continue
        
        # If all methods fail, raise the last error
        if last_error:
            raise last_error
        else:
            raise Exception("All API methods failed for unknown reasons")
    
    def _extract_video_id(self, url):
        """Extract YouTube video ID from URL"""
        import re
        patterns = [
            r'(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com\/shorts\/([a-zA-Z0-9_-]{11})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    async def _download_via_rapidapi(self, video_id):
        """Download using RapidAPI YouTube services"""
        if not self.has_rapidapi:
            raise Exception("RapidAPI key is not configured properly")
            
        # Define the endpoint details
        info_url = "https://youtube-mp36.p.rapidapi.com/dl"
        host = "youtube-mp36.p.rapidapi.com"
        params = {"id": video_id}
        headers = {
            "X-RapidAPI-Key": self.rapidapi_key,
            "X-RapidAPI-Host": host
        }
        
        try:
            logger.info(f"Calling RapidAPI endpoint: {info_url} with host {host}")
            async with aiohttp.ClientSession() as session:
                # First, get the download link
                async with session.get(info_url, headers=headers, params=params, timeout=30) as response:
                    logger.info(f"RapidAPI response status: {response.status}")
                    response_text = await response.text() # Read response text for logging
                    
                    if response.status != 200:
                        logger.error(f"RapidAPI Error Response: {response_text}")
                        raise Exception(f"API Error: {response.status} - {response_text}")
                    
                    try:
                        data = json.loads(response_text)
                    except json.JSONDecodeError:
                        logger.error(f"RapidAPI returned non-JSON response: {response_text}")
                        raise Exception("API returned invalid JSON")
                    
                    logger.debug(f"RapidAPI response data: {data}")
                    
                    if "link" not in data or not data["link"]:
                        logger.error(f"No download link found in RapidAPI response: {data}")
                        raise Exception(f"No download link in API response: {data}")
                    
                    download_url = data["link"]
                    title = data.get("title", f"youtube_{video_id}")
                    
                    logger.info(f"Successfully obtained download link from RapidAPI: {download_url}")
                    
                    # Prefix the title to indicate which method was used
                    title = f"API_{title}"
                    
                    # Download the file
                    return await self._download_file(download_url, title, "mp3")
        
        except asyncio.TimeoutError:
            logger.error(f"RapidAPI call timed out for {info_url}")
            raise Exception("RapidAPI call timed out")
        except aiohttp.ClientError as e:
            logger.error(f"HTTP client error during RapidAPI call: {str(e)}")
            raise Exception(f"HTTP error during API call: {str(e)}")
        except Exception as e:
            logger.error(f"Error using RapidAPI YouTube service ({host}): {str(e)}")
            # Re-raise the original exception to preserve context
            raise
    
    async def _download_with_custom_api(self, video_id):
        """Download using a custom YouTube API (if you have your own service)"""
        if not self.has_custom_api:
            raise Exception("Custom API key or URL is not configured properly")
            
        api_url = f"{self.base_url}/api/v1/download?videoId={video_id}&apiKey={self.api_key}"
        
        try:
            logger.info(f"Calling Custom API endpoint: {api_url}")
            async with aiohttp.ClientSession() as session:
                # Get download information
                async with session.get(api_url, timeout=30) as response:
                    logger.info(f"Custom API response status: {response.status}")
                    response_text = await response.text() # Read response text for logging

                    if response.status != 200:
                        logger.error(f"Custom API Error Response: {response_text}")
                        raise Exception(f"API Error: {response.status} - {response_text}")
                    
                    try:
                        data = json.loads(response_text)
                    except json.JSONDecodeError:
                        logger.error(f"Custom API returned non-JSON response: {response_text}")
                        raise Exception("API returned invalid JSON")

                    logger.debug(f"Custom API response data: {data}")

                    if "downloadUrl" not in data or not data["downloadUrl"]:
                        logger.error(f"No download URL found in Custom API response: {data}")
                        raise Exception(f"No download URL in API response: {data}")
                    
                    download_url = data["downloadUrl"]
                    title = data.get("title", f"youtube_{video_id}")
                    format_ext = data.get("format", "mp4")
                    
                    logger.info(f"Successfully obtained download link from Custom API: {download_url}")

                    # Prefix the title to indicate which method was used
                    title = f"API_{title}"
                    
                    # Download the file
                    return await self._download_file(download_url, title, format_ext)
                    
        except asyncio.TimeoutError:
            logger.error(f"Custom API call timed out for {api_url}")
            raise Exception("Custom API call timed out")
        except aiohttp.ClientError as e:
            logger.error(f"HTTP client error during Custom API call: {str(e)}")
            raise Exception(f"HTTP error during API call: {str(e)}")
        except Exception as e:
            logger.error(f"Error using custom YouTube API: {str(e)}")
            # Re-raise the original exception
            raise
    
    async def _download_via_public_api(self, original_url, video_id):
        """Try multiple public YouTube download APIs that don't require API keys"""
        # List of public APIs to try
        public_apis = [
            {
                "name": "y2mate-style",
                "function": self._try_y2mate_style
            },
            {
                "name": "save-from-style",
                "function": self._try_savefrom_style
            },
            {
                "name": "ytstream",
                "function": self._try_ytstream
            },
            {
                "name": "ytdl-api",
                "function": self._try_ytdl_api
            },
            {
                "name": "ytdownloader",
                "function": self._try_ytdownloader
            }
        ]
        
        last_error = None
        for api in public_apis:
            try:
                logger.info(f"Trying public API: {api['name']}")
                return await api["function"](original_url, video_id)
            except Exception as e:
                last_error = e
                logger.warning(f"Failed with {api['name']}: {str(e)}")
                continue
        
        # If all APIs fail, raise the last error
        if last_error:
            raise last_error
        else:
            raise Exception("All public APIs failed")
    
    async def _try_y2mate_style(self, original_url, video_id):
        """Try downloading using Y2Mate-style APIs"""
        try:
            # These APIs typically work in two steps: get the links, then download
            api_url = f"https://api.onlinevideoconverter.pro/api/convert"
            
            payload = {
                "url": original_url
            }
            
            headers = {
                "Content-Type": "application/json",
                "Origin": "https://onlinevideoconverter.pro",
                "Referer": "https://onlinevideoconverter.pro/"
            }
            
            async with aiohttp.ClientSession() as session:
                # Step 1: Get available formats
                async with session.post(api_url, json=payload, headers=headers) as response:
                    if response.status != 200:
                        raise Exception(f"API Error: {response.status}")
                    
                    data = await response.json()
                    
                    if not data.get("url") or not data.get("formats"):
                        raise Exception("Invalid API response format")
                    
                    # Get the best quality MP4 format
                    mp4_formats = [f for f in data["formats"] if f.get("ext") == "mp4"]
                    
                    if not mp4_formats:
                        raise Exception("No MP4 formats available")
                    
                    # Sort by height (quality) and take the highest
                    best_format = sorted(mp4_formats, key=lambda x: x.get("height", 0), reverse=True)[0]
                    
                    title = data.get("title", f"youtube_{video_id}")
                    download_url = best_format.get("url")
                    
                    if not download_url:
                        raise Exception("No download URL found")
                    
                    # Use API prefix in title to indicate which method was used
                    title = f"API_{title}"
                    
                    # Step 2: Download the file
                    return await self._download_file(download_url, title, "mp4")
                    
        except Exception as e:
            logger.error(f"Y2Mate-style API error: {str(e)}")
            raise
    
    async def _try_savefrom_style(self, original_url, video_id):
        """Try downloading using SaveFrom-style APIs"""
        try:
            encoded_url = urllib.parse.quote(original_url)
            api_url = f"https://sfrom.net/api/convert?url={encoded_url}"
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Referer": "https://sfrom.net/",
                "Origin": "https://sfrom.net"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, headers=headers) as response:
                    if response.status != 200:
                        raise Exception(f"API Error: {response.status}")
                    
                    data = await response.json()
                    
                    if "url" not in data or "title" not in data:
                        raise Exception(f"Invalid API response: {data}")
                    
                    # Get highest quality MP4
                    mp4_urls = [url for url in data.get("url", []) if url.get("type") == "mp4"]
                    
                    if not mp4_urls:
                        raise Exception("No MP4 URLs found")
                    
                    # Sort by quality and get the best one
                    best_quality = sorted(mp4_urls, key=lambda x: x.get("quality", 0), reverse=True)[0]
                    
                    title = data.get("title", f"youtube_{video_id}")
                    download_url = best_quality.get("url")
                    
                    if not download_url:
                        raise Exception("No download URL found")
                    
                    # Use API prefix in title to indicate which method was used
                    title = f"API_{title}"
                    
                    # Download the file
                    return await self._download_file(download_url, title, "mp4")
        
        except Exception as e:
            logger.error(f"SaveFrom-style API error: {str(e)}")
            raise
    
    async def _try_ytstream(self, original_url, video_id):
        """Try using another public YouTube stream extractor API"""
        try:
            api_url = f"https://yt-stream.onrender.com/api/streams/{video_id}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as response:
                    if response.status != 200:
                        raise Exception(f"API Error: {response.status}")
                    
                    data = await response.json()
                    
                    if "formats" not in data:
                        raise Exception(f"Invalid API response: {data}")
                    
                    # Find MP4 with audio
                    mp4_formats = [f for f in data["formats"] if f.get("mimeType", "").startswith("video/mp4") and f.get("audioQuality")]
                    
                    if not mp4_formats:
                        raise Exception("No MP4 formats with audio found")
                    
                    # Sort by quality
                    best_format = sorted(mp4_formats, key=lambda x: int(x.get("qualityLabel", "0").replace("p", "")), reverse=True)[0]
                    
                    title = data.get("title", f"youtube_{video_id}")
                    download_url = best_format.get("url")
                    
                    if not download_url:
                        raise Exception("No download URL found")
                    
                    # Use API prefix in title to indicate which method was used
                    title = f"API_{title}"
                    
                    # Download the file
                    return await self._download_file(download_url, title, "mp4")
        
        except Exception as e:
            logger.error(f"YT Stream API error: {str(e)}")
            raise
            
    async def _try_ytdl_api(self, original_url, video_id):
        """Try using the ytdl-api.dev service API"""
        try:
            api_url = f"https://ytdl-api.dev/api/download?url={original_url}&format=best"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, timeout=30) as response:
                    if response.status != 200:
                        raise Exception(f"API Error: {response.status}")
                    
                    data = await response.json()
                    
                    if "url" not in data:
                        raise Exception(f"Invalid API response: {data}")
                    
                    download_url = data["url"]
                    title = data.get("title", f"youtube_{video_id}")
                    
                    # Use API prefix in title to indicate which method was used
                    title = f"API_{title}"
                    
                    # Download the file
                    return await self._download_file(download_url, title, "mp4")
        
        except Exception as e:
            logger.error(f"YTDL API error: {str(e)}")
            raise
    
    async def _try_ytdownloader(self, original_url, video_id):
        """Try using YTDownloader API service"""
        try:
            api_url = f"https://ytdownloader.io/api/json/mp4/{video_id}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, timeout=30) as response:
                    if response.status != 200:
                        raise Exception(f"API Error: {response.status}")
                    
                    data = await response.json()
                    
                    if not data.get("success") or "download" not in data:
                        raise Exception(f"Invalid API response: {data}")
                    
                    download_url = data["download"]
                    title = data.get("title", f"youtube_{video_id}")
                    
                    # Use API prefix in title to indicate which method was used
                    title = f"API_{title}"
                    
                    # Download the file
                    return await self._download_file(download_url, title, "mp4")
        
        except Exception as e:
            logger.error(f"YTDownloader API error: {str(e)}")
            raise
    
    async def _download_file(self, url, title, format_ext):
        """Download a file from URL and save it locally"""
        logger.info(f"Downloading file from URL: {url}")
        
        # Sanitize filename
        safe_title = "".join([c for c in title if c.isalpha() or c.isdigit() or c in ' -_.']).strip()
        if not safe_title:
            safe_title = f"youtube_video_{int(time.time())}"
        
        file_path = os.path.join(self.download_dir, f"{safe_title}.{format_ext}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=120) as response:
                    if response.status != 200:
                        raise Exception(f"Download failed with status {response.status}")
                    
                    # Download file in chunks
                    with open(file_path, 'wb') as f:
                        while True:
                            chunk = await response.content.read(1024 * 1024)  # 1MB chunks
                            if not chunk:
                                break
                            f.write(chunk)
            
            # Check file exists and has content
            if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
                raise Exception("Downloaded file is empty or does not exist")
            
            return file_path
            
        except Exception as e:
            logger.error(f"Error downloading file: {str(e)}")
            # Clean up any partially downloaded file
            if os.path.exists(file_path):
                os.remove(file_path)
            raise 