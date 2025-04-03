# Telegram YTDL Bot

This project is a Telegram bot that allows users to download content from various platforms and upload it back to the chat.

## Features

- Download videos from YouTube and other platforms using `yt-dlp`
- Specialized support for Instagram content using `Instaloader`
- Spotify music download support with high-quality MP3 conversion
- Easy to use Telegram bot interface
- Configurable settings for the bot

## Requirements

- Python 3.7 or higher
- `pyrogram` and `tgcrypto` for Telegram API
- `yt-dlp` for general video downloads
- `instaloader` for Instagram content
- `spotipy` and `youtube-dl-spotify` for Spotify content
- `ffmpeg` for audio/video processing

## Installation

1. Clone the repository:

   ```
   git clone https://github.com/yourusername/telegram-ytdl-bot.git
   cd telegram-ytdl-bot
   ```

2. Create a virtual environment (optional but recommended):

   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install the required packages:

   ```
   pip install -r requirements.txt
   ```

4. Set up your environment variables:
   - Copy `.env.example` to `.env` and fill in your bot token and API credentials
   - For Spotify support, you'll need to add your Spotify API credentials

## Usage

1. Run the bot:

   ```
   python src/bot.py
   ```

2. Interact with the bot on Telegram by sending URLs to download:
   - YouTube videos: `https://www.youtube.com/watch?v=...`
   - Instagram posts/reels: `https://www.instagram.com/p/...` or `https://www.instagram.com/reel/...`
   - Spotify tracks: `https://open.spotify.com/track/...`

## Supported Platforms

- YouTube and other video platforms (via yt-dlp)
- Instagram posts, reels, and stories (via Instaloader with yt-dlp fallback)
- Spotify tracks, albums, and playlists (via specialized Spotify downloader)

## Contributing

Feel free to submit issues or pull requests for improvements or bug fixes.

## License

This project is licensed under the MIT License.
