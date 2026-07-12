from unittest.mock import patch

import pytest

from src.instagram_downloader import InstagramDownloader


def test_configured_cookies_are_loaded_into_instaloader(mock_config, tmp_path):
    cookie_file = tmp_path / "instagram-cookies.txt"
    cookie_file.write_text(
        "# Netscape HTTP Cookie File\n"
        ".instagram.com\tTRUE\t/\tTRUE\t2147483647\tsessionid\ttest-session\n"
    )
    mock_config.COOKIE_FILE_PATH = str(cookie_file)

    downloader = InstagramDownloader(mock_config)

    assert (
        downloader.loader.context._session.cookies.get(
            "sessionid", domain=".instagram.com", path="/"
        )
        == "test-session"
    )


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
