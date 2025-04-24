# Telegram YTDL Bot

This project is a Telegram bot that allows users to download content from various platforms and upload it back to the chat.

## Features

- Download videos from YouTube and other platforms using `yt-dlp`
- Enhanced YouTube support with multiple bypass methods for blocked regions
- Specialized support for Instagram content using `Instaloader`
- Spotify music download support with high-quality MP3 conversion
- Easy to use Telegram bot interface
- Configurable settings for the bot

## Requirements

- Python 3.7 or higher
- `pyrogram` and `tgcrypto` for Telegram API
- `yt-dlp` for general video downloads
- `instaloader` for Instagram content
- `spotipy` for Spotify content
- `ffmpeg` for audio/video processing
- `aiohttp` for API-based YouTube downloads

### Optional Requirements

For browser-based YouTube downloads:

- `playwright` (recommended) or `selenium` for browser automation
- A browser installed on the system (Firefox or Chrome)

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

4. For browser automation support (optional):

   ```
   # Uncomment the browser automation dependencies in requirements.txt first, then:
   pip install -r requirements.txt

   # If using playwright, install browsers:
   playwright install firefox  # or chrome
   ```

5. Set up your environment variables:
   - Copy `.env.example` to `.env` and fill in your bot token and API credentials
   - For Spotify support, you'll need to add your Spotify API credentials
   - For enhanced YouTube support, consider adding RapidAPI key or proxy settings
   - To enable browser automation, set `BROWSER_ENABLED=true` in your `.env` file

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
  - Enhanced YouTube support with API-based downloads, proxies, and alternate frontends
  - Browser-based downloads for heavily blocked regions
  - Multiple fallback mechanisms to handle blocked or restricted content
- Instagram posts, reels, and stories (via Instaloader with yt-dlp fallback)
- Spotify tracks, albums, and playlists (via specialized Spotify downloader)

## YouTube Download Methods

The bot uses a multi-layered approach to download YouTube content, especially useful when your server is located in a region where YouTube is blocked:

1. **API-based Downloads**: Uses various public and premium APIs to download YouTube content without direct access to YouTube
2. **Proxy Method**: If configured, uses a proxy to bypass regional restrictions
3. **Browser Automation**: Uses headless browsers (Firefox/Chrome) to simulate a real user accessing YouTube
4. **Alternative Frontends**: Uses Invidious and other alternative YouTube frontend instances to download videos
5. **Direct Download**: Falls back to direct yt-dlp download as a last resort

To enable these features, configure the appropriate options in your `.env` file:

```
# YouTube Download Configuration
RAPIDAPI_KEY=your_rapidapi_key          # For premium API service
PROXY_URL=http://user:pass@proxy:port   # For proxy method
BROWSER_ENABLED=true                    # For browser-based downloads
YOUTUBE_STRATEGY=api_first              # Download method priority
```

### Browser-based Downloads

The browser-based approach simulates a real browser visiting YouTube or a YouTube downloader service, which can bypass many restrictions. This method requires:

1. Either `playwright` (recommended) or `selenium` installed
2. A browser (Firefox or Chrome) installed on the system
3. Setting `BROWSER_ENABLED=true` in your `.env` file

This method is slower but more reliable in heavily restricted environments.

### Alternative API Methods

The bot also supports several alternative API services for downloading YouTube content:

1. **RapidAPI-based services**: Premium YouTube downloader APIs (requires API key)
2. **Public YouTube downloaders**: Several free public APIs that don't require authentication
3. **Custom API services**: Support for your own YouTube download API if you have one

## Additional Bypass Methods

Other methods that can be implemented if the current approaches fail:

1. **Rotating IP addresses**: Use a service that provides rotating IPs to avoid blocking
2. **VPN integration**: Integrate with a VPN service to change IP addresses
3. **Tor network**: Use the Tor network to access YouTube through different exit nodes
4. **Cloud-based download**: Use cloud functions or services in unblocked regions to download the content
5. **P2P downloads**: Use a peer-to-peer network of bots to download content from regions where YouTube is accessible

## Contributing

Feel free to submit issues or pull requests for improvements or bug fixes.

## License

This project is licensed under the MIT License.
