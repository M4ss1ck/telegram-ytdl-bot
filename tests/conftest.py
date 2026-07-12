import os
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


@pytest.fixture(autouse=True)
def env_vars():
    with patch.dict(os.environ, {"API_ID": "12345", "API_HASH": "abc123", "BOT_TOKEN": "fake_token"}):
        yield


@pytest.fixture
def downloads_dir(tmp_path):
    return tmp_path / "downloads"


@pytest.fixture
def mock_config(downloads_dir):
    from unittest.mock import MagicMock
    cfg = MagicMock()
    cfg.downloads_dir = downloads_dir
    cfg.API_ID = 12345
    cfg.API_HASH = "abc123"
    cfg.BOT_TOKEN = "fake_token"
    cfg.MAX_FILE_SIZE = 300 * 1024 * 1024
    cfg.GROUP_MAX_FILE_SIZE = 300 * 1024 * 1024
    cfg.COOKIE_FILE_PATH = None
    return cfg


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.on_message = MagicMock(return_value=lambda f: f)
    return client
