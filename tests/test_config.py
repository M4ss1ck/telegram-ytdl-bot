import os
from unittest.mock import patch

import pytest

from src.config import Config


@pytest.fixture(autouse=True)
def no_dotenv():
    with patch("src.config.load_dotenv"):
        yield


def test_video_max_resolution_defaults_to_480():
    with patch.dict(os.environ):
        os.environ.pop("VIDEO_MAX_RESOLUTION", None)
        assert Config().VIDEO_MAX_RESOLUTION == 480


def test_video_max_resolution_reads_env():
    with patch.dict(os.environ, {"VIDEO_MAX_RESOLUTION": "360"}):
        assert Config().VIDEO_MAX_RESOLUTION == 360


@pytest.mark.parametrize("value", ["0", "-1"])
def test_video_max_resolution_rejects_non_positive(value):
    with patch.dict(os.environ, {"VIDEO_MAX_RESOLUTION": value}):
        with pytest.raises(ValueError, match="VIDEO_MAX_RESOLUTION"):
            Config()
