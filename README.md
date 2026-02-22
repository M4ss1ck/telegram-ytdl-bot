# Telegram YTDL Bot

This project is a Telegram bot that allows users to download content from various platforms and upload it back to the chat.

## Features

- Download videos from YouTube and other platforms using `yt-dlp`
- Enhanced YouTube support with multiple bypass methods for blocked regions
- Specialized support for Instagram content using `Instaloader`
- Spotify music download support with high-quality MP3 conversion
- Easy to use Telegram bot interface
- Configurable settings for the bot
- Group file size limits to prevent large files in group chats (default: 300MB limit)

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
   - To use cookies with yt-dlp methods, set `COOKIE_FILE_PATH` to the path of your cookies.txt file
   - To configure group file size limits, set `GROUP_MAX_FILE_SIZE` (default: 300MB)

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
  - Optional cookie support for yt-dlp methods to bypass login/bot checks
  - Multiple fallback mechanisms to handle blocked or restricted content
- Instagram posts, reels, and stories (via Instaloader with yt-dlp fallback)
- Spotify tracks, albums, and playlists (via specialized Spotify downloader)

## YouTube Download Methods

The bot uses a multi-layered approach to download YouTube content, especially useful when your server is located in a region where YouTube is blocked:

1. **API-based Downloads**: Uses various public and premium APIs (e.g., from RapidAPI) to download YouTube content without direct access to YouTube. The bot cycles through multiple known endpoints.
2. **Proxy Method**: If configured (`PROXY_URL`), uses a proxy to bypass regional restrictions. Works best when combined with cookies.
3. **Browser Automation**: Uses headless browsers (`BROWSER_ENABLED=true`) to simulate a real user accessing YouTube. Requires `playwright` or `selenium`.
4. **Alternative Frontends**: Uses Invidious instances to download videos. Often requires cookies now.
5. **Direct Download**: Falls back to direct yt-dlp download as a last resort (least likely to work if blocked).

To enable these features, configure the appropriate options in your `.env` file:

```
# YouTube Download Configuration
RAPIDAPI_KEY=your_rapidapi_key          # For premium API service
PROXY_URL=http://user:pass@proxy:port   # For proxy method
BROWSER_ENABLED=true                    # For browser-based downloads
COOKIE_FILE_PATH=/path/to/cookies.txt   # Optional: For yt-dlp methods
YOUTUBE_STRATEGY=api_first              # Download method priority
```

### Cookie Support

If the proxy or alternate frontend methods fail with errors like "Sign in to confirm" or "Failed to extract player response", YouTube might require authentication cookies. You can provide these using the `COOKIE_FILE_PATH` setting:

1.  **Export Cookies**: Use a browser extension like "Get cookies.txt" or "EditThisCookie" to export your YouTube cookies from a logged-in browser session into a Netscape-formatted `cookies.txt` file.
2.  **Configure Path**: Place the `cookies.txt` file on your server and set the absolute path in `COOKIE_FILE_PATH` in your `.env` file.

The bot will automatically use these cookies for `yt-dlp` based download methods (proxy and alternate frontends).

### Browser-based Downloads

The browser-based approach simulates a real browser visiting YouTube or a YouTube downloader service, which can bypass many restrictions. This method requires:

1. Either `playwright` (recommended) or `selenium` installed
2. A browser (Firefox or Chrome) installed on the system
3. Setting `BROWSER_ENABLED=true` in your `.env` file

This method is slower but more reliable in heavily restricted environments.

## Group File Size Limits

The bot includes a feature to limit file downloads in group chats to prevent large files from being shared inappropriately:

- **Default Limit**: 300MB for group and supergroup chats
- **Private Chats**: Uses the standard `MAX_FILE_SIZE` cap (default 300MB)
- **Size Check**: The bot checks file size before downloading to avoid wasting resources
- **User Feedback**: In groups, oversized downloads are skipped; in private chats an error is returned

### Configuration

Set the overall file size cap using `MAX_FILE_SIZE`, and optionally override the group limit using `GROUP_MAX_FILE_SIZE`:

```
MAX_FILE_SIZE=314572800        # 300MB in bytes (default)
GROUP_MAX_FILE_SIZE=314572800  # 300MB in bytes (default)
GROUP_MAX_FILE_SIZE=104857600  # 100MB in bytes
GROUP_MAX_FILE_SIZE=1073741824 # 1GB in bytes
```

The effective group limit is the smaller of `GROUP_MAX_FILE_SIZE` and `MAX_FILE_SIZE`.

### Behavior

- **Instagram/Spotify**: Size limits are not enforced for Instagram and Spotify downloads as their downloaders don't provide reliable size information before download
- **YouTube/Other platforms**: Size is checked before download using yt-dlp's info extraction
- **Fallback**: If size checking fails, the download proceeds normally

### Alternative API Methods

The bot also supports several alternative API services for downloading YouTube content:

1. **RapidAPI-based services**: Premium YouTube downloader APIs (requires API key)
2. **Public YouTube downloaders**: Several free public APIs that don't require authentication (often unreliable)
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
