"""Run yt-dlp's real format selector over format lists shaped like the ones
TikTok, Instagram and YouTube return, so the size preset is tested offline."""
import pytest
import yt_dlp

from src.downloader import video_format_options


def fmt(format_id, width=None, height=None, vcodec="h264", acodec="aac",
        size=None, tbr=None, ext="mp4"):
    return {
        "format_id": format_id,
        "url": f"https://example.com/{format_id}",
        "protocol": "https",
        "ext": ext,
        "width": width,
        "height": height,
        "vcodec": vcodec,
        "acodec": acodec,
        "filesize": size,
        "tbr": tbr,
    }


def select(formats, max_resolution=480):
    info = {
        "id": "clip",
        "title": "clip",
        "extractor": "generic",
        "extractor_key": "Generic",
        "webpage_url": "https://example.com/clip",
        "formats": formats,
    }
    opts = {"quiet": True, "no_warnings": True, "simulate": True,
            **video_format_options(max_resolution)}
    with yt_dlp.YoutubeDL(opts) as ydl:
        result = ydl.process_ie_result(info, download=False)
    chosen = result.get("requested_formats") or [result]
    return [f["format_id"] for f in chosen]


# Captured from a real TikTok (-F) on 2026-09-13; sizes in bytes.
TIKTOK = [
    fmt("h264_540p_992286", 576, 1024, "h264", "aac", 1_310_000, 992),
    fmt("h264_540p_1376802", 576, 1024, "h264", "aac", 1_810_000, 1376),
    fmt("h264_540p_2240963", 576, 1024, "h264", "aac", 2_960_000, 2240),
    fmt("bytevc1_540p_1297374", 576, 1024, "h265", "aac", 1_730_000, 1297),
    fmt("bytevc1_720p_1504834", 720, 1280, "h265", "aac", 2_000_000, 1504),
]

# Instagram reel DASH ladder: video-only renditions plus one audio track.
INSTAGRAM = [
    fmt("dash-v322", 322, 572, "avc1.4d401f", "none", 900_000),
    fmt("dash-v720", 720, 1280, "avc1.4d401f", "none", 3_000_000),
    fmt("dash-a", None, None, "none", "mp4a.40.2", 200_000),
    fmt("progressive-720", 720, 1280, None, None),
]

# YouTube Short: AV1 at 480 competes with H.264 at 406.
YOUTUBE = [
    fmt("139", None, None, "none", "mp4a.40.5", 90_000, ext="m4a"),
    fmt("140", None, None, "none", "mp4a.40.2", 230_000, ext="m4a"),
    fmt("251", None, None, "none", "opus", 210_000, ext="webm"),
    fmt("136", 406, 720, "avc1.4d401e", "none", 600_000),
    fmt("137", 608, 1080, "avc1.64001f", "none", 1_700_000),
    fmt("397", 480, 854, "av01.0.04M.08", "none", 940_000),
    fmt("398", 720, 1280, "av01.0.05M.08", "none", 1_740_000),
    fmt("247", 720, 1280, "vp9", "none", 2_290_000, ext="webm"),
]


def test_tiktok_picks_smallest_h264_instead_of_720p_hevc():
    # The old preset chose bytevc1_720p (2.0 MB); this is 1.3 MB.
    assert select(TIKTOK) == ["h264_540p_992286"]


def test_vertical_video_is_not_rejected_by_the_resolution_cap():
    # Only 576x1024 and 720x1280 exist; short side decides, closest wins.
    only_vertical = [f for f in TIKTOK if f["vcodec"] == "h264"]
    assert select(only_vertical) == ["h264_540p_992286"]


def test_instagram_merges_smallest_dash_video_with_audio():
    assert select(INSTAGRAM) == ["dash-v322", "dash-a"]


def test_youtube_prefers_h264_over_av1_and_smallest_audio():
    assert select(YOUTUBE) == ["136", "139"]


def test_resolution_cap_is_configurable():
    assert select(YOUTUBE, max_resolution=720) == ["137", "139"]


def test_single_progressive_format_without_metadata_still_downloads():
    # Some posts expose one file with no codec or size info (e.g. images).
    assert select([fmt("only", vcodec=None, acodec=None, ext="jpg")]) == ["only"]


def test_video_without_audio_track_still_downloads():
    silent = [f for f in INSTAGRAM if f["format_id"].startswith("dash-v")]
    assert select(silent) == ["dash-v322"]


@pytest.mark.parametrize("cap", [240, 480, 720])
def test_options_carry_the_cap(cap):
    options = video_format_options(cap)
    assert options["format"] == "bv*+ba/b"
    assert f"res:{cap}" in options["format_sort"]
    assert options["format_sort"][0] == "vcodec:h264"
