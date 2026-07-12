from unittest.mock import patch

import pytest

from src.instagram_downloader import InstagramDownloader


@pytest.mark.asyncio
async def test_download_returns_instagram_post_image(mock_config):
    downloader = InstagramDownloader(mock_config)

    def write_image(post, target):
        temp_dir = mock_config.downloads_dir / "instagram_example"
        (temp_dir / "post.jpg").write_bytes(b"full-size post image")

    with (
        patch("src.instagram_downloader.instaloader.Post.from_shortcode"),
        patch.object(downloader.loader, "download_post", side_effect=write_image),
    ):
        result = await downloader.download(
            "https://www.instagram.com/p/example/"
        )

    expected = mock_config.downloads_dir / "instagram_example.jpg"
    assert result == str(expected)
    assert expected.read_bytes() == b"full-size post image"
