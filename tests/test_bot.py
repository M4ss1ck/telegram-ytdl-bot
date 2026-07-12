import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from src.bot import Bot


def _make_bot():
    client = MagicMock()
    client.on_message.return_value = lambda handler: handler
    with patch("src.bot.Client", return_value=client):
        bot = Bot()
    bot.downloader = AsyncMock()
    bot.downloader.get_file_info = AsyncMock(return_value={"file_size": 1000000})
    bot.downloader.download = AsyncMock(return_value="/tmp/test.mp4")
    return bot


def _make_message(chat_type="private"):
    msg = MagicMock()
    msg.chat.type = chat_type
    msg.from_user.id = 123
    msg.id = 42
    msg.text = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    return msg


class TestSendError:
    @pytest.mark.asyncio
    async def test_sends_error_in_private(self):
        bot = _make_bot()
        message = _make_message("private")
        message.reply_text = AsyncMock()

        await bot.send_error(message, "something went wrong")

        message.reply_text.assert_called_once()
        call_args = message.reply_text.call_args
        assert "something went wrong" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_silent_in_group(self):
        bot = _make_bot()
        message = _make_message("supergroup")
        message.reply_text = AsyncMock()

        await bot.send_error(message, "something went wrong")

        message.reply_text.assert_not_called()


class TestUploadFile:
    """Verify upload_file sends exactly one media response."""

    @pytest.mark.asyncio
    async def test_sends_video_and_edits_status(self, tmp_path):
        bot = _make_bot()
        message = _make_message("private")
        message.reply_video = AsyncMock()

        status_msg = AsyncMock()

        file_path = tmp_path / "test.mp4"
        file_path.write_bytes(b"fake mp4 data")

        await bot.upload_file(message, str(file_path), status_msg)

        message.reply_video.assert_called_once()
        assert message.reply_video.call_args.kwargs["progress"] == bot._upload_progress

    @pytest.mark.asyncio
    async def test_sends_document_for_non_video(self, tmp_path):
        bot = _make_bot()
        message = _make_message("private")
        message.reply_document = AsyncMock()

        status_msg = AsyncMock()

        file_path = tmp_path / "test.mp3"
        file_path.write_bytes(b"fake mp3 data")

        await bot.upload_file(message, str(file_path), status_msg)

        message.reply_document.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_receives_existing_status_for_progress(self, tmp_path):
        bot = _make_bot()
        message = _make_message("private")
        message.reply_video = AsyncMock()

        status_msg = AsyncMock()

        file_path = tmp_path / "test.mp4"
        file_path.write_bytes(b"fake mp4 data")

        await bot.upload_file(message, str(file_path), status_msg)

        message.reply_video.assert_called_once()
        progress_args = message.reply_video.call_args.kwargs["progress_args"]
        assert progress_args[0] is status_msg


class TestProcessRequestSuccess:
    """After successful processing, exactly one bot response remains (the media)."""

    @pytest.mark.asyncio
    async def test_status_deleted_after_success(self, tmp_path):
        bot = _make_bot()
        file_path = tmp_path / "result.mp4"
        file_path.write_bytes(b"video data")
        bot.downloader.download = AsyncMock(return_value=str(file_path))

        message = _make_message("private")
        status_msg = AsyncMock()
        message.reply_text = AsyncMock(return_value=status_msg)
        message.reply_video = AsyncMock()

        await bot._process_request(
            message=message,
            url="https://youtube.com/watch?v=test",
            is_instagram=False,
            is_spotify=False,
            is_youtube=True,
            is_group=False,
        )

        status_msg.delete.assert_called_once()
        message.reply_text.assert_called_once()
        message.reply_video.assert_called_once()

    @pytest.mark.asyncio
    async def test_status_deleted_after_success_spotify(self, tmp_path):
        """Spotify success also leaves only the uploaded media."""
        bot = _make_bot()
        file_path = tmp_path / "track.mp3"
        file_path.write_bytes(b"audio data")
        bot.downloader.download = AsyncMock(return_value=str(file_path))

        message = _make_message("private")
        status_msg = AsyncMock()

        message.reply_text = AsyncMock(return_value=status_msg)
        message.reply_document = AsyncMock()

        await bot._process_request(
            message=message,
            url="https://open.spotify.com/track/abc",
            is_instagram=False,
            is_spotify=True,
            is_youtube=False,
            is_group=False,
        )

        status_msg.delete.assert_called_once()
        message.reply_document.assert_called_once()


