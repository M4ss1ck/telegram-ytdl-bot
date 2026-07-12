import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.gallery_downloader import GalleryDownloader


@pytest.mark.asyncio
async def test_download_returns_all_gallery_media(mock_config):
    downloader = GalleryDownloader(mock_config)

    async def create_process(*command, **kwargs):
        download_dir = mock_config.downloads_dir / "gallery-dl"
        (download_dir / "01_small.jpg").write_bytes(b"small")
        (download_dir / "02_large.jpg").write_bytes(b"largest image")
        process = MagicMock(returncode=0)
        process.communicate = AsyncMock(return_value=(b"", b""))
        return process

    with patch(
        "src.gallery_downloader.asyncio.create_subprocess_exec",
        side_effect=create_process,
    ) as create_subprocess:
        result = await downloader.download("https://www.instagram.com/p/example/")

    expected_small = str(mock_config.downloads_dir / "instagram_01_small.jpg")
    expected_large = str(mock_config.downloads_dir / "instagram_02_large.jpg")
    assert result == [expected_small, expected_large]
    assert (mock_config.downloads_dir / "instagram_01_small.jpg").read_bytes() == b"small"
    assert (mock_config.downloads_dir / "instagram_02_large.jpg").read_bytes() == b"largest image"
    assert not (mock_config.downloads_dir / "gallery-dl").exists()
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


@pytest.mark.asyncio
async def test_multi_file_gallery_returns_sorted_paths(mock_config):
    downloader = GalleryDownloader(mock_config)

    async def create_process(*command, **kwargs):
        download_dir = mock_config.downloads_dir / "gallery-dl"
        (download_dir / "img_3.jpg").write_bytes(b"third")
        (download_dir / "img_1.jpg").write_bytes(b"first")
        (download_dir / "img_2.jpg").write_bytes(b"second")
        process = MagicMock(returncode=0)
        process.communicate = AsyncMock(return_value=(b"", b""))
        return process

    with patch(
        "src.gallery_downloader.asyncio.create_subprocess_exec",
        side_effect=create_process,
    ):
        result = await downloader.download("https://www.instagram.com/p/multi/")

    expected = [
        str(mock_config.downloads_dir / "instagram_img_1.jpg"),
        str(mock_config.downloads_dir / "instagram_img_2.jpg"),
        str(mock_config.downloads_dir / "instagram_img_3.jpg"),
    ]
    assert result == expected
    for path, content in zip(expected, [b"first", b"second", b"third"]):
        assert os.path.exists(path)
        with open(path, "rb") as f:
            assert f.read() == content
    assert not (mock_config.downloads_dir / "gallery-dl").exists()
