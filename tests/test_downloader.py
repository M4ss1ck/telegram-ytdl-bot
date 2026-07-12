from pathlib import Path
from unittest.mock import AsyncMock, patch

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
