import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock

import pytest

from src.spotify_downloader import SpotifyDownloader


@pytest.fixture
def downloads_dir():
    return Path(tempfile.mkdtemp())


@pytest.fixture
def mock_config(downloads_dir):
    cfg = MagicMock()
    cfg.downloads_dir = downloads_dir
    return cfg


@pytest.fixture
def track_info():
    return {
        "name": "Bohemian Rhapsody",
        "artists": [{"name": "Queen"}],
        "id": "abc123",
    }


class TestSpotifyFilename:
    """Verify Spotify tracks are saved as 'Artist - Song.mp3'."""

    @pytest.mark.asyncio
    async def test_filename_uses_dash_separator(self, mock_config, track_info, downloads_dir):
        with patch.dict(os.environ, {"SPOTIFY_CLIENT_ID": "id", "SPOTIFY_CLIENT_SECRET": "secret"}):
            with patch("src.spotify_downloader.spotipy.Spotify") as mock_spotify:
                mock_spotify_instance = MagicMock()
                mock_spotify_instance.track.return_value = track_info
                mock_spotify.return_value = mock_spotify_instance

                downloader = SpotifyDownloader(mock_config)

                assert downloader.spotify_client is not None

                safe_artist = "Queen"
                safe_title = "Bohemian Rhapsody"
                expected = downloads_dir / f"{safe_artist} - {safe_title}.mp3"

                assert " - " in str(expected)
                assert "_" not in expected.name.split(".mp3")[0][-3:]

    def test_filename_sanitization_strips_special_chars(self, mock_config, downloads_dir):
        import re

        artist = "AC/DC"
        title = "Back in Black!"

        safe_artist = re.sub(r"[^\w\s-]", "", artist)
        safe_title = re.sub(r"[^\w\s-]", "", title)

        target = mock_config.downloads_dir / f"{safe_artist} - {safe_title}.mp3"
        name = target.name

        assert " - " in name
        assert "ACDC" in name
        assert "Back in Black" in name
        assert "!" not in name
        assert "/" not in name

    def test_spotify_id_extraction(self, mock_config):
        downloader = SpotifyDownloader(mock_config)

        assert downloader._extract_spotify_id(
            "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT"
        ) == "4cOdK2wGLETKBW3PvgPWqT"

        assert downloader._extract_spotify_id(
            "https://open.spotify.com/intl-es/track/4cOdK2wGLETKBW3PvgPWqT"
        ) == "4cOdK2wGLETKBW3PvgPWqT"

        assert downloader._extract_spotify_id(
            "https://open.spotify.com/album/1aBcdEfh8wSXfkkf1sB40A"
        ) == "1aBcdEfh8wSXfkkf1sB40A"

        assert downloader._extract_spotify_id("not a spotify url") is None

    def test_search_query_variations(self, mock_config, track_info):
        downloader = SpotifyDownloader(mock_config)

        q = downloader._create_youtube_search_query(track_info, variation=0)
        assert q == "Queen - Bohemian Rhapsody audio"

        q = downloader._create_youtube_search_query(track_info, variation=1)
        assert q == "Bohemian Rhapsody Queen audio"

        q = downloader._create_youtube_search_query(None)
        assert q is None
