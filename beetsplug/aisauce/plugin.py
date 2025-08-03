from __future__ import annotations
from collections.abc import Iterable
from typing import Sequence, TypedDict

from beets.autotag import TrackInfo, AlbumInfo
from beets.metadata_plugins import MetadataSourcePlugin
from beets.library import Item
import confuse


class Provider(TypedDict):
    """A provider for open ai api."""

    id: str
    api_key: str
    api_base_url: str
    model: str


class AISauceSource(TypedDict):
    """Configuration for AISauce plugin."""

    provider: Provider
    user_prompt: str
    system_prompt: str

    # (
    #     {
    #         # "system_prompt": _default_system_prompt,
    #         # "user_prompt": __default_user_prompt,
    #         "clean_all_fields": True,
    #         # should all incoming data be removed before write back?
    #         # this likely only keeps: title, artist, album, genre, year
    #         "title_as_album": True,
    #         "album_overwrite": False,  # set to string to always set the album
    #         "album_artist_overwrite": False,  # set to string to always set the album artist
    #         "compilation": False,  # set to True to always set compilation to True
    #         "ensure_this_str_in_title": "Bootleg",
    #         # if ensured_string.lower() not in meta.title.lower():
    #         # meta.title = f"{meta.title} [{ensured_string}]"
    #     }
    # )


class AISauce(MetadataSourcePlugin):
    """AI Sauce is a metadata source plugin for beets that does not support"""

    def __init__(self):
        super().__init__()
        self.config.add(
            {
                "providers": [],
                "sources": [],
            }
        )

    # ------------------------------ Config related ------------------------------ #

    @property
    def providers(self) -> list[Provider]:
        """Return the list of providers."""
        config_subview = self.config["providers"].get(
            confuse.Sequence(
                {
                    "id": str,
                    "api_key": str,
                    "api_base_url": str,
                    "model": str,
                }
            )
        )
        return [Provider(sv) for sv in config_subview]  # type: ignore

    def provider_for_id(self, provider_id: str) -> Provider | None:
        """Return the provider with the given ID, or None if not found."""
        for provider in self.providers:
            if provider["id"] == provider_id:
                return provider
        return None

    @property
    def default_provider_id(self) -> str:
        """Return the ID of the first provider, or None if no providers are configured."""
        if len(self.providers) > 0:
            return self.providers[0]["id"]
        else:
            raise ValueError("No providers configured in AISauce plugin.")

    @property
    def sources(self) -> list[AISauceSource]:
        """Return the list of AISauce sources."""
        config_subview = self.config["sources"].get(
            confuse.Sequence(
                {
                    "provider_id": str,
                    "user_prompt": _default_user_prompt,
                    "system_prompt": _default_system_prompt,
                }
            )
        )

        if len(config_subview) == 0:  # type: ignore
            # If no sources are configured, use the default provider with default prompts
            provider = self.provider_for_id(self.default_provider_id)
            if provider is None:
                raise ValueError(
                    f"Default provider with ID {self.default_provider_id} not found in AISauce sources."
                )

            return [
                AISauceSource(
                    provider=provider,
                    user_prompt=_default_user_prompt,
                    system_prompt=_default_system_prompt,
                )
            ]

        rets: Sequence[AISauceSource] = []
        for sv in config_subview:  # type: ignore
            provider = self.provider_for_id(sv["provider_id"])
            if provider is None:
                raise ValueError(
                    f"Provider with ID {sv['provider_id']} not found in AISauce sources."
                )

            rets.append(
                AISauceSource(
                    provider=provider,
                    user_prompt=sv["user_prompt"],
                    system_prompt=sv["system_prompt"],
                )
            )

        return rets

    # ------------------------------- Source lookup ------------------------------ #

    def album_for_id(self, album_id: str) -> AlbumInfo | None:
        # Lookup by album ID is not supported in AISauce
        return None

    def track_for_id(self, track_id: str) -> TrackInfo | None:
        # Lookup by track ID is not supported in AISauce
        return None

    def candidates(
        self, items: Sequence[Item], artist: str, album: str, va_likely: bool
    ) -> Iterable[AlbumInfo]:
        # What weights and distances? AI!?
        return []

    def item_candidates(
        self, item: Item, artist: str, title: str
    ) -> Iterable[TrackInfo]:
        """
        Beets by default calls this for singletons, but not for albums.
        """
        return []


_default_system_prompt = """
You are a helpful programming assistant, and an expert in musical metadata.
The user will provide messy metadata, and your task is to clean up the metadata with
consistent formatting. Often the metadata is for bootlegs.

Please parse the following quantities and output them in JSON format:
- title
- artist
- album
- genre
- date, but only keep the year (YYYY)

Do not invent values for fields that you cannot infer from the input.

EXAMPLE INPUT:
Clean up the following metadata:
{
    "FILE:": ["  Busta Rhymes - Gimme Some More (winslow.edit).mp3 "],
    "TITLE": [" Busta Rhymes - Gimme Some More [Free DL via Soundcloud] "],
    "ARTIST": ["  winslow "],
    "ALBUM": [""],
    "GENRE": ["  DnB, neurofunk  "],
    "DATE": ["  14.11.2021  "]
    "COMPOSER": ["  Jablonksy, Steve  "],
    "COMMENT": ["  got this from a friend  "]
    "OTHER FIELD:": ["  some other value  "]
}

EXAMPLE JSON OUTPUT:
{
    "title": "Gimme Some More [Busta Rhymes] (winslow.edit)",
    "artist": "winslow",
    "album": "",
    "genre": "Drum And Bass; Neurofunk",
    "date": "2014"
}
"""

_default_user_prompt = """
Clean up the following metadata for a bootleg I downloaded.

Often, Artist, Title and Album are empty or malformatted, but the file name might provide
a clue.

Note, for my bootlegs, a song with an input title like
"Ed Sheeran - Shape Of You (IZUK Bootleg)"
should have in the output
"IZUK" as the artist
and "Shape Of You [Ed Sheeran] (IZUK Bootleg)" for both the title and album.

If genres are contained, Title-case them and dont use abbreviations like "DnB" or "D&B",
use "Drum And Bass" instead. If multiple genres are returned, separate them in your reply
with a semicolon. In most cases, the genre is likely "Drum And Bass".

Make sure the casing is sensible - OFTEN THE INPUT HAS SHOUTCASE (capslock),
But I Prefer Title Case.

Remove strings like "Free DL via Soundcloud", "[Free Download]" and "FREE DOWNLOAD" from the title and other fields.

Make sure that the word "Bootleg" is contained in the title, and if not, add it as "[Bootleg]" at the end.
Usually you will find something like "(Danny Bird Remix)" towards the end of the title, in this case, add "Bootleg" there: "(Danny Bird Remix, Bootleg)".

INPUT:
{}
"""
