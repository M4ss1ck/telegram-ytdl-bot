# Telegram YTDL Bot

This project is a Telegram bot that allows users to download content from URLs using `yt-dlp` and upload it back to the chat.

## Features

- Download videos and audio from various platforms using `yt-dlp`.
- Easy to use Telegram bot interface.
- Configurable settings for the bot.

## Requirements

- Python 3.7 or higher
- `python-telegram-bot`
- `yt-dlp`

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
   - Copy `.env.example` to `.env` and fill in your bot token.

## Usage

1. Run the bot:
   ```
   python src/bot.py
   ```

2. Interact with the bot on Telegram by sending URLs to download.

## Contributing

Feel free to submit issues or pull requests for improvements or bug fixes.

## License

This project is licensed under the MIT License.