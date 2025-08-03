"""
Bootleg module to grab stuff from Soundcloud and Youtube.
"""

from datetime import datetime
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from pprint import pformat
from typing import Tuple, cast

import requests
import taglib
from humanize import naturalsize

from .models.track import Track
from .ai import cleanup_metadata

TEMP_DIR = tempfile.mkdtemp()


@dataclass
class MinimalMetaData:
    title: str = ""
    artist: str = ""
    album: str = ""
    album_artist: str = ""
    genre: str = ""
    date: str = ""

    def __post_init__(self):
        if self.album_artist == "":
            self.album_artist = self.artist

    def copy_with_unknown(self):
        return MinimalMetaData(
            title=self.title or "Unknown Title",
            artist=self.artist or "Unknown Artist",
            album=self.album or "Unknown Album",
            album_artist=self.album_artist or "Unknown Album Artist",
            genre=self.genre or "Unknown Genre",
            date=self.date or "Unknown Date",
        )

    def to_tag_dict(self):
        return {
            "TITLE": self.title,
            "ARTIST": self.artist,
            "ALBUM": self.album,
            "ALBUMARTIST": self.album_artist,
            "GENRE": self.genre,
            "DATE": self.date,
        }

    def __repr__(self):
        return pformat(self.__dict__, sort_dicts=False)


def resolve_soundcloud_url(short_url):
    web_log.info(f"resolving url: {short_url}")
    try:
        response = requests.get(short_url, allow_redirects=True)
        return response.url
    except requests.RequestException as e:
        web_log.error(f"Error resolving URL: {e}")
        return None


@rq.job("tidal", timeout=600)
@redirect_stdout_to_logger(web_log)
def submit_and_callback(dl_id: str):
    """This is the main download function, runs in the worker."""

    global settings, tidal
    from .routes.sse import update_client_view

    with db_session() as session:
        srv_log.info(f"Starting bootleg download for {dl_id}")

        # get the download object
        dl = session.get(Download, dl_id)
        if not dl:
            srv_log.error(f"Download {dl_id} not found")
            return

        # multiple urls?
        urls = dl.url.split()
        dl.total_tracks = len(urls)
        dl.finished_tracks = 0
        dl.status = DownloadStatus.IN_PROGRESS

        if len(urls) > 1:
            dl.title = f"{source_for_url(urls[0])} batch download"

        web_log.info(f"Found {dl.total_tracks} tracks passed as urls")

        num_failed = 0
        for url in urls:
            srv_log.debug(f"Starting download for {dl.url}")

            t = Track(download_id=dl.id)
            session.add(t)
            session.commit()
            update_client_view("downloads")

            # the downloader doesnt like the on.soundcloud links
            if "on.soundcloud.com/" in url:
                url = resolve_soundcloud_url(url)

            try:
                source = source_for_url(url)
                if len(urls) > 1:
                    extra_path = f"{dl.title.replace(' ', '_')}_{datetime.now().strftime('%Y-%m-%d')}"
                else:
                    extra_path = ""

                track_path, meta = bootleg_download(url, extra_path)
                meta = meta.copy_with_unknown()

                t.title = meta.title
                t.path = str(track_path)
                t.size = naturalsize(os.path.getsize(t.path))
                t.status = DownloadStatus.COMPLETED

                dl.finished_tracks += 1
                if len(urls) == 1:
                    source = "[yt]" if source == "youtube" else "[sc]"
                    dl.title = f"{source} {meta.artist} - {meta.title}"

            except Exception as e:
                web_log.error(e)
                t.status = DownloadStatus.FAILED
                num_failed += 1

                update_client_view("downloads")

            session.commit()

        if num_failed != 0:
            dl.status = DownloadStatus.FAILED
            srv_log.error(f"Download {dl.id} failed for {num_failed} tracks")
        else:
            dl.status = DownloadStatus.COMPLETED
            srv_log.info(f"Download {dl.id} completed")

        session.commit()
        update_client_view("downloads")

        if dl.callback_url:
            requests.post(
                dl.callback_url,
                json={
                    "status": "download done",
                    "trackPaths": [t.path for t in dl.tracks],
                    "downloadId": dl.id,
                    "numTracks": dl.total_tracks,
                },
            )


