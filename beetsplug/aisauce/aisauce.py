from __future__ import annotations
import asyncio
from collections.abc import Iterable
from typing import Coroutine, Literal, Sequence

from beets.autotag import TrackInfo, AlbumInfo
from beets.importer import ImportTask
from beets.metadata_plugins import MetadataSourcePlugin
from beets.library import Item
from beets.ui import UserError
import confuse


from .ai import get_ai_client, get_structured_output
from .types import Provider, AISauceSource, AlbumInfoAIResponse, TrackInfoAIResponse
from .prompts import _default_user_prompt, _default_system_prompt


class AISauce(MetadataSourcePlugin):
    """
    AISauce is a metadata source plugin for Beets that augments music metadata using AI.

    It doesn't support classical music sources directly but provides AI-driven enhancements.
    """

    def __init__(self):
        super().__init__()
        self.config.add(
            {
                "mode": "metadata_source",
                "providers": [],
                "sources": [],
            }
        )

        self.register_listener("import_task_start", self.on_import_task_choice)

    @property
    def mode(self) -> Literal["metadata_source", "metadata_cleanup"]:
        mode = self.config["mode"].get()
        if mode not in ("metadata_source", "metadata_cleanup"):
            raise UserError(
                f"AISauce plugin mode must be either 'metadata_source' or 'metadata_cleanup', got: {mode}"
            )
        return mode

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

    def on_import_task_choice(self, task: ImportTask, session):
        if self.mode != "metadata_cleanup":
            # AISauce is not intended to be used as a candidate source when
            # operating in metadata cleanup mode.
            return

        self._log.info("Enhancing metadata using AI before candidate lookup...")

        async def _run():
            source = self.sources[0]
            provider = source["provider"]
            client = get_ai_client(provider)
            return await get_structured_output(
                client=client,
                user_prompt=_format_user_prompt(
                    source["user_prompt"],
                    task.items,
                ),
                system_prompt=source["system_prompt"],
                type=AlbumInfoAIResponse,
                model=provider["model"],
            )

        candidate = asyncio.run(_run())
        diff = candidate.apply_to_items(task.items)
        for item, changes in zip(task.items, diff):
            if not changes:
                continue
            self._log.info(f"Updated metadata for {item.path!r}:")
            for field, change in changes.items():
                self._log.info(f"  {field}: {change['old']} -> {change['new']}")

        self._log.info("AISauce: Metadata enhancement complete.")

    def album_for_id(self, album_id: str) -> AlbumInfo | None:
        # Lookup by album ID is not supported in AISauce
        return None

    def track_for_id(self, track_id: str) -> TrackInfo | None:
        # Lookup by track ID is not supported in AISauce
        return None

    def candidates(
        self,
        items: Sequence[Item],
        artist: str,
        album: str,
        va_likely: bool,
    ) -> Iterable[AlbumInfo]:
        if self.mode != "metadata_source":
            # AISauce is not intended to be used as a candidate source when
            # operating in metadata cleanup mode.
            return []

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

        candidates = asyncio.run(_run())
        return [c.to_album_info(data_source=self.data_source) for c in candidates]

    def item_candidates(
        self,
        item: Item,
        artist: str,
        title: str,
    ) -> Iterable[TrackInfo]:
        """
        Beets by default calls this for singletons, but not for albums.
        """
        if self.mode != "metadata_source":
            # AISauce is not intended to be used as a candidate source when
            # operating in metadata cleanup mode.
            return []

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

        item_candidates: list[TrackInfoAIResponse] = asyncio.run(_run())
        return [i.to_track_info(data_source=self.data_source) for i in item_candidates]


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
