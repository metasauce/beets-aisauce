from __future__ import annotations
from collections.abc import Iterable
from typing import Sequence

from beets.autotag import TrackInfo, AlbumInfo
from beets.metadata_plugins import MetadataSourcePlugin
from beets.library import Item


class AISauce(MetadataSourcePlugin):
    """AI Sauce is a metadata source plugin for beets that does not support"""

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
        return []