def bootleg_download(
    url: str, extra_path: str = ""
) -> Tuple[Path, MinimalMetaData, str]:
    """
    Wrap the download function and do some file moving and tag cleaning.

    Args:
        url (str): single URL to download from
        extra_paths (str):
            optionally add an extra folder level after configured inbox

    Returns:
        Path: Path to the downloaded file
        MinimalMetaData: Metadata of the downloaded file
        source: str, "youtube" or "soundcloud"
    """
    # this used to be main(), fake args
    yt_infer_artist = True

    # Download, services are detected automatically
    path, source = __download(url)

    # Tag the audio file
    web_log.info(f"Tagging audio file: {path}")
    with taglib.File(path, save_on_exit=True) as f:
        # The tags are stored in the attribute *tags* as a *dict* mapping strings (tag names)
        # to lists of strings (tag values).

        # I noticed that artist if often fucked with youtube downloads
        # So we try to infer the artist from the title {artist} - {title}
        title_0: str = f.tags["TITLE"][0] or ""
        if yt_infer_artist and source == "youtube" and len(title_0.split(" - ")) == 2:
            artist_title = title_0.split(" - ")
            f.tags["ARTIST"] = [artist_title[0]]
            f.tags["TITLE"] = [artist_title[1]]

        web_log.info(f"Tags:\n{pformat(f.tags, sort_dicts=False)}")
        if len(f.tags["ARTIST"]) == 0 or len(f.tags["TITLE"]) == 0:
            return

        # remove 'free download' crap, since ai sometimes fails to do it.
        # use very stronk regex
        cleaned_title = re.sub(
            r"\s*[\(\[]?(free download|free dl|\[free\]|\(free\))[\)\]]?\s*",
            "",
            f.tags["TITLE"][0],
            flags=re.IGNORECASE,
        )
        f.tags["TITLE"] = [cleaned_title]

        # AI cleanup. TODO: separate step with DL progress field
        try:
            ai_cleaned = cleanup_metadata(f.tags, path)
            meta = MinimalMetaData(
                title=ai_cleaned["title"],
                artist=ai_cleaned["artist"],
                album=ai_cleaned["album"],
                genre=ai_cleaned["genre"],
                date=ai_cleaned["date"],
            )
            web_log.info(f"AI cleaned metadata: {meta}")
        except Exception as e:
            web_log.error(f"AI cleanup failed: {e}")
            meta = MinimalMetaData(
                artist=" ".join(f.tags.get("ARTIST", [""])),
                album=" ".join(f.tags.get("ALBUM", [""])),
                title=" ".join(f.tags.get("TITLE", [""])),
            )

        # write back to file. optionally clean all tags we dont want
        if os.getenv("BTL_CLEAN_ALL_TAGS", "False").lower() in ("true", "1", "yes"):
            for tag in list(f.tags.keys()):
                del f.tags[tag]

        # some manual user tweaks
        if os.getenv("BTL_ENSURE_THIS_STR_IN_TITLE", None) is not None:
            # I use a smart playlist looking for 'bootleg' so I always want this in the title
            ensured_string = os.getenv("BTL_ENSURE_THIS_STR_IN_TITLE")
            if ensured_string.lower() not in meta.title.lower():
                meta.title = f"{meta.title} [{ensured_string}]"
        if os.getenv("BTL_TITLE_AS_ALBUM", "False").lower() in ("true", "1", "yes"):
            meta.album = meta.title
        if os.getenv("BTL_ALBUM_OVERRIDE", None) is not None:
            meta.album = os.getenv("BTL_ALBUM_OVERRIDE")
        if os.getenv("BTL_ALBUMARTIST_OVERRIDE", None) is not None:
            meta.album_artist = os.getenv("BTL_ALBUMARTIST_OVERRIDE")

        web_log.info(f"Metadata after user tweaks: {meta}")

        final_tags = meta.to_tag_dict()
        for tag, value in final_tags.items():
            f.tags[tag] = value

        # PS: somehow, for me the with save_on_exit=True did not work
        f.save()

        # just for the ui and folders on disk
        mu = meta.copy_with_unknown()

        # Move and rename file
        inbox_dir = Path(os.getenv("BTL_DOWNLOAD_BASE_PATH"))
        if (
            os.getenv("BTL_CREATE_ALBUM_DIR", "True").lower() in ("true", "1", "yes")
            and extra_path == ""
        ):
            web_log.debug("Creating album directory")
            new_path = (
                inbox_dir / f"{mu.artist} - {mu.album}" / f"{mu.title}{path.suffix}"
            )
        else:
            new_path = inbox_dir / extra_path / f"{mu.artist} - {mu.title}{path.suffix}"

        web_log.info(f"Moving / Renaming file '{path}' -> '{new_path}'")
        os.makedirs(new_path.parent, exist_ok=True)
        # path.rename seems to give Cross-device link error with docker mounts
        shutil.move(str(path), str(new_path))

        return new_path, meta


