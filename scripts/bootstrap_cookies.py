#!/usr/bin/env python3
"""Export logged-in site cookies from the local Floorp profile for Docker.

Writes one Netscape cookie file that yt-dlp and gallery-dl both read. Each
requested site must have its login cookie, otherwise nothing is written.
Cookies of other domains already in the file are kept.
"""

from dataclasses import dataclass
from http.cookiejar import MozillaCookieJar
from pathlib import Path
import argparse
import os


PROJECT_DIR = Path(__file__).resolve().parent.parent
FLOORP_DIR = Path.home() / ".var/app/one.ablaze.floorp/.floorp"
COOKIE_FILE = PROJECT_DIR / "secrets/cookies.txt"
ENV_FILE = PROJECT_DIR / ".env"
CONTAINER_COOKIE_FILE = "/run/secrets/cookies.txt"


@dataclass(frozen=True)
class Site:
    domain: str
    login_cookie: str


SITES = {
    "instagram": Site("instagram.com", "sessionid"),
    # token_v2 is not a login signal: Reddit also issues it to anonymous visitors.
    "reddit": Site("reddit.com", "reddit_session"),
}


def find_floorp_cookie_database() -> Path:
    databases = list(FLOORP_DIR.glob("*/cookies.sqlite"))
    if not databases:
        raise RuntimeError(f"No Floorp cookie database found under {FLOORP_DIR}")
    return max(databases, key=lambda path: path.stat().st_mtime)


def floorp_loader(database: Path):
    import browser_cookie3

    def load(domain: str):
        return browser_cookie3.firefox(cookie_file=str(database), domain_name=domain)

    return load


def belongs_to(cookie, domain: str) -> bool:
    # browser_cookie3 filters with a substring match, so drop lookalike domains.
    host = cookie.domain.lstrip(".")
    return host == domain or host.endswith("." + domain)


def collect_cookies(site_names, load_domain) -> dict:
    """Return {site name: cookies}; raise if any site lacks its login cookie."""
    collected = {}
    for name in site_names:
        site = SITES[name]
        cookies = [c for c in load_domain(site.domain) if belongs_to(c, site.domain)]
        if not any(cookie.name == site.login_cookie for cookie in cookies):
            found = "no cookies" if not cookies else "cookies but no login session"
            raise RuntimeError(
                f"{site.domain}: found {found} (missing {site.login_cookie}). "
                f"Log into {site.domain} with Floorp first."
            )
        collected[name] = cookies
    return collected


def write_cookie_file(cookies, path: Path, replace_domains=()) -> None:
    """Write a Netscape cookie file that only the owner can read.

    Cookies already in the file for domains outside ``replace_domains`` are
    kept. Aged anonymous cookies (e.g. YouTube's visitor cookies) get past bot
    checks that a fresh visitor fails, so an export must not discard them.
    """
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    # Restrict the mode before any secret is written. Truncating in place keeps
    # the inode, so a running container's bind mount sees the new contents.
    os.close(os.open(path, os.O_WRONLY | os.O_CREAT, 0o600))
    os.chmod(path, 0o600)
    jar = MozillaCookieJar(str(path))
    if path.stat().st_size:
        jar.load(ignore_discard=True, ignore_expires=True)
        for cookie in list(jar):
            if any(belongs_to(cookie, domain) for domain in replace_domains):
                jar.clear(cookie.domain, cookie.path, cookie.name)
    for cookie in cookies:
        jar.set_cookie(cookie)
    jar.save(ignore_discard=True, ignore_expires=True)


def configure_env(env_file: Path = ENV_FILE) -> None:
    if not env_file.exists():
        raise RuntimeError(f"{env_file} does not exist")

    setting = f"COOKIE_FILE_PATH={CONTAINER_COOKIE_FILE}"
    lines = env_file.read_text().splitlines()
    updated = []
    replaced = False
    for line in lines:
        if line.lstrip().startswith("COOKIE_FILE_PATH="):
            if not replaced:
                updated.append(setting)
                replaced = True
            continue
        updated.append(line)
    if not replaced:
        updated.extend(["", "# Browser cookies mounted into the bot container", setting])
    env_file.write_text("\n".join(updated) + "\n")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--site",
        action="append",
        choices=sorted(SITES),
        help="site to export (repeatable, default: instagram)",
    )
    args = parser.parse_args(argv)
    args.site = list(dict.fromkeys(args.site or ["instagram"]))
    return args


def main(argv=None) -> None:
    args = parse_args(argv)
    database = find_floorp_cookie_database()
    collected = collect_cookies(args.site, floorp_loader(database))
    write_cookie_file(
        [cookie for cookies in collected.values() for cookie in cookies],
        COOKIE_FILE,
        replace_domains=[SITES[name].domain for name in collected],
    )
    configure_env()
    for name, cookies in collected.items():
        site = SITES[name]
        print(f"{site.domain}: {len(cookies)} cookies, {site.login_cookie} present")
    print(f"Cookie file: {COOKIE_FILE}")
    print("Restart the bot with: docker compose up -d --force-recreate")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        raise SystemExit(f"Error: {error}") from error
