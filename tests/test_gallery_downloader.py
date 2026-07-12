from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.gallery_downloader import GalleryDownloader


@pytest.mark.asyncio
async def test_download_returns_largest_gallery_media(mock_config):
    downloader = GalleryDownloader(mock_config)

    async def create_process(*command, **kwargs):
        download_dir = mock_config.downloads_dir / "gallery-dl"
        (download_dir / "small.jpg").write_bytes(b"small")
        (download_dir / "large.jpg").write_bytes(b"largest image")
        process = MagicMock(returncode=0)
        process.communicate = AsyncMock(return_value=(b"", b""))
        return process

    with patch(
        "src.gallery_downloader.asyncio.create_subprocess_exec",
        side_effect=create_process,
    ) as create_subprocess:
        result = await downloader.download("https://www.instagram.com/p/example/")

    result_path = mock_config.downloads_dir / "instagram_large.jpg"
    assert result == str(result_path)
    assert result_path.read_bytes() == b"largest image"
    command = create_subprocess.call_args.args
    assert "gallery_dl" in command
    assert "--cookies" not in command


@pytest.mark.asyncio
async def test_download_passes_configured_cookies(mock_config, tmp_path):
    cookie_file = tmp_path / "cookies.txt"
    cookie_file.write_text("# Netscape HTTP Cookie File\n")
    mock_config.COOKIE_FILE_PATH = str(cookie_file)
    downloader = GalleryDownloader(mock_config)

    async def create_process(*command, **kwargs):
        download_dir = mock_config.downloads_dir / "gallery-dl"
        (download_dir / "photo.jpg").write_bytes(b"photo")
        process = MagicMock(returncode=0)
        process.communicate = AsyncMock(return_value=(b"", b""))
        return process

    with patch(
        "src.gallery_downloader.asyncio.create_subprocess_exec",
        side_effect=create_process,
    ) as create_subprocess:
        await downloader.download("https://www.instagram.com/p/example/")

    command = create_subprocess.call_args.args
    cookie_index = command.index("--cookies")
    assert command[cookie_index + 1] == str(cookie_file)
