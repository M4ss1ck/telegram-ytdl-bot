from pyrogram import Client, filters
import os
import asyncio
import re
import logging

from src.config import Config
from src.downloader import Downloader

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

        # Register handlers
        @self.app.on_message(filters.command("start"))
        async def start(client, message):
            await message.reply_text(
                "Welcome! Send me a URL and I'll download it for you using yt-dlp."
            )

        @self.app.on_message(filters.command("ping"))
        async def ping(client, message):
            await message.reply_text("Pong!")

        @self.app.on_message(filters.text)
        async def handle_url(client, message):
            # Ignore commands
            if message.text.startswith('/'):
                return

            # Find first URL in message
            url_pattern = r'(https?://\S+)'
            match = re.search(url_pattern, message.text)
            
            if not match:
                return
                
            url = match.group(1)
            status_message = await message.reply_text("Downloading...")
            
            try:
                file_path = await self.downloader.download(url)
                await status_message.edit_text("Upload in progress...")
                
                progress_args = (status_message,)
                
                if file_path.endswith(('.mp4', '.mkv')):
                    await message.reply_video(
                        file_path,
                        progress=self._upload_progress,
                        progress_args=progress_args
                    )
                else:
                    await message.reply_document(
                        file_path,
                        progress=self._upload_progress,
                        progress_args=progress_args
                    )
                
                os.remove(file_path)
                await status_message.delete()
                
            except Exception as e:
                logging.error(f"Error processing URL {url}: {str(e)}")
                await status_message.delete()

    async def _upload_progress(self, current, total, status_message):
        try:
            percent = current * 100 / total
            await status_message.edit_text(f"Uploading: {percent:.1f}%")
            await asyncio.sleep(0.5)  # Prevent flood
        except Exception:
            pass

    def run(self):
        print("Bot is running...")
        self.app.run()

if __name__ == "__main__":
    bot = Bot()
    bot.run()