import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yt_dlp

from src.downloader import Downloader, cookie_names_for_domain, explain_ytdlp_error


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
    downloader.gallery_downloader.download = AsyncMock()

    with patch.object(
        downloader,
        "_download_with_ytdlp",
        new=AsyncMock(return_value="video.mp4"),
    ) as ytdlp_download:
        result = await downloader.download("https://www.instagram.com/reel/example/")

    assert result == "video.mp4"
    downloader.gallery_downloader.download.assert_not_awaited()
    ytdlp_download.assert_awaited_once_with(
        "https://www.instagram.com/reel/example/",
        is_instagram=True,
    )


@pytest.mark.asyncio
async def test_instagram_photo_falls_back_to_gallery_dl(mock_config):
    downloader = Downloader(mock_config)
    downloader.gallery_downloader.download = AsyncMock(
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
    downloader.gallery_downloader.download.assert_awaited_once()


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
    assert "postprocessors" not in options


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url, flags",
    [
        ("https://www.instagram.com/reel/example/", {"is_instagram": True}),
        ("https://www.tiktok.com/@user/video/123", {}),
        ("https://www.youtube.com/shorts/abc", {"is_youtube": True}),
    ],
)
async def test_video_downloads_use_small_size_preset(mock_config, url, flags):
    mock_config.VIDEO_MAX_RESOLUTION = 360
    downloader = Downloader(mock_config)

    with patch.object(downloader, "_download_video", return_value="v.mp4") as dl:
        await downloader._download_with_ytdlp(url, **flags)

    options = dl.call_args.args[1]
    assert options["format"] == "bv*+ba/b"
    assert options["format_sort"][:2] == ["vcodec:h264", "res:360"]
    assert options["merge_output_format"] == "mp4"


@pytest.mark.asyncio
async def test_spotify_fallback_does_not_pick_smallest_audio(mock_config):
    downloader = Downloader(mock_config)

    with patch.object(downloader, "_download_video", return_value="s.mp3") as dl:
        await downloader._download_with_ytdlp(
            "https://open.spotify.com/track/x", is_spotify=True
        )

    options = dl.call_args.args[1]
    assert options["format"] == "bestaudio/best"
    assert "format_sort" not in options


@pytest.mark.asyncio
async def test_size_estimate_uses_same_selector_as_download(mock_config):
    downloader = Downloader(mock_config)

    with patch.object(downloader, "_extract_info", return_value={}) as extract, \
            patch.object(downloader, "_download_video", return_value="v.mp4") as dl:
        await downloader.get_file_info("https://www.tiktok.com/@u/video/1")
        await downloader._download_with_ytdlp("https://www.tiktok.com/@u/video/1")

    info_opts = extract.call_args.args[1]
    download_opts = dl.call_args.args[1]
    assert info_opts["format"] == download_opts["format"]
    assert info_opts["format_sort"] == download_opts["format_sort"]


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


REDDIT_AUTH_ERROR = (
    "ERROR: [Reddit] 1xgk0mo: Account authentication is required. "
    "Use --cookies-from-browser or --cookies for the authentication."
)


def _write_cookie_file(path, rows):
    lines = ["# Netscape HTTP Cookie File"]
    for domain, name in rows:
        lines.append(f"{domain}\tTRUE\t/\tTRUE\t0\t{name}\tvalue")
    path.write_text("\n".join(lines) + "\n")
    return str(path)


def test_cookie_names_for_domain_matches_subdomains_and_httponly(tmp_path):
    cookie_file = _write_cookie_file(tmp_path / "c.txt", [
        (".reddit.com", "csv"),
        ("#HttpOnly_.reddit.com", "reddit_session"),
        ("www.reddit.com", "token_v2"),
        (".notreddit.com", "evil"),
        (".instagram.com", "sessionid"),
    ])

    assert cookie_names_for_domain(cookie_file, "reddit.com") == {
        "csv", "reddit_session", "token_v2",
    }


