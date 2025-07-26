from pyrogram import Client, filters
import os
import asyncio
import re
import logging
from urllib.parse import urlparse

from src.config import Config
from src.downloader import Downloader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Bot:
    def __init__(self):
        self.config = Config()
        self.downloader = Downloader(self.config)
        self.app = Client(
            "ytdl_bot",
            api_id=self.config.API_ID,
            api_hash=self.config.API_HASH,
            bot_token=self.config.BOT_TOKEN
        )
        self.active_uploads = {}  # Track active uploads for progress throttling
        self.last_progress = self.config.LAST_PROGRESS

        # Register handlers
        self.register_handlers()

    def register_handlers(self):
        @self.app.on_message(filters.command("start"))
        async def start(client, message):
            logger.info(f"Received /start command from user {message.from_user.id}")
            await message.reply_text(
                "Welcome! Send me a URL and I'll download it for you using yt-dlp."
            )

        @self.app.on_message(filters.command("ping"))
        async def ping(client, message):
            logger.info(f"Received /ping command from user {message.from_user.id}")
            await message.reply_text("Pong!")
            
        @self.app.on_message(filters.command("help"))
        async def help_cmd(client, message):
            logger.info(f"Received /help command from user {message.from_user.id}")
            is_group = message.chat.type in ["group", "supergroup"]
            group_limit_mb = self.config.GROUP_MAX_FILE_SIZE / (1024 * 1024)
            
            help_text = (
                "📥 **YouTube Downloader Bot** 📥\n\n"
                "Send me a URL from YouTube, Instagram, Spotify, or other supported sites, and I'll download it for you.\n\n"
                "**Commands:**\n"
                "/start - Start the bot\n"
                "/ping - Check if bot is running\n"
                "/help - Show this help message\n\n"
                "**Supported Platforms:**\n"
                "• YouTube (Videos, Shorts, Playlists)\n"
                "• Instagram (Posts, Reels, Stories)\n"
                "• Spotify (Tracks, Albums)\n"
                "• Many other video platforms\n\n"
            )
            
            if is_group:
                help_text += (
                    f"**📊 Group Limits:**\n"
                    f"• File size limit: {group_limit_mb:.0f}MB\n"
                    f"• For larger files, use the bot in private chat\n\n"
                )
            
            help_text += "**Note:** All downloads are processed using yt-dlp for reliable and consistent quality."
            
            await message.reply_text(help_text)
            
        @self.app.on_message(filters.text & ~filters.create(
            lambda _, __, m: m.text.startswith('/')
        ))
        async def handle_url(client, message):
            logger.info(f"Received message from user {message.from_user.id}: {message.text[:50]}...")
            urls = self.extract_urls(message.text)
            if not urls:
                return

            url = urls[0]
            is_instagram = 'instagram.com' in url or 'instagr.am' in url
            is_spotify = 'spotify.com' in url or 'spotify:' in url
            is_youtube = self.is_youtube_url(url)
            is_group = message.chat.type in ["group", "supergroup"]
            
            # Check file size for groups (only for standard downloads that support size checking)
            if is_group and not is_instagram and not is_spotify:
                try:
                    status_message = await message.reply_text("Checking file size...")
                    file_info = await self.downloader.get_file_info(url)
                    
                    if file_info['file_size'] > self.config.GROUP_MAX_FILE_SIZE:
                        size_mb = file_info['file_size'] / (1024 * 1024)
                        limit_mb = self.config.GROUP_MAX_FILE_SIZE / (1024 * 1024)
                        await status_message.edit_text(
                            f"❌ File too large for group chats!\n\n"
                            f"📁 **{file_info['title']}**\n"
                            f"📊 Size: {size_mb:.1f}MB\n"
                            f"🚫 Group limit: {limit_mb:.0f}MB\n\n"
                            f"💡 Try this link in a private chat with the bot for larger files."
                        )
                        return
                    else:
                        await status_message.delete()
                except Exception as e:
                    logger.warning(f"Failed to check file size for group: {e}")
                    # Continue with download if size check fails
                    try:
                        await status_message.delete()
                    except:
                        pass
            
            # Provide specific status message based on URL type
            if is_instagram:
                status_message = await message.reply_text(
                    "Processing Instagram content with Instaloader... This may take a moment."
                )
            elif is_spotify:
                status_message = await message.reply_text(
                    "Processing Spotify content... Converting to MP3."
                )
            elif is_youtube:
                status_message = await message.reply_text(
                    "Processing YouTube content... Downloading with yt-dlp."
                )
            else:
                status_message = await message.reply_text("Downloading...")
            
            file_path = None
            downloader_used = "yt-dlp"

            try:
                # Download with timeout
                file_path = await asyncio.wait_for(
                    self.downloader.download(url),
                    timeout=self.config.DOWNLOAD_TIMEOUT
                )
                
                # Check which downloader was used based on the file path
                if is_instagram and "instagram_" in file_path:
                    downloader_used = "Instaloader"
                    await status_message.edit_text("Instagram content downloaded successfully with Instaloader. Preparing to upload...")
                elif is_instagram:
                    downloader_used = "yt-dlp (fallback)"
                    await status_message.edit_text("Instagram content downloaded with yt-dlp fallback. Preparing to upload...")
                elif is_spotify and any(keyword in file_path for keyword in ["spotify_", "_"]):
                    downloader_used = "Spotify Downloader"
                    await status_message.edit_text("Spotify content downloaded successfully. Preparing to upload...")
                elif is_spotify:
                    downloader_used = "yt-dlp (fallback)"
                    await status_message.edit_text("Spotify content downloaded with yt-dlp fallback. Preparing to upload...")
                else:
                    await status_message.edit_text("Download complete. Preparing to upload...")

                # Validate downloaded file
                if not file_path or not os.path.exists(file_path):
                    raise ValueError("Download failed - no file created")

                file_size = os.path.getsize(file_path)
                if file_size > self.config.MAX_FILE_SIZE:
                    raise ValueError(f"File too large ({file_size/1024/1024:.1f}MB > "
                                    f"{self.config.MAX_FILE_SIZE/1024/1024}MB")

                await status_message.edit_text("Upload in progress...")
                
                # Upload with progress tracking
                await self.upload_file(message, file_path, status_message)

                # Only delete if upload succeeded
                os.remove(file_path)

            except asyncio.TimeoutError:
                error_msg = "Download timed out."
                if is_instagram:
                    error_msg += " Instagram may be rate-limiting requests."
                elif is_spotify:
                    error_msg += " Spotify conversion may be taking longer than expected."
                elif is_youtube:
                    error_msg += " YouTube download took too long. Try again later."
                logger.error(error_msg)
                await self.send_error(message, error_msg)
            except Exception as e:
                error_msg = str(e)
                
                # Provide more helpful error messages for specific platforms
                if is_instagram and "login_required" in error_msg.lower():
                    error_msg = "This Instagram content requires login. Try using a different URL or content that's publicly accessible."
                elif is_instagram and "private" in error_msg.lower():
                    error_msg = "This Instagram content is private. Only public content can be downloaded."
                elif is_instagram and "not available" in error_msg.lower():
                    error_msg = "This Instagram content is no longer available or has been removed."
                elif is_spotify and "premium" in error_msg.lower():
                    error_msg = "This Spotify content requires a premium account. Only publicly available tracks can be downloaded."
                elif is_spotify and "region" in error_msg.lower():
                    error_msg = "This Spotify content is not available in your region."
                elif is_youtube and ("block" in error_msg.lower() or "unavailable" in error_msg.lower()):
                    error_msg = "YouTube content couldn't be accessed. The video might be restricted or unavailable."
                
                logger.error(f"Error processing URL {url}: {error_msg}", exc_info=True)
                await self.send_error(message, f"Error: {error_msg}")
            finally:
                # Cleanup files only if they exist
                if file_path and os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        logger.error(f"Error deleting file: {e}")
                await status_message.delete()

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
                
    def extract_urls(self, text):
        """Improved URL extraction with basic validation"""
        url_pattern = r'https?://(?:www\.)?[^\s<>"]+|www\.[^\s<>"]+'
        matches = re.findall(url_pattern, text)
        valid_urls = []
        
        for url in matches:
            # Add http:// prefix if missing
            if not url.startswith(('http://', 'https://')):
                url = f'http://{url}'
            # Basic URL validation
            try:
                result = urlparse(url)
                if all([result.scheme, result.netloc]):
                    valid_urls.append(url)
            except:
                continue
        
        return valid_urls

    async def upload_file(self, message, file_path, status_message):
        """Handle file upload with progress throttling"""
        try:
            # Use list for mutable start time
            progress_args = (status_message, [asyncio.get_event_loop().time()])
            
            if file_path.endswith(('.mp4', '.mkv', '.webm')):
                await message.reply_video(
                    video=file_path,
                    progress=self._upload_progress,
                    progress_args=progress_args,
                    supports_streaming=True
                )
            else:
                await message.reply_document(
                    document=file_path,
                    progress=self._upload_progress,
                    progress_args=progress_args
                )
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            raise

    async def _upload_progress(self, current, total, status_message, start_time):
        """Throttled progress updates"""
        try:
            now = asyncio.get_event_loop().time()
            elapsed = now - start_time[0]
            
            # Calculate current progress ratio
            current_progress = current / total
            
            # Update at most every 2 seconds or when 5% progress is made
            if elapsed < 2 and (current_progress - self.last_progress) < 0.05:
                return
            
            # Update tracking variables
            self.last_progress = current_progress
            start_time[0] = now
            
            percent = current_progress * 100
            await status_message.edit_text(
                f"Uploading: {percent:.1f}%\n"
                f"Size: {current//1024}KB/{total//1024}KB"
            )
        except Exception as e:
            logger.warning(f"Progress update failed: {e}")

    async def send_error(self, message, error_text):
        """Send error messages only in private chats"""
        if message.chat.type == "private":
            try:
                await message.reply_text(
                    error_text,
                    disable_web_page_preview=True,
                    reply_to_message_id=message.id
                )
            except Exception as e:
                logger.error(f"Failed to send error message in private chat: {e}")
        else:
            logger.info(f"Error occurred in {message.chat.type} chat")

    def run(self):
        logger.info("Bot is starting...")
        self.app.run()

if __name__ == "__main__":
    bot = Bot()
    bot.run()