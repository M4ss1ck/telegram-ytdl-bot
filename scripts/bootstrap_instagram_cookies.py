#!/usr/bin/env python3
"""Export Instagram cookies from the local Floorp profile for Docker."""

from http.cookiejar import MozillaCookieJar
from pathlib import Path
import os

import browser_cookie3


PROJECT_DIR = Path(__file__).resolve().parent.parent
FLOORP_DIR = Path.home() / ".var/app/one.ablaze.floorp/.floorp"
COOKIE_FILE = PROJECT_DIR / "secrets/instagram-cookies.txt"
ENV_FILE = PROJECT_DIR / ".env"
CONTAINER_COOKIE_FILE = "/run/secrets/instagram-cookies.txt"


def find_floorp_cookie_database() -> Path:
    databases = list(FLOORP_DIR.glob("*/cookies.sqlite"))
    if not databases:
        raise RuntimeError(f"No Floorp cookie database found under {FLOORP_DIR}")
    return max(databases, key=lambda path: path.stat().st_mtime)


def export_instagram_cookies(database: Path) -> int:
    cookies = browser_cookie3.firefox(
        cookie_file=str(database),
        domain_name="instagram.com",
    )
    exported = list(cookies)
    if not exported:
        raise RuntimeError(
            "No Instagram cookies found. Log into instagram.com with Floorp first."
        )
    if not any(cookie.name == "sessionid" for cookie in exported):
        raise RuntimeError(
            "Instagram cookies were found, but no login session was present. "
            "Log into instagram.com with Floorp first."
        )

    COOKIE_FILE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    jar = MozillaCookieJar(str(COOKIE_FILE))
    for cookie in exported:
        jar.set_cookie(cookie)
    jar.save(ignore_discard=True, ignore_expires=True)
    os.chmod(COOKIE_FILE, 0o600)
    return len(exported)


def configure_env() -> None:
    if not ENV_FILE.exists():
        raise RuntimeError(f"{ENV_FILE} does not exist")

    setting = f"COOKIE_FILE_PATH={CONTAINER_COOKIE_FILE}"
    lines = ENV_FILE.read_text().splitlines()
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
    ENV_FILE.write_text("\n".join(updated) + "\n")


def main() -> None:
    database = find_floorp_cookie_database()
    count = export_instagram_cookies(database)
    configure_env()
    print(f"Exported {count} Instagram cookies from Floorp.")
    print(f"Cookie file: {COOKIE_FILE}")
    print("Restart the bot with: docker compose up -d --force-recreate")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        raise SystemExit(f"Error: {error}") from error