def test_cookie_names_for_domain_handles_missing_file():
    assert cookie_names_for_domain(None, "reddit.com") == set()
    assert cookie_names_for_domain("/nonexistent/cookies.txt", "reddit.com") == set()


def test_explain_ignores_unrelated_errors(tmp_path):
    assert explain_ytdlp_error("ERROR: [youtube] x: Video unavailable") is None
    # Instagram uses the same wording, but the Reddit diagnosis does not apply
    assert explain_ytdlp_error(
        "ERROR: [Instagram] x: Account authentication is required"
    ) is None


def test_explain_reddit_block_without_login_cookie(tmp_path):
    # Anonymous cookies, including token_v2, are what Reddit hands everyone
    cookie_file = _write_cookie_file(tmp_path / "c.txt", [
        (".reddit.com", "csv"),
        (".reddit.com", "token_v2"),
    ])

    cause = explain_ytdlp_error(
        REDDIT_AUTH_ERROR, cookie_file, impersonation_available=True
    )

    assert "no reddit_session cookie is configured" in cause
    assert "--site reddit" in cause
    assert "curl_cffi" not in cause


def test_explain_reddit_block_with_rejected_login_cookie(tmp_path):
    cookie_file = _write_cookie_file(tmp_path / "c.txt", [
        ("#HttpOnly_.reddit.com", "reddit_session"),
    ])

    cause = explain_ytdlp_error(
        REDDIT_AUTH_ERROR, cookie_file, impersonation_available=True
    )

    assert "rejected the configured reddit_session cookie" in cause


def test_explain_reddit_block_reports_missing_impersonation():
    cause = explain_ytdlp_error(
        REDDIT_AUTH_ERROR, None, impersonation_available=False
    )

    assert "curl_cffi is not installed" in cause
    assert "no reddit_session cookie" in cause


def test_impersonation_dependency_is_installed():
    # yt-dlp[curl-cffi] is what lets the Reddit session request through
    assert explain_ytdlp_error(REDDIT_AUTH_ERROR) is not None
    assert "curl_cffi" not in explain_ytdlp_error(REDDIT_AUTH_ERROR)


def test_download_error_logs_reddit_cause(mock_config, caplog):
    downloader = Downloader(mock_config)
    ydl = MagicMock()
    ydl.__enter__.return_value = ydl
    ydl.extract_info.side_effect = yt_dlp.utils.DownloadError(REDDIT_AUTH_ERROR)

    with patch("src.downloader.yt_dlp.YoutubeDL", return_value=ydl), \
            caplog.at_level(logging.WARNING, logger="src.downloader"), \
            pytest.raises(Exception, match="Download error"):
        downloader._download_video("https://www.reddit.com/r/x/comments/1xgk0mo/", {})

    assert "Reddit download blocked" in caplog.text


def test_info_error_logs_reddit_cause(mock_config, caplog):
    downloader = Downloader(mock_config)
    ydl = MagicMock()
    ydl.__enter__.return_value = ydl
    ydl.extract_info.side_effect = yt_dlp.utils.DownloadError(REDDIT_AUTH_ERROR)

    with patch("src.downloader.yt_dlp.YoutubeDL", return_value=ydl), \
            caplog.at_level(logging.WARNING, logger="src.downloader"), \
            pytest.raises(Exception, match="Info extraction error"):
        downloader._extract_info("https://www.reddit.com/r/x/comments/1xgk0mo/", {})

    assert "Reddit download blocked" in caplog.text


@pytest.mark.asyncio
async def test_ytdlp_requests_use_library_headers(mock_config):
    # A fixed old Chrome UA contradicts the impersonated TLS fingerprint
    downloader = Downloader(mock_config)

    with patch.object(downloader, "_extract_info", return_value={}) as extract, \
            patch.object(downloader, "_download_video", return_value="v.mp4") as dl:
        await downloader.get_file_info("https://www.reddit.com/r/x/comments/1/")
        await downloader._download_with_ytdlp("https://www.reddit.com/r/x/comments/1/")

    assert "http_headers" not in extract.call_args.args[1]
    assert "http_headers" not in dl.call_args.args[1]
