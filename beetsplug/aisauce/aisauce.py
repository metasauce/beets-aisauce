from __future__ import annotations
import asyncio
from collections.abc import Iterable
from typing import Coroutine, Sequence

from beets.autotag import TrackInfo, AlbumInfo
from beets.metadata_plugins import MetadataSourcePlugin
from beets.library import Item
import confuse


from .ai import get_ai_client, get_structured_output
from .types import Provider, AISauceSource, AlbumInfoAIResponse, TrackInfoAIResponse
from .prompts import _default_user_prompt, _default_system_prompt


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

        rets: list[AISauceSource] = []
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
        async def _run() -> list[AlbumInfoAIResponse]:
            tasks: list[Coroutine[None, None, AlbumInfoAIResponse]] = []
            for source in self.sources:
                provider = source["provider"]
                client = get_ai_client(provider)
                tasks.append(
                    get_structured_output(
                        client=client,
                        user_prompt=_format_user_prompt(
                            source["user_prompt"],
                            items,
                            artist=artist,
                            album=album,
                            va_likely=va_likely,
                        ),
                        system_prompt=source["system_prompt"],
                        type=AlbumInfoAIResponse,
                        model=provider["model"],
                    )
                )
            return await asyncio.gather(*tasks)

        return [i.to_album_info() for i in asyncio.run(_run())]

    def item_candidates(
        self, item: Item, artist: str, title: str
    ) -> Iterable[TrackInfo]:
        """
        Beets by default calls this for singletons, but not for albums.
        """

        async def _run() -> list[TrackInfoAIResponse]:
            tasks: list[Coroutine[None, None, TrackInfoAIResponse]] = []
            for source in self.sources:
                provider = source["provider"]
                client = get_ai_client(provider)
                tasks.append(
                    get_structured_output(
                        client=client,
                        user_prompt=_format_user_prompt(
                            source["user_prompt"],
                            [item],
                            artist=artist,
                        ),
                        system_prompt=source["system_prompt"],
                        type=TrackInfoAIResponse,
                        model=provider["model"],
                    )
                )
            return await asyncio.gather(*tasks)

        return [i.to_track_info() for i in asyncio.run(_run())]


def _format_user_prompt(
    user_prompt: str,
    items: Sequence[Item],
    artist: str | None = None,
    album: str | None = None,
    va_likely: bool = False,
) -> str:
    """
    Format the user prompt with the provided items and additional information.
    """
    # Create user prompt with input file(s) metadata
    formatted_input = "\n\nINPUT FILES:\n["
    for item in items:
        formatted_input += "\n{"
        # TODO: Parsing
        for key, value in item.items():
            if isinstance(value, str):
                formatted_input += f'\n  "{key}": "{value}",'
            elif isinstance(value, list):
                formatted_input += f'\n  "{key}": {value},'
            else:
                formatted_input += f'\n  "{key}": {str(value)},'
        formatted_input += "\n}"
    formatted_input += "\n]"

    # Additional info for album
    if album or artist or va_likely:
        formatted_input += "\n\nADDITIONAL INFO (heuristics from all files combined):"
    if album:
        formatted_input += f"\n- ALBUM: {album}"
    if artist:
        formatted_input += f"\n- ALBUMARTIST: {artist}"
    if va_likely:
        formatted_input += "\n- This is likely a compilation album (Various Artists)."

    return user_prompt + formatted_input
