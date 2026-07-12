from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.downloader import Downloader


def test_cookie_file_is_copied_to_writable_runtime_path(mock_config, tmp_path):
    source = tmp_path / "mounted-cookies.txt"
    source.write_text("# Netscape HTTP Cookie File\n")
    source.chmod(0o400)
    mock_config.COOKIE_FILE_PATH = str(source)

    downloader = Downloader(mock_config)
    runtime_file = Path(downloader._prepare_cookie_file())

    assert runtime_file == mock_config.downloads_dir / ".runtime-cookies.txt"
    assert runtime_file.read_text() == source.read_text()
    assert runtime_file.stat().st_mode & 0o777 == 0o600


@pytest.mark.asyncio
async def test_instagram_uses_ytdlp_without_trying_instaloader(mock_config):
    downloader = Downloader(mock_config)
    downloader.instagram_downloader.download = AsyncMock()

    with patch.object(
        downloader,
        "_download_with_ytdlp",
        new=AsyncMock(return_value="video.mp4"),
    ) as ytdlp_download:
        result = await downloader.download("https://www.instagram.com/reel/example/")

    assert result == "video.mp4"
    downloader.instagram_downloader.download.assert_not_awaited()
    ytdlp_download.assert_awaited_once_with(
        "https://www.instagram.com/reel/example/",
        is_instagram=True,
    )


@pytest.mark.asyncio
async def test_instagram_photo_falls_back_to_instaloader(mock_config):
    downloader = Downloader(mock_config)
    downloader.instagram_downloader.download = AsyncMock(
        return_value="instagram_example.jpg"
    )

    with patch.object(
        downloader,
        "_download_with_ytdlp",
        new=AsyncMock(side_effect=Exception("No video formats found!")),
    ):
        result = await downloader.download(
            "https://www.instagram.com/p/example/"
        )

    assert result == "instagram_example.jpg"
    downloader.instagram_downloader.download.assert_awaited_once()


@pytest.mark.asyncio
async def test_instagram_download_does_not_force_video_conversion(mock_config):
    downloader = Downloader(mock_config)

    with patch.object(
        downloader,
        "_download_video",
        return_value="picture.jpg",
    ) as download_video:
        result = await downloader._download_with_ytdlp(
            "https://www.instagram.com/p/example/",
            is_instagram=True,
        )

    assert result == "picture.jpg"
    options = download_video.call_args.args[1]
    assert options["format"] == "best"
    assert "postprocessors" not in options


def test_download_uses_image_filepath_reported_by_ytdlp(mock_config, tmp_path):
    downloader = Downloader(mock_config)
    image_path = tmp_path / "instagram-picture.jpg"
    image_path.write_bytes(b"image data")
    info = {
        "title": "instagram-picture",
        "ext": "jpg",
        "requested_downloads": [{"filepath": str(image_path)}],
    }
    ydl = MagicMock()
    ydl.__enter__.return_value = ydl
    ydl.extract_info.return_value = info

    with patch("src.downloader.yt_dlp.YoutubeDL", return_value=ydl):
        result = downloader._download_video("https://example.com/picture.jpg", {})

    assert result == str(image_path)