def source_for_url(url: str) -> str:
    url_switch = {
        "soundcloud": "soundcloud",
        "youtube": "youtube",
        "youtu.be": "youtube",
    }

    for key in url_switch.keys():
        if key in url:
            return url_switch[key]

    raise ValueError(f"Could not detect source from url: {url}")


def __download(url: str) -> Tuple[Path, str]:
    url_switch = {
        "soundcloud": __download_soundlcoud,
        "youtube": __download_youtube,
        "youtu.be": __download_youtube,
    }

    for key in url_switch.keys():
        if key in url:
            web_log.info(f"Detected {key} url!")
            p = url_switch[key](url)
            web_log.info(f"Downloaded file: {p}")
            source = key
            if source == "youtu.be":
                source = "youtube"
            return (cast(Path, p), source)

    raise ValueError(f"Could not detect source from url: {url}")


def __download_soundlcoud(url: str) -> Path:
    from scdl import scdl

    # Monkeypatch download to return get path
    filename: Path | None = None
    is_downloaded = False
    download_original_file_org = scdl.download_original_file
    download_hls_org = scdl.download_hls

    def download_original_file(*args, **kwargs):
        nonlocal filename
        nonlocal is_downloaded
        r = download_original_file_org(*args, **kwargs)
        if r[0]:
            filename = Path(r[0])
        is_downloaded = r[1]
        return r

    def download_hls(*args, **kwargs):
        nonlocal filename
        nonlocal is_downloaded
        r = download_hls_org(*args, **kwargs)
        if r[0]:
            filename = Path(r[0])
        is_downloaded = r[1]
        return r

    scdl.download_original_file = download_original_file
    scdl.download_hls = download_hls

    from scdl.scdl import (
        SCDLArgs,
        SoundCloud,
        SoundCloudException,
        Track,
        download_track,
        get_config,
        validate_url,
    )

    # For simplicity we do not allow to configure the client
    if "XDG_CONFIG_HOME" in os.environ:
        config_file = Path(os.environ["XDG_CONFIG_HOME"], "scdl", "scdl.cfg")
    else:
        config_file = Path.home().joinpath(".config", "scdl", "scdl.cfg")
    config = get_config(config_file)

    kwargs = cast(
        SCDLArgs,
        {
            "flac": True,
            "auth_token": os.getenv("BTL_SOUNDCLOUD_AUTH_TOKEN"),
            "onlymp3": False,
            "name_format": config["scdl"]["name_format"],
            "debug": False,
            "add_description": False,
            "c": True,
            "extract_artist": True,
            "overwrite": True,
            "path": TEMP_DIR,
            "hide_progress": True,
        },
    )
    client = SoundCloud(None, kwargs["auth_token"])

    try:
        url = validate_url(client, url)
    except Exception as e:
        raise ValueError(f"Could not validate soundcloud url: {e}")

    item = client.resolve(url)
    if not isinstance(item, Track):
        raise ValueError(f"Item is not a track! {item}")

    # title = item.title
    # title = title.encode("utf-8", "ignore").decode("utf-8")

    try:
        download_track(client, item, kwargs)
    except Exception as e:
        print(f"Could not download track: {e}")
        raise

    if filename is None:
        raise ValueError("Could not get filename!")

    return Path(Path.cwd(), filename)


def __download_youtube(url: str):
    import yt_dlp

    # Select best quality audio stream (selects mp4 by default, todo: add selector for better quality of other types)
    ydl_opts = {
        "format": "bestaudio",
        "postprocessor_args": {
            "ffmpeg": [
                "-c:v",
                "mjpeg",
                "-vf",
                "crop='if(gt(ih,iw),iw,ih)':'if(gt(iw,ih),ih,iw)'",
            ]
        },
        "postprocessors": [
            {
                "format": "jpg",
                "key": "FFmpegThumbnailsConvertor",
                "when": "before_dl",
            },
            {  # Add metadata using FFmpeg
                "add_metadata": True,
                "key": "FFmpegMetadata",
            },
            {  # Extract audio using ffmpeg
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
            },
            {
                "already_have_thumbnail": False,
                "key": "EmbedThumbnail",
            },
        ],
        "writethumbnail": True,
        "outtmpl": {"default": f"{TEMP_DIR}/%(title)s.%(ext)s"},
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info_dict)
    return Path(Path.cwd(), filename.replace(".webm", ".mp3"))