class TestProcessRequestError:
    """After error, exactly one error message in private; zero in group."""

    @pytest.mark.asyncio
    async def test_download_error_private_sends_one_error(self):
        bot = _make_bot()
        bot.downloader.download = AsyncMock(side_effect=Exception("download failed"))

        message = _make_message("private")

        status_msg = AsyncMock()
        message.reply_text = AsyncMock(return_value=status_msg)

        await bot._process_request(
            message=message,
            url="https://youtube.com/watch?v=test",
            is_instagram=False,
            is_spotify=False,
            is_youtube=True,
            is_group=False,
        )

        status_msg.delete.assert_not_called()
        assert "Error: download failed" in status_msg.edit_text.call_args.args[0]
        message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_download_error_group_silent(self):
        bot = _make_bot()
        bot.downloader.download = AsyncMock(side_effect=Exception("download failed"))

        message = _make_message("supergroup")

        status_msg = AsyncMock()
        message.reply_text = AsyncMock(return_value=status_msg)

        await bot._process_request(
            message=message,
            url="https://youtube.com/watch?v=test",
            is_instagram=False,
            is_spotify=False,
            is_youtube=True,
            is_group=False,
        )

        status_msg.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_too_large_post_download_private_sends_error(self, tmp_path):
        bot = _make_bot()
        bot.config.MAX_FILE_SIZE = 1024  # 1KB
        bot.downloader.get_file_info = AsyncMock(return_value={"file_size": 0})

        file_path = tmp_path / "big.mp4"
        file_path.write_bytes(b"x" * 5000)  # 5KB
        bot.downloader.download = AsyncMock(return_value=str(file_path))

        message = _make_message("private")
        status_msg = AsyncMock()
        message.reply_text = AsyncMock(return_value=status_msg)

        await bot._process_request(
            message=message,
            url="https://youtube.com/watch?v=test",
            is_instagram=False,
            is_spotify=False,
            is_youtube=True,
            is_group=False,
        )

        status_msg.delete.assert_not_called()
        assert "File too large" in status_msg.edit_text.call_args.args[0]

    @pytest.mark.asyncio
    async def test_too_large_post_download_group_silent(self, tmp_path):
        bot = _make_bot()
        bot.config.GROUP_MAX_FILE_SIZE = 1024

        file_path = tmp_path / "big.mp4"
        file_path.write_bytes(b"x" * 5000)
        bot.downloader.download = AsyncMock(return_value=str(file_path))

        message = _make_message("supergroup")

        status_msg = AsyncMock()
        message.reply_text = AsyncMock(return_value=status_msg)

        await bot._process_request(
            message=message,
            url="https://youtube.com/watch?v=test",
            is_instagram=False,
            is_spotify=False,
            is_youtube=True,
            is_group=False,
        )

        status_msg.delete.assert_called_once()


class TestProcessWithSemaphore:
    @pytest.mark.asyncio
    async def test_queue_full_replies_and_returns(self):
        bot = _make_bot()
        bot.queue_waiting = bot.max_queue_size

        message = _make_message("private")
        message.reply_text = AsyncMock()

        await bot._process_with_semaphore(
            message=message,
            url="https://youtube.com/watch?v=test",
            is_instagram=False,
            is_spotify=False,
            is_youtube=True,
            is_group=False,
        )

        message.reply_text.assert_called_once()


class TestProgressReporting:
    """Progress reporting should edit the status message during processing."""

    @pytest.mark.asyncio
    async def test_existing_queue_message_is_reused(self, tmp_path):
        bot = _make_bot()
        file_path = tmp_path / "video.mp4"
        file_path.write_bytes(b"video data")
        bot.downloader.download = AsyncMock(return_value=str(file_path))

        message = _make_message("private")
        message.reply_text = AsyncMock()
        message.reply_video = AsyncMock()
        queued_status = AsyncMock()

        await bot._process_request(
            message=message,
            url="https://youtube.com/watch?v=test",
            is_instagram=False,
            is_spotify=False,
            is_youtube=True,
            is_group=False,
            status_message=queued_status,
        )

        message.reply_text.assert_not_called()
        queued_status.edit_text.assert_called()
        queued_status.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_status_edited_during_lifecycle(self, tmp_path):
        bot = _make_bot()
        file_path = tmp_path / "video.mp4"
        file_path.write_bytes(b"video data")
        bot.downloader.download = AsyncMock(return_value=str(file_path))

        message = _make_message("private")
        status_msg = AsyncMock()
        message.reply_text = AsyncMock(return_value=status_msg)
        message.reply_video = AsyncMock()

        await bot._process_request(
            message=message,
            url="https://youtube.com/watch?v=test",
            is_instagram=False,
            is_spotify=False,
            is_youtube=True,
            is_group=False,
        )

        assert status_msg.edit_text.call_count >= 1
        status_msg.delete.assert_called_once()
