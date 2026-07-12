import asyncio
import logging
import os
import shutil
import sys
from pathlib import Path


logger = logging.getLogger(__name__)


class GalleryDownloader:
    def __init__(self, config):
        self.config = config

    async def download(self, url):
        """Download an Instagram post's actual media with gallery-dl."""
        download_dir = self.config.downloads_dir / "gallery-dl"
        shutil.rmtree(download_dir, ignore_errors=True)
        download_dir.mkdir(parents=True)

        command = [
            sys.executable,
            "-m",
            "gallery_dl",
            "--config-ignore",
            "--no-input",
            "--no-mtime",
            "--no-part",
            "--directory",
            str(download_dir),
            "--option",
            "extractor.cookies-update=false",
        ]
        cookie_file = self.config.COOKIE_FILE_PATH
        if cookie_file and os.path.exists(cookie_file):
            command.extend(("--cookies", cookie_file))
        command.append(url)

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()
        if process.returncode:
            error = stderr.decode(errors="replace").strip()
            raise ValueError(f"gallery-dl failed: {error or 'unknown error'}")

        media_files = sorted(
            [path for path in download_dir.rglob("*") if path.is_file()],
            key=lambda path: path.name,
        )
        if not media_files:
            raise ValueError("gallery-dl did not download any Instagram media")

        result_files = []
        for media_file in media_files:
            target_file = (
                self.config.downloads_dir
                / f"instagram_{media_file.stem}{media_file.suffix.lower()}"
            )
            shutil.move(str(media_file), str(target_file))
            result_files.append(str(target_file))

        shutil.rmtree(download_dir, ignore_errors=True)
        logger.info(
            f"Downloaded Instagram gallery media with gallery-dl: "
            f"{len(result_files)} file(s)"
        )
        return result_files
