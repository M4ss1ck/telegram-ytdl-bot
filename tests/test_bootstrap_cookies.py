import importlib.util
from http.cookiejar import Cookie, MozillaCookieJar
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parent.parent / "scripts/bootstrap_cookies.py"
spec = importlib.util.spec_from_file_location("bootstrap_cookies", SCRIPT)
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


def _cookie(domain, name, value="secret-value"):
    return Cookie(
        version=0, name=name, value=value, port=None, port_specified=False,
        domain=domain, domain_specified=True, domain_initial_dot=domain.startswith("."),
        path="/", path_specified=True, secure=True, expires=None, discard=False,
        comment=None, comment_url=None, rest={},
    )


def _loader(cookies):
    """Mimic browser_cookie3: substring domain match, like its SQL LIKE filter."""
    return lambda domain: [c for c in cookies if domain in c.domain]


BROWSER = [
    _cookie(".instagram.com", "sessionid"),
    _cookie(".instagram.com", "csrftoken"),
    _cookie(".reddit.com", "reddit_session"),
    _cookie(".reddit.com", "token_v2"),
    _cookie(".notreddit.com", "reddit_session"),
]


def test_default_site_is_instagram_only():
    assert bootstrap.parse_args([]).site == ["instagram"]


def test_sites_are_repeatable_and_deduplicated():
    args = bootstrap.parse_args(["--site", "instagram", "--site", "reddit", "--site", "reddit"])
    assert args.site == ["instagram", "reddit"]


def test_unknown_site_is_rejected():
    with pytest.raises(SystemExit):
        bootstrap.parse_args(["--site", "myspace"])


def test_collects_requested_sites_and_drops_lookalike_domains():
    collected = bootstrap.collect_cookies(["instagram", "reddit"], _loader(BROWSER))

    assert {c.name for c in collected["instagram"]} == {"sessionid", "csrftoken"}
    assert [c.domain for c in collected["reddit"]] == [".reddit.com", ".reddit.com"]


def test_unrequested_site_is_not_checked():
    # No Reddit login in the browser must not block an Instagram-only export
    browser = [c for c in BROWSER if "reddit" not in c.domain]
    collected = bootstrap.collect_cookies(["instagram"], _loader(browser))
    assert list(collected) == ["instagram"]


def test_requested_site_without_login_cookie_fails():
    # Anonymous Reddit visitors get token_v2 too; it must not count as a login
    browser = [c for c in BROWSER if c.name != "reddit_session"]
    with pytest.raises(RuntimeError, match="reddit.com: found cookies but no login session"):
        bootstrap.collect_cookies(["instagram", "reddit"], _loader(browser))


def test_lookalike_domain_login_cookie_does_not_count():
    browser = [_cookie(".notreddit.com", "reddit_session")]
    with pytest.raises(RuntimeError, match="reddit.com: found no cookies"):
        bootstrap.collect_cookies(["reddit"], _loader(browser))


def test_failure_message_never_contains_cookie_values():
    browser = [_cookie(".instagram.com", "csrftoken", value="do-not-leak")]
    with pytest.raises(RuntimeError) as error:
        bootstrap.collect_cookies(["instagram"], _loader(browser))
    assert "do-not-leak" not in str(error.value)


def test_written_file_is_owner_only_and_loadable(tmp_path):
    path = tmp_path / "secrets/cookies.txt"
    collected = bootstrap.collect_cookies(["instagram", "reddit"], _loader(BROWSER))

    bootstrap.write_cookie_file(
        [c for cookies in collected.values() for c in cookies], path
    )

    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700
    jar = MozillaCookieJar(str(path))
    jar.load(ignore_discard=True, ignore_expires=True)
    assert {(c.domain, c.name) for c in jar} == {
        (".instagram.com", "sessionid"),
        (".instagram.com", "csrftoken"),
        (".reddit.com", "reddit_session"),
        (".reddit.com", "token_v2"),
    }


def _netscape(*rows):
    lines = ["# Netscape HTTP Cookie File"]
    for domain, name, value in rows:
        lines.append(f"{domain}\tTRUE\t/\tTRUE\t0\t{name}\t{value}")
    return "\n".join(lines) + "\n"


def _names(path):
    jar = MozillaCookieJar(str(path))
    jar.load(ignore_discard=True, ignore_expires=True)
    return {(c.domain, c.name, c.value) for c in jar}


def test_rewrite_tightens_existing_permissive_file_in_place(tmp_path):
    path = tmp_path / "cookies.txt"
    path.write_text(_netscape((".instagram.com", "sessionid", "stale")))
    path.chmod(0o644)
    inode = path.stat().st_ino

    bootstrap.write_cookie_file(
        [_cookie(".instagram.com", "sessionid", "fresh")], path,
        replace_domains=["instagram.com"],
    )

    assert path.stat().st_mode & 0o777 == 0o600
    # Same inode: a running container's single-file bind mount sees the update
    assert path.stat().st_ino == inode
    assert _names(path) == {(".instagram.com", "sessionid", "fresh")}


def test_export_keeps_other_domains_and_replaces_requested_ones(tmp_path):
    # YouTube bot-checks fresh visitors; the aged visitor cookies must survive
    path = tmp_path / "cookies.txt"
    path.write_text(
        _netscape(
            (".youtube.com", "VISITOR_INFO1_LIVE", "aged"),
            (".instagram.com", "sessionid", "old"),
            (".instagram.com", "logged_out_leftover", "x"),
        ).replace(".instagram.com\tTRUE\t/\tTRUE\t0\tsessionid",
                  "#HttpOnly_.instagram.com\tTRUE\t/\tTRUE\t0\tsessionid")
    )

    bootstrap.write_cookie_file(
        [_cookie(".instagram.com", "sessionid", "new")], path,
        replace_domains=["instagram.com"],
    )

    assert _names(path) == {
        (".youtube.com", "VISITOR_INFO1_LIVE", "aged"),
        (".instagram.com", "sessionid", "new"),
    }


def test_existing_file_that_is_not_netscape_is_not_silently_discarded(tmp_path):
    path = tmp_path / "cookies.txt"
    path.write_text("not a cookie file")

    with pytest.raises(Exception):
        bootstrap.write_cookie_file([_cookie(".instagram.com", "sessionid")], path)

    assert path.read_text() == "not a cookie file"


def test_configure_env_replaces_existing_setting(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "BOT_TOKEN=x\n"
        "COOKIE_FILE_PATH=/run/secrets/instagram-cookies.txt\n"
        "COOKIE_FILE_PATH=/duplicate\n"
    )

    bootstrap.configure_env(env)

    assert env.read_text() == "BOT_TOKEN=x\nCOOKIE_FILE_PATH=/run/secrets/cookies.txt\n"


def test_configure_env_appends_when_missing(tmp_path):
    env = tmp_path / ".env"
    env.write_text("BOT_TOKEN=x\n")

    bootstrap.configure_env(env)

    assert env.read_text().endswith("COOKIE_FILE_PATH=/run/secrets/cookies.txt\n")
