from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pyrogram.types import InputMediaPhoto, InputMediaVideo
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
        self.download_semaphore = asyncio.Semaphore(1)
        self.queue_lock = asyncio.Lock()
        self.queue_waiting = 0
        self.max_queue_size = 50
        self.app = Client(
            "ytdl_bot",
            workdir=str(self.config.sessions_dir),
            api_id=self.config.API_ID,
            api_hash=self.config.API_HASH,
            bot_token=self.config.BOT_TOKEN
        )
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
            max_limit_mb = self.config.MAX_FILE_SIZE / (1024 * 1024)
            effective_group_limit = min(self.config.GROUP_MAX_FILE_SIZE, self.config.MAX_FILE_SIZE)
            effective_group_limit_mb = effective_group_limit / (1024 * 1024)
            
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
                    f"**📊 Limits:**\n"
                    f"• File size limit: {effective_group_limit_mb:.0f}MB\n"
                    f"• For larger files, use the bot in private chat\n\n"
                )
            else:
                help_text += (
                    f"**📊 Limits:**\n"
                    f"• File size limit: {max_limit_mb:.0f}MB\n\n"
                )
            
            help_text += "**Note:** All downloads are processed using yt-dlp for reliable and consistent quality."
            
            await message.reply_text(help_text)
            
        @self.app.on_message(filters.text & ~filters.create(
            lambda _, __, m: m.text.startswith('/')
        ))
        async def handle_url(client, message):
            text_preview = str(message.text or "")[:50]
            logger.info(f"Received message from user {message.from_user.id}: {text_preview}...")
            urls = self.extract_urls(message.text)
            if not urls:
                return

            url = urls[0]
            is_instagram = 'instagram.com' in url or 'instagr.am' in url
            is_spotify = 'spotify.com' in url or 'spotify:' in url
            is_youtube = self.downloader.is_youtube_url(url)
            is_group = message.chat.type in ["group", "supergroup"]
            await self._process_with_semaphore(
                message=message,
                url=url,
                is_instagram=is_instagram,
                is_spotify=is_spotify,
                is_youtube=is_youtube,
                is_group=is_group,
            )

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

    async def _process_with_semaphore(self, message, url, is_instagram, is_spotify, is_youtube, is_group):
        queued_message = None
        acquired = False

        try:
            if not self.download_semaphore.locked():
                await self.download_semaphore.acquire()
                acquired = True
            else:
                async with self.queue_lock:
                    if self.queue_waiting >= self.max_queue_size:
                        await message.reply_text(
                            "Too many requests are queued right now. Please try again later."
                        )
                        return
                    self.queue_waiting += 1
                    position = self.queue_waiting

                queued_message = await message.reply_text(
                    f"Queued (position {position}). I'll start processing as soon as possible."
                )

                try:
                    await self.download_semaphore.acquire()
                    acquired = True
                except BaseException:
                    async with self.queue_lock:
                        if self.queue_waiting > 0:
                            self.queue_waiting -= 1
                    raise

                async with self.queue_lock:
                    if self.queue_waiting > 0:
                        self.queue_waiting -= 1

            status_message = queued_message
            queued_message = None
            await self._process_request(
                message=message,
                url=url,
                is_instagram=is_instagram,
                is_spotify=is_spotify,
                is_youtube=is_youtube,
                is_group=is_group,
                status_message=status_message,
            )
        finally:
            if acquired:
                self.download_semaphore.release()
            if queued_message:
                try:
                    await queued_message.delete()
                except Exception as e:
                    logger.debug(f"Failed to delete queue message: {e}")

    async def _process_request(
        self, message, url, is_instagram, is_spotify, is_youtube, is_group,
        status_message=None,
    ):
        effective_max_size = self.config.MAX_FILE_SIZE
        if is_group:
            effective_max_size = min(self.config.GROUP_MAX_FILE_SIZE, self.config.MAX_FILE_SIZE)
        status_deleted = False
        keep_status = False

        # Pre-download size check (when yt-dlp estimates are available)
        if not is_instagram and not is_spotify:
            try:
                if status_message:
                    await status_message.edit_text("🔍 Checking file size before download...")
                else:
                    status_message = await message.reply_text("🔍 Checking file size before download...")
                file_info = await self.downloader.get_file_info(url)

                # Only skip download if we have a size estimate and it's significantly over the limit
                # Add 10% buffer to account for yt-dlp estimate inaccuracies
                estimated_size = file_info.get('file_size', 0)
                size_threshold = effective_max_size * 1.1  # 10% buffer

                if estimated_size > 0 and estimated_size > size_threshold:
                    size_mb = estimated_size / (1024 * 1024)
                    limit_mb = effective_max_size / (1024 * 1024)

                    if is_group:
                        await status_message.delete()
                        status_deleted = True
                    else:
                        await status_message.edit_text(
                            f"File too large ({size_mb:.1f}MB > {limit_mb:.0f}MB limit)."
                        )
                        keep_status = True

                    logger.info(f"Pre-download check: File too large. "
                               f"Estimated: {size_mb:.1f}MB > {limit_mb:.0f}MB limit")
                    return
                else:
                    if estimated_size > 0:
                        logger.info(f"Pre-download check passed. Estimated size: {estimated_size/1024/1024:.1f}MB")
                    else:
                        logger.info("Pre-download check: no size estimate available, proceeding with download")

            except Exception as e:
                logger.warning(f"Pre-download size check failed: {e}")
                # Continue with the same status and rely on the post-download check.

        # Provide specific status message based on URL type
        if is_instagram:
            status_text = "Processing Instagram content with Instaloader... This may take a moment."
        elif is_spotify:
            status_text = "Processing Spotify content... Converting to MP3."
        elif is_youtube:
            status_text = "Processing YouTube content... Downloading with yt-dlp."
        else:
            status_text = "Downloading..."

        if status_message:
            await status_message.edit_text(status_text)
        else:
            status_message = await message.reply_text(status_text)

        file_paths = []

        try:
            # Download with timeout
            result = await asyncio.wait_for(
                self.downloader.download(url),
                timeout=self.config.DOWNLOAD_TIMEOUT
            )

            # Normalize to list (gallery-dl returns list, yt-dlp returns str)
            if isinstance(result, list):
                file_paths = result
            else:
                file_paths = [result]

            # Validate downloaded files
            file_paths = [f for f in file_paths if f and os.path.exists(f)]
            if not file_paths:
                raise ValueError("Download failed - no files created")

            # Per-file size check: skip oversized files, delete them immediately
            oversized = []
            valid_paths = []
            first_oversized_size = 0
            for fp in file_paths:
                file_size = os.path.getsize(fp)
                if file_size > effective_max_size:
                    oversized.append(fp)
                    if first_oversized_size == 0:
                        first_oversized_size = file_size
                else:
                    valid_paths.append(fp)

            for fp in oversized:
                try:
                    os.remove(fp)
                except Exception as e:
                    logger.error(f"Error deleting oversized file: {e}")

            if not valid_paths:
                size_mb = first_oversized_size / (1024 * 1024)
                limit_mb = effective_max_size / (1024 * 1024)
                if is_group:
                    await status_message.delete()
                    status_deleted = True
                    logger.info(
                        f"Post-download check: All files too large for group. "
                        f"Largest: {size_mb:.1f}MB > {limit_mb:.0f}MB limit"
                    )
                    return
                raise ValueError(
                    f"File too large ({size_mb:.1f}MB > {limit_mb:.0f}MB limit)"
                )

            if oversized:
                logger.info(
                    f"Skipped {len(oversized)} oversized file(s) from gallery"
                )

            file_paths = valid_paths

            await status_message.edit_text("Download complete. Preparing to upload...")

            if len(file_paths) == 1:
                await status_message.edit_text("Upload in progress...")
                await self.upload_file(message, file_paths[0], status_message)
            else:
                await status_message.edit_text("Upload in progress...")
                await self._upload_album(message, file_paths, status_message)

            # Delete uploaded files
            for fp in file_paths:
                try:
                    os.remove(fp)
                except Exception as e:
                    logger.error(f"Error deleting uploaded file: {e}")

        except asyncio.TimeoutError:
            error_msg = "Download timed out."
            if is_instagram:
                error_msg += " Instagram may be rate-limiting requests."
            elif is_spotify:
                error_msg += " Spotify conversion may be taking longer than expected."
            elif is_youtube:
                error_msg += " YouTube download took too long. Try again later."
            logger.error(error_msg)
            keep_status = await self.send_error(message, error_msg, status_message)
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
            keep_status = await self.send_error(
                message, f"Error: {error_msg}", status_message
            )
        finally:
            # Cleanup files only if they exist
            for fp in file_paths:
                if os.path.exists(fp):
                    try:
                        os.remove(fp)
                    except Exception as e:
                        logger.error(f"Error deleting file: {e}")
            # Safely delete status message if it still exists
            if not status_deleted and not keep_status:
                try:
                    await status_message.delete()
                except Exception as e:
                    # Message may have already been deleted, which is fine
                    logger.debug(f"Status message already deleted or couldn't be deleted: {e}")

    async def upload_file(self, message, file_path, status_message):
        """Upload one file while updating the existing status message."""
        try:
            progress_args = (status_message, [asyncio.get_event_loop().time(), False])
            extension = os.path.splitext(file_path)[1].lower()
            if extension in ('.jpg', '.jpeg', '.png', '.webp'):
                await message.reply_photo(
                    photo=file_path,
                    progress=self._upload_progress,
                    progress_args=progress_args,
                )
            elif extension in ('.mp4', '.mkv', '.webm'):
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
                    progress_args=progress_args,
                )

        except FloodWait as e:
            logger.warning(f"FloodWait during upload, waiting {e.value} seconds before retry...")
            await asyncio.sleep(e.value)
            # Retry without progress updates to avoid further flood
            try:
                extension = os.path.splitext(file_path)[1].lower()
                if extension in ('.jpg', '.jpeg', '.png', '.webp'):
                    await message.reply_photo(photo=file_path)
                elif extension in ('.mp4', '.mkv', '.webm'):
                    await message.reply_video(video=file_path, supports_streaming=True)
                else:
                    await message.reply_document(document=file_path)
            except Exception as retry_e:
                logger.error(f"Upload retry failed: {retry_e}")
                raise
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            raise

    async def _upload_album(self, message, file_paths, status_message):
        photo_extensions = {'.jpg', '.jpeg', '.png', '.webp'}
        video_extensions = {'.mp4', '.mkv', '.webm'}

        media_items = []
        for fp in file_paths:
            ext = os.path.splitext(fp)[1].lower()
            if ext in photo_extensions:
                media_items.append(InputMediaPhoto(media=fp))
            elif ext in video_extensions:
                media_items.append(InputMediaVideo(media=fp))
            else:
                await self.upload_file(message, fp, status_message)

        if media_items:
            for i in range(0, len(media_items), 10):
                chunk = media_items[i:i + 10]
                try:
                    await message.reply_media_group(media=chunk)
                except FloodWait as e:
                    logger.warning(
                        f"FloodWait during album upload, waiting {e.value}s"
                    )
                    await asyncio.sleep(e.value)
                    await message.reply_media_group(media=chunk)

    async def _upload_progress(self, current, total, status_message, tracking_data):
        """Update upload progress at most once every five seconds."""
        try:
            if tracking_data[1]:
                return
            now = asyncio.get_event_loop().time()
            if now - tracking_data[0] < 5:
                return
            tracking_data[0] = now
            percent = (current / total) * 100
            await status_message.edit_text(
                f"Uploading: {percent:.0f}%  "
                f"({current//(1024*1024)}MB / {total//(1024*1024)}MB)"
            )
        except FloodWait:
            tracking_data[1] = True
            logger.warning("FloodWait during progress update, disabling further updates")
        except Exception as e:
            logger.warning(f"Progress update failed: {e}")

    async def send_error(self, message, error_text, status_message=None):
        """Show an error in the existing private-chat status message."""
        if message.chat.type == "private":
            try:
                if status_message:
                    await status_message.edit_text(error_text)
                else:
                    await message.reply_text(
                        error_text,
                        disable_web_page_preview=True,
                        reply_to_message_id=message.id,
                    )
                return True
            except Exception as e:
                logger.error(f"Failed to send error message in private chat: {e}")
        else:
            logger.info(f"Error occurred in {message.chat.type} chat")
        return False

    def run(self):
        logger.info("Bot is starting...")
        self.app.run()

if __name__ == "__main__":
    bot = Bot()
    bot.run()
